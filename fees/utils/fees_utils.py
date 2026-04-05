# fees/utils/fees_utils.py
# ─────────────────────────────────────────────────────────────────────────────
# Helpers for SchoolFees views:
#   - Manual field validation
#   - POST data parsing
#   - List-level and detail statistics
# ─────────────────────────────────────────────────────────────────────────────

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.db.models import Avg, Count, Max, Min, Q, Sum

from fees.models import SchoolFees
from academics.utils.subject_utils import get_sch_supported_classes


# ═══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

VALID_FEES_TYPES = {
    'tuition', 'development', 'activity', 'lunch',
    'transport', 'uniform', 'boarding', 'pta',
    'exam', 'admission', 'other',
}

FEES_TYPE_LABELS = {
    'tuition':     'Tuition Fees',
    'development': 'Development / Building Levy',
    'activity':    'Activity / Games Fees',
    'lunch':       'Lunch / Feeding Fees',
    'transport':   'Transport / Bus Fees',
    'uniform':     'Uniform Fees',
    'boarding':    'Boarding Fees',
    'pta':         'PTA Contribution',
    'exam':        'Examination Fees',
    'admission':   'Admission / Registration Fees',
    'other':       'Other',
}


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

def validate_and_parse_fees(
    post: dict,
    instance: SchoolFees | None = None,
) -> tuple[dict, dict]:
    """
    Manually validate all SchoolFees POST fields.

    Returns:
        (cleaned_data, errors)

    cleaned_data — ready for setattr loop. school_class_id and term_id
                   stored as ints; view resolves FKs.
    errors       — dict of field_name → error message.
                   Empty = passed.
    """
    errors:  dict = {}
    cleaned: dict = {}

    # ── school_class (required FK) ────────────────────────────────────────────
    supported_classes = get_sch_supported_classes()
    affected_classess = []
    for sc in supported_classes:
        class_ = (post.get(f'class_{sc.supported_class.key.lower()}') or '').strip()
        
        if class_:
            affected_classess.append(class_)
    
    if not affected_classess:
        errors["class_"] = 'Atleast on Class is Required'
    else:
        cleaned['affected_classes'] = affected_classess

    # ── term (required FK) ────────────────────────────────────────────────────
    term_id = (post.get('term') or '').strip()
    if not term_id:
        errors['term'] = 'Term is required.'
    else:
        try:
            cleaned['term_id'] = int(term_id)
        except ValueError:
            errors['term'] = 'Invalid term selected.'

    # ── fees_type (required choice) ───────────────────────────────────────────
    fees_type = (post.get('fees_type') or '').strip()
    if not fees_type:
        errors['fees_type'] = 'Fee type is required.'
    elif fees_type not in VALID_FEES_TYPES:
        errors['fees_type'] = 'Invalid fee type selected.'
    else:
        cleaned['fees_type'] = fees_type

    # -- 
    fees_title = (post.get('fees_title') or '').strip()
    if cleaned['fees_type'] == 'other':
        if not fees_title:
            errors['fees_title'] = 'You choose fees type as Others, Please specify the title'
        else:
            cleaned['fees_title'] = fees_title
    

    # ── amount (required, positive decimal, UGX) ──────────────────────────────
    amount_raw = (post.get('amount') or '').strip()
    if not amount_raw:
        errors['amount'] = 'Amount is required.'
    else:
        try:
            amount = Decimal(amount_raw.replace(',', ''))
            if amount <= 0:
                errors['amount'] = 'Amount must be greater than zero.'
            elif amount > Decimal('999999999.99'):
                errors['amount'] = 'Amount is too large.'
            else:
                cleaned['amount'] = amount
        except InvalidOperation:
            errors['amount'] = 'Amount must be a valid number (e.g. 250000).'

    # ── description ───────────────────────────────────────────────────────────
    cleaned['description'] = (post.get('description') or '').strip()

    # ── due_date (optional) ───────────────────────────────────────────────────
    cleaned['due_date'] = _parse_date(post.get('due_date'), 'Due date', errors)

    # ── is_active ─────────────────────────────────────────────────────────────
    cleaned['is_active'] = (
        str(post.get('is_active', '')).strip().lower()
        in ('1', 'true', 'on', 'yes')
    )
    return cleaned, errors


# ═══════════════════════════════════════════════════════════════════════════════
#  LIST STATS
# ═══════════════════════════════════════════════════════════════════════════════

