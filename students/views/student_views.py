# students/views/student_views.py
# ─────────────────────────────────────────────────────────────────────────────
# All Student views.
#
# DIRECT CREATE FLOW  (3 steps — no admission required)
#   student_create_step1   — student details     (GET/POST → session → step2)
#   student_create_step2   — parent details      (GET/POST → session → step3)
#   student_create_step3   — confirm + create    (GET/POST → DB → detail)
#
# STANDARD VIEWS
#   student_list           — paginated list with stats + filters
#   student_detail         — full analysis page
#   student_toggle_active  — POST-only: activate / deactivate
#
# Rules:
#   - Function-based views only        - No Django Forms / forms.py
#   - No Class-based Views             - No JSON responses
#   - Manual validation via utils      - login_required on every view
#   - django.contrib.messages          - transaction.atomic() on all saves
# ─────────────────────────────────────────────────────────────────────────────

from datetime import date

from django.contrib import messages
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from academics.models import SchoolClass,SchoolSupportedClasses
from students.models import Student, StudentParentRelationship
from students.utils.admission_utils import (
    RELATIONSHIP_CHOICES,
    generate_access_token,
)
from students.utils.student_utils import (
    create_student_directly,
    get_student_detail_stats,
    get_student_list_stats,
    session_clear_direct_create,
    session_get_direct_parents_data,
    session_get_direct_student_data,
    session_set_direct_parents_data,
    session_set_direct_student_data,
    suggest_student_id,
    validate_direct_confirm_step,
    validate_direct_parents_step,
    validate_direct_student_step,
)
from permissions.decorators import has_permission

_T = 'students/'

_GENDER_CHOICES = [('male', 'Male'), ('female', 'Female')]
_BLOOD_GROUPS   = ['A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-']
_CLASS_LEVEL_CHOICES = [
    ('baby', 'Baby Class'), ('middle', 'Middle Class'), ('top', 'Top Class'),
    ('p1', 'P1'), ('p2', 'P2'), ('p3', 'P3'), ('p4', 'P4'),
    ('p5', 'P5'), ('p6', 'P6'), ('p7', 'P7'),
]


def _get_class_lookups():
    return SchoolSupportedClasses.objects.order_by('supported_class__section')


def _progress_ctx(current_step: int) -> dict:
    return {'current_step': current_step, 'total_steps': 3}


# ═══════════════════════════════════════════════════════════════════════════════
#  DIRECT CREATE — STEP 1: STUDENT DETAILS
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('enrol_student', action='create')
def student_create_step1(request):
    """
    Step 1 of the 3-step direct student creation flow.

    Collects the full Student model field set (richer than the admission form):
    includes health fields, blood group, secondary guardian, village, etc.

    GET  — Blank form; student_id auto-suggested.
    POST — Validate; session cleaned data; redirect to Step 2.
    """
    all_classes  = _get_class_lookups()
    suggested_id = suggest_student_id()
    today_str    = date.today().strftime('%Y-%m-%d')
    current_year = str(date.today().year)
    existing     = session_get_direct_student_data(request)

    if request.method == 'GET':
        return render(request, f'{_T}create_step1.html', {
            'page_title':     'Enrol Student — Step 1: Student Details',
            'post':           existing or {},
            'errors':         {},
            'all_classes':    all_classes,
            'gender_choices': _GENDER_CHOICES,
            'blood_groups':   _BLOOD_GROUPS,
            'suggested_id':   suggested_id,
            'today_str':      today_str,
            'current_year':   current_year,
            **_progress_ctx(1),
        })

    cleaned, errors = validate_direct_student_step(request.POST)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}create_step1.html', {
            'page_title':     'Enrol Student — Step 1: Student Details',
            'post':           request.POST,
            'errors':         errors,
            'all_classes':    all_classes,
            'gender_choices': _GENDER_CHOICES,
            'blood_groups':   _BLOOD_GROUPS,
            'suggested_id':   suggested_id,
            'today_str':      today_str,
            'current_year':   current_year,
            **_progress_ctx(1),
        })

    session_set_direct_student_data(request, cleaned)
    return redirect('students:student_create_step2')


