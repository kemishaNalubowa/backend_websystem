# academics/utils/term_utils.py
# ─────────────────────────────────────────────────────────────────────────────
# All helper functions for Term views:
#   - Manual field-by-field validation
#   - Data parsing from POST
#   - Per-section statistics builders
# ─────────────────────────────────────────────────────────────────────────────

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import (
    Avg, Count, DecimalField, ExpressionWrapper, F, Q, Sum
)
from django.shortcuts import get_object_or_404

from academics.models import SchoolClass, Term


# ═══════════════════════════════════════════════════════════════════════════════
#  DATE PARSING
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_date(value: str, field_label: str, errors: dict) -> date | None:
    """
    Parse a date string from POST data.
    Returns a date object or None; records an error if the value is
    present but unparseable.
    """
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


def _parse_bool(value: str) -> bool:
    return str(value).strip().lower() in ('1', 'true', 'on', 'yes')


# ═══════════════════════════════════════════════════════════════════════════════
#  MANUAL VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def validate_and_parse_term(post: dict, instance: Term | None = None) -> tuple[dict, dict]:
    """
    Validate all Term POST fields manually.

    Returns:
        (cleaned_data, errors)

    cleaned_data — ready to pass into Term(**cleaned) or Term.objects.filter().update()
    errors       — dict of  field_name → error message string
                   Empty dict means validation passed.

    Covers:
      • Required fields
      • Date order: start → BOT → MOT → EOT → closing
      • Holiday studies consistency
      • Uniqueness: (name, start_date) if creating / changing
    """
    errors: dict = {}
    cleaned: dict = {}

    # ── name ──────────────────────────────────────────────────────────────────
    name_raw = (post.get('name') or '').strip()
    if not name_raw:
        errors['name'] = 'Term number is required.'
    elif name_raw not in ('1', '2', '3'):
        errors['name'] = 'Term must be 1, 2, or 3.'
    else:
        cleaned['name'] = int(name_raw)

    # ── Core dates ────────────────────────────────────────────────────────────
    start_date = _parse_date(post.get('start_date'), 'Start date', errors)
    end_date   = _parse_date(post.get('end_date'),   'End date',   errors)

    if not start_date:
        errors.setdefault('start_date', 'Start date is required.')
    if not end_date:
        errors.setdefault('end_date', 'End date is required.')

    if start_date and end_date:
        if end_date <= start_date:
            errors['end_date'] = 'End date must be after start date.'
        else:
            cleaned['start_date'] = start_date
            cleaned['end_date']   = end_date

    # ── BOT window ────────────────────────────────────────────────────────────
    bot_start = _parse_date(post.get('bot_start_date'), 'BOT start', errors)
    bot_end   = _parse_date(post.get('bot_end_date'),   'BOT end',   errors)

    if bot_start or bot_end:
        if not bot_start:
            errors['bot_start_date'] = 'BOT start date is required when BOT end is set.'
        if not bot_end:
            errors['bot_end_date'] = 'BOT end date is required when BOT start is set.'
        if bot_start and bot_end:
            if bot_end < bot_start:
                errors['bot_end_date'] = 'BOT end must be on or after BOT start.'
            if start_date and bot_start < start_date:
                errors['bot_start_date'] = 'BOT exam cannot begin before the term opens.'
            if not errors.get('bot_start_date') and not errors.get('bot_end_date'):
                cleaned['bot_start_date'] = bot_start
                cleaned['bot_end_date']   = bot_end
    else:
        cleaned['bot_start_date'] = None
        cleaned['bot_end_date']   = None

    # ── MOT window ────────────────────────────────────────────────────────────
    mot_start = _parse_date(post.get('mot_start_date'), 'MOT start', errors)
    mot_end   = _parse_date(post.get('mot_end_date'),   'MOT end',   errors)

    if mot_start or mot_end:
        if not mot_start:
            errors['mot_start_date'] = 'MOT start date is required when MOT end is set.'
        if not mot_end:
            errors['mot_end_date'] = 'MOT end date is required when MOT start is set.'
        if mot_start and mot_end:
            if mot_end < mot_start:
                errors['mot_end_date'] = 'MOT end must be on or after MOT start.'
            if bot_end and mot_start <= bot_end:
                errors['mot_start_date'] = 'MOT exam must start after BOT exam ends.'
            if not errors.get('mot_start_date') and not errors.get('mot_end_date'):
                cleaned['mot_start_date'] = mot_start
                cleaned['mot_end_date']   = mot_end
    else:
        cleaned['mot_start_date'] = None
        cleaned['mot_end_date']   = None

    # ── EOT window ────────────────────────────────────────────────────────────
    eot_start = _parse_date(post.get('eot_start_date'), 'EOT start', errors)
    eot_end   = _parse_date(post.get('eot_end_date'),   'EOT end',   errors)

    if eot_start or eot_end:
        if not eot_start:
            errors['eot_start_date'] = 'EOT start date is required when EOT end is set.'
        if not eot_end:
            errors['eot_end_date'] = 'EOT end date is required when EOT start is set.'
        if eot_start and eot_end:
            if eot_end < eot_start:
                errors['eot_end_date'] = 'EOT end must be on or after EOT start.'
            if mot_end and eot_start <= mot_end:
                errors['eot_start_date'] = 'EOT exam must start after MOT exam ends.'
            if not errors.get('eot_start_date') and not errors.get('eot_end_date'):
                cleaned['eot_start_date'] = eot_start
                cleaned['eot_end_date']   = eot_end
    else:
        cleaned['eot_start_date'] = None
        cleaned['eot_end_date']   = None

    # ── Closing / opening ─────────────────────────────────────────────────────
    closing_date = _parse_date(post.get('closing_date'), 'Closing date', errors)
    opening_date = _parse_date(post.get('opening_date'), 'Opening date', errors)

    if closing_date:
        if eot_end and closing_date < eot_end:
            errors['closing_date'] = 'Closing date must be on or after EOT exam end.'
        else:
            cleaned['closing_date'] = closing_date
    else:
        cleaned['closing_date'] = None

    cleaned['opening_date'] = opening_date  # optional, no strict ordering constraint

    # ── Holiday studies ───────────────────────────────────────────────────────
    has_holiday = _parse_bool(post.get('has_holiday_studies', ''))
    cleaned['has_holiday_studies'] = has_holiday

    hs_start = _parse_date(post.get('holiday_study_start'), 'Holiday study start', errors)
    hs_end   = _parse_date(post.get('holiday_study_end'),   'Holiday study end',   errors)

    if has_holiday:
        if not hs_start:
            errors['holiday_study_start'] = (
                'Holiday study start date is required when holiday studies are enabled.'
            )
        if not hs_end:
            errors['holiday_study_end'] = (
                'Holiday study end date is required when holiday studies are enabled.'
            )
        if hs_start and closing_date and hs_start <= closing_date:
            errors['holiday_study_start'] = (
                'Holiday studies must start after the closing date — '
                'students need at least a day at home first.'
            )
        if hs_start and hs_end and hs_end < hs_start:
            errors['holiday_study_end'] = (
                'Holiday study end must be on or after holiday study start.'
            )

    cleaned['holiday_study_start'] = hs_start if has_holiday else None
    cleaned['holiday_study_end']   = hs_end   if has_holiday else None

    # Auto-compute long_holiday_start
    if has_holiday and hs_end:
        cleaned['long_holiday_start'] = hs_end + timedelta(days=1)
    elif closing_date:
        cleaned['long_holiday_start'] = closing_date
    else:
        cleaned['long_holiday_start'] = None

    # ── Holiday study note ────────────────────────────────────────────────────
    cleaned['holiday_study_note'] = (post.get('holiday_study_note') or '').strip()

    # ── is_current ────────────────────────────────────────────────────────────
    cleaned['is_current'] = _parse_bool(post.get('is_current', ''))

    # ── Uniqueness check: (name, start_date) ─────────────────────────────────
    if 'name' in cleaned and 'start_date' in cleaned:
        qs = Term.objects.filter(
            name=cleaned['name'],
            start_date=cleaned['start_date'],
        )
        if instance and instance.pk:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            errors['name'] = (
                f"Term {cleaned['name']} for {cleaned['start_date'].year} already exists."
            )

    return cleaned, errors


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION STATISTICS
# ═══════════════════════════════════════════════════════════════════════════════

