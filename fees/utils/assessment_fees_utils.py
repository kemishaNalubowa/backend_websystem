# fees/utils/assessment_fees_utils.py

from decimal import Decimal, InvalidOperation
from datetime import date, datetime

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
    Returns (cleaned_data, errors).
    """
    errors:  dict = {}
    cleaned: dict = {}

    # ── assessment (required FK) ──────────────────────────────────────────────
    assessment_id = (post.get('assessment') or '').strip()
    if not assessment_id:
        errors['assessment'] = 'Assessment is required.'
    else:
        try:
            cleaned['assessment_id'] = int(assessment_id)
        except ValueError:
            errors['assessment'] = 'Invalid assessment selected.'

    # ── term (required FK) ────────────────────────────────────────────────────
    term_id = (post.get('term') or '').strip()
    if not term_id:
        errors['term'] = 'Term is required.'
    else:
        try:
            cleaned['term_id'] = int(term_id)
        except ValueError:
            errors['term'] = 'Invalid term selected.'

    # ── amount (required, positive decimal) ───────────────────────────────────
    amount_raw = (post.get('amount') or '').strip()
    if not amount_raw:
        errors['amount'] = 'The assessment amount is required.'
    else:
        try:
            req = Decimal(amount_raw.replace(',', ''))
            if req < 0:
                errors['amount'] = 'Amount cannot be negative.'
            elif req > Decimal('999999999.99'):
                errors['amount'] = 'Amount is too large.'
            else:
                cleaned['amount'] = req
        except InvalidOperation:
            errors['amount'] = 'Amount must be a valid number (e.g. 750000).'

    # ── due_date (optional) ───────────────────────────────────────────────────
    due_date_raw = (post.get('due_date') or '').strip()   # fixed: was reading 'amount'
    if due_date_raw:
        parsed = None
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
            try:
                parsed = datetime.strptime(due_date_raw, fmt).date()
                break
            except ValueError:
                continue
        if not parsed:
            errors['due_date'] = 'Due date is not a valid date (use YYYY-MM-DD).'
        else:
            cleaned['due_date'] = parsed
    else:
        cleaned['due_date'] = None

    return cleaned, errors


# ═══════════════════════════════════════════════════════════════════════════════
#  RECALCULATE FROM PAYMENTS
# ═══════════════════════════════════════════════════════════════════════════════

def recalculate_from_payments(assessment: AssessmentFees) -> dict:
    """Re-sync assessment total_paid from actual FeesPayment records."""
    payments_qs = FeesPayment.objects.filter(term=assessment.term)

    new_paid  = payments_qs.aggregate(s=Sum('amount_paid'))['s'] or Decimal('0')
    last_date = (
        payments_qs.order_by('-payment_date')
        .values_list('payment_date', flat=True)
        .first()
    )

    old_paid = getattr(assessment, 'total_paid', Decimal('0'))
    changed  = (old_paid != new_paid)

    assessment.save()

    return {
        'old_paid': old_paid,
        'new_paid': new_paid,
        'changed':  changed,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  BULK GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def bulk_generate_for_class(school_class, term, generated_by, overwrite: bool = False) -> dict:
    from students.models import Student

    students = Student.objects.filter(current_class=school_class, is_active=True)

    created = updated = skipped = 0
    errors  = []

    for student in students:
        try:
            existing = AssessmentFees.objects.filter(term=term).first()

            if existing:
                if overwrite:
                    existing.generated_by = generated_by
                    existing.save()
                    updated += 1
                else:
                    skipped += 1
                continue

            AssessmentFees.objects.create(
                term         = term,
                generated_by = generated_by,
            )
            created += 1

        except Exception as exc:
            errors.append(f'{student}: {exc}')

    return {'created': created, 'updated': updated, 'skipped': skipped, 'errors': errors}


# ═══════════════════════════════════════════════════════════════════════════════
#  LIST STATS
# ═══════════════════════════════════════════════════════════════════════════════

def get_assessment_fees_list_stats() -> dict:
    today = date.today()
    qs    = AssessmentFees.objects.all()
    total = qs.count()

    from academics.models import Term
    current_term = Term.objects.filter(is_current=True).first()
    terms        = Term.objects.all().order_by('-start_date')

    return {
        'total':              total,
        'current_term':       current_term,
        'terms':              terms,
        'today':              today,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  DETAIL STATS
# ═══════════════════════════════════════════════════════════════════════════════

def get_assessment_fees_detail_stats(assessment: AssessmentFees) -> dict:
    payments = list(
        FeesPayment.objects.filter(term=assessment.term)
        .select_related('school_fees')
        .order_by('-payment_date')
    )

    return {
        'payments':      payments,
        'payment_count': len(payments),
    }