# ═══════════════════════════════════════════════════════════════════════════════
#  DIRECT CREATE — STEP 2: PARENT DETAILS
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('enrol_student', action='create')
def student_create_step2(request):
    
    
    """
    Step 2 — Multi-parent details (always new-parent mode for direct creation).

    GET  — Multi-parent form using _parent_block.html partial.
    POST — Validate all parent blocks; session the list; redirect to Step 3.
    """
    student_data = session_get_direct_student_data(request)
    if not student_data:
        messages.warning(request, 'Session expired. Please start again.')
        return redirect('students:student_create_step1')

    existing_parents = session_get_direct_parents_data(request)

    if request.method == 'GET':
        return render(request, f'{_T}create_step2.html', {
            'page_title':          'Enrol Student — Step 2: Parent Details',
            'student_data':        student_data,
            'relationship_choices': RELATIONSHIP_CHOICES,
            'existing_parents':    existing_parents,
            'post':                {},
            'errors':              {},
            **_progress_ctx(2),
        })

    parents_list, errors = validate_direct_parents_step(request.POST)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}create_step2.html', {
            'page_title':          'Enrol Student — Step 2: Parent Details',
            'student_data':        student_data,
            'relationship_choices': RELATIONSHIP_CHOICES,
            'existing_parents':    existing_parents,
            'post':                request.POST,
            'errors':              errors,
            **_progress_ctx(2),
        })

    session_set_direct_parents_data(request, parents_list)
    return redirect('students:student_create_step3')