def get_overview_stats(term: Term) -> dict:
    """High-level stats shown on the Term Overview tab."""
    from students.models import Student
    from accounts.models import CustomUser
    from fees.models import FeesPayment, AssessmentFees

    today = date.today()

    # Term timeline
    days_total     = term.term_duration_days or 0
    days_elapsed   = max((today - term.start_date).days, 0) if term.start_date else 0
    days_remaining = max((term.end_date - today).days, 0)   if term.end_date and today <= term.end_date else 0
    progress_pct   = round((days_elapsed / days_total) * 100, 1) if days_total else 0

    # Active student & CustomUser counts
    student_count = Student.objects.filter(is_active=True).count()
    teacher_count = CustomUser.objects.filter(is_active=True, user_type="teacher").count()
    class_count   = SchoolClass.objects.filter(
                        academic_year=term.academic_year,
                        is_active=True
                    ).count()

    # Fees overview
    total_expected = AssessmentFees.objects.filter(term=term).aggregate(
        s=Sum('total_required')
    )['s'] or Decimal('0')
    total_collected = FeesPayment.objects.aggregate(s=Sum('amount_paid'))['s'] or Decimal('0')
    collection_rate = (
        round((total_collected / total_expected) * 100, 1)
        if total_expected else 0
    )

    # Assessment snapshot
    from assessments.models import AssessmentPerformance
    perf_qs = AssessmentPerformance.objects.filter(assessment__term=term, assessment__assessment_type='eot')
    total_assessed   = perf_qs.count()
    total_promoted   = perf_qs.filter(is_pass=True).count()


    # Exam windows — which are past, active, upcoming
    def exam_status(start, end):
        if not start:
            return 'not_set'
        if today < start:
            return 'upcoming'
        if start <= today <= end:
            return 'active'
        return 'done'

    return {
        'days_total':       days_total,
        'days_elapsed':     days_elapsed,
        'days_remaining':   days_remaining,
        'progress_pct':     progress_pct,
        'student_count':    student_count,
        'teacher_count':    teacher_count,
        'class_count':      class_count,
        'total_expected':   total_expected,
        'total_collected':  total_collected,
        'collection_rate':  collection_rate,
        'total_assessed':   total_assessed,
        'total_promoted':   total_promoted,
        'bot_status': exam_status(term.bot_start_date, term.bot_end_date),
        'mot_status': exam_status(term.mot_start_date, term.mot_end_date),
        'eot_status': exam_status(term.eot_start_date, term.eot_end_date),
        'holiday_classes': term.holiday_study_classes.all() if term.has_holiday_studies else [],
    }


