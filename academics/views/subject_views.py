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
#  ASSIGN SUBJECT → TEACHER  (revised flow)
# ═══════════════════════════════════════════════════════════════════════════════
#
#  GUARD: If the subject has no ClassSubject rows → block and notify.
#
#  Step 1  GET  /subjects/<pk>/assign-teacher/
#               Query all classes assigned to this subject (ClassSubject).
#               For each class, list all teachers assigned to that class
#               via TeacherClass.  Render as a grouped checklist so the
#               user picks one teacher per class (or none).
#
#  Step 1  POST step=1
#               Collect selections: field name pattern → "cls_{class_pk}" = teacher_user_pk
#               Build a list of (class_pk, teacher_user_pk) pairs.
#               Store in session.  Redirect to GET step=2.
#
#  Step 2  GET  ?step=2
#               Show chosen pairs side-by-side with any previously assigned
#               teacher for that class.
#               Previously assigned teachers appear pre-checked. If the user
#               unchecks one it means "remove this teacher from the subject
#               in this class".
#               The page also shows newly chosen teachers (from step 1) so
#               the user can review everything before committing.
#
#  Step 2  POST step=2
#               Collect "keep_previous" checkboxes and merge with new choices.
#               Store final decision in session.  Redirect to GET step=3.
#
#  Step 3  GET  ?step=3
#               Display a full diff:
#                 • New assignments  (class → teacher)
#                 • Kept assignments (class → teacher, was already there)
#                 • Removed          (class → teacher, was there, now unchecked)
#               Password field to confirm.
#
#  Step 3  POST step=3
#               Verify password → apply changes in one transaction →
#               redirect to subject_detail_teachers.
#
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('subject', action='edit')
def assign_subject_to_teacher(request, pk):
    subject = get_object_or_404(Subject, pk=pk)

    from academics.models import SchoolSupportedClasses, TeacherClass
    from accounts.models import StaffProfile
    from authentication.models import CustomUser

    # ── Session keys (scoped to this subject) ─────────────────────────────────
    S_NEW      = f'asgn_tr_{pk}_new'       # list of [class_pk, teacher_user_pk]
    S_FINAL    = f'asgn_tr_{pk}_final'     # same shape, after step-2 review

    def _clear_session():
        for k in (S_NEW, S_FINAL):
            request.session.pop(k, None)

    # ── Helper: classes assigned to this subject ───────────────────────────────
    def _subject_classes():
        return (
            ClassSubject.objects
            .filter(subject=subject)
            .select_related('school_class__supported_class')
            .order_by('school_class__supported_class__order')
        )

    # ── Helper: current TeacherSubject map for this subject ────────────────────
    # Returns {class_pk: [teacher_user, ...]}
    def _current_teacher_map():
        rows = (
            TeacherSubject.objects
            .filter(subject=subject)
            .select_related('teacher', 'school_class')
        )
        mapping = {}
        for row in rows:
            cpk = row.school_class_id
            mapping.setdefault(cpk, [])
            mapping[cpk].append(row.teacher)
        return mapping

    # ── Helper: teachers in a class via TeacherClass ───────────────────────────
    def _teachers_for_class(school_class_pk):
        user_pks = (
            TeacherClass.objects
            .filter(school_class_id=school_class_pk, is_active=True)
            .values_list('teacher_id', flat=True)
        )
        return (
            CustomUser.objects
            .filter(pk__in=user_pks)
            .select_related('staff_profile')
        )

    # ─────────────────────────────────────────────────────────────────────────
    #  GUARD — no classes on this subject yet
    # ─────────────────────────────────────────────────────────────────────────
    subject_class_rows = _subject_classes()
    if not subject_class_rows.exists():
        return render(request, f'{_T}assign-tr/assign_teacher_no_classes.html', {
            'subject': subject,
            'section': 'assign_teacher',
        })

    # ─────────────────────────────────────────────────────────────────────────
    #  POST
    # ─────────────────────────────────────────────────────────────────────────
    if request.method == 'POST':
        step = request.POST.get('step', '1')

        # ── Step 1 POST: collect new teacher selections per class ─────────────
        if step == '1':
            new_pairs = []
            for cs in subject_class_rows:
                cpk = cs.school_class_id
                tpk = request.POST.get(f'cls_{cpk}', '').strip()
                if tpk:
                    try:
                        tpk_int = int(tpk)
                        new_pairs.append([cpk, tpk_int])
                    except ValueError:
                        pass

            if not new_pairs:
                messages.error(
                    request,
                    'Please select at least one teacher for at least one class.'
                )
                # rebuild context and re-render step 1
                grouped = _build_step1_groups(subject_class_rows, _current_teacher_map())
                return render(request, f'{_T}assign-tr/assign_teacher_step1.html', {
                    'subject':  subject,
                    'grouped':  grouped,
                    'section':  'assign_teacher',
                })

            request.session[S_NEW] = new_pairs
            return redirect(f"{request.path}?step=2")

        # ── Step 2 POST: merge kept-previous + new, store final ───────────────
        if step == '2':
            new_pairs = request.session.get(S_NEW)
            if not new_pairs:
                messages.error(request, 'Session expired. Please start over.')
                _clear_session()
                return redirect(request.path)

            current_map = _current_teacher_map()
            final_pairs = []   # [class_pk, teacher_user_pk, action]
            #  action: 'add' | 'keep' | 'remove'

            # Determine what the user wants to keep from previous assignments
            # Checkbox name: keep_{class_pk}_{teacher_user_pk}
            for cpk, teachers in current_map.items():
                for t in teachers:
                    cb_name = f'keep_{cpk}_{t.pk}'
                    if request.POST.get(cb_name):
                        final_pairs.append([cpk, t.pk, 'keep'])
                    else:
                        final_pairs.append([cpk, t.pk, 'remove'])

            # Merge new selections (avoid duplicating a 'keep' as 'add')
            keep_and_kept_pairs = {(p[0], p[1]) for p in final_pairs if p[2] == 'keep'}
            for cpk, tpk in new_pairs:
                if (cpk, tpk) not in keep_and_kept_pairs:
                    final_pairs.append([cpk, tpk, 'add'])

            request.session[S_FINAL] = final_pairs
            return redirect(f"{request.path}?step=3")

        # ── Step 3 POST: verify password and commit ───────────────────────────
        if step == '3':
            final_pairs = request.session.get(S_FINAL)
            if not final_pairs:
                messages.error(request, 'Session expired. Please start over.')
                _clear_session()
                return redirect(request.path)

            password = request.POST.get('password', '').strip()
            if not request.user.check_password(password):
                messages.error(request, 'Incorrect password. No changes were saved.')
                diff = _build_diff(final_pairs)
                return render(request, f'{_T}assign-tr/assign_teacher_step3.html', {
                    'subject':        subject,
                    'diff':           diff,
                    'password_error': True,
                    'section':        'assign_teacher',
                })

            try:
                with transaction.atomic():
                    for cpk, tpk, action in final_pairs:
                        teacher_user = CustomUser.objects.get(pk=tpk)
                        cls          = SchoolSupportedClasses.objects.get(pk=cpk)

                        if action == 'remove':
                            TeacherSubject.objects.filter(
                                teacher=teacher_user,
                                subject=subject,
                                school_class=cls,
                            ).delete()

                        elif action in ('add', 'keep'):
                            TeacherSubject.objects.get_or_create(
                                teacher=teacher_user,
                                subject=subject,
                                school_class=cls,
                            )

                _clear_session()

            except Exception as exc:
                messages.error(request, f'Could not save changes: {exc}')
                return redirect(request.path)

            added   = sum(1 for p in final_pairs if p[2] == 'add')
            removed = sum(1 for p in final_pairs if p[2] == 'remove')
            messages.success(
                request,
                f'Teacher assignments updated for "{subject.name}". '
                f'{added} added, {removed} removed.'
            )
            return redirect('academics:subject_detail_teachers', pk=subject.pk)

    # ─────────────────────────────────────────────────────────────────────────
    #  GET
    # ─────────────────────────────────────────────────────────────────────────
    step = request.GET.get('step', '1')

    # ── Step 3 GET: diff + password ───────────────────────────────────────────
    if step == '3':
        final_pairs = request.session.get(S_FINAL)
        if not final_pairs:
            messages.warning(request, 'Session expired. Please start over.')
            _clear_session()
            return redirect(request.path)

        diff = _build_diff(final_pairs)
        return render(request, f'{_T}assign-tr/assign_teacher_step3.html', {
            'subject': subject,
            'diff':    diff,
            'section': 'assign_teacher',
        })

    # ── Step 2 GET: review + previous-teacher checkboxes ─────────────────────
    if step == '2':
        new_pairs = request.session.get(S_NEW)
        if not new_pairs:
            messages.warning(request, 'No selections found. Please start over.')
            return redirect(request.path)

        current_map = _current_teacher_map()
        review_rows = _build_step2_rows(subject_class_rows, new_pairs, current_map)
        return render(request, f'{_T}assign-tr/assign_teacher_step2.html', {
            'subject':     subject,
            'review_rows': review_rows,
            'section':     'assign_teacher',
        })

    # ── Step 1 GET: grouped class → teacher checklist ─────────────────────────
    _clear_session()
    current_map = _current_teacher_map()
    grouped = _build_step1_groups(subject_class_rows, current_map)
    return render(request, f'{_T}assign-tr/assign_teacher_step1.html', {
        'subject': subject,
        'grouped': grouped,
        'section': 'assign_teacher',
    })


