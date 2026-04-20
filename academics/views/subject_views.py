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

_T = 'academics/subject/'


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

# from django.shortcuts import render, get_object_or_404
# from django.contrib.auth.decorators import login_required
# from django.core.paginator import Paginator
# from django.db.models import Q

# Assuming these are your models
# from .models import Subject, TeacherSubject, ClassSubject



@login_required
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