def get_calendar_stats(term: Term) -> dict:
    """Stats and structured data for the Term Calendar tab."""
    from school.models import SchoolEvent
    today = date.today()

    events_qs = SchoolEvent.objects.filter(
        Q(start_date__gte=term.start_date) &
        Q(start_date__lte=term.end_date   if term.end_date else date.max)
    ).prefetch_related('school_classes').select_related('organized_by')

    by_type = events_qs.values('event_type').annotate(total=Count('id'))

    upcoming = events_qs.filter(start_date__gte=today).order_by('start_date')[:5]
    past     = events_qs.filter(end_date__lt=today).order_by('-start_date')[:5]

    # Build timeline: exam windows + closing + holiday studies
    milestones = []
    def _add(label, d, category):
        if d:
            milestones.append({'label': label, 'date': d, 'category': category})

    _add('Term Opens',          term.start_date,          'term')
    _add('BOT Exams Begin',     term.bot_start_date,      'exam')
    _add('BOT Exams End',       term.bot_end_date,        'exam')
    _add('MOT Exams Begin',     term.mot_start_date,      'exam')
    _add('MOT Exams End',       term.mot_end_date,        'exam')
    _add('Normal Lessons End',  term.end_date,            'term')
    _add('EOT Exams Begin',     term.eot_start_date,      'exam')
    _add('EOT Exams End',       term.eot_end_date,        'exam')
    _add('School Closes',       term.closing_date,        'term')
    _add('Holiday Studies Begin', term.holiday_study_start, 'holiday')
    _add('Holiday Studies End', term.holiday_study_end,   'holiday')
    _add('Long Holiday Begins', term.long_holiday_start,  'holiday')
    _add('Next Term Opens',     term.opening_date,        'term')

    milestones = sorted([m for m in milestones if m['date']], key=lambda x: x['date'])

    for m in milestones:
        m['is_past']   = m['date'] < today
        m['is_today']  = m['date'] == today
        m['days_from_today'] = (m['date'] - today).days

    return {
        'events':         events_qs,
        'events_count':   events_qs.count(),
        'by_type':        list(by_type),
        'upcoming':       upcoming,
        'past':           past,
        'milestones':     milestones,
    }


