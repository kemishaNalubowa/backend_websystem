# fees/utils/payment_utils.py
# ─────────────────────────────────────────────────────────────────────────────
# Helpers for FeesPayment views:
#   - Auto receipt number generation
#   - Manual field validation
#   - List-level and detail statistics
# ─────────────────────────────────────────────────────────────────────────────

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.db.models import Avg, Count, Max, Min, Q, Sum

from fees.models import FeesPayment, SchoolFees


# ═══════════════════════════════════════════════════════════════════════════════
#  RECEIPT NUMBER GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def generate_receipt_number() -> str:
    """
    Auto-generate a unique receipt number in the format RCP<YEAR><SEQ>.
    Example: RCP2025001, RCP2025002 … RCP2025999
    Sequence resets each calendar year.
    Thread-safe: uses DB MAX + 1, wrapped in atomic() by the view.
    """
    year = date.today().year
    prefix = f'RCP{year}'

    last = (
        FeesPayment.objects
        .filter(receipt_number__startswith=prefix)
        .aggregate(m=Max('receipt_number'))['m']
    )

    if last:
        try:
            seq = int(last.replace(prefix, '')) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1

    return f'{prefix}{seq:04d}'    # e.g. RCP20250001



from fees.models import ScholasticRequirementPayment

def generate_receipt_number_scholastic() -> str:
    year   = date.today().year
    prefix = f'SRR{year}'

    last = (
        ScholasticRequirementPayment.objects  # ← correct model
        .filter(receipt_number__startswith=prefix)
        .aggregate(m=Max('receipt_number'))['m']
    )

    if last:
        try:
            seq = int(last.replace(prefix, '')) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1

    return f'{prefix}{seq:04d}'
