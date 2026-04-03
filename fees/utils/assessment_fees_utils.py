# fees/utils/assessment_fees_utils.py
# ─────────────────────────────────────────────────────────────────────────────
# Helpers for AssessmentFees views:
#   - Manual field validation
#   - POST data parsing
#   - Bulk generation logic (all students in a class / term)
#   - Recalculate total_paid from actual FeesPayment records
#   - List-level and detail statistics
# ─────────────────────────────────────────────────────────────────────────────

from decimal import Decimal, InvalidOperation
from datetime import date

from django.db.models import Count, Q, Sum

from fees.models import AssessmentFees, FeesPayment, SchoolFees


# ═══════════════════════════════════════════════════════════════════════════════
#  VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def validate_and_parse_assessment_fees(
    post: dict,
    instance: AssessmentFees | None = None,
) -> tuple[dict, dict]:
    """
    Manually validate all AssessmentFees POST fields.

    Returns:
        (cleaned_data, errors)

    cleaned_data — ready for setattr loop.
                   student_id and term_id stored as ints; view resolves FKs.
    errors       — dict of field_name → error message. Empty = passed.

    Note: balance and is_cleared are auto-computed in model.save() —
          they are never validated here.
    """
    errors:  dict = {}
    cleaned: dict = {}

    # ── student (required FK) ─────────────────────────────────────────────────
    student_id = (post.get('student') or '').strip()
    if not student_id:
        errors['student'] = 'Student is required.'
    else:
        try:
            cleaned['student_id'] = int(student_id)
        except ValueError:
            errors['student'] = 'Invalid student selected.'

    # ── term (required FK) ────────────────────────────────────────────────────
    term_id = (post.get('term') or '').strip()
    if not term_id:
        errors['term'] = 'Term is required.'
    else:
        try:
            cleaned['term_id'] = int(term_id)
        except ValueError:
            errors['term'] = 'Invalid term selected.'

    # ── Uniqueness: one assessment per student per term ───────────────────────
    if 'student_id' in cleaned and 'term_id' in cleaned:
        qs = AssessmentFees.objects.filter(
            student_id=cleaned['student_id'],
            term_id=cleaned['term_id'],
        )
        if instance and instance.pk:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            errors['student'] = (
                'A fees assessment for this student and term already exists. '
                'Edit the existing record instead.'
            )

    # ── total_required (required, positive) ───────────────────────────────────
    req_raw = (post.get('total_required') or '').strip()
    if not req_raw:
        errors['total_required'] = 'Total required amount is required.'
    else:
        try:
            req = Decimal(req_raw.replace(',', ''))
            if req < 0:
                errors['total_required'] = 'Total required cannot be negative.'
            elif req > Decimal('999999999.99'):
                errors['total_required'] = 'Total required amount is too large.'
            else:
                cleaned['total_required'] = req
        except InvalidOperation:
            errors['total_required'] = 'Total required must be a valid number (e.g. 750000).'

    # ── total_paid (optional — usually auto-synced, but editable) ─────────────
    paid_raw = (post.get('total_paid') or '0').strip()
    try:
        paid = Decimal(paid_raw.replace(',', ''))
        if paid < 0:
            errors['total_paid'] = 'Total paid cannot be negative.'
        else:
            cleaned['total_paid'] = paid
    except InvalidOperation:
        errors['total_paid'] = 'Total paid must be a valid number.'

    # ── discount_amount (optional) ────────────────────────────────────────────
    disc_raw = (post.get('discount_amount') or '0').strip()
    try:
        disc = Decimal(disc_raw.replace(',', ''))
        if disc < 0:
            errors['discount_amount'] = 'Discount amount cannot be negative.'
        else:
            cleaned['discount_amount'] = disc
    except InvalidOperation:
        errors['discount_amount'] = 'Discount amount must be a valid number.'

    # Cross-check: discount must not exceed total_required
    if (
        'total_required' in cleaned
        and 'discount_amount' in cleaned
        and cleaned['discount_amount'] > cleaned['total_required']
    ):
        errors['discount_amount'] = (
            f'Discount (UGX {cleaned["discount_amount"]:,.0f}) cannot exceed '
            f'total required (UGX {cleaned["total_required"]:,.0f}).'
        )

    # ── discount_reason ───────────────────────────────────────────────────────
    disc_reason = (post.get('discount_reason') or '').strip()
    if cleaned.get('discount_amount', Decimal('0')) > 0 and not disc_reason:
        errors['discount_reason'] = (
            'Discount reason is required when a discount amount is entered.'
        )
    elif len(disc_reason) > 200:
        errors['discount_reason'] = 'Discount reason must not exceed 200 characters.'
    else:
        cleaned['discount_reason'] = disc_reason

    # ── notes ─────────────────────────────────────────────────────────────────
    cleaned['notes'] = (post.get('notes') or '').strip()

    return cleaned, errors


# ═══════════════════════════════════════════════════════════════════════════════
#  RECALCULATE FROM PAYMENTS
# ═══════════════════════════════════════════════════════════════════════════════