def get_admissions_stats(term: Term) -> dict:
    """Stats for the Term Admissions tab."""
    from students.models import Admission

    # Admissions for the academic year this term belongs to
    qs = Admission.objects.filter(
        academic_year=str(term.academic_year)
    ).select_related('applied_class', 'reviewed_by')

    total        = qs.count()
    by_status    = {
        item['status']: item['total']
        for item in qs.values('status').annotate(total=Count('id'))
    }
    by_class     = qs.values(
        'applied_class__level', 'applied_class__stream'
    ).annotate(total=Count('id')).order_by('applied_class__level')
    by_gender    = qs.values('gender').annotate(total=Count('id'))
    recent       = qs.order_by('-application_date')[:10]

    return {
        'admissions':       qs,
        'total':            total,
        'pending':          by_status.get('pending', 0),
        'approved':         by_status.get('approved', 0),
        'enrolled':         by_status.get('enrolled', 0),
        'rejected':         by_status.get('rejected', 0),
        'waitlisted':       by_status.get('waitlisted', 0),
        'shortlisted':      by_status.get('shortlisted', 0),
        'by_class':         list(by_class),
        'by_gender':        list(by_gender),
        'recent':           recent,
        'approval_rate':    round((by_status.get('approved', 0) / total) * 100, 1) if total else 0,
    }


def get_requirements_stats(term: Term) -> dict:
    """Stats for the Term School Requirements tab."""
    from school.models import SchoolRequirement

    qs = SchoolRequirement.objects.filter(term=term).select_related(
        'school_class', 'created_by'
    )
    total         = qs.count()
    by_category   = qs.values('category').annotate(total=Count('id'))
    by_class      = qs.values(
        'school_class__level', 'school_class__stream'
    ).annotate(total=Count('id'))
    compulsory    = qs.filter(is_compulsory=True).count()
    optional      = qs.filter(is_compulsory=False).count()
    published     = qs.filter(is_published=True).count()
    draft         = qs.filter(is_published=False).count()
    total_est_cost = qs.aggregate(s=Sum('estimated_cost'))['s'] or Decimal('0')

    return {
        'requirements':   qs,
        'total':          total,
        'compulsory':     compulsory,
        'optional':       optional,
        'published':      published,
        'draft':          draft,
        'by_category':    list(by_category),
        'by_class':       list(by_class),
        'total_est_cost': total_est_cost,
    }


def get_fees_stats(term: Term) -> dict:
    """Stats for the Term School Fees (structure) tab."""
    from fees.models import SchoolFees

    qs = SchoolFees.objects.filter(term=term, is_active=True).select_related('school_class')

    total_structures = qs.count()
    total_amount     = qs.aggregate(s=Sum('amount'))['s'] or Decimal('0')
    by_type          = list(
        qs.values('fees_type').annotate(
            total=Count('id'),
            total_amount=Sum('amount')
        ).order_by('fees_type')
    )
    by_class         = list(
        qs.values(
            'school_class__level', 'school_class__stream', 'school_class__section'
        ).annotate(
            total=Count('id'),
            total_amount=Sum('amount')
        ).order_by('school_class__section', 'school_class__level')
    )
    compulsory_total = qs.filter(is_compulsory=True).aggregate(
        s=Sum('amount')
    )['s'] or Decimal('0')

    return {
        'fees':              qs,
        'total_structures':  total_structures,
        'total_amount':      total_amount,
        'compulsory_total':  compulsory_total,
        'optional_total':    total_amount - compulsory_total,
        'by_type':           by_type,
        'by_class':          by_class,
    }


def get_payments_stats(term: Term) -> dict:
    """Stats for the Term Fees Payments tab."""
    from fees.models import FeesPayment

    qs = FeesPayment.objects.filter(term=term).select_related(
        'student', 'student__current_class', 'school_fees'
    )

    total_confirmed = qs.aggregate(s=Sum('amount_paid'))['s'] or Decimal('0')
    by_class = list(
        qs.values(
            'student__current_class__level',
            'student__current_class__stream',
        ).annotate(
            count=Count('id'),
            total=Sum('amount_paid')
        ).order_by('-total')
    )
    daily = list(
        qs.values('payment_date').annotate(
            total=Sum('amount_paid'),
            count=Count('id')
        ).order_by('-payment_date')[:30]
    )

    recent = qs.order_by('-payment_date', '-created_at')[:15]

    return {
        'payments':         qs,
        'total_payments':   qs.count(),
        'confirmed_count':  qs.count(),
        'total_confirmed':  total_confirmed,
        'by_class':         by_class,
        'daily_trend':      daily,
        'recent':           recent,
    }


