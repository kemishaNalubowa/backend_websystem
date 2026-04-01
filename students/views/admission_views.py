# students/views/admission_views.py
# ─────────────────────────────────────────────────────────────────────────────
# All Admission views.
#
# ADD FLOW  (3 steps — sessioned, confirmed with password)
#   admission_add_step1   — student details   (GET/POST → session → step2)
#   admission_add_step2   — parent details    (GET/POST → session → step3)
#   admission_add_step3   — confirm + save    (GET/POST → DB → detail)
#
# STANDARD VIEWS
#   admission_list          — list + stats + filters
#   admission_detail        — full single application page
#   admission_delete        — confirm + perform deletion
#   admission_update_status — move to a new status
#   admission_edit_parents  — edit parents_data JSON on an existing admission
#
# VERIFY FLOW  (4 steps — approved admissions only)
#   admission_verify_step1  — review / update admission data + mark verified
#   admission_verify_step2  — create Student object
#   admission_verify_step3  — create parent user(s) + profile(s)
#   admission_verify_step4  — create StudentParentRelationship(s) + summary
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
from django.utils import timezone

from academics.models import SchoolClass, Term
from students.models import Admission, Student, StudentParentRelationship
from students.utils.admission_utils import (
    RELATIONSHIP_CHOICES,
    STATUS_LABELS,
    STATUS_TRANSITIONS,
    create_parent_objects,
    create_student_from_admission,
    generate_admission_number,
    get_admission_detail_stats,
    get_admission_list_stats,
    get_or_create_student_token,
    link_existing_parent,
    session_clear_admission,
    session_get_parents_data,
    session_get_student_data,
    session_set_parents_data,
    session_set_student_data,
    suggest_student_id,
    validate_admission_confirm_step,
    validate_admission_parents_step,
    validate_admission_student_step,
    validate_status_update,
    validate_verify_student_step,
)

_T               = 'students/admissions/'
_STATUS_CHOICES  = list(STATUS_LABELS.items())
_GENDER_CHOICES  = [('male', 'Male'), ('female', 'Female')]
_CLASS_LEVEL_CHOICES = [
    ('baby', 'Baby Class'), ('middle', 'Middle Class'), ('top', 'Top Class'),
    ('p1', 'P1'), ('p2', 'P2'), ('p3', 'P3'), ('p4', 'P4'),
    ('p5', 'P5'), ('p6', 'P6'), ('p7', 'P7'),
]


def _get_class_lookups():
    return SchoolClass.objects.filter(is_active=True).order_by('section', 'level', 'stream')


def _progress_ctx(current_step: int) -> dict:
    """Shared flow-progress context for the add flow templates."""
    return {'current_step': current_step, 'total_steps': 3}


def _verify_progress_ctx(current_step: int) -> dict:
    return {'current_step': current_step, 'total_steps': 4}


# ═══════════════════════════════════════════════════════════════════════════════
#  ADD FLOW — STEP 1: STUDENT DETAILS
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def admission_add_step1(request):
    """
    Step 1 of the 3-step admission add flow.

    GET  — Blank student details form.
           Includes checkbox: "Parent already has a student in this school?"
    POST — Validate all student fields.
           Session the cleaned data.
           Redirect to Step 2.
    """
    all_classes = _get_class_lookups()
    existing    = session_get_student_data(request)   # repopulate if navigating back

    if request.method == 'GET':
        return render(request, f'{_T}add_step1.html', {
            'page_title':     'New Admission — Step 1: Student Details',
            'post':           existing or {},
            'errors':         {},
            'all_classes':    all_classes,
            'gender_choices': _GENDER_CHOICES,
            'next_year':      str(date.today().year + 1),
            **_progress_ctx(1),
        })

    cleaned, errors = validate_admission_student_step(request.POST)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}add_step1.html', {
            'page_title':     'New Admission — Step 1: Student Details',
            'post':           request.POST,
            'errors':         errors,
            'all_classes':    all_classes,
            'gender_choices': _GENDER_CHOICES,
            'next_year':      str(date.today().year + 1),
            **_progress_ctx(1),
        })

    session_set_student_data(request, cleaned)
    return redirect('students:admission_add_step2')


