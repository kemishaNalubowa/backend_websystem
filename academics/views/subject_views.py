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
from academics.models import Subject,ClassSubject
from academics.utils.subject_utils import (
    get_subject_classes_stats,
    get_subject_info_stats,
    get_subject_list_stats,
    get_subject_teachers_stats,
    validate_and_parse_subject,
    get_sch_supported_classes,
    # LEVEL_DISPLAY,
)

_T = 'academics/subjects/'


# ═══════════════════════════════════════════════════════════════════════════════
#  1. SUBJECTS LIST
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
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

@login_required
def subject_detail_info(request, pk):
    """
    Standalone subject info page.
    Shows all core fields, current term teaching status,
    class + teacher counts, and primary teacher.
    Links out to the teachers and classes pages.
    """
    subject = get_object_or_404(Subject, pk=pk)
    stats   = get_subject_info_stats(subject)

    context = {
        'subject':       subject,
        # 'level_display': LEVEL_DISPLAY.get(subject.level, subject.level),
        'page_title':    f'{subject.name} ({subject.code})',
        **stats,
    }
    return render(request, f'{_T}info.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  7. SUBJECT TEACHERS PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def subject_detail_teachers(request, pk):
    """
    Standalone page — all teachers assigned to this subject.
    Shows TeacherSubject records, current term active assignments,
    historical class/term counts, and qualification breakdown.

    Filters:
      ?primary=1     — primary/specialist teachers only
      ?active_only=1 — only those with a current-term assignment
      ?q=search      — search by teacher name or employee ID
    """
    subject = get_object_or_404(Subject, pk=pk)
    stats   = get_subject_teachers_stats(subject)

    # ── Filters ───────────────────────────────────────────────────────────────
    primary_filter      = request.GET.get('primary', '').strip()
    active_only_filter  = request.GET.get('active_only', '').strip()
    search              = request.GET.get('q', '').strip()

    teacher_subjects = stats['teacher_subjects']

    if primary_filter == '1':
        teacher_subjects = teacher_subjects.filter(is_primary=True)

    if active_only_filter == '1' and stats['current_term']:
        from academics.models import TeacherClass
        active_teacher_ids = TeacherClass.objects.filter(
            subject=subject,
            term=stats['current_term'],
            is_active=True,
        ).values_list('teacher_id', flat=True)
        teacher_subjects = teacher_subjects.filter(teacher_id__in=active_teacher_ids)

    if search:
        teacher_subjects = teacher_subjects.filter(
            Q(teacher__user__first_name__icontains=search) |
            Q(teacher__user__last_name__icontains=search)  |
            Q(teacher__employee_id__icontains=search)
        )

    paginator = Paginator(teacher_subjects, 20)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    context = {
        'subject':            subject,
        'level_display':      LEVEL_DISPLAY.get(subject.level, subject.level),
        'page_title':         f'Teachers — {subject.name} ({subject.code})',
        **stats,
        'teacher_subjects':   page_obj.object_list,
        'page_obj':           page_obj,
        'primary_filter':     primary_filter,
        'active_only_filter': active_only_filter,
        'search':             search,
    }
    return render(request, f'{_T}teachers.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  8. SUBJECT CLASSES PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def subject_detail_classes(request, pk):
    """
    Standalone page — all classes assigned to this subject.
    Shows ClassSubject records, current term assignments with teacher names,
    section/level breakdown, and EOT average marks per class.

    Filters:
      ?section=nursery|primary
      ?level=p1|p2|...
      ?active=1|0
      ?q=search
    """
    subject = get_object_or_404(Subject, pk=pk)
    stats   = get_subject_classes_stats(subject)

    # ── Filters ───────────────────────────────────────────────────────────────
    section_filter = request.GET.get('section', '').strip()
    level_filter   = request.GET.get('level', '').strip()
    active_filter  = request.GET.get('active', '').strip()
    search         = request.GET.get('q', '').strip()

    class_subjects = stats['class_subjects']

    if section_filter:
        class_subjects = class_subjects.filter(school_class__section=section_filter)

    if level_filter:
        class_subjects = class_subjects.filter(school_class__level=level_filter)

    if active_filter == '1':
        class_subjects = class_subjects.filter(is_active=True)
    elif active_filter == '0':
        class_subjects = class_subjects.filter(is_active=False)

    if search:
        class_subjects = class_subjects.filter(
            Q(school_class__level__icontains=search) |
            Q(school_class__stream__icontains=search)
        )

    paginator = Paginator(class_subjects, 20)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    CLASS_LEVEL_CHOICES = [
        ('baby', 'Baby Class'), ('middle', 'Middle Class'), ('top', 'Top Class'),
        ('p1', 'P1'), ('p2', 'P2'), ('p3', 'P3'), ('p4', 'P4'),
        ('p5', 'P5'), ('p6', 'P6'), ('p7', 'P7'),
    ]

    context = {
        'subject':        subject,
        # 'level_display':  LEVEL_DISPLAY.get(subject.level, subject.level),
        'page_title':     f'Classes — {subject.name} ({subject.code})',
        **stats,
        'class_subjects': page_obj.object_list,
        'page_obj':       page_obj,
        'section_filter': section_filter,
        'level_filter':   level_filter,
        'active_filter':  active_filter,
        'search':         search,
        'level_choices':  CLASS_LEVEL_CHOICES,
    }
    return render(request, f'{_T}classes.html', context)