def get_assessment_fees_stats(term: Term) -> dict:
    """Stats for the Term Assessment Fees tab."""
    from fees.models import AssessmentFees

    qs = AssessmentFees.objects.filter(term=term).select_related(
        'student', 'student__current_class', 'generated_by'
    )

    total         = qs.count()
    cleared       = qs.filter(is_cleared=True).count()
    outstanding   = qs.filter(is_cleared=False).count()

    agg = qs.aggregate(
        total_required=Sum('total_required'),
        total_paid=Sum('total_paid'),
        total_balance=Sum('balance'),
        total_discount=Sum('discount_amount'),
    )
    total_required  = agg['total_required']  or Decimal('0')
    total_paid      = agg['total_paid']      or Decimal('0')
    total_balance   = agg['total_balance']   or Decimal('0')
    total_discount  = agg['total_discount']  or Decimal('0')

    collection_rate = (
        round((total_paid / total_required) * 100, 1)
        if total_required else 0
    )
    by_class = list(
        qs.values(
            'student__current_class__level',
            'student__current_class__stream',
        ).annotate(
            count=Count('id'),
            cleared=Count('id', filter=Q(is_cleared=True)),
            balance_total=Sum('balance'),
        ).order_by('student__current_class__level')
    )
    # Defaulters — most overdue first
    defaulters = qs.filter(is_cleared=False).order_by('-balance')[:20]

    return {
        'assessments':      qs,
        'total':            total,
        'cleared':          cleared,
        'outstanding':      outstanding,
        'cleared_pct':      round((cleared / total) * 100, 1) if total else 0,
        'total_required':   total_required,
        'total_paid':       total_paid,
        'total_balance':    total_balance,
        'total_discount':   total_discount,
        'collection_rate':  collection_rate,
        'by_class':         by_class,
        'defaulters':       defaulters,
    }


def get_assessments_stats(term: Term) -> dict:
    """Stats for the Term Assessments tab (academic performance)."""
    from assessments.models import AssessmentSubject, AssessmentClass, AssessmentPerformance
    from academics.models import Subject

    # ── Class-level summaries ─────────────────────────────────────────────────
    class_summaries = AssessmentClass.objects.filter(assessment__term=term).select_related(
        'school_class',
    ).order_by('school_class__section', 'school_class__level')

    # ── Student performance ────────────────────────────────────────────────────
    perf_qs = AssessmentPerformance.objects.filter(assessment__term=term).select_related(
        'student', 'school_class'
    )
    total_students_assessed = perf_qs.count()
    promoted                = perf_qs.filter(is_pass=True).count()
    retained                = perf_qs.filter(is_pass=False).count()


    top_students = perf_qs.filter(
        assessment__assessment_type='eot'
    ).order_by('marks_obtained')[:10]

    # ── Subject-level averages ─────────────────────────────────────────────────
    subj_avgs = list(
        AssessmentSubject.objects.filter(assessment__term=term).values(
            'subject__name', 'subject__code', 'assessment__assessment_type'
        ).annotate(
            count=Count('id'),
        ).order_by('subject__sort_order')
    )

    # ── Per exam type counts ───────────────────────────────────────────────────
    by_exam_type = list(
        perf_qs.values('assessment__assessment_type').annotate(
            count=Count('id'),
        ).order_by('assessment__assessment_type')
    )

    # ── Division distribution (EOT, primary) ──────────────────────────────────
    divisions = list(
        perf_qs.filter(assessment__assessment_type='eot').values('grade').annotate(
            count=Count('id')
        ).order_by('grade')
    )

    return {
        'class_summaries':          class_summaries,
        'total_students_assessed':  total_students_assessed,
        'promoted':                 promoted,
        'retained':                 retained,
        'promotion_rate':           round((promoted / total_students_assessed) * 100, 1)
                                    if total_students_assessed else 0,
        'top_students':             top_students,
        'subject_averages':         subj_avgs,
        'by_exam_type':             by_exam_type,
        'divisions':                divisions,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  SMALL HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_classes() -> list:
    """Return all active SchoolClass objects for select dropdowns."""
    return SchoolClass.objects.filter(is_active=True).order_by('section', 'level', 'stream')


def get_terms_list_stats() -> dict:
    """
    High-level stats shown above the terms list page.
    """
    from fees.models import FeesPayment
    from students.models import Student

    total_terms   = Term.objects.count()
    current_term  = Term.objects.filter(is_current=True).first()
    total_students = (
        Student.objects.filter(is_active=True).count()
    )
    # Total fees ever collected
    total_collected = FeesPayment.objects.aggregate(s=Sum('amount_paid'))['s'] or Decimal('0')

    return {
        'total_terms':    total_terms,
        'current_term':   current_term,
        'total_students': total_students,
        'total_collected': total_collected,
    }


def set_current_term(term: Term):
    """
    Ensure only the given term is marked as current.
    Deactivates all others first.
    """
    Term.objects.exclude(pk=term.pk).update(is_current=False)
    term.is_current = True
    term.save(update_fields=['is_current'])