# ═══════════════════════════════════════════════════════════════════════════════
#  ADD FLOW — STEP 2: PARENT DETAILS
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def admission_add_step2(request):
    """
    Step 2 of the 3-step admission add flow.

    Reads parent_already_exists flag from the sessioned student data.

    If True:
        Shows a single parent-ID lookup field + relationship selector.
    If False:
        Shows multi-parent form (Add Another Parent button powered by JS counter).

    POST — Validate parent data.
           Session the parents list.
           Redirect to Step 3.
    """
    student_data = session_get_student_data(request)
    if not student_data:
        messages.warning(request, 'Session expired. Please start again.')
        return redirect('students:admission_add_step1')

    parent_already_exists = student_data.get('parent_already_exists', False)
    existing_parents      = session_get_parents_data(request)

    if request.method == 'GET':
        return render(request, f'{_T}add_step2.html', {
            'page_title':             'New Admission — Step 2: Parent Details',
            'student_data':           student_data,
            'parent_already_exists':  parent_already_exists,
            'relationship_choices':   RELATIONSHIP_CHOICES,
            'post':                   {},
            'errors':                 {},
            'existing_parents':       existing_parents,
            **_progress_ctx(2),
        })

    parents_list, errors = validate_admission_parents_step(
        request.POST, parent_already_exists
    )

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}add_step2.html', {
            'page_title':            'New Admission — Step 2: Parent Details',
            'student_data':          student_data,
            'parent_already_exists': parent_already_exists,
            'relationship_choices':  RELATIONSHIP_CHOICES,
            'post':                  request.POST,
            'errors':                errors,
            'existing_parents':      existing_parents,
            **_progress_ctx(2),
        })

    session_set_parents_data(request, parents_list)
    return redirect('students:admission_add_step3')