def get_fees_list_stats() -> dict:
    """High-level statistics shown above the fees list page."""
    qs = SchoolFees.objects.all()

    total       = qs.count()
    active      = qs.filter(is_active=True).count()
    inactive    = qs.filter(is_active=False).count()
    # compulsory  = qs.filter(is_compulsory=True, is_active=True).count()
    # optional    = qs.filter(is_compulsory=False, is_active=True).count()

    # Total UGX across all active fee structures
    total_amount = (
        qs.filter(is_active=True).aggregate(s=Sum('amount'))['s']
        or Decimal('0')
    )
    # compulsory_amount = (
    #     qs.filter(is_active=True, is_compulsory=True).aggregate(s=Sum('amount'))['s']
    #     or Decimal('0')
    # )

    # By fee type
    by_type = list(
        qs.filter(is_active=True)
        .values('fees_type')
        .annotate(count=Count('id'), total_amount=Sum('amount'))
        .order_by('-total_amount')
    )
    for row in by_type:
        row['label'] = FEES_TYPE_LABELS.get(row['fees_type'], row['fees_type'])

    # By term
    by_term = list(
        qs.filter(is_active=True)
        .values('term__name', 'term__start_date')
        .annotate(count=Count('id'), total_amount=Sum('amount'))
        .order_by('-term__start_date')[:6]
    )

    # By class section
    by_section = list(
        qs.filter(is_active=True)
        # .values('school_class__supported_class__section')
        .annotate(count=Count('id'), total_amount=Sum('amount'))
        # .order_by('school_class__supported_class__section')
    )

    # By class level
    # by_class = list(
    #     qs.filter(is_active=True)
    #     .values(
    #         'school_class__supported_class__section',
    #     )
    #     .annotate(count=Count('id'), total_amount=Sum('amount'))
    #     .order_by('school_class__supported_class__section')
    # )

    # Highest and lowest single fee amount
    agg = qs.filter(is_active=True).aggregate(
        highest=Max('amount'),
        lowest=Min('amount'),
        average=Avg('amount'),
    )

    # Current term fee structures
    from academics.models import Term
    current_term = Term.objects.filter(is_current=True).first()
    current_term_fees = None
    current_term_total = Decimal('0')
    if current_term:
        current_term_fees = qs.filter(
            term=current_term, is_active=True
        ).select_related('school_class').order_by(
            # 'school_class__supported_class__section',
            'fees_type'
        )
        current_term_total = (
            current_term_fees.aggregate(s=Sum('amount'))['s'] or Decimal('0')
        )

    # Overdue fees (due_date passed, still active)
    today = date.today()
    overdue = qs.filter(
        is_active=True,
        due_date__lt=today,
        due_date__isnull=False,
    ).count()

    # Available terms for filter dropdown
    from academics.models import Term as TermModel
    terms = TermModel.objects.all().order_by('-start_date')

    return {
        'total':                total,
        'active':               active,
        'inactive':             inactive,
        # 'compulsory':           compulsory,
        # 'optional':             optional,
        'total_amount':         total_amount,
        # 'compulsory_amount':    compulsory_amount,
        # 'optional_amount':      total_amount - compulsory_amount,
        'by_type':              by_type,
        'by_term':              by_term,
        'by_section':           by_section,
        # 'by_class':             by_class,
        'highest_fee':          agg['highest'] or Decimal('0'),
        'lowest_fee':           agg['lowest']  or Decimal('0'),
        'average_fee':          round(agg['average'], 0) if agg['average'] else Decimal('0'),
        'overdue':              overdue,
        'current_term':         current_term,
        # 'current_term_fees':    current_term_fees,
        'current_term_total':   current_term_total,
        'terms':                terms,
        'today':                today,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  DETAIL STATS
# ═══════════════════════════════════════════════════════════════════════════════

def get_fees_detail_stats(fee: SchoolFees) -> dict:
    """Stats and context for the single SchoolFees detail page."""
    today = date.today()

    # Overdue flag
    is_overdue = (
        fee.due_date is not None
        and fee.due_date < today
        and fee.is_active
    )
    days_overdue = (today - fee.due_date).days if is_overdue else None

    # How much has been collected against this fee structure
    from fees.models import FeesPayment
    payments_qs = FeesPayment.objects.filter(
        school_fees=fee, #status='confirmed'
    )
    total_collected  = payments_qs.aggregate(s=Sum('amount_paid'))['s'] or Decimal('0')
    payment_count    = payments_qs.count()
    collection_rate  = (
        round((total_collected / fee.amount) * 100, 1)
        if fee.amount else 0
    )

    # Students in this class (potential payers)
    from students.models import Student
    student_count = Student.objects.filter(
       # current_class=fee.school_class, 
        is_active=True
    ).count()
    expected_total = fee.amount * student_count

    # Students who have paid at least once for this fee
    paid_student_count = (
        payments_qs.values('student').distinct().count()
    )
    unpaid_student_count = max(student_count - paid_student_count, 0)

    # Payment method breakdown
    # by_method = list(
    #     payments_qs.values('payment_method')
    #     .annotate(count=Count('id'), total=Sum('amount_paid'))
    #     .order_by('-total')
    # )

    # Recent 10 payments for this fee structure
    # recent_payments = list(
    #     FeesPayment.objects.filter(school_fees=fee)
    #     .select_related('student', 'received_by')
    #     .order_by('-payment_date')[:10]
    # )

    # Sibling fee structures — same term, same class, different type
    # siblings = list(
    #     SchoolFees.objects.filter(
    #         term=fee.term,
    #         school_class=fee.school_class,
    #     )
    #     .exclude(pk=fee.pk)
    #     .order_by('fees_type')
    # )

    # Same fee type across other classes in the same term (for benchmarking)
    same_type_others = list(
        SchoolFees.objects.filter(
            term=fee.term,
            fees_type=fee.fees_type,
            is_active=True,
        )
        .exclude(pk=fee.pk)
        # .select_related('school_class')
        # .order_by('school_class__section', 'school_class__level')
    )

    return {
        'is_overdue':          is_overdue,
        'days_overdue':        days_overdue,
        'total_collected':     total_collected,
        'payment_count':       payment_count,
        'collection_rate':     collection_rate,
        'student_count':       student_count,
        'expected_total':      expected_total,
        'paid_student_count':  paid_student_count,
        'unpaid_student_count': unpaid_student_count,
        'shortfall':           max(fee.amount * student_count - total_collected, Decimal('0')),
        # 'by_method':           by_method,
        # 'recent_payments':     recent_payments,
        # 'siblings':            siblings,
        'same_type_others':    same_type_others,
        'fees_type_label':     FEES_TYPE_LABELS.get(fee.fees_type, fee.fees_type),
        'today':               today,
    }
