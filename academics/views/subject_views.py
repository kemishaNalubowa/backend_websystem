# academics/views/subject_views.py
# ─────────────────────────────────────────────────────────────────────────────
# All Subject views.
# Rules (same as term_views):
#   - Function-based views only
#   - No forms.py / Django Forms
#   - No Class-based Views
#   - No JSON responses
#   - Manual validation via subject_utils.validate_and_parse_subject()
#   - Django messages for all feedback
#   - login_required on every view
# ─────────────────────────────────────────────────────────────────────────────

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from academics.models import base
from academics.models import Subject,ClassSubject,TeacherSubject
from academics.utils.subject_utils import (
    get_subject_classes_stats,
    get_subject_info_stats,
    get_subject_list_stats,
    get_subject_teachers_stats,
    validate_and_parse_subject,
    get_sch_supported_classes,
    # LEVEL_DISPLAY,
)
from permissions.decorators import has_permission

_T = 'academics/subject/'


# ═══════════════════════════════════════════════════════════════════════════════
#  1. SUBJECTS LIST
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('subject', action='read')
def subject_list(request):
    """
    All subjects with filtering and list-level statistics.

    Filters:
      ?status=active|inactive
      ?level=nursery|lower_primary|upper_primary|all
      ?compulsory=1|0
      ?q=search term
    """
    qs = Subject.objects.all()

    # ── Filters ───────────────────────────────────────────────────────────────
    status_filter     = request.GET.get('status', '').strip()
    # level_filter      = request.GET.get('level', '').strip()
    # compulsory_filter = request.GET.get('compulsory', '').strip()
    search            = request.GET.get('q', '').strip()

    if status_filter == 'active':
        qs = qs.filter(is_active=True)
    elif status_filter == 'inactive':
        qs = qs.filter(is_active=False)


    if search:
        qs = qs.filter(
            Q(name__icontains=search) |
            Q(code__icontains=search) |
            Q(description__icontains=search)
        )

    qs = qs.order_by('name')

    # ── Pagination ────────────────────────────────────────────────────────────
    paginator  = Paginator(qs, 15)
    page_obj   = paginator.get_page(request.GET.get('page', 1))

    # ── Stats ─────────────────────────────────────────────────────────────────
    stats = get_subject_list_stats()

    context = {
        'subjects':           page_obj.object_list,
        'page_obj':           page_obj,
        'status_filter':      status_filter,
        # 'level_filter':       level_filter,
        # 'compulsory_filter':  compulsory_filter,
        'search':             search,
        # 'level_choices':      list(LEVEL_DISPLAY.items()),
        'section':            'list',
        **stats,
    }
    return render(request, f'{_T}list.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  2. ADD SUBJECT
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('subject', action='create')
def subject_add(request):
    """
    Add a new subject.
    GET  — render blank form.
    POST — validate; save on success; re-render with errors on failure.
    """
    if request.method == 'GET':
        return render(request, f'{_T}form.html', {
            'form_title':   'Add New Subject',
            'action':       'add',
            'section':      'add',
            'post':         {},
            'errors':       {},
            "classes":get_sch_supported_classes(),
            # 'level_choices': list(LEVEL_DISPLAY.items()),
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    cleaned, errors = validate_and_parse_subject(request.POST)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}form.html', {
            'form_title':    'Add New Subject',
            'action':        'add',
            'section':       'add',
            'post':          request.POST,
            'errors':        errors,
            "classes":get_sch_supported_classes(),
            # 'level_choices': list(LEVEL_DISPLAY.items()),
        })

    try:
        with transaction.atomic():
            subject = Subject.objects.create(
                name=cleaned['name'],
                code=cleaned['code'],
                description=cleaned['description'],
                is_active=cleaned['is_active'],
            )

            # Creating the supported Classess

            for cls in cleaned["classes"]:
                ClassSubject.objects.create(
                    school_class=cls,  # the actual Class FK
                    subject=subject,
                )



    except Exception as exc:
        messages.error(request, f'Could not save subject: {exc}')
        return render(request, f'{_T}form.html', {
            'form_title':    'Add New Subject',
            'action':        'add',
            'section':       'add',
            'post':          request.POST,
            'errors':        {},
            'classes':       get_sch_supported_classes(),
            # 'level_choices': list(LEVEL_DISPLAY.items()),
        })

    messages.success(
        request,
        f'Subject "{subject.name}" ({subject.code}) has been created successfully.'
    )
    return redirect('academics:subject_detail_info', pk=subject.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  3. EDIT SUBJECT
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('subject', action='edit')
def subject_edit(request, pk):
    """
    Edit an existing subject.
    GET  — render form pre-filled with current values.
    POST — validate; save on success; re-render with errors on failure.
    """
    subject = get_object_or_404(Subject, pk=pk)

    if request.method == 'GET':
        return render(request, f'{_T}form.html', {
            'subject':       subject,
            'form_title':    f'Edit Subject — {subject.name} ({subject.code})',
            'action':        'edit',
            'section':       'edit',
            "classes":get_sch_supported_classes(),
            'post':          {},
            'errors':        {},
            # 'level_choices': list(LEVEL_DISPLAY.items()),
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    cleaned, errors = validate_and_parse_subject(request.POST, instance=subject)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}form.html', {
            'subject':       subject,
            'form_title':    f'Edit Subject — {subject.name} ({subject.code})',
            'action':        'edit',
            'section':       'edit',
            'post':          request.POST,
            "classes":get_sch_supported_classes(),
            'errors':        errors,
            # 'level_choices': list(LEVEL_DISPLAY.items()),
        })

    try:
        with transaction.atomic():
            # Update Subject fields only
            subject_fields = {k: v for k, v in cleaned.items() if k != 'classes'}
            for field, value in subject_fields.items():
                setattr(subject, field, value)
            subject.save()

            # Sync ClassSubject records
            ClassSubject.objects.filter(subject=subject).delete()
            for cls in cleaned['classes']:
                ClassSubject.objects.create(
                    school_class=cls,
                    subject=subject,
                )
    except Exception as exc:
        messages.error(request, f'Could not update subject: {exc}')
        return render(request, f'{_T}form.html', {
            'subject':       subject,
            'form_title':    f'Edit Subject — {subject.name} ({subject.code})',
            'action':        'edit',
            'section':       'edit',
            'post':          request.POST,
            'errors':        {},
            'classes':       get_sch_supported_classes(),
            # 'level_choices': list(LEVEL_DISPLAY.items()),
        })

    messages.success(
        request,
        f'Subject "{subject.name}" ({subject.code}) has been updated successfully.'
    )
    return redirect('academics:subject_detail_info', pk=subject.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  4. DELETE SUBJECT
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('subject', action='delete')
def subject_delete(request, pk):
    """
    Delete a subject.
    GET  — confirmation page showing full impact (assignments, marks, etc.)
    POST — perform deletion.

    Guard: subjects with confirmed assessment marks cannot be deleted.
    The admin must deactivate the subject instead.
    """
    subject = get_object_or_404(Subject, pk=pk)

    # ── Impact counts ─────────────────────────────────────────────────────────
    from academics.models import ClassSubject, TeacherSubject, TeacherClass
    from assessments.models import AssessmentSubject

    impact = {
        'class_assignments':   ClassSubject.objects.filter(subject=subject).count(),
        'teacher_assignments': TeacherSubject.objects.filter(subject=subject).count(),
        'teaching_records':    TeacherClass.objects.filter(subject=subject).count(),
        'assessment_marks':    AssessmentSubject.objects.filter(subject=subject).count(),
    }

    has_marks = impact['assessment_marks'] > 0

    if request.method == 'GET':
        return render(request, f'{_T}delete_confirm.html', {
            'subject':   subject,
            'impact':    impact,
            'has_marks': has_marks,
            'section':   'delete',
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    # Hard block: never delete a subject that has actual student marks attached.
    # Direct them to deactivate instead.
    if has_marks:
        messages.error(
            request,
            f'"{subject.name}" has {impact["assessment_marks"]:,} student assessment '
            f'mark(s) on record and cannot be deleted. '
            f'Deactivate it instead to hide it from new assignments.'
        )
        return redirect('academics:subject_detail_info', pk=subject.pk)

    label = f'{subject.name} ({subject.code})'
    try:
        subject.delete()
        messages.success(request, f'Subject "{label}" has been permanently deleted.')
    except Exception as exc:
        messages.error(request, f'Could not delete subject: {exc}')
        return redirect('academics:subject_detail_info', pk=subject.pk)

    return redirect('academics:subject_list')


# ═══════════════════════════════════════════════════════════════════════════════
#  5. TOGGLE ACTIVE STATUS  (POST-only quick action)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('subject', action='toggle')
def subject_toggle_active(request, pk):
    """
    Quick POST-only toggle for is_active.
    Allows activating/deactivating a subject without opening the full edit form.
    """
    if request.method != 'POST':
        messages.warning(request, 'Invalid request method.')
        return redirect('academics:subject_list')

    subject = get_object_or_404(Subject, pk=pk)
    subject.is_active = not subject.is_active
    subject.save(update_fields=['is_active', 'updated_at'])

    state = 'activated' if subject.is_active else 'deactivated'
    messages.success(request, f'"{subject.name}" has been {state}.')

    # Return to wherever the request came from
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('academics:subject_list')


# ═══════════════════════════════════════════════════════════════════════════════
#  6. SUBJECT INFO PAGE
# ═══════════════════════════════════════════════════════════════════════════════

# from django.shortcuts import render, get_object_or_404
# from django.contrib.auth.decorators import login_required
# from django.core.paginator import Paginator
# from django.db.models import Q

# Assuming these are your models
# from .models import Subject, TeacherSubject, ClassSubject



@login_required
@has_permission('subject', action='read')
def subject_detail_info(request, pk):
    subject = get_object_or_404(Subject, pk=pk)

    teacher_count = subject.subject_teachers.count()
    class_count = subject.class_subjects.count()

    context = {
        'subject': subject,
        'teacher_count': teacher_count,
        'class_count': class_count,
    }
    return render(request, f'{_T}info.html', context)


@login_required
@has_permission('subject', action='read')
def subject_detail_teachers(request, pk):
    subject = get_object_or_404(Subject, pk=pk)

    teacher_subjects = TeacherSubject.objects.filter(subject=subject)

    

    # Simple search only (removed complex filters as per your request)
    search = request.GET.get('q', '').strip()
    if search:
        teacher_subjects = teacher_subjects.filter(
            Q(teacher__user__first_name__icontains=search) |
            Q(teacher__user__last_name__icontains=search) |
            Q(teacher__employee_id__icontains=search)
        )

    paginator = Paginator(teacher_subjects, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'subject': subject,
        'teacher_subjects': page_obj.object_list,
        'page_obj': page_obj,
        'search': search,
    }
    return render(request, f'{_T}teachers.html', context)


@login_required
@has_permission('subject', action='read')
def subject_detail_classes(request, pk):
    subject = get_object_or_404(Subject, pk=pk)

    class_subjects = subject.class_subjects.select_related('school_class__supported_class')

    # Simple search only
    search = request.GET.get('q', '').strip()
    if search:
        class_subjects = class_subjects.filter(
            Q(school_class__supported_class__name__icontains=search) |
            Q(school_class__supported_class__key__icontains=search)
        )

    paginator = Paginator(class_subjects, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'subject': subject,
        'class_subjects': page_obj.object_list,
        'page_obj': page_obj,
        'search': search,
    }
    return render(request, f'{_T}classes.html', context)





# ═══════════════════════════════════════════════════════════════════════════════
#  7. ASSIGN SUBJECT → CLASSES  (multi-step)
# ═══════════════════════════════════════════════════════════════════════════════
#
#  Step 1  GET  /subjects/<pk>/assign-classes/
#               → Render checklist of ALL SchoolSupportedClasses.
#                 Classes already linked are pre-checked.
#
#  Step 2  POST step=1
#               → Validate at least one class was chosen.
#                 Store chosen class PKs in session.
#                 Redirect to GET step 2 (confirmation page).
#
#  Step 2  GET  /subjects/<pk>/assign-classes/?step=2
#               → Show summary of chosen classes + password field.
#
#  Step 3  POST step=2
#               → Verify password.
#                 Sync ClassSubject rows (add new, keep existing, remove unchecked).
#                 Clear session key.  Redirect to subject classes tab.
#
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('subject', action='edit')
def assign_subject_to_class(request, pk):
    """
    Assign (or re-sync) a subject to one or more SchoolSupportedClasses.
    Uses session to carry chosen class PKs between step 1 and step 2.
    """
    subject = get_object_or_404(Subject, pk=pk)

    # Session key is unique per subject so concurrent tabs don't collide.
    SESSION_KEY = f'assign_cls_{pk}'

    # ── Already-linked class PKs (for pre-checking checkboxes) ────────────────
    already_linked_pks = set(
        ClassSubject.objects.filter(subject=subject)
        .values_list('school_class_id', flat=True)
    )

    # ── All supported classes ─────────────────────────────────────────────────
    from academics.models import SchoolSupportedClasses
    all_classes = (
        SchoolSupportedClasses.objects
        .select_related('supported_class')
        .order_by('supported_class__order')
    )

    # ─────────────────────────────────────────────────────────────────────────
    #  POST — determine which step we're processing
    # ─────────────────────────────────────────────────────────────────────────
    if request.method == 'POST':
        step = request.POST.get('step', '1')

        # ── Step 1 POST: collect chosen classes, redirect to confirmation ────
        if step == '1':
            chosen_pks = request.POST.getlist('classes')  # list of str PKs

            if not chosen_pks:
                messages.error(request, 'Please select at least one class.')
                return render(request, f'{_T}assign-class/assign_class_step1.html', {
                    'subject':           subject,
                    'all_classes':       all_classes,
                    'already_linked_pks': already_linked_pks,
                    'section':           'assign_class',
                })

            # Validate that submitted PKs actually exist
            valid_classes = SchoolSupportedClasses.objects.filter(
                pk__in=chosen_pks
            )
            valid_pks = list(valid_classes.values_list('pk', flat=True))

            if not valid_pks:
                messages.error(request, 'None of the selected classes were valid.')
                return render(request, f'{_T}assign-class/assign_class_step1.html', {
                    'subject':           subject,
                    'all_classes':       all_classes,
                    'already_linked_pks': already_linked_pks,
                    'section':           'assign_class',
                })

            # Stash in session and show confirmation
            request.session[SESSION_KEY] = valid_pks
            return redirect(
                f"{request.path}?step=2"
            )

        # ── Step 2 POST: verify password and commit ──────────────────────────
        if step == '2':
            chosen_pks = request.session.get(SESSION_KEY)
            if not chosen_pks:
                messages.error(request, 'Session expired. Please start over.')
                return redirect(request.path)

            password = request.POST.get('password', '').strip()
            if not request.user.check_password(password):
                messages.error(request, 'Incorrect password. Assignment not saved.')
                # Re-render confirmation page — fetch classes from session
                chosen_classes = SchoolSupportedClasses.objects.filter(
                    pk__in=chosen_pks
                ).select_related('supported_class').order_by('supported_class__order')
                return render(request, f'{_T}assign-class/assign_class_step2.html', {
                    'subject':         subject,
                    'chosen_classes':  chosen_classes,
                    'password_error':  True,
                    'section':         'assign_class',
                })

            # Commit: sync ClassSubject rows
            try:
                with transaction.atomic():
                    # Remove any existing links NOT in the new selection
                    ClassSubject.objects.filter(subject=subject).exclude(
                        school_class_id__in=chosen_pks
                    ).delete()

                    # Add new links (skip duplicates via get_or_create)
                    chosen_classes_qs = SchoolSupportedClasses.objects.filter(
                        pk__in=chosen_pks
                    )
                    added = 0
                    for cls in chosen_classes_qs:
                        _, created = ClassSubject.objects.get_or_create(
                            school_class=cls,
                            subject=subject,
                        )
                        if created:
                            added += 1

                del request.session[SESSION_KEY]

            except Exception as exc:
                messages.error(request, f'Could not save assignment: {exc}')
                return redirect(request.path)

            messages.success(
                request,
                f'"{subject.name}" is now assigned to {len(chosen_pks)} class(es). '
                f'({added} newly added)'
            )
            return redirect('academics:subject_detail_classes', pk=subject.pk)

    # ─────────────────────────────────────────────────────────────────────────
    #  GET
    # ─────────────────────────────────────────────────────────────────────────
    step = request.GET.get('step', '1')

    # ── Step 2 GET: confirmation / password page ──────────────────────────────
    if step == '2':
        chosen_pks = request.session.get(SESSION_KEY)
        if not chosen_pks:
            messages.warning(request, 'No classes selected. Please start again.')
            return redirect(request.path)

        chosen_classes = (
            SchoolSupportedClasses.objects
            .filter(pk__in=chosen_pks)
            .select_related('supported_class')
            .order_by('supported_class__order')
        )
        return render(request, f'{_T}assign-class/assign_class_step2.html', {
            'subject':        subject,
            'chosen_classes': chosen_classes,
            'section':        'assign_class',
        })

    # ── Step 1 GET: class-selection checklist ─────────────────────────────────
    return render(request, f'{_T}assign-class/assign_class_step1.html', {
        'subject':            subject,
        'all_classes':        all_classes,
        'already_linked_pks': already_linked_pks,
        'section':            'assign_class',
    })


# ═══════════════════════════════════════════════════════════════════════════════
#  8. ASSIGN SUBJECT → TEACHER  (multi-step)
# ═══════════════════════════════════════════════════════════════════════════════
#
#  Step 1  GET  /subjects/<pk>/assign-teacher/
#               → Form: enter teacher Employee ID / Staff ID.
#
#  Step 1  POST step=1
#               → Look up teacher by employee_id on StaffProfile.
#                 If not found → error, re-render step 1.
#                 If found → store teacher user PK in session.
#                 Redirect to GET step 2.
#
#  Step 2  GET  ?step=2
#               → Display teacher info + checklist of ALL
#                 SchoolSupportedClasses the teacher is linked to
#                 via TeacherSubject (or TeacherClass).
#                 Classes where this teacher already teaches THIS subject
#                 are pre-checked.
#
#  Step 2  POST step=2
#               → Validate at least one class selected.
#                 Store chosen class PKs in session.
#                 Redirect to GET step 3.
#
#  Step 3  GET  ?step=3
#               → Summary + password confirmation.
#
#  Step 3  POST step=3
#               → Verify password.
#                 Sync TeacherSubject rows for this teacher+subject combination.
#                 Clear session keys.  Redirect to subject teachers tab.
#
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('subject', action='edit')
def assign_subject_to_teacher(request, pk):
    """
    Assign a subject to a teacher for one or more classes they already teach.

    Session keys (all scoped to this subject pk):
        assign_tch_{pk}_teacher_pk   → int  — resolved teacher user PK
        assign_tch_{pk}_classes      → list — chosen SchoolSupportedClasses PKs
    """
    subject = get_object_or_404(Subject, pk=pk)

    S_TEACHER = f'assign_tch_{pk}_teacher_pk'
    S_CLASSES = f'assign_tch_{pk}_classes'

    from accounts.models import StaffProfile
    from academics.models import SchoolSupportedClasses, TeacherClass

    def _clear_session():
        request.session.pop(S_TEACHER, None)
        request.session.pop(S_CLASSES, None)

    # ─────────────────────────────────────────────────────────────────────────
    #  POST
    # ─────────────────────────────────────────────────────────────────────────
    if request.method == 'POST':
        step = request.POST.get('step', '1')

        # ── Step 1 POST: resolve teacher by employee / staff ID ──────────────
        if step == '1':
            staff_id = request.POST.get('staff_id', '').strip().upper()

            if not staff_id:
                messages.error(request, 'Please enter a Staff / Employee ID.')
                return render(request, f'{_T}assign-tr/assign_teacher_step1.html', {
                    'subject': subject,
                    'section': 'assign_teacher',
                    'post':    request.POST,
                })

            try:
                staff_profile = StaffProfile.objects.select_related('user').get(
                    employee_id__iexact=staff_id
                )
            except StaffProfile.DoesNotExist:
                messages.error(
                    request,
                    f'No staff member found with ID "{staff_id}". '
                    'Check the ID and try again.'
                )
                return render(request, f'{_T}assign-tr/assign_teacher_step1.html', {
                    'subject': subject,
                    'section': 'assign_teacher',
                    'post':    request.POST,
                })

            # Store teacher reference and move to step 2
            request.session[S_TEACHER] = staff_profile.user.pk
            return redirect(f"{request.path}?step=2")

        # ── Step 2 POST: collect chosen classes ──────────────────────────────
        if step == '2':
            teacher_user_pk = request.session.get(S_TEACHER)
            if not teacher_user_pk:
                messages.error(request, 'Session expired. Please start over.')
                _clear_session()
                return redirect(request.path)

            chosen_pks = request.POST.getlist('classes')

            if not chosen_pks:
                messages.error(request, 'Please select at least one class.')
                # Re-render step 2 without losing teacher context
                return redirect(f"{request.path}?step=2")

            valid_pks = list(
                SchoolSupportedClasses.objects.filter(pk__in=chosen_pks)
                .values_list('pk', flat=True)
            )
            if not valid_pks:
                messages.error(request, 'None of the selected classes were valid.')
                return redirect(f"{request.path}?step=2")

            request.session[S_CLASSES] = valid_pks
            return redirect(f"{request.path}?step=3")

        # ── Step 3 POST: verify password and commit ──────────────────────────
        if step == '3':
            teacher_user_pk = request.session.get(S_TEACHER)
            chosen_pks      = request.session.get(S_CLASSES)

            if not teacher_user_pk or not chosen_pks:
                messages.error(request, 'Session expired. Please start over.')
                _clear_session()
                return redirect(request.path)

            password = request.POST.get('password', '').strip()
            if not request.user.check_password(password):
                messages.error(request, 'Incorrect password. Assignment not saved.')
                # Re-render step 3 confirmation
                try:
                    staff_profile = StaffProfile.objects.select_related('user').get(
                        user_id=teacher_user_pk
                    )
                except StaffProfile.DoesNotExist:
                    _clear_session()
                    messages.error(request, 'Teacher record no longer found.')
                    return redirect(request.path)

                chosen_classes = (
                    SchoolSupportedClasses.objects
                    .filter(pk__in=chosen_pks)
                    .select_related('supported_class')
                    .order_by('supported_class__order')
                )
                return render(request, f'{_T}assign-tr/assign_teacher_step3.html', {
                    'subject':        subject,
                    'staff_profile':  staff_profile,
                    'chosen_classes': chosen_classes,
                    'password_error': True,
                    'section':        'assign_teacher',
                })

            # Commit: sync TeacherSubject rows for this teacher+subject
            try:
                staff_profile = StaffProfile.objects.select_related('user').get(
                    user_id=teacher_user_pk
                )
                teacher_user = staff_profile.user

                with transaction.atomic():
                    # Remove links for this teacher+subject NOT in new selection
                    TeacherSubject.objects.filter(
                        teacher=teacher_user,
                        subject=subject,
                    ).exclude(school_class_id__in=chosen_pks).delete()

                    # Add new links
                    chosen_classes_qs = SchoolSupportedClasses.objects.filter(
                        pk__in=chosen_pks
                    )
                    added = 0
                    for cls in chosen_classes_qs:
                        _, created = TeacherSubject.objects.get_or_create(
                            teacher=teacher_user,
                            subject=subject,
                            school_class=cls,
                        )
                        if created:
                            added += 1

                _clear_session()

            except Exception as exc:
                messages.error(request, f'Could not save assignment: {exc}')
                return redirect(request.path)

            messages.success(
                request,
                f'"{subject.name}" assigned to {staff_profile.full_name} '
                f'for {len(chosen_pks)} class(es). ({added} newly added)'
            )
            return redirect('academics:subject_detail_teachers', pk=subject.pk)

    # ─────────────────────────────────────────────────────────────────────────
    #  GET
    # ─────────────────────────────────────────────────────────────────────────
    step = request.GET.get('step', '1')

    # ── Step 3 GET: confirmation / password ───────────────────────────────────
    if step == '3':
        teacher_user_pk = request.session.get(S_TEACHER)
        chosen_pks      = request.session.get(S_CLASSES)

        if not teacher_user_pk or not chosen_pks:
            messages.warning(request, 'Session expired. Please start over.')
            _clear_session()
            return redirect(request.path)

        try:
            staff_profile = StaffProfile.objects.select_related('user').get(
                user_id=teacher_user_pk
            )
        except StaffProfile.DoesNotExist:
            messages.error(request, 'Teacher record no longer found.')
            _clear_session()
            return redirect(request.path)

        chosen_classes = (
            SchoolSupportedClasses.objects
            .filter(pk__in=chosen_pks)
            .select_related('supported_class')
            .order_by('supported_class__order')
        )
        return render(request, f'{_T}assign-tr/assign_teacher_step3.html', {
            'subject':        subject,
            'staff_profile':  staff_profile,
            'chosen_classes': chosen_classes,
            'section':        'assign_teacher',
        })

    # ── Step 2 GET: class checklist for chosen teacher ────────────────────────
    if step == '2':
        teacher_user_pk = request.session.get(S_TEACHER)

        if not teacher_user_pk:
            messages.warning(request, 'No teacher selected. Please start over.')
            return redirect(request.path)

        try:
            staff_profile = StaffProfile.objects.select_related('user').get(
                user_id=teacher_user_pk
            )
        except StaffProfile.DoesNotExist:
            messages.error(request, 'Teacher record no longer found.')
            _clear_session()
            return redirect(request.path)

        teacher_user = staff_profile.user

        # All classes this teacher is assigned to (via TeacherClass)
        teacher_class_pks = (
            TeacherClass.objects
            .filter(teacher=teacher_user, is_active=True)
            .values_list('school_class_id', flat=True)
        )
        teacher_classes = (
            SchoolSupportedClasses.objects
            .filter(pk__in=teacher_class_pks)
            .select_related('supported_class')
            .order_by('supported_class__order')
        )

        # Classes where teacher already teaches THIS subject (pre-check)
        already_assigned_pks = set(
            TeacherSubject.objects.filter(
                teacher=teacher_user,
                subject=subject,
            ).values_list('school_class_id', flat=True)
        )

        return render(request, f'{_T}assign-tr/assign_teacher_step2.html', {
            'subject':             subject,
            'staff_profile':       staff_profile,
            'teacher_classes':     teacher_classes,
            'already_assigned_pks': already_assigned_pks,
            'section':             'assign_teacher',
        })

    # ── Step 1 GET: staff ID entry form ──────────────────────────────────────
    _clear_session()   # always reset on fresh start
    return render(request, f'{_T}assign-tr/assign_teacher_step1.html', {
        'subject': subject,
        'section': 'assign_teacher',
        'post':    {},
    })