# ═══════════════════════════════════════════════════════════════════════════════
#  ADD FLOW — STEP 3: CONFIRM + SAVE
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def admission_add_step3(request):
    """
    Step 3 of the 3-step admission add flow.

    GET  — Shows a read-only review of all sessioned data.
           Asks for the submitting staff member's password to confirm.
    POST — Authenticate password.
           Build Admission record from session data.
           Auto-generate admission_number.
           Save inside transaction.atomic().
           Clear session.
           Redirect to admission_detail.
    """
    student_data = session_get_student_data(request)
    parents_data = session_get_parents_data(request)

    if not student_data or not parents_data:
        messages.warning(request, 'Session expired or incomplete. Please start again.')
        return redirect('students:admission_add_step1')

    if request.method == 'GET':
        all_classes = _get_class_lookups()
        applied_class = None
        if student_data.get('applied_class_id'):
            try:
                applied_class = SchoolClass.objects.get(pk=student_data['applied_class_id'])
            except SchoolClass.DoesNotExist:
                pass
        return render(request, f'{_T}add_step3.html', {
            'page_title':    'New Admission — Step 3: Confirm',
            'student_data':  student_data,
            'parents_data':  parents_data,
            'applied_class': applied_class,
            'errors':        {},
            **_progress_ctx(3),
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    cleaned, errors = validate_admission_confirm_step(request.POST)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}add_step3.html', {
            'page_title':   'New Admission — Step 3: Confirm',
            'student_data': student_data,
            'parents_data': parents_data,
            'errors':       errors,
            **_progress_ctx(3),
        })

    # Authenticate the submitting staff member
    user = authenticate(
        request,
        username=request.user.get_username(),
        password=cleaned['password'],
    )
    if user is None:
        messages.error(request, 'Incorrect password. The application has not been saved.')
        return render(request, f'{_T}add_step3.html', {
            'page_title':   'New Admission — Step 3: Confirm',
            'student_data': student_data,
            'parents_data': parents_data,
            'errors':       {'confirm_password': 'Incorrect password.'},
            **_progress_ctx(3),
        })

    try:
        with transaction.atomic():
            adm = Admission()

            # Student fields
            adm.first_name           = student_data['first_name']
            adm.last_name            = student_data['last_name']
            adm.other_names          = student_data.get('other_names', '')
            adm.date_of_birth        = student_data['date_of_birth']
            adm.gender               = student_data['gender']
            adm.nationality          = student_data.get('nationality', 'Ugandan')
            adm.district_of_origin   = student_data.get('district_of_origin', '')
            adm.religion             = student_data.get('religion', '')
            adm.birth_certificate_no = student_data.get('birth_certificate_no', '')
            adm.previous_school      = student_data.get('previous_school', '')
            adm.previous_class       = student_data.get('previous_class', '')
            adm.last_result          = student_data.get('last_result', '')
            adm.academic_year        = student_data['academic_year']

            if student_data.get('applied_class_id'):
                adm.applied_class_id = student_data['applied_class_id']

            # Multi-parent JSON
            adm.parents_data = parents_data

            adm.admission_number = generate_admission_number()
            adm.status           = 'pending'
            adm.reviewed_by      = request.user
            adm.save()

    except Exception as exc:
        messages.error(request, f'Could not save application: {exc}')
        return redirect('students:admission_add_step3')

    session_clear_admission(request)

    messages.success(
        request,
        f'Application submitted — {adm.admission_number}: '
        f'{adm.first_name} {adm.last_name}.'
    )
    return redirect('students:admission_detail', pk=adm.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  ADMISSION LIST
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def admission_list(request):
    """
    All admission applications with statistics and filters.

    Filters (GET):
        ?q=         name / admission number search
        ?status=    pending|shortlisted|approved|rejected|waitlisted|enrolled
        ?verified=  1 | 0
        ?year=      academic_year
        ?class=     applied_class level
        ?section=   nursery | primary
        ?gender=    male | female
        ?interview= upcoming
    """
    today = date.today()
    qs    = Admission.objects.select_related('applied_class', 'reviewed_by', 'student')

    search           = request.GET.get('q', '').strip()
    status_filter    = request.GET.get('status', '').strip()
    verified_filter  = request.GET.get('verified', '').strip()
    year_filter      = request.GET.get('year', '').strip()
    class_filter     = request.GET.get('class', '').strip()
    section_filter   = request.GET.get('section', '').strip()
    gender_filter    = request.GET.get('gender', '').strip()
    interview_filter = request.GET.get('interview', '').strip()

    if search:
        qs = qs.filter(
            Q(admission_number__icontains=search) |
            Q(first_name__icontains=search)       |
            Q(last_name__icontains=search)        |
            Q(other_names__icontains=search)
        )

    if status_filter:
        qs = qs.filter(status=status_filter)

    if verified_filter == '1':
        qs = qs.filter(is_verified=True)
    elif verified_filter == '0':
        qs = qs.filter(is_verified=False)

    if year_filter:
        qs = qs.filter(academic_year=year_filter)

    if class_filter:
        qs = qs.filter(applied_class__level=class_filter)

    if section_filter:
        qs = qs.filter(applied_class__section=section_filter)

    if gender_filter:
        qs = qs.filter(gender=gender_filter)

    if interview_filter == 'upcoming':
        qs = qs.filter(interview_date__gte=today)

    qs = qs.order_by('-application_date')

    paginator = Paginator(qs, 20)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    items = list(page_obj.object_list)
    for item in items:
        item.status_label           = STATUS_LABELS.get(item.status, item.status)
        item.allowed_transitions    = [
            (s, STATUS_LABELS[s]) for s in STATUS_TRANSITIONS.get(item.status, set())
        ]
        item.days_since_application = (today - item.application_date).days
        item.days_until_interview   = (
            (item.interview_date - today).days if item.interview_date else None
        )

    stats = get_admission_list_stats()

    context = {
        'admissions':          items,
        'page_obj':            page_obj,
        'search':              search,
        'status_filter':       status_filter,
        'verified_filter':     verified_filter,
        'year_filter':         year_filter,
        'class_filter':        class_filter,
        'section_filter':      section_filter,
        'gender_filter':       gender_filter,
        'interview_filter':    interview_filter,
        'status_choices':      _STATUS_CHOICES,
        'gender_choices':      _GENDER_CHOICES,
        'class_level_choices': _CLASS_LEVEL_CHOICES,
        'today':               today,
        **stats,
    }
    return render(request, f'{_T}list.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  ADMISSION DETAIL
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def admission_detail(request, pk):
    """
    Full single admission application page.
    Reads parents_data JSON for display.
    Shows verify button when status=approved and not yet verified.
    """
    adm = get_object_or_404(
        Admission.objects.select_related(
            'applied_class', 'reviewed_by', 'verified_by',
            'student', 'student__current_class',
        ),
        pk=pk,
    )
    stats = get_admission_detail_stats(adm)

    context = {
        'admission':  adm,
        'page_title': f'{adm.admission_number} — {adm.first_name} {adm.last_name}',
        **stats,
    }
    return render(request, f'{_T}detail.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  ADMISSION DELETE
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def admission_delete(request, pk):
    """
    GET  — confirmation page.
    POST — delete (blocked if enrolled or verified).
    """
    adm = get_object_or_404(
        Admission.objects.select_related('applied_class', 'student'), pk=pk
    )

    if request.method == 'GET':
        return render(request, f'{_T}delete_confirm.html', {
            'admission':    adm,
            'status_label': STATUS_LABELS.get(adm.status, adm.status),
            'is_enrolled':  adm.status == 'enrolled',
            'is_verified':  adm.is_verified,
        })

    if adm.status == 'enrolled' or adm.is_verified:
        messages.error(
            request,
            f'Application {adm.admission_number} has an enrolled / verified student '
            f'and cannot be deleted.'
        )
        return redirect('students:admission_detail', pk=adm.pk)

    label = f'{adm.admission_number} — {adm.first_name} {adm.last_name}'
    try:
        adm.delete()
        messages.success(request, f'Application "{label}" has been permanently deleted.')
    except Exception as exc:
        messages.error(request, f'Could not delete: {exc}')
        return redirect('students:admission_detail', pk=pk)

    return redirect('students:admission_list')


# ═══════════════════════════════════════════════════════════════════════════════
#  ADMISSION UPDATE STATUS
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def admission_update_status(request, pk):
    """
    GET  — status-update form (pre-selects target status from ?to= param).
    POST — validate transition; save; redirect to detail.
    """
    adm = get_object_or_404(
        Admission.objects.select_related('applied_class'), pk=pk
    )

    target_status = (
        request.POST.get('status') or request.GET.get('to') or ''
    ).strip()

    allowed = [
        (s, STATUS_LABELS[s]) for s in STATUS_TRANSITIONS.get(adm.status, set())
    ]

    if request.method == 'GET':
        if target_status and target_status not in STATUS_TRANSITIONS.get(adm.status, set()):
            messages.error(
                request,
                f'Cannot move from "{STATUS_LABELS[adm.status]}" '
                f'to "{STATUS_LABELS.get(target_status, target_status)}".'
            )
            return redirect('students:admission_detail', pk=adm.pk)

        return render(request, f'{_T}update_status.html', {
            'admission':     adm,
            'target_status': target_status,
            'status_label':  STATUS_LABELS.get(adm.status, adm.status),
            'target_label':  STATUS_LABELS.get(target_status, target_status),
            'allowed':       allowed,
            'post':          {},
            'errors':        {},
        })

    cleaned, errors = validate_status_update(request.POST, adm.status)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}update_status.html', {
            'admission':     adm,
            'target_status': target_status,
            'status_label':  STATUS_LABELS.get(adm.status, adm.status),
            'target_label':  STATUS_LABELS.get(target_status, target_status),
            'allowed':       allowed,
            'post':          request.POST,
            'errors':        errors,
        })

    try:
        with transaction.atomic():
            for field, value in cleaned.items():
                setattr(adm, field, value)
            adm.reviewed_by = request.user
            adm.save()
    except Exception as exc:
        messages.error(request, f'Could not update status: {exc}')
        return redirect('students:admission_detail', pk=adm.pk)

    new_label = STATUS_LABELS.get(cleaned['status'], cleaned['status'])
    messages.success(
        request,
        f'Application {adm.admission_number} moved to "{new_label}".'
    )
    if cleaned['status'] == 'approved':
        messages.info(
            request,
            'Application approved. Use "Verify Admission" to create the student record.'
        )
    return redirect('students:admission_detail', pk=adm.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  EDIT PARENTS DATA
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def admission_edit_parents(request, pk):
    """
    Edit the parents_data JSON on an existing admission (not yet verified).

    GET  — renders the same multi-parent form as Step 2 but pre-populated
           from the existing JSON.
    POST — re-validates and updates parents_data in the DB.
    """
    adm = get_object_or_404(Admission, pk=pk)

    if adm.is_verified:
        messages.warning(
            request,
            f'Admission {adm.admission_number} is already verified and parent '
            f'accounts have been created. Parent data cannot be changed here.'
        )
        return redirect('students:admission_detail', pk=pk)

    parent_already_exists = False   # edit always uses the full form

    if request.method == 'GET':
        return render(request, f'{_T}edit_parents.html', {
            'admission':             adm,
            'page_title':            f'Edit Parents — {adm.admission_number}',
            'parent_already_exists': parent_already_exists,
            'relationship_choices':  RELATIONSHIP_CHOICES,
            'existing_parents':      adm.get_parents_data(),
            'post':                  {},
            'errors':                {},
        })

    parents_list, errors = validate_admission_parents_step(
        request.POST, parent_already_exists
    )

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}edit_parents.html', {
            'admission':             adm,
            'page_title':            f'Edit Parents — {adm.admission_number}',
            'parent_already_exists': parent_already_exists,
            'relationship_choices':  RELATIONSHIP_CHOICES,
            'existing_parents':      adm.get_parents_data(),
            'post':                  request.POST,
            'errors':                errors,
        })

    try:
        with transaction.atomic():
            adm.parents_data = parents_list
            adm.save(update_fields=['parents_data'])
    except Exception as exc:
        messages.error(request, f'Could not update parent data: {exc}')
        return redirect('students:admission_detail', pk=pk)

    messages.success(
        request,
        f'Parent information updated for {adm.admission_number}.'
    )
    return redirect('students:admission_detail', pk=pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  VERIFY FLOW — STEP 1: REVIEW + MARK VERIFIED
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def admission_verify_step1(request, pk):
    """
    Verify flow Step 1.

    Guards: admission must be 'approved' and not yet verified.

    GET  — Read-only review of ALL admission data (student + parents).
           Staff can confirm the data is correct before proceeding.
           Also shows an "Edit Parents" link.
    POST — Mark is_verified=True, set verified_at and verified_by.
           Redirect to Step 2.
    """
    adm = get_object_or_404(
        Admission.objects.select_related('applied_class', 'reviewed_by'),
        pk=pk,
    )

    if adm.status != 'approved':
        messages.error(
            request,
            f'Only approved applications can be verified. '
            f'Current status: "{STATUS_LABELS.get(adm.status, adm.status)}".'
        )
        return redirect('students:admission_detail', pk=pk)

    if adm.is_verified:
        messages.info(
            request,
            f'Admission {adm.admission_number} is already verified. '
            f'Continue from Step 2.'
        )
        return redirect('students:admission_verify_step2', pk=pk)

    parents_list = adm.get_parents_data()

    if request.method == 'GET':
        return render(request, f'{_T}verify_step1.html', {
            'admission':    adm,
            'parents_list': parents_list,
            'page_title':   f'Verify Admission — Step 1: Review',
            **_verify_progress_ctx(1),
        })

    # POST — mark verified
    try:
        with transaction.atomic():
            adm.is_verified  = True
            adm.verified_at  = timezone.now()
            adm.verified_by  = request.user
            adm.save(update_fields=['is_verified', 'verified_at', 'verified_by'])
    except Exception as exc:
        messages.error(request, f'Could not mark as verified: {exc}')
        return redirect('students:admission_detail', pk=pk)

    messages.success(
        request,
        f'Admission {adm.admission_number} marked as verified. Proceed to create the student.'
    )
    return redirect('students:admission_verify_step2', pk=pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  VERIFY FLOW — STEP 2: CREATE STUDENT OBJECT
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def admission_verify_step2(request, pk):
    """
    Verify flow Step 2 — Create the Student record.

    Guards: admission must be verified. If a student already exists → skip.

    GET  — enrolment form: student_id (auto-suggested), class, academic_year,
           date_enrolled.
    POST — validate; create Student; link adm.student; update status → enrolled.
           Redirect to Step 3.
    """
    adm = get_object_or_404(
        Admission.objects.select_related('applied_class', 'student'), pk=pk
    )

    if not adm.is_verified:
        messages.warning(request, 'Please complete Step 1 first.')
        return redirect('students:admission_verify_step1', pk=pk)

    # If student already created, skip to step 3
    if adm.student_id:
        messages.info(request, 'Student already created. Continuing to Step 3.')
        return redirect('students:admission_verify_step3', pk=pk)

    all_classes  = _get_class_lookups()
    suggested_id = suggest_student_id()
    today_str    = date.today().strftime('%Y-%m-%d')
    current_year = str(date.today().year)

    if request.method == 'GET':
        return render(request, f'{_T}verify_step2.html', {
            'admission':     adm,
            'page_title':    f'Verify Admission — Step 2: Create Student',
            'suggested_id':  suggested_id,
            'today_str':     today_str,
            'current_year':  current_year,
            'all_classes':   all_classes,
            'post':          {},
            'errors':        {},
            **_verify_progress_ctx(2),
        })

    cleaned, errors = validate_verify_student_step(request.POST)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}verify_step2.html', {
            'admission':    adm,
            'page_title':   f'Verify Admission — Step 2: Create Student',
            'suggested_id': suggested_id,
            'today_str':    today_str,
            'current_year': current_year,
            'all_classes':  all_classes,
            'post':         request.POST,
            'errors':       errors,
            **_verify_progress_ctx(2),
        })

    try:
        with transaction.atomic():
            student = create_student_from_admission(adm, cleaned)
            adm.student     = student
            adm.status      = 'enrolled'
            adm.reviewed_by = request.user
            adm.save(update_fields=['student', 'status', 'reviewed_by'])
    except Exception as exc:
        messages.error(request, f'Could not create student: {exc}')
        return render(request, f'{_T}verify_step2.html', {
            'admission':    adm,
            'page_title':   f'Verify Admission — Step 2: Create Student',
            'suggested_id': suggested_id,
            'today_str':    today_str,
            'current_year': current_year,
            'all_classes':  all_classes,
            'post':         request.POST,
            'errors':       {},
            **_verify_progress_ctx(2),
        })

    messages.success(
        request,
        f'Student {student.student_id} — {student.full_name} created successfully.'
    )
    return redirect('students:admission_verify_step3', pk=pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  VERIFY FLOW — STEP 3: CREATE PARENT USERS + PROFILES
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def admission_verify_step3(request, pk):
    """
    Verify flow Step 3 — Create parent user + profile for each parent
    in parents_data.

    For existing-parent entries (existing=True):  link_existing_parent()
    For new parent entries    (existing=False): create_parent_objects()

    All parents of the same student share one access_token
    (generated once via get_or_create_student_token).

    GET  — Shows parents_data list with creation status per parent.
    POST — Creates all parent objects in one transaction.
           Redirect to Step 4.
    """
    adm = get_object_or_404(
        Admission.objects.select_related('student'), pk=pk
    )

    if not adm.is_verified or not adm.student_id:
        messages.warning(request, 'Please complete Steps 1 and 2 first.')
        return redirect('students:admission_verify_step1', pk=pk)

    student      = adm.student
    parents_list = adm.get_parents_data()

    # Check if parents are already created (in case of page refresh)
    existing_rels = StudentParentRelationship.objects.filter(
        student=student
    ).select_related('parent', 'parent__user').count()

    if request.method == 'GET':
        return render(request, f'{_T}verify_step3.html', {
            'admission':     adm,
            'student':       student,
            'parents_list':  parents_list,
            'already_done':  existing_rels > 0,
            'page_title':    f'Verify Admission — Step 3: Create Parent Accounts',
            **_verify_progress_ctx(3),
        })

    # Guard: don't double-create if already done
    if existing_rels > 0:
        messages.info(request, 'Parent accounts already created. Continuing to Step 4.')
        return redirect('students:admission_verify_step4', pk=pk)

    created_parents = []
    try:
        with transaction.atomic():
            # Generate one shared token for this student's family
            access_token = get_or_create_student_token(student)

            for i, p_dict in enumerate(parents_list):
                is_primary   = (i == 0)
                relationship = p_dict.get('relationship', 'other')

                if p_dict.get('existing'):
                    profile, rel = link_existing_parent(
                        parent_id_str = p_dict['parent_id'],
                        student       = student,
                        relationship  = relationship,
                        access_token  = access_token,
                        is_primary    = is_primary,
                    )
                    created_parents.append({
                        'full_name':  profile.full_name,
                        'parent_id':  profile.parent_id,
                        'existing':   True,
                    })
                else:
                    user, profile, rel = create_parent_objects(
                        parent_dict  = p_dict,
                        student      = student,
                        relationship = relationship,
                        verified_by  = request.user,
                        access_token = access_token,
                        is_primary   = is_primary,
                    )
                    created_parents.append({
                        'full_name':  profile.full_name,
                        'parent_id':  profile.parent_id,
                        'existing':   False,
                    })

            # Store summary in session for Step 4
            request.session['verify_created_parents'] = created_parents
            request.session['verify_access_token']    = access_token
            request.session.modified = True

    except Exception as exc:
        messages.error(request, f'Could not create parent accounts: {exc}')
        return redirect('students:admission_verify_step3', pk=pk)

    messages.success(
        request,
        f'{len(created_parents)} parent account(s) created successfully.'
    )
    return redirect('students:admission_verify_step4', pk=pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  VERIFY FLOW — STEP 4: SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def admission_verify_step4(request, pk):
    """
    Verify flow Step 4 — Read-only summary.

    Shows:
        - Student record created
        - All parent accounts created
        - Access token (shown once — staff should note it down)
        - StudentParentRelationship rows
    """
    adm = get_object_or_404(
        Admission.objects.select_related('student', 'student__current_class'), pk=pk
    )

    student = adm.student
    if not student:
        messages.warning(request, 'No student record found. Please check Step 2.')
        return redirect('students:admission_verify_step2', pk=pk)

    # Load relationships
    relationships = StudentParentRelationship.objects.filter(
        student=student
    ).select_related('parent', 'parent__user').order_by('-is_primary', 'relationship')

    # Pull session summary data (only available immediately after step 3)
    created_parents = request.session.pop('verify_created_parents', [])
    access_token    = request.session.pop('verify_access_token', '')
    request.session.modified = True

    # Fallback: reconstruct from DB if session already cleared
    if not access_token and relationships.exists():
        access_token = relationships.first().access_token

    context = {
        'admission':       adm,
        'student':         student,
        'relationships':   relationships,
        'created_parents': created_parents,
        'access_token':    access_token,
        'page_title':      f'Verification Complete — {adm.admission_number}',
        **_verify_progress_ctx(4),
    }
    return render(request, f'{_T}verify_step4.html', context)