# ═══════════════════════════════════════════════════════════════════════════════
#  DATE PARSING
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_date(value: str, field_label: str, errors: dict) -> date | None:
    value = (value or '').strip()
    if not value:
        return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    errors[field_label] = f'{field_label} is not a valid date (use YYYY-MM-DD).'
    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def validate_and_parse_payment(
    post: dict,
    instance: FeesPayment | None = None,
) -> tuple[dict, dict]:
    """
    Manually validate all FeesPayment POST fields.

    Returns:
        (cleaned_data, errors)

    cleaned_data — ready for setattr loop. All FK ids stored as ints.
    errors       — dict of field_name → error message.
                   Empty = passed.

    Note: receipt_number is NOT validated here — it is auto-generated
          by generate_receipt_number() in the add view.
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

    # ── school_class (required FK) ────────────────────────────────────────────
    class_id = (post.get('school_class') or '').strip()
    if not class_id:
        errors['school_class'] = 'Class is required.'
    else:
        try:
            cleaned['school_class_id'] = int(class_id)
        except ValueError:
            errors['school_class'] = 'Invalid class selected.'

    # ── school_fees (required FK) ─────────────────────────────────────────────
    fees_id = (post.get('school_fees') or '').strip()
    if not fees_id:
        errors['school_fees'] = 'Fee item is required.'
    else:
        try:
            cleaned['school_fees_id'] = int(fees_id)
        except ValueError:
            errors['school_fees'] = 'Invalid fee item selected.'

    # Cross-check: school_fees must belong to the selected term and class
    if (
        'school_fees_id' in cleaned
        and 'term_id' in cleaned
        and 'school_class_id' in cleaned
    ):
        fee_ok = SchoolFees.objects.filter(
            pk=cleaned['school_fees_id'],
            term_id=cleaned['term_id'],
            school_class_id=cleaned['school_class_id'],
            is_active=True,
        ).exists()
        if not fee_ok:
            errors['school_fees'] = (
                'The selected fee item does not belong to the chosen class '
                'and term, or it is inactive.'
            )

    # ── amount_paid (required, positive decimal) ───────────────────────────────
    amount_raw = (post.get('amount_paid') or '').strip()
    if not amount_raw:
        errors['amount_paid'] = 'Amount paid is required.'
    else:
        try:
            amount = Decimal(amount_raw.replace(',', ''))
            if amount <= 0:
                errors['amount_paid'] = 'Amount paid must be greater than zero.'
            elif amount > Decimal('999999999.99'):
                errors['amount_paid'] = 'Amount paid is too large.'
            else:
                # Warn (not block) if amount exceeds fee structure amount
                if 'school_fees_id' in cleaned and not errors.get('school_fees'):
                    try:
                        fee_obj = SchoolFees.objects.get(pk=cleaned['school_fees_id'])
                        if amount > fee_obj.amount:
                            errors['amount_paid'] = (
                                f'Amount paid (UGX {amount:,.0f}) exceeds the '
                                f'fee structure amount (UGX {fee_obj.amount:,.0f}). '
                                f'Please verify.'
                            )
                    except SchoolFees.DoesNotExist:
                        pass
                if not errors.get('amount_paid'):
                    cleaned['amount_paid'] = amount
        except InvalidOperation:
            errors['amount_paid'] = 'Amount paid must be a valid number (e.g. 250000).'

    # ── payment_date (required) ────────────────────────────────────────────────
    payment_date = _parse_date(post.get('payment_date'), 'Payment date', errors)
    if not payment_date:
        errors.setdefault('payment_date', 'Payment date is required.')
    else:
        if payment_date > date.today():
            errors['payment_date'] = 'Payment date cannot be in the future.'
        else:
            cleaned['payment_date'] = payment_date

    return cleaned, errors


# ═══════════════════════════════════════════════════════════════════════════════
#  LIST STATS
# ═══════════════════════════════════════════════════════════════════════════════

def get_payment_list_stats() -> dict:
    """High-level statistics shown above the payments list page."""
    today = date.today()
    qs    = FeesPayment.objects.all()

    total         = qs.count()
    total_amount  = qs.aggregate(s=Sum('amount_paid'))['s'] or Decimal('0')

    # By term
    by_term = list(
        qs.values('term__name', 'term__start_date')
        .annotate(count=Count('id'), total=Sum('amount_paid'))
        .order_by('-term__start_date')[:6]
    )

    # By class section
    by_section = list(
        qs.values('school_class__section')
        .annotate(count=Count('id'), total=Sum('amount_paid'))
        .order_by('school_class__section')
    )

    # By class level
    by_class = list(
        qs.values(
            'school_class__level',
            'school_class__stream',
            'school_class__section',
        )
        .annotate(count=Count('id'), total=Sum('amount_paid'))
        .order_by('school_class__section', 'school_class__level')
    )

    # By fee type (via school_fees)
    by_fee_type = list(
        qs.values('school_fees__fees_type')
        .annotate(count=Count('id'), total=Sum('amount_paid'))
        .order_by('-total')
    )
    from fees.utils.fees_utils import FEES_TYPE_LABELS
    for row in by_fee_type:
        ft = row['school_fees__fees_type'] or ''
        row['label'] = FEES_TYPE_LABELS.get(ft, ft)

    # Daily trend — last 30 days
    from django.db.models.functions import TruncDate
    daily_trend = list(
        qs.filter(payment_date__gte=date.fromordinal(today.toordinal() - 30))
        .values('payment_date')
        .annotate(count=Count('id'), total=Sum('amount_paid'))
        .order_by('payment_date')
    )

    # Monthly totals for current year
    from django.db.models.functions import ExtractMonth
    monthly = list(
        qs.filter(payment_date__year=today.year)
        .annotate(month=ExtractMonth('payment_date'))
        .values('month')
        .annotate(count=Count('id'), total=Sum('amount_paid'))
        .order_by('month')
    )

    # Highest / lowest / average single payment
    agg = qs.aggregate(
        highest=Max('amount_paid'),
        lowest=Min('amount_paid'),
        average=Avg('amount_paid'),
    )

    # Today's collection
    today_total = (
        qs.filter(payment_date=today)
        .aggregate(s=Sum('amount_paid'))['s'] or Decimal('0')
    )
    today_count = qs.filter(payment_date=today).count()

    # Current term context
    from academics.models import Term
    current_term = Term.objects.filter(is_current=True).first()
    current_term_total = Decimal('0')
    current_term_count = 0
    if current_term:
        ct_qs = qs.filter(term=current_term)
        current_term_total = ct_qs.aggregate(s=Sum('amount_paid'))['s'] or Decimal('0')
        current_term_count = ct_qs.count()

    # Recent 10 payments for the summary strip
    recent = list(
        qs.select_related('student', 'school_class', 'school_fees', 'term')
        .order_by('-payment_date', '-created_at')[:10]
    )

    # Available terms for filter dropdown
    terms = Term.objects.all().order_by('-start_date')

    return {
        'total':               total,
        'total_amount':        total_amount,
        'today_total':         today_total,
        'today_count':         today_count,
        'current_term':        current_term,
        'current_term_total':  current_term_total,
        'current_term_count':  current_term_count,
        'by_term':             by_term,
        'by_section':          by_section,
        'by_class':            by_class,
        'by_fee_type':         by_fee_type,
        'daily_trend':         daily_trend,
        'monthly':             monthly,
        'highest_payment':     agg['highest'] or Decimal('0'),
        'lowest_payment':      agg['lowest']  or Decimal('0'),
        'average_payment':     round(agg['average'], 0) if agg['average'] else Decimal('0'),
        'recent':              recent,
        'terms':               terms,
        'today':               today,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  DETAIL STATS
# ═══════════════════════════════════════════════════════════════════════════════

def get_payment_detail_stats(payment: FeesPayment) -> dict:
    """Stats and context for the single payment detail page."""

    # Fee structure context: how much of the fee does this payment cover?
    fee        = payment.school_fees
    fee_amount = fee.amount if fee else Decimal('0')
    coverage   = (
        round((payment.amount_paid / fee_amount) * 100, 1)
        if fee_amount else 0
    )

    # Total paid by this student for this fee across all payments
    student_total_for_fee = (
        FeesPayment.objects.filter(
            student=payment.student,
            school_fees=payment.school_fees,
        )
        .aggregate(s=Sum('amount_paid'))['s'] or Decimal('0')
    )
    outstanding = max(fee_amount - student_total_for_fee, Decimal('0'))
    is_cleared  = outstanding == 0

    # All payments by the same student in the same term
    student_term_payments = list(
        FeesPayment.objects.filter(
            student=payment.student,
            term=payment.term,
        )
        .select_related('school_fees')
        .order_by('-payment_date')
        .exclude(pk=payment.pk)
    )
    student_term_total = (
        FeesPayment.objects.filter(
            student=payment.student,
            term=payment.term,
        ).aggregate(s=Sum('amount_paid'))['s'] or Decimal('0')
    )

    # Prev / next payments (by date) for navigation
    prev_payment = (
        FeesPayment.objects
        .filter(payment_date__lt=payment.payment_date)
        .exclude(pk=payment.pk)
        .order_by('-payment_date')
        .first()
    )
    next_payment = (
        FeesPayment.objects
        .filter(payment_date__gt=payment.payment_date)
        .exclude(pk=payment.pk)
        .order_by('payment_date')
        .first()
    )

    from fees.utils.fees_utils import FEES_TYPE_LABELS
    fee_type_label = FEES_TYPE_LABELS.get(fee.fees_type, fee.fees_type) if fee else '—'

    return {
        'fee':                      fee,
        'fee_amount':               fee_amount,
        'coverage':                 coverage,
        'student_total_for_fee':    student_total_for_fee,
        'outstanding':              outstanding,
        'is_cleared':               is_cleared,
        'student_term_payments':    student_term_payments,
        'student_term_total':       student_term_total,
        'prev_payment':             prev_payment,
        'next_payment':             next_payment,
        'fee_type_label':           fee_type_label,
    }