def recalculate_from_payments(assessment: AssessmentFees) -> dict:
    """
    Re-sync assessment.total_paid from actual FeesPayment records.
    Updates last_payment_date as well.
    Calls assessment.save() which auto-recomputes balance and is_cleared.

    Returns a dict describing what changed:
        { 'old_paid': ..., 'new_paid': ..., 'changed': bool }
    """
    payments_qs = FeesPayment.objects.filter(
        student=assessment.student,
        term=assessment.term,
    )

    new_paid = payments_qs.aggregate(
        s=Sum('amount_paid')
    )['s'] or Decimal('0')

    last_date = (
        payments_qs.order_by('-payment_date')
        .values_list('payment_date', flat=True)
        .first()
    )

    old_paid = assessment.total_paid
    changed  = (old_paid != new_paid)

    assessment.total_paid        = new_paid
    assessment.last_payment_date = last_date
    assessment.save()   # auto-recomputes balance + is_cleared

    return {
        'old_paid': old_paid,
        'new_paid': new_paid,
        'changed':  changed,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  BULK GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def bulk_generate_for_class(
    school_class,
    term,
    generated_by,
    overwrite: bool = False,
) -> dict:
    """
    Generate AssessmentFees records for all active students in a class
    for a given term.

    total_required is computed as the sum of all compulsory SchoolFees
    for that class + term.

    total_paid is synced from existing FeesPayment records.

    Args:
        school_class  — SchoolClass instance
        term          — Term instance
        generated_by  — User instance
        overwrite     — if True, update existing records; if False, skip them

    Returns:
        {
            'created':  int,   # new records created
            'updated':  int,   # existing records updated (if overwrite=True)
            'skipped':  int,   # skipped because record exists and overwrite=False
            'errors':   list,  # error strings for any students that failed
        }
    """
    from students.models import Student

    students = Student.objects.filter(
        current_class=school_class, is_active=True
    )

    # Total compulsory fees for this class + term
    compulsory_total = (
        SchoolFees.objects.filter(
            school_class=school_class,
            term=term,
            is_active=True,
            is_compulsory=True,
        ).aggregate(s=Sum('amount'))['s'] or Decimal('0')
    )

    created = updated = skipped = 0
    errors  = []

    for student in students:
        try:
            existing = AssessmentFees.objects.filter(
                student=student, term=term
            ).first()

            if existing:
                if overwrite:
                    existing.total_required = compulsory_total
                    existing.generated_by   = generated_by
                    recalculate_from_payments(existing)
                    updated += 1
                else:
                    skipped += 1
                continue

            # Compute total_paid from existing payments
            total_paid = (
                FeesPayment.objects.filter(
                    student=student, term=term
                ).aggregate(s=Sum('amount_paid'))['s'] or Decimal('0')
            )
            last_date = (
                FeesPayment.objects.filter(
                    student=student, term=term
                ).order_by('-payment_date')
                .values_list('payment_date', flat=True)
                .first()
            )

            AssessmentFees.objects.create(
                student          = student,
                term             = term,
                total_required   = compulsory_total,
                total_paid       = total_paid,
                discount_amount  = Decimal('0'),
                last_payment_date= last_date,
                generated_by     = generated_by,
            )
            created += 1

        except Exception as exc:
            errors.append(f'{student}: {exc}')

    return {
        'created': created,
        'updated': updated,
        'skipped': skipped,
        'errors':  errors,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  LIST STATS
# ═══════════════════════════════════════════════════════════════════════════════

def get_assessment_fees_list_stats() -> dict:
    """High-level statistics shown above the assessment fees list page."""
    today = date.today()
    qs    = AssessmentFees.objects.all()

    total      = qs.count()
    cleared    = qs.filter(is_cleared=True).count()
    outstanding= qs.filter(is_cleared=False).count()
    discounted = qs.filter(discount_amount__gt=0).count()

    agg = qs.aggregate(
        sum_required   = Sum('total_required'),
        sum_paid       = Sum('total_paid'),
        sum_balance    = Sum('balance'),
        sum_discount   = Sum('discount_amount'),
    )
    total_required  = agg['sum_required']  or Decimal('0')
    total_paid      = agg['sum_paid']      or Decimal('0')
    total_balance   = agg['sum_balance']    or Decimal('0')
    total_discount  = agg['sum_discount']  or Decimal('0')

    collection_rate = (
        round((total_paid / total_required) * 100, 1)
        if total_required else 0
    )

    # By term
    by_term = list(
        qs.values('term__name', 'term__start_date')
        .annotate(
            count        = Count('id'),
            cleared_count= Count('id', filter=Q(is_cleared=True)),
            sum_required = Sum('total_required'),
            sum_paid     = Sum('total_paid'),
            sum_balance  = Sum('balance'),
        )
        .order_by('-term__start_date')[:6]
    )

    # By class
    by_class = list(
        qs.values(
            'student__current_class__supported_class__key',
            'student__current_class__supported_class__section',
        )
        .annotate(
            count        = Count('id'),
            cleared_count= Count('id', filter=Q(is_cleared=True)),
            sum_required = Sum('total_required'),
            sum_paid     = Sum('total_paid'),
            sum_balance  = Sum('balance'),
        )
        .order_by(
            'student__current_class__supported_class__section',
            'student__current_class__supported_class__key',
        )
    )

    # Top 10 defaulters (highest outstanding balance)
    defaulters = list(
        qs.filter(is_cleared=False)
        .select_related('student', 'student__current_class', 'term')
        .order_by('-balance')[:10]
    )

    # Current term summary
    from academics.models import Term
    current_term = Term.objects.filter(is_current=True).first()
    current_term_stats = {}
    if current_term:
        ct = qs.filter(term=current_term)
        ct_agg = ct.aggregate(
            count        = Count('id'),
            cleared_count= Count('id', filter=Q(is_cleared=True)),
            sum_required = Sum('total_required'),
            sum_paid     = Sum('total_paid'),
            sum_balance  = Sum('balance'),
        )
        ct_agg['collection_rate'] = (
            round((ct_agg['sum_paid'] / ct_agg['sum_required']) * 100, 1)
            if ct_agg['sum_required'] else 0
        )
        current_term_stats = ct_agg

    terms = Term.objects.all().order_by('-start_date')

    return {
        'total':             total,
        'cleared':           cleared,
        'outstanding':       outstanding,
        'discounted':        discounted,
        'cleared_pct':       round((cleared / total) * 100, 1) if total else 0,
        'total_required':    total_required,
        'total_paid':        total_paid,
        'total_balance':     total_balance,
        'total_discount':    total_discount,
        'collection_rate':   collection_rate,
        'by_term':           by_term,
        'by_class':          by_class,
        'defaulters':        defaulters,
        'current_term':      current_term,
        'current_term_stats': current_term_stats,
        'terms':             terms,
        'today':             today,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  DETAIL STATS
# ═══════════════════════════════════════════════════════════════════════════════

def get_assessment_fees_detail_stats(assessment: AssessmentFees) -> dict:
    """Stats and context for the single AssessmentFees detail page."""

    # All actual payment records for this student + term
    payments = list(
        FeesPayment.objects.filter(
            student=assessment.student,
            term=assessment.term,
        )
        .select_related('school_fees')
        .order_by('-payment_date')
    )

    # Breakdown by fee type from payment records
    by_fee_type = list(
        FeesPayment.objects.filter(
            student=assessment.student,
            term=assessment.term,
        )
        .values('school_fees__fees_type')
        .annotate(total=Sum('amount_paid'), count=Count('id'))
        .order_by('-total')
    )
    from fees.utils.fees_utils import FEES_TYPE_LABELS
    for row in by_fee_type:
        ft = row['school_fees__fees_type'] or ''
        row['label'] = FEES_TYPE_LABELS.get(ft, ft)

    # All fee structures applicable to this student's class + term
    applicable_fees = list(
        SchoolFees.objects.filter(
            school_class=assessment.student.current_class,
            term=assessment.term,
            is_active=True,
        ).order_by('fees_type')
    )

    # For each applicable fee, how much has this student paid toward it?
    fee_breakdown = []
    for fee in applicable_fees:
        paid_for = (
            FeesPayment.objects.filter(
                student=assessment.student,
                school_fees=fee,
            ).aggregate(s=Sum('amount_paid'))['s'] or Decimal('0')
        )
        fee_breakdown.append({
            'fee':        fee,
            'required':   fee.amount,
            'paid':       paid_for,
            'balance':    max(fee.amount - paid_for, Decimal('0')),
            'cleared':    paid_for >= fee.amount,
        })

    # Other students in the same class+term for context (anonymised stats)
    class_peers = AssessmentFees.objects.filter(
        term=assessment.term,
        student__current_class=assessment.student.current_class,
    ).exclude(pk=assessment.pk)

    class_agg = class_peers.aggregate(
        count        = Count('id'),
        cleared_count= Count('id', filter=Q(is_cleared=True)),
        avg_balance  = Sum('balance'),
    )

    # Prev / next assessments for same student (different terms)
    prev_assessment = (
        AssessmentFees.objects
        .filter(
            student=assessment.student,
            term__start_date__lt=assessment.term.start_date,
        )
        .select_related('term')
        .order_by('-term__start_date')
        .first()
    )
    next_assessment = (
        AssessmentFees.objects
        .filter(
            student=assessment.student,
            term__start_date__gt=assessment.term.start_date,
        )
        .select_related('term')
        .order_by('term__start_date')
        .first()
    )

    return {
        'payments':         payments,
        'payment_count':    len(payments),
        'by_fee_type':      by_fee_type,
        'applicable_fees':  applicable_fees,
        'fee_breakdown':    fee_breakdown,
        'class_agg':        class_agg,
        'prev_assessment':  prev_assessment,
        'next_assessment':  next_assessment,
    }