# ═══════════════════════════════════════════════════════════════════════════════
#  DIRECT CREATE — STEP 3: CONFIRM + CREATE
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('enrol_student', action='create')
def student_create_step3(request):
    """
    Step 3 — Review, enter password, and create all objects atomically:
        Student + CustomUser(s) + ParentProfile(s) + StudentParentRelationship(s)

    All records are created active immediately (no pending/verify phase).

    GET  — Read-only review of session data.
    POST — Authenticate password; call create_student_directly(); clear session;
           redirect to student_detail.
    """
    student_data = session_get_direct_student_data(request)
    parents_data = session_get_direct_parents_data(request)

    if not student_data or not parents_data:
        messages.warning(request, 'Session expired or incomplete. Please start again.')
        return redirect('students:student_create_step1')

    # Resolve class name for display
    applied_class = None
    if student_data.get('current_class_id'):
        try:
            applied_class = SchoolSupportedClasses.objects.get(
                pk=student_data['current_class_id']
            )
        except SchoolSupportedClasses.DoesNotExist:
            pass

    if request.method == 'GET':
        return render(request, f'{_T}create_step3.html', {
            'page_title':    'Enrol Student — Step 3: Confirm',
            'student_data':  student_data,
            'parents_data':  parents_data,
            'applied_class': applied_class,
            'errors':        {},
            **_progress_ctx(3),
        })

    cleaned, errors = validate_direct_confirm_step(request.POST)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}create_step3.html', {
            'page_title':    'Enrol Student — Step 3: Confirm',
            'student_data':  student_data,
            'parents_data':  parents_data,
            'applied_class': applied_class,
            'errors':        errors,
            **_progress_ctx(3),
        })

    # Authenticate the submitting staff member
    user = authenticate(
        request,
        username=request.user.get_username(),
        password=cleaned['password'],
    )
    if user is None:
        messages.error(request, 'Incorrect password. No records have been created.')
        return render(request, f'{_T}create_step3.html', {
            'page_title':    'Enrol Student — Step 3: Confirm',
            'student_data':  student_data,
            'parents_data':  parents_data,
            'applied_class': applied_class,
            'errors':        {'confirm_password': 'Incorrect password.'},
            **_progress_ctx(3),
        })

    try:
        with transaction.atomic():
            result = create_student_directly(
                student_data = student_data,
                parents_data = parents_data,
                created_by   = request.user,
            )
    except Exception as exc:
        messages.error(request, f'Could not create student: {exc}')
        return redirect('students:student_create_step3')

    session_clear_direct_create(request)

    student      = result['student']
    access_token = result['access_token']

    # Store token in session for the detail page to display once
    request.session['new_student_token'] = access_token
    request.session['new_student_pk']    = student.pk
    request.session.modified = True

    messages.success(
        request,
        f'Student {student.student_id} — {student.full_name} enrolled successfully. '
        f'{len(result["parent_results"])} parent account(s) created.'
    )
    return redirect('students:student_detail', pk=student.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  STUDENT LIST
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('students_list', action='read')
def student_list(request):
    """
    All active students with stats and filters.

    Filters (GET):
        ?q=       name / student_id search
        ?class=   class level
        ?section= nursery | primary
        ?gender=  male | female
        ?active=  1 | 0
        ?special= 1  (special needs only)
    """
    qs = Student.objects.select_related('current_class').prefetch_related(
        'parent_relationships__parent__user'
    )

    search         = request.GET.get('q', '').strip()
    class_filter   = request.GET.get('class', '').strip()
    section_filter = request.GET.get('section', '').strip()
    gender_filter  = request.GET.get('gender', '').strip()
    active_filter  = request.GET.get('active', '1').strip()
    special_filter = request.GET.get('special', '').strip()

    if search:
        qs = qs.filter(
            Q(student_id__icontains=search)  |
            Q(first_name__icontains=search)  |
            Q(last_name__icontains=search)   |
            Q(other_names__icontains=search)
        )

    if class_filter:
        qs = qs.filter(current_class__level=class_filter)

    if section_filter:
        qs = qs.filter(current_class__section=section_filter)

    if gender_filter:
        qs = qs.filter(gender=gender_filter)

    if active_filter == '0':
        qs = qs.filter(is_active=False)
    else:
        qs = qs.filter(is_active=True)

    if special_filter == '1':
        qs = qs.filter(is_special_needs=True)

    qs = qs.order_by('current_class__supported_class__section',
                     'last_name', 'first_name')

    paginator = Paginator(qs, 25)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    stats = get_student_list_stats()

    context = {
        'students':            page_obj.object_list,
        'page_obj':            page_obj,
        'search':              search,
        'class_filter':        class_filter,
        'section_filter':      section_filter,
        'gender_filter':       gender_filter,
        'active_filter':       active_filter,
        'special_filter':      special_filter,
        'gender_choices':      _GENDER_CHOICES,
        'class_level_choices': _CLASS_LEVEL_CHOICES,
        'page_title':          'Students',
        **stats,
    }
    return render(request, f'{_T}student_list.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  STUDENT DETAIL — FULL ANALYSIS PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('student_details', action='read')
def student_detail(request, pk):
    """
    Full student analysis page.

    Sections:
        - Identity + bio (left)
        - Parents / relationships
        - Fees: current term fee structure, current term balance,
                lifetime totals, all assessment statements, recent payments
        - Assessments: performance by term, subjects, marks
        - Admission record link (if applicable)

    Also reads and clears the one-time new_student_token from the session
    so the access token is shown once immediately after direct creation.
    """
    student = get_object_or_404(
        Student.objects.select_related(
            'current_class', 'admission'
        ),
        pk=pk,
    )

    stats = get_student_detail_stats(student)

    # One-time token display (set by student_create_step3 or verify_step3)
    new_token = None
    if request.session.get('new_student_pk') == student.pk:
        new_token = request.session.pop('new_student_token', None)
        request.session.pop('new_student_pk', None)
        request.session.modified = True

    context = {
        'student':    student,
        'page_title': f'{student.student_id} — {student.full_name}',
        'new_token':  new_token,
        **stats,
    }
    return render(request, f'{_T}student_detail.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  TOGGLE ACTIVE  (POST-only)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('activate_deactivate_student', action='toggle')
def student_toggle_active(request, pk):
    """POST-only: flip is_active on a student."""
    if request.method != 'POST':
        messages.warning(request, 'Invalid request method.')
        return redirect('students:student_list')

    student = get_object_or_404(Student, pk=pk)
    student.is_active = not student.is_active
    student.save(update_fields=['is_active'])

    state = 'activated' if student.is_active else 'deactivated'
    messages.success(
        request,
        f'Student {student.student_id} — {student.full_name} has been {state}.'
    )

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    return redirect(next_url or 'students:student_detail', pk=student.pk) \
        if not next_url else redirect(next_url)







# Add these imports at the top of student_views.py
from decimal import Decimal
from academics.models import Term
from fees.models import (
    SchoolFees, FeesPayment, StudentFeesPaymentsStatus,
    SchoolScholasticRequirements, StudentScholasticRequirementStatus,
    ScholasticRequirementPayment,
)
from assessments.models import AssessmentPerformance, Assessment
from students.models import StudentClassPromotion




# ═══════════════════════════════════════════════════════════════════════════════
#  ADMIN — STUDENT ACADEMIC HISTORY (class → term → fees/scholastic/performance)
# ═══════════════════════════════════════════════════════════════════════════════

def _admin_get_student_classes(student):
    """Collect every class the student has appeared in, oldest first."""
    promotions = StudentClassPromotion.objects.filter(
        student=student,
    ).select_related(
        'previous_class', 'current_class', 'upcoming_class', 'academic_year'
    ).order_by('academic_year')

    seen_ids = set()
    classes  = []
    for p in promotions:
        for cls in [p.previous_class, p.current_class, p.upcoming_class]:
            if cls is not None and cls.pk not in seen_ids:
                seen_ids.add(cls.pk)
                classes.append(cls)

    if not classes and student.current_class:
        classes.append(student.current_class)

    return classes


@login_required
@has_permission('view_student_academic_history', action='read')
def admin_student_history(request, pk):
    """Class cards for this student — entry point into the history drill-down."""
    student       = get_object_or_404(Student, pk=pk)
    class_list    = _admin_get_student_classes(student)
    current_class = student.current_class

    return render(request, 'students/details/admin_student_history.html', {
        'student':       student,
        'current_class': current_class,
        'class_list':    class_list,
        'page_title':    f'{student.full_name} — Class History',
    })


@login_required
@has_permission('view_history_by_term', action='read')
def admin_student_class_terms(request, pk, class_id):
    """Term cards for a given class."""
    student      = get_object_or_404(Student, pk=pk)
    school_class = get_object_or_404(SchoolSupportedClasses, pk=class_id)

    fees_term_ids = SchoolFees.objects.filter(
        affected_school_class__school_class=school_class,
        is_active=True,
    ).values_list('term_id', flat=True).distinct()

    scholastic_term_ids = SchoolScholasticRequirements.objects.filter(
        assigned_classes__school_class=school_class,
        is_active=True,
    ).values_list('term_id', flat=True).distinct()

    all_term_ids = set(list(fees_term_ids) + list(scholastic_term_ids))
    terms = Term.objects.filter(
        pk__in=all_term_ids,
    ).order_by('-is_active', '-start_date')

    terms_data = []
    for term in terms:
        fees_qs = SchoolFees.objects.filter(
            affected_school_class__school_class=school_class,
            term=term, is_active=True,
        ).distinct()

        statuses = StudentFeesPaymentsStatus.objects.filter(
            student=student, school_fees__in=fees_qs,
        )

        total_fees    = sum(f.amount for f in fees_qs)
        total_paid    = sum(s.amount_paid for s in statuses)
        total_balance = total_fees - total_paid
        paid_count    = statuses.filter(fully_paid=True).count()

        scholastic_total = SchoolScholasticRequirements.objects.filter(
            assigned_classes__school_class=school_class,
            term=term, is_active=True,
        ).distinct().count()

        scholastic_met = StudentScholasticRequirementStatus.objects.filter(
            student=student,
            requirement__assigned_classes__school_class=school_class,
            requirement__term=term,
            fully_met=True,
        ).count()

        terms_data.append({
            'term':             term,
            'total_fees':       total_fees,
            'total_paid':       total_paid,
            'total_balance':    total_balance,
            'fees_items':       fees_qs.count(),
            'paid_count':       paid_count,
            'scholastic_total': scholastic_total,
            'scholastic_met':   scholastic_met,
        })

    return render(request, 'students/details/admin_student_class_terms.html', {
        'student':       student,
        'school_class':  school_class,
        'current_class': student.current_class,
        'terms_data':    terms_data,
        'page_title':    f'{student.full_name} — {school_class}',
    })


@login_required
@has_permission('view_history_by_term', action='read')
def admin_student_class_term_overview(request, pk, class_id, term_id):
    """Section mini-cards (Fees, Scholastic, Performance) for one term."""
    student      = get_object_or_404(Student, pk=pk)
    school_class = get_object_or_404(SchoolSupportedClasses, pk=class_id)
    term         = get_object_or_404(Term, pk=term_id)

    # Fees summary
    fees_qs = SchoolFees.objects.filter(
        affected_school_class__school_class=school_class,
        term=term, is_active=True,
    ).distinct()
    statuses      = StudentFeesPaymentsStatus.objects.filter(student=student, school_fees__in=fees_qs)
    total_fees    = sum(f.amount for f in fees_qs)
    total_paid    = sum(s.amount_paid for s in statuses)
    total_balance = total_fees - total_paid
    fees_summary  = {
        'total_fees':       total_fees,
        'total_paid':       total_paid,
        'total_balance':    total_balance,
        'fully_paid_count': statuses.filter(fully_paid=True).count(),
        'total_items':      fees_qs.count(),
    }

    # Scholastic summary
    scholastic_qs  = SchoolScholasticRequirements.objects.filter(
        assigned_classes__school_class=school_class, term=term, is_active=True,
    ).distinct()
    scholastic_met = StudentScholasticRequirementStatus.objects.filter(
        student=student, requirement__in=scholastic_qs, fully_met=True,
    ).count()
    scholastic_summary = {'total': scholastic_qs.count(), 'met': scholastic_met}

    # Performance summary
    performance_count = AssessmentPerformance.objects.filter(
        student=student, assessment__term=term,
    ).count()

    return render(request, 'students/details/admin_student_class_term_overview.html', {
        'student':             student,
        'school_class':        school_class,
        'current_class':       student.current_class,
        'term':                term,
        'fees_summary':        fees_summary,
        'scholastic_summary':  scholastic_summary,
        'performance_count':   performance_count,
        'page_title':          f'{student.full_name} — {school_class} / {term}',
    })


@login_required
@has_permission('view_history_fees', action='read')
def admin_student_class_term_fees(request, pk, class_id, term_id):
    """Fees structure table for one class + term."""
    student      = get_object_or_404(Student, pk=pk)
    school_class = get_object_or_404(SchoolSupportedClasses, pk=class_id)
    term         = get_object_or_404(Term, pk=term_id)

    fees_qs = SchoolFees.objects.filter(
        affected_school_class__school_class=school_class,
        term=term, is_active=True,
    ).select_related('term').distinct().order_by('fees_type')

    total_fees_amount = Decimal('0')
    total_paid        = Decimal('0')
    total_balance     = Decimal('0')
    fully_paid_count  = 0
    fees_structure_data = []

    for fee in fees_qs:
        status = StudentFeesPaymentsStatus.objects.filter(
            student=student, school_fees=fee,
        ).first()

        raw_txns = FeesPayment.objects.filter(
            student=student, school_fees=fee,
        ).order_by('payment_date', 'created_at')

        running       = fee.amount
        enriched_txns = []
        for txn in raw_txns:
            prev_bal = running
            running  = running - txn.amount
            enriched_txns.append({
                'txn':             txn,
                'prev_balance':    prev_bal,
                'current_balance': max(running, Decimal('0')),
            })

        fees_structure_data.append({
            'fee': fee, 'status': status, 'transactions': enriched_txns,
        })

        total_fees_amount += fee.amount
        if status:
            total_paid    += status.amount_paid
            total_balance += status.amount_balance
            if status.fully_paid:
                fully_paid_count += 1
        else:
            total_balance += fee.amount

    fees_stats = {
        'total_fees':       total_fees_amount,
        'total_paid':       total_paid,
        'total_balance':    total_balance,
        'fully_paid_count': fully_paid_count,
        'total_items':      len(fees_structure_data),
    }

    return render(request, 'students/details/admin_student_class_term_fees.html', {
        'student':              student,
        'school_class':         school_class,
        'current_class':        student.current_class,
        'term':                 term,
        'fees_structure_data':  fees_structure_data,
        'fees_stats':           fees_stats,
        'page_title':           f'School Fees — {school_class} / {term}',
    })


@login_required
@has_permission('view_history_scholastic', action='read')
def admin_student_class_term_scholastic(request, pk, class_id, term_id):
    """Scholastic requirements table for one class + term."""
    student      = get_object_or_404(Student, pk=pk)
    school_class = get_object_or_404(SchoolSupportedClasses, pk=class_id)
    term         = get_object_or_404(Term, pk=term_id)

    scholastic_qs = SchoolScholasticRequirements.objects.filter(
        assigned_classes__school_class=school_class,
        term=term, is_active=True,
    ).distinct().order_by('item_name')

    total_items      = 0
    fully_met_count  = 0
    total_cash_value = Decimal('0')
    total_cash_paid  = Decimal('0')
    scholastic_data  = []

    for req in scholastic_qs:
        status = StudentScholasticRequirementStatus.objects.filter(
            student=student, requirement=req,
        ).first()

        transactions = ScholasticRequirementPayment.objects.filter(
            student=student, requirement=req,
        ).order_by('payment_date', 'created_at')

        enriched_txns = []
        for txn in transactions:
            if txn.brought_item and txn.brought_cash:
                txn_type = 'Mixed'
            elif txn.brought_item:
                txn_type = 'Items'
            else:
                txn_type = 'Cash'
            enriched_txns.append({'txn': txn, 'txn_type': txn_type})

        scholastic_data.append({
            'req': req, 'status': status, 'transactions': enriched_txns,
        })

        total_items      += 1
        total_cash_value += req.monetary_value
        if status:
            total_cash_paid += status.amount_paid_ugx
            if status.fully_met:
                fully_met_count += 1

    scholastic_stats = {
        'total_items':      total_items,
        'fully_met_count':  fully_met_count,
        'total_cash_value': total_cash_value,
        'total_cash_paid':  total_cash_paid,
    }

    return render(request, 'students/details/admin_student_class_term_scholastic.html', {
        'student':           student,
        'school_class':      school_class,
        'current_class':     student.current_class,
        'term':              term,
        'scholastic_data':   scholastic_data,
        'scholastic_stats':  scholastic_stats,
        'page_title':        f'Scholastic Items — {school_class} / {term}',
    })


@login_required
@has_permission('view_history_performance', action='read')
def admin_student_class_term_performance(request, pk, class_id, term_id):
    """Assessment performance table for one class + term."""
    from assessments.models import AssessmentSubject, AssessmentTotalMark

    student      = get_object_or_404(Student, pk=pk)
    school_class = get_object_or_404(SchoolSupportedClasses, pk=class_id)
    term         = get_object_or_404(Term, pk=term_id)

    performance_qs = AssessmentPerformance.objects.filter(
        student=student,
        assessment__term=term,
        school_class=school_class,
    ).select_related(
        'assessment',
        'assessment__term',
        'subject',
    ).order_by('subject__name', 'assessment__date_given')

    performance_data = []

    for perf in performance_qs:
        # Pass mark lives on AssessmentSubject, not Assessment
        assessment_subject = AssessmentSubject.objects.filter(
            assessment=perf.assessment,
            subject=perf.subject,
            assessment_class=school_class,
        ).first()
        pass_mark = assessment_subject.passmark if assessment_subject else None

        # Total mark lives on AssessmentTotalMark
        total_mark_obj = AssessmentTotalMark.objects.filter(
            assessment=perf.assessment,
            subject=assessment_subject,
        ).first() if assessment_subject else None
        total_mark = total_mark_obj.total_mark if total_mark_obj else None

        # Pass / fail
        if pass_mark is not None and perf.marks_obtained is not None:
            passed = perf.marks_obtained >= pass_mark
        else:
            passed = None

        # Percentage
        if total_mark and total_mark > 0:
            percentage = round((perf.marks_obtained / total_mark) * 100, 1)
        else:
            percentage = None

        performance_data.append({
            'assessment': perf.assessment,
            'subject':    perf.subject,
            'obtained':   perf.marks_obtained,
            'total':      total_mark,
            'pass_mark':  pass_mark,
            'passed':     passed,
            'percentage': percentage,
            'comment':    perf.comment,
        })

    scored         = [r for r in performance_data if r['percentage'] is not None]
    passed_count   = sum(1 for r in performance_data if r['passed'] is True)
    avg_percentage = round(sum(r['percentage'] for r in scored) / len(scored), 1) if scored else 0

    performance_stats = {
        'total_assessments':  len(performance_data),
        'passed_count':       passed_count,
        'average_percentage': avg_percentage,
    }

    return render(request, 'students/details/admin_student_class_term_performance.html', {
        'student':           student,
        'school_class':      school_class,
        'current_class':     student.current_class,
        'term':              term,
        'performance_data':  performance_data,
        'performance_stats': performance_stats,
        'page_title':        f'Performance — {school_class} / {term}',
    })