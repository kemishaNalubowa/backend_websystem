# academics/views/term_views.py
# ─────────────────────────────────────────────────────────────────────────────
# All Term views.
# Rules:
#   - Function-based views only
#   - No forms.py / Django Forms
#   - No Class-based Views
#   - No JSON responses
#   - Manual validation via term_utils.validate_and_parse_term()
#   - Django messages for all feedback
#   - login_required on every view
# ─────────────────────────────────────────────────────────────────────────────

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from academics.models import Term
from academics.utils.term_utils import (
    get_admissions_stats,
    get_all_classes,
    get_assessment_fees_stats,
    get_assessments_stats,
    get_calendar_stats,
    get_fees_stats,
    get_overview_stats,
    get_payments_stats,
    get_requirements_stats,
    get_terms_list_stats,
    set_current_term,
    validate_and_parse_term,
)

# Shared template base paths
_T = 'academics/terms/'


# ═══════════════════════════════════════════════════════════════════════════════
#  1. TERMS LIST
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def term_list(request):
    """
    Lists all terms with high-level statistics.
    Supports filtering by academic year and term number.
    """
    qs = Term.objects.all().prefetch_related('holiday_study_classes')

    # ── Filters ───────────────────────────────────────────────────────────────
    filter_year = request.GET.get('year', '').strip()
    filter_term = request.GET.get('term', '').strip()

    if filter_year:
        # academic_year is a property derived from start_date.year
        qs = qs.filter(start_date__year=filter_year)
    if filter_term and filter_term in ('1', '2', '3'):
        qs = qs.filter(name=int(filter_term))

    qs = qs.order_by('-start_date', 'name')

    # ── Pagination ────────────────────────────────────────────────────────────
    paginator = Paginator(qs, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # ── List-level stats ──────────────────────────────────────────────────────
    stats = get_terms_list_stats()

    # Distinct years for filter dropdown
    years = (
        Term.objects.dates('start_date', 'year', order='DESC')
        .values_list('start_date__year', flat=True)
        .distinct()
    )

    context = {
        'page_obj':     page_obj,
        'terms':        page_obj.object_list,
        'filter_year':  filter_year,
        'filter_term':  filter_term,
        'years':        years,
        **stats,
        # Active section for sidebar
        'section': 'list',
    }
    return render(request, f'{_T}list.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  2. ADD TERM
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def term_add(request):
    """
    Add a new Term.
    GET  — render blank form.
    POST — validate manually; save on success; re-render with errors on failure.
    """
    all_classes = get_all_classes()

    if request.method == 'GET':
        return render(request, f'{_T}form.html', {
            'all_classes': all_classes,
            'form_title':  'Add New Term',
            'action':      'add',
            'section':     'add',
            'post':        {},    # empty — template reads from here
            'errors':      {},
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    cleaned, errors = validate_and_parse_term(request.POST)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}form.html', {
            'all_classes': all_classes,
            'form_title':  'Add New Term',
            'action':      'add',
            'section':     'add',
            'post':        request.POST,
            'errors':      errors,
        })

    try:
        with transaction.atomic():
            # If this term is marked current, deactivate others first
            if cleaned.get('is_current'):
                Term.objects.all().update(is_current=False)

            # Separate M2M data before creating the instance
            holiday_class_ids = request.POST.getlist('holiday_study_classes')
            cleaned.pop('holiday_study_classes', None)   # not a model field directly

            term = Term.objects.create(**cleaned)

            if cleaned.get('has_holiday_studies') and holiday_class_ids:
                term.holiday_study_classes.set(holiday_class_ids)

    except Exception as exc:
        messages.error(request, f'Could not save term: {exc}')
        return render(request, f'{_T}form.html', {
            'all_classes': all_classes,
            'form_title':  'Add New Term',
            'action':      'add',
            'section':     'add',
            'post':        request.POST,
            'errors':      {},
        })

    messages.success(
        request,
        f'Term {term.name} — {term.academic_year} has been created successfully.'
    )
    return redirect('academics:term_detail_overview', pk=term.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  3. EDIT TERM
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def term_edit(request, pk):
    """
    Edit an existing Term.
    GET  — render form pre-filled with current values.
    POST — validate; save on success; re-render with errors on failure.
    """
    term = get_object_or_404(Term, pk=pk)
    all_classes = get_all_classes()
    selected_class_ids = list(
        term.holiday_study_classes.values_list('id', flat=True)
    )

    if request.method == 'GET':
        return render(request, f'{_T}form.html', {
            'term':                term,
            'all_classes':         all_classes,
            'selected_class_ids':  selected_class_ids,
            'form_title':          f'Edit — Term {term.name} ({term.academic_year})',
            'action':              'edit',
            'section':             'edit',
            'post':                {},
            'errors':              {},
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    cleaned, errors = validate_and_parse_term(request.POST, instance=term)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}form.html', {
            'term':                term,
            'all_classes':         all_classes,
            'selected_class_ids':  selected_class_ids,
            'form_title':          f'Edit — Term {term.name} ({term.academic_year})',
            'action':              'edit',
            'section':             'edit',
            'post':                request.POST,
            'errors':              errors,
        })

    try:
        with transaction.atomic():
            holiday_class_ids = request.POST.getlist('holiday_study_classes')

            # If marking current, deactivate all other terms
            if cleaned.get('is_current') and not term.is_current:
                Term.objects.exclude(pk=term.pk).update(is_current=False)

            for field, value in cleaned.items():
                setattr(term, field, value)
            term.save()

            if cleaned.get('has_holiday_studies'):
                term.holiday_study_classes.set(holiday_class_ids)
            else:
                term.holiday_study_classes.clear()

    except Exception as exc:
        messages.error(request, f'Could not update term: {exc}')
        return render(request, f'{_T}form.html', {
            'term':                term,
            'all_classes':         all_classes,
            'selected_class_ids':  selected_class_ids,
            'form_title':          f'Edit — Term {term.name} ({term.academic_year})',
            'action':              'edit',
            'section':             'edit',
            'post':                request.POST,
            'errors':              {},
        })

    messages.success(
        request,
        f'Term {term.name} — {term.academic_year} has been updated.'
    )
    return redirect('academics:term_detail_overview', pk=term.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  4. DELETE TERM
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def term_delete(request, pk):
    """
    Delete a Term.
    GET  — confirmation page showing what will be lost.
    POST — perform deletion with cascade guard.

    Guard: a current term cannot be deleted. Admin must first
    mark another term as current before deleting this one.
    """
    term = get_object_or_404(Term, pk=pk)

    if request.method == 'GET':
        # Build an impact summary so the confirmation page can warn the user
        from fees.models import FeesPayment, SchoolFees, AssessmentFees
        from assessments.models import AssessmentSubject, AssessmentPerformance, AssessmentClass
        from school.models import SchoolEvent, SchoolRequirement

        impact = {
            'fee_structures':       SchoolFees.objects.filter(term=term).count(),
            'payments':             FeesPayment.objects.filter(term=term).count(),
            'assessment_fees':      AssessmentFees.objects.filter(term=term).count(),
            'assessment_subjects':  AssessmentSubject.objects.filter(term=term).count(),
            'performance_reports':  AssessmentPerformance.objects.filter(term=term).count(),
            'class_assessments':    AssessmentClass.objects.filter(term=term).count(),
            'requirements':         SchoolRequirement.objects.filter(term=term).count(),
            'calendar_entries':     term.calendar_entries.count(),
        }
        return render(request, f'{_T}delete_confirm.html', {
            'term':    term,
            'impact':  impact,
            'section': 'delete',
        })

    # ── POST: perform deletion ────────────────────────────────────────────────
    if term.is_current:
        messages.error(
            request,
            f'Term {term.name} ({term.academic_year}) is currently active. '
            f'Please mark another term as current before deleting this one.'
        )
        return redirect('academics:term_detail_overview', pk=term.pk)

    label = f'Term {term.name} — {term.academic_year}'
    try:
        term.delete()
        messages.success(request, f'{label} has been permanently deleted.')
    except Exception as exc:
        messages.error(request, f'Could not delete term: {exc}')

    return redirect('academics:term_list')


# ═══════════════════════════════════════════════════════════════════════════════
#  5. TERM DETAIL — shared loader
# ═══════════════════════════════════════════════════════════════════════════════

def _load_term_base(pk) -> dict:
    """
    Fetched by every detail sub-view.
    Returns the term and the tab navigation context.
    """
    term = get_object_or_404(
        Term.objects.prefetch_related('holiday_study_classes'),
        pk=pk
    )
    return term


DETAIL_SECTIONS = (
    ('overview',        'Overview'),
    ('calendar',        'Calendar'),
    ('admissions',      'Admissions'),
    ('requirements',    'Requirements'),
    ('fees',            'Fees Structure'),
    ('payments',        'Payments'),
    ('assessment_fees', 'Fees Assessment'),
    ('assessments',     'Assessments'),
)


def _base_ctx(term, section: str) -> dict:
    return {
        'term':             term,
        'section':          section,
        'detail_sections':  DETAIL_SECTIONS,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  6. TERM DETAIL — OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def term_detail_overview(request, pk):
    """
    Overview tab: timeline progress, student/teacher counts,
    fees collection snapshot, assessment snapshot, exam window statuses.
    """
    term = _load_term_base(pk)
    stats = get_overview_stats(term)

    context = {
        **_base_ctx(term, 'overview'),
        **stats,
    }
    return render(request, f'{_T}detail/overview.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  7. TERM DETAIL — CALENDAR
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def term_detail_calendar(request, pk):
    """
    Calendar tab: structured term milestones (BOT/MOT/EOT windows,
    closing, holiday studies, reopening) + school events in this term.
    """
    term = _load_term_base(pk)
    stats = get_calendar_stats(term)

    # Optional filter for event type
    event_type_filter = request.GET.get('event_type', '').strip()
    events = stats['events']
    if event_type_filter:
        events = events.filter(event_type=event_type_filter)

    # Paginate events
    paginator = Paginator(events, 15)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    context = {
        **_base_ctx(term, 'calendar'),
        **stats,
        'events':           page_obj.object_list,
        'page_obj':         page_obj,
        'event_type_filter': event_type_filter,
        'event_types': [
            ('academic', 'Academic'), ('exam', 'Examination'),
            ('sports', 'Sports'), ('cultural', 'Cultural'),
            ('religious', 'Religious'), ('holiday', 'Holiday'),
            ('meeting', 'Meeting'), ('trip', 'School Trip'),
            ('graduation', 'Graduation'), ('open_day', 'Open Day'),
        ],
    }
    return render(request, f'{_T}detail/calendar.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  8. TERM DETAIL — ADMISSIONS
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def term_detail_admissions(request, pk):
    """
    Admissions tab: all admission applications for this term's academic year.
    Stats: by status, by class, by gender. Recent 10 applications.
    """
    term  = _load_term_base(pk)
    stats = get_admissions_stats(term)

    # Filter support
    status_filter = request.GET.get('status', '').strip()
    class_filter  = request.GET.get('class', '').strip()
    gender_filter = request.GET.get('gender', '').strip()

    admissions = stats['admissions']
    if status_filter:
        admissions = admissions.filter(status=status_filter)
    if class_filter:
        admissions = admissions.filter(applied_class__level=class_filter)
    if gender_filter:
        admissions = admissions.filter(gender=gender_filter)

    paginator = Paginator(admissions, 20)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    context = {
        **_base_ctx(term, 'admissions'),
        **stats,
        'admissions':     page_obj.object_list,
        'page_obj':       page_obj,
        'status_filter':  status_filter,
        'class_filter':   class_filter,
        'gender_filter':  gender_filter,
        'status_choices': [
            ('pending', 'Pending'), ('shortlisted', 'Shortlisted'),
            ('approved', 'Approved'), ('rejected', 'Rejected'),
            ('waitlisted', 'Waitlisted'), ('enrolled', 'Enrolled'),
        ],
        'all_classes': get_all_classes(),
    }
    return render(request, f'{_T}detail/admissions.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  9. TERM DETAIL — SCHOOL REQUIREMENTS
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def term_detail_requirements(request, pk):
    """
    Requirements tab: scholastic requirements published for this term.
    Stats: by category, compulsory vs optional, published vs draft.
    """
    term  = _load_term_base(pk)
    stats = get_requirements_stats(term)

    category_filter   = request.GET.get('category', '').strip()
    published_filter  = request.GET.get('published', '').strip()

    requirements = stats['requirements']
    if category_filter:
        requirements = requirements.filter(category=category_filter)
    if published_filter in ('1', '0'):
        requirements = requirements.filter(is_published=(published_filter == '1'))

    paginator = Paginator(requirements, 20)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    context = {
        **_base_ctx(term, 'requirements'),
        **stats,
        'requirements':     page_obj.object_list,
        'page_obj':         page_obj,
        'category_filter':  category_filter,
        'published_filter': published_filter,
        'category_choices': [
            ('stationery', 'Stationery'), ('uniform', 'Uniform'),
            ('scholastic', 'Scholastic'), ('sports', 'Sports/P.E.'),
            ('equipment', 'Equipment'), ('other', 'Other'),
        ],
    }
    return render(request, f'{_T}detail/requirements.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  10. TERM DETAIL — SCHOOL FEES STRUCTURE
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def term_detail_fees(request, pk):
    """
    Fees Structure tab: all SchoolFees records for this term.
    Stats: total expected, by fee type, by class, compulsory total.
    """
    term  = _load_term_base(pk)
    stats = get_fees_stats(term)

    fees_type_filter = request.GET.get('fees_type', '').strip()
    class_filter     = request.GET.get('class', '').strip()

    fees = stats['fees']
    if fees_type_filter:
        fees = fees.filter(fees_type=fees_type_filter)
    if class_filter:
        fees = fees.filter(school_class__level=class_filter)

    paginator = Paginator(fees, 20)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    context = {
        **_base_ctx(term, 'fees'),
        **stats,
        'fees':             page_obj.object_list,
        'page_obj':         page_obj,
        'fees_type_filter': fees_type_filter,
        'class_filter':     class_filter,
        'fees_type_choices': [
            ('tuition', 'Tuition'), ('development', 'Development'),
            ('activity', 'Activity'), ('lunch', 'Lunch'),
            ('transport', 'Transport'), ('uniform', 'Uniform'),
            ('boarding', 'Boarding'), ('pta', 'PTA'),
            ('exam', 'Exam'), ('admission', 'Admission/Registration'),
            ('other', 'Other'),
        ],
        'all_classes': get_all_classes(),
    }
    return render(request, f'{_T}detail/fees.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  11. TERM DETAIL — FEES PAYMENTS
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def term_detail_payments(request, pk):
    """
    Payments tab: all actual fee payments recorded for this term.
    Stats: total collected by method, by class, daily trend, recent payments.
    Search by student name or receipt number.
    """
    term  = _load_term_base(pk)
    stats = get_payments_stats(term)

    # ── Search ────────────────────────────────────────────────────────────────
    search        = request.GET.get('q', '').strip()
    method_filter = request.GET.get('method', '').strip()
    status_filter = request.GET.get('status', '').strip()
    class_filter  = request.GET.get('class', '').strip()

    payments = stats['payments']

    if search:
        payments = payments.filter(
            Q(receipt_number__icontains=search)            |
            Q(student__first_name__icontains=search)      |
            Q(student__last_name__icontains=search)       |
            Q(student__student_id__icontains=search)      |
            Q(mobile_ref__icontains=search)               |
            Q(bank_ref__icontains=search)
        )
    if method_filter:
        payments = payments.filter(payment_method=method_filter)
    if status_filter:
        payments = payments.filter(status=status_filter)
    if class_filter:
        payments = payments.filter(student__current_class__level=class_filter)

    payments = payments.order_by('-payment_date', '-created_at')
    paginator = Paginator(payments, 25)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    from django.db.models import Q

    context = {
        **_base_ctx(term, 'payments'),
        **stats,
        'payments':         page_obj.object_list,
        'page_obj':         page_obj,
        'search':           search,
        'method_filter':    method_filter,
        'status_filter':    status_filter,
        'class_filter':     class_filter,
        'method_choices': [
            ('cash', 'Cash'), ('mtn_momo', 'MTN MoMo'),
            ('airtel_money', 'Airtel Money'), ('bank', 'Bank'),
            ('cheque', 'Cheque'), ('pesapal', 'PesaPal'), ('other', 'Other'),
        ],
        'all_classes': get_all_classes(),
    }
    return render(request, f'{_T}detail/payments.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  12. TERM DETAIL — ASSESSMENT FEES
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def term_detail_assessment_fees(request, pk):
    """
    Assessment Fees tab: per-student fee assessment statements for this term.
    Stats: cleared vs outstanding, total balance, by class, defaulters list.
    """
    term  = _load_term_base(pk)
    stats = get_assessment_fees_stats(term)

    # ── Filters ───────────────────────────────────────────────────────────────
    search       = request.GET.get('q', '').strip()
    class_filter = request.GET.get('class', '').strip()
    cleared_filter = request.GET.get('cleared', '').strip()

    assessments = stats['assessments']

    if search:
        from django.db.models import Q
        assessments = assessments.filter(
            Q(student__first_name__icontains=search) |
            Q(student__last_name__icontains=search)  |
            Q(student__student_id__icontains=search)
        )
    if class_filter:
        assessments = assessments.filter(student__current_class__level=class_filter)
    if cleared_filter in ('1', '0'):
        assessments = assessments.filter(is_cleared=(cleared_filter == '1'))

    assessments = assessments.order_by('-balance', 'student__last_name')
    paginator   = Paginator(assessments, 25)
    page_obj    = paginator.get_page(request.GET.get('page', 1))

    context = {
        **_base_ctx(term, 'assessment_fees'),
        **stats,
        'assessments':    page_obj.object_list,
        'page_obj':       page_obj,
        'search':         search,
        'class_filter':   class_filter,
        'cleared_filter': cleared_filter,
        'all_classes':    get_all_classes(),
    }
    return render(request, f'{_T}detail/assessment_fees.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  13. TERM DETAIL — ASSESSMENTS
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def term_detail_assessments(request, pk):
    """
    Assessments tab: academic performance for this term.
    Stats: class summaries (avg, pass rate, top student),
    subject averages (BOT/MOT/EOT), division distribution,
    promotion rate.
    """
    term  = _load_term_base(pk)
    stats = get_assessments_stats(term)

    # ── Filters ───────────────────────────────────────────────────────────────
    exam_type_filter = request.GET.get('exam_type', 'eot').strip()
    class_filter     = request.GET.get('class', '').strip()

    from assessments.models import AssessmentPerformance
    from django.db.models import Q

    perf_qs = AssessmentPerformance.objects.filter(assessment__term=term).select_related(
        'student', 'school_class'
    )
    if exam_type_filter:
        perf_qs = perf_qs.filter(assessment__assessment_type=exam_type_filter)
    if class_filter:
        perf_qs = perf_qs.filter(school_class__level=class_filter)

    perf_qs = perf_qs.order_by('marks_obtained', 'student__last_name')
    paginator = Paginator(perf_qs, 30)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    context = {
        **_base_ctx(term, 'assessments'),
        **stats,
        'performances':      page_obj.object_list,
        'page_obj':          page_obj,
        'exam_type_filter':  exam_type_filter,
        'class_filter':      class_filter,
        'exam_type_choices': [
            ('bot', 'Beginning of Term (BOT)'),
            ('mot', 'Middle of Term (MOT)'),
            ('eot', 'End of Term (EOT)'),
            ('mock', 'Mock Exam'),
            ('ple', 'PLE / Prelims'),
        ],
        'all_classes': get_all_classes(),
    }
    return render(request, f'{_T}detail/assessments.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  14. MARK TERM AS CURRENT  (quick action, POST only)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def term_set_current(request, pk):
    """
    Quick POST-only action to mark a term as the current active term.
    Deactivates all other terms automatically.
    Only accessible by admin / head teacher.
    """
    if request.method != 'POST':
        messages.warning(request, 'Invalid request method.')
        return redirect('academics:term_list')

    if not request.user.role in ('admin', 'head_teacher'):
        messages.error(request, 'You do not have permission to change the active term.')
        return redirect('academics:term_list')

    term = get_object_or_404(Term, pk=pk)
    set_current_term(term)
    messages.success(
        request,
        f'Term {term.name} — {term.academic_year} is now set as the current active term.'
    )
    return redirect('academics:term_detail_overview', pk=term.pk)