# ─────────────────────────────────────────────────────────────────────────────
#  Private helpers  (defined at module level so they're importable in tests)
# ─────────────────────────────────────────────────────────────────────────────

def _build_step1_groups(subject_class_rows, current_map):
    """
    Returns a list of dicts, one per class:
    {
        'class_subject': ClassSubject instance,
        'teachers':      [CustomUser, ...],   # active in this class
        'current_pks':   set of int,          # teacher user PKs already assigned to subject here
    }
    """
    from academics.models import TeacherClass
    from authentication.models import CustomUser

    groups = []
    for cs in subject_class_rows:
        cpk = cs.school_class_id
        teacher_user_pks = (
            TeacherClass.objects
            .filter(school_class_id=cpk, is_active=True)
            .values_list('teacher_id', flat=True)
        )
        teachers = list(
            CustomUser.objects
            .filter(pk__in=teacher_user_pks)
            .select_related('staff_profile')
            .order_by('last_name', 'first_name')
        )
        current_pks = {t.pk for t in current_map.get(cpk, [])}
        groups.append({
            'class_subject': cs,
            'teachers':      teachers,
            'current_pks':   current_pks,
        })
    return groups


def _build_step2_rows(subject_class_rows, new_pairs, current_map):
    """
    Returns a list of dicts, one per class that has either a new selection
    or an existing teacher assignment:
    {
        'school_class':       SchoolSupportedClasses instance,
        'class_name':         str,
        'new_teacher':        CustomUser | None,
        'previous_teachers':  [{'teacher': CustomUser, 'cb_name': str}, ...]
    }
    Only classes that appear in new_pairs OR have previous teachers are included.
    """
    from authentication.models import CustomUser

    # Map class_pk → new teacher user pk
    new_map = {cpk: tpk for cpk, tpk in new_pairs}

    # Collect all relevant class pks
    relevant_cpks = set(new_map.keys()) | set(current_map.keys())

    # Build a lookup for class objects
    class_lookup = {cs.school_class_id: cs for cs in subject_class_rows}

    rows = []
    for cpk in sorted(relevant_cpks,
                       key=lambda x: class_lookup[x].school_class.supported_class.order
                       if x in class_lookup else 9999):
        cs = class_lookup.get(cpk)
        if not cs:
            continue

        # New teacher for this class
        new_teacher = None
        ntpk = new_map.get(cpk)
        if ntpk:
            try:
                new_teacher = CustomUser.objects.select_related('staff_profile').get(pk=ntpk)
            except CustomUser.DoesNotExist:
                pass

        # Previous teachers
        prev = []
        for t in current_map.get(cpk, []):
            # Don't show previous teacher as "previous" if they are the new selection too
            prev.append({
                'teacher': t,
                'cb_name': f'keep_{cpk}_{t.pk}',
                'is_same_as_new': new_teacher and t.pk == new_teacher.pk,
            })

        rows.append({
            'school_class':      cs.school_class,
            'class_name':        cs.school_class.supported_class.name,
            'class_pk':          cpk,
            'new_teacher':       new_teacher,
            'previous_teachers': prev,
        })
    return rows


def _build_diff(final_pairs):
    """
    Resolve user PKs and class PKs into objects and group by action.
    Returns:
    {
        'added':   [{'class_name': str, 'teacher_name': str}, ...],
        'kept':    [...],
        'removed': [...],
    }
    """
    from authentication.models import CustomUser
    from academics.models import SchoolSupportedClasses

    # Bulk fetch to avoid N+1
    user_pks  = {p[1] for p in final_pairs}
    class_pks = {p[0] for p in final_pairs}

    users   = {u.pk: u for u in CustomUser.objects.filter(pk__in=user_pks).select_related('staff_profile')}
    classes = {c.pk: c for c in SchoolSupportedClasses.objects.filter(pk__in=class_pks).select_related('supported_class')}

    diff = {'added': [], 'kept': [], 'removed': []}
    for cpk, tpk, action in final_pairs:
        u = users.get(tpk)
        c = classes.get(cpk)
        entry = {
            'class_name':   c.supported_class.name if c else str(cpk),
            'teacher_name': u.get_full_name() if u else str(tpk),
        }
        if action == 'add':
            diff['added'].append(entry)
        elif action == 'keep':
            diff['kept'].append(entry)
        elif action == 'remove':
            diff['removed'].append(entry)

    return diff



