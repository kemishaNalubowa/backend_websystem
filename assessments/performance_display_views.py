# assessments/performance_display_views.py
# ─────────────────────────────────────────────────────────────────────────────
# Read-only display views + inline single-student edit for the 4-page
# performance drill-down:
#
#   1. performance_overview          /assessments/<pk>/performance/
#   2. performance_class             /assessments/<pk>/performance/class/<ac_pk>/
#   3. performance_class_subject     /assessments/<pk>/performance/class/<ac_pk>/subject/<as_pk>/
#   4. performance_student_edit      /assessments/<pk>/performance/class/<ac_pk>/subject/<as_pk>/student/<perf_pk>/edit/
#
# Rules:
#   • FBV only, no forms.py, no JSON, no CBV.
#   • @login_required on every view.
#   • transaction.atomic() on every save.
#   • messages for all feedback.
#   • Re-render with errors={} + post=POST on validation failure.
#   • Search is server-side via GET ?q=…
# ─────────────────────────────────────────────────────────────────────────────

from decimal import Decimal, InvalidOperation

from django.contrib                 import messages
from django.contrib.auth.decorators import login_required
from django.db                      import transaction
from django.db.models               import Q
from django.shortcuts               import get_object_or_404, redirect, render
from django.urls                    import reverse

from .models import (
    Assessment,
    AssessmentClass,
    AssessmentModification,
    AssessmentPerformance,
    AssessmentPerformanceEntryStatus,
    AssessmentSubject,
    AssessmentTotalMark,
)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helper
# ─────────────────────────────────────────────────────────────────────────────

def _get_or_create_mod(assessment):
    mod, _ = AssessmentModification.objects.get_or_create(
        assessment=assessment,
        defaults={'modify_class': True},
    )
    return mod


# =============================================================================
# 1.  PERFORMANCE OVERVIEW
#     Shows: overall completion card, total classes count, searchable class list
# =============================================================================

@login_required
def performance_overview(request, pk):
    assessment = get_object_or_404(Assessment, pk=pk)
    mod        = _get_or_create_mod(assessment)

    search = request.GET.get('q', '').strip()

    # ── All assessment classes (for unfiltered totals) ────────────────────────
    all_acs = AssessmentClass.objects.filter(
        assessment=assessment
    ).select_related('school_class__supported_class').order_by(
        'school_class__supported_class__order'
    )
    total_classes = all_acs.count()

    # ── Filtered list (for the rendered table) ────────────────────────────────
    acs_qs = all_acs
    if search:
        acs_qs = acs_qs.filter(
            school_class__supported_class__name__icontains=search
        )

    # ── Build class_groups + rolling overall totals ───────────────────────────
    class_groups  = []
    overall_done  = 0
    overall_total = 0

    # Grab all statuses in one query, group by school_class_id
    all_statuses = list(
        AssessmentPerformanceEntryStatus.objects.filter(assessment=assessment)
    )
    status_by_ac = {}
    for s in all_statuses:
        status_by_ac.setdefault(s.school_class_id, []).append(s)
        # Rolling totals are always over the full set
        overall_total += 1
        if s.is_done:
            overall_done += 1

    for ac in acs_qs:
        statuses      = status_by_ac.get(ac.pk, [])
        total_subj    = len(statuses)
        done_subj     = sum(1 for s in statuses if s.is_done)
        total_entered = sum(s.students_entered  for s in statuses)
        total_attended= sum(s.students_attended for s in statuses)
        all_done      = total_subj > 0 and done_subj == total_subj
        cls_pct       = round((done_subj / total_subj) * 100) if total_subj else 0

        class_groups.append({
            'ac':               ac,
            'ac_pk':            ac.pk,
            'class_name':       ac.school_class.supported_class.name,
            'students_attended': ac.students_attended,
            'total_subjects':   total_subj,
            'done_subjects':    done_subj,
            'total_entered':    total_entered,
            'total_attended':   total_attended,
            'all_done':         all_done,
            'cls_pct':          cls_pct,
        })

    overall_pct = round((overall_done / overall_total) * 100) if overall_total else 0

    return render(request, 'assessments/display/assessment_performance_list.html', {
        'assessment':    assessment,
        'mod':           mod,
        'class_groups':  class_groups,
        'overall_done':  overall_done,
        'overall_total': overall_total,
        'overall_pct':   overall_pct,
        'total_classes': total_classes,
        'search':        search,
    })


# =============================================================================
# 2.  PERFORMANCE CLASS DETAIL
#     Shows: class stats card, searchable subject list with per-subject progress
# =============================================================================

@login_required
def performance_class(request, pk, ac_pk):
    assessment = get_object_or_404(Assessment, pk=pk)
    ac         = get_object_or_404(AssessmentClass, pk=ac_pk, assessment=assessment)
    mod        = _get_or_create_mod(assessment)

    search = request.GET.get('q', '').strip()

    # ── Unfiltered stats ──────────────────────────────────────────────────────
    all_statuses   = list(
        AssessmentPerformanceEntryStatus.objects.filter(
            assessment=assessment, school_class=ac
        ).select_related('subject__subject')
    )
    total_subjects = len(all_statuses)
    done_subjects  = sum(1 for s in all_statuses if s.is_done)
    total_entered  = sum(s.students_entered  for s in all_statuses)
    total_attended = sum(s.students_attended for s in all_statuses)
    all_done       = total_subjects > 0 and done_subjects == total_subjects
    class_pct      = round((total_entered / total_attended) * 100) if total_attended else 0

    # ── Filtered display list ─────────────────────────────────────────────────
    statuses = all_statuses
    if search:
        statuses = [
            s for s in all_statuses
            if search.lower() in s.subject.subject.name.lower()
            or search.lower() in s.subject.subject.code.lower()
        ]

    return render(request, 'assessments/display/performance_class.html', {
        'assessment':     assessment,
        'ac':             ac,
        'mod':            mod,
        'statuses':       statuses,
        'total_subjects': total_subjects,
        'done_subjects':  done_subjects,
        'total_entered':  total_entered,
        'total_attended': total_attended,
        'class_pct':      class_pct,
        'all_done':       all_done,
        'search':         search,
    })


# =============================================================================
# 3.  PERFORMANCE CLASS SUBJECT DETAIL
#     Shows: subject info card, entry status card, searchable student list
# =============================================================================

@login_required
def performance_class_subject(request, pk, ac_pk, as_pk):
    assessment = get_object_or_404(Assessment, pk=pk)
    ac         = get_object_or_404(AssessmentClass,   pk=ac_pk, assessment=assessment)
    as_subj    = get_object_or_404(AssessmentSubject, pk=as_pk, assessment=assessment)
    mod        = _get_or_create_mod(assessment)

    entry_status = AssessmentPerformanceEntryStatus.objects.filter(
        assessment=assessment,
        school_class=ac,
        subject=as_subj,
    ).first()

    total_mark = AssessmentTotalMark.objects.filter(
        assessment=assessment,
        subject=as_subj,
    ).first()

    search = request.GET.get('q', '').strip()

    perfs_qs = AssessmentPerformance.objects.filter(
        assessment=assessment,
        school_class=ac.school_class,
        subject=as_subj.subject,
    ).select_related('student', 'entered_by', 'verified_by')

    if search:
        perfs_qs = perfs_qs.filter(
            Q(student__first_name__icontains=search) |
            Q(student__last_name__icontains=search)  |
            Q(student__student_id__icontains=search)
        )

    performances = list(
        perfs_qs.order_by('student__last_name', 'student__first_name')
    )

    return render(request, 'assessments/display/performance_class_subject.html', {
        'assessment':   assessment,
        'ac':           ac,
        'as_subj':      as_subj,
        'mod':          mod,
        'entry_status': entry_status,
        'total_mark':   total_mark,
        'performances': performances,
        'search':       search,
    })


# =============================================================================
# 4.  PERFORMANCE STUDENT EDIT
#     Edit marks_obtained + comment for a single student on one subject.
#     Recalculates passed / tried on the linked EntryStatus after every save.
# =============================================================================

@login_required
def performance_student_edit(request, pk, ac_pk, as_pk, perf_pk):
    assessment  = get_object_or_404(Assessment,          pk=pk)
    ac          = get_object_or_404(AssessmentClass,     pk=ac_pk,   assessment=assessment)
    as_subj     = get_object_or_404(AssessmentSubject,   pk=as_pk,   assessment=assessment)
    performance = get_object_or_404(AssessmentPerformance, pk=perf_pk, assessment=assessment)
    mod         = _get_or_create_mod(assessment)

    total_mark = AssessmentTotalMark.objects.filter(
        assessment=assessment,
        subject=as_subj,
    ).first()

    errors = {}

    if request.method == 'POST':
        marks_raw = (request.POST.get('marks_obtained') or '').strip()
        comment   = (request.POST.get('comment') or '').strip()

        # ── Validate marks ────────────────────────────────────────────────────
        if not marks_raw:
            errors['marks_obtained'] = 'Marks obtained is required.'
        else:
            try:
                mark = Decimal(marks_raw)
                if mark < 0:
                    raise ValueError('Negative mark not allowed.')
                if total_mark and mark > total_mark.total_mark:
                    errors['marks_obtained'] = (
                        f'Mark {mark} exceeds the total mark of {total_mark.total_mark}.'
                    )
            except (ValueError, InvalidOperation):
                errors['marks_obtained'] = 'Enter a valid positive number.'

        if not errors:
            with transaction.atomic():
                performance.marks_obtained = marks_raw
                performance.comment        = comment
                performance.entered_by     = request.user
                performance.save(update_fields=['marks_obtained', 'comment', 'entered_by'])

                # ── Recalculate entry_status passed / tried ───────────────────
                entry_status = AssessmentPerformanceEntryStatus.objects.filter(
                    assessment=assessment,
                    school_class=ac,
                    subject=as_subj,
                ).first()

                if entry_status:
                    passmark = as_subj.passmark
                    passed   = AssessmentPerformance.objects.filter(
                        assessment=assessment,
                        school_class=ac.school_class,
                        subject=as_subj.subject,
                        marks_obtained__gte=passmark,
                    ).count()
                    tried    = AssessmentPerformance.objects.filter(
                        assessment=assessment,
                        school_class=ac.school_class,
                        subject=as_subj.subject,
                        marks_obtained__lt=passmark,
                    ).count()
                    entry_status.students_passed = passed
                    entry_status.students_tried  = tried
                    entry_status.save(update_fields=['students_passed', 'students_tried'])

            messages.success(
                request,
                (
                    f'Performance for {performance.student.first_name} '
                    f'{performance.student.last_name} updated successfully.'
                )
            )
            return redirect(
                reverse('assessments:performance_class_subject', args=[pk, ac_pk, as_pk])
            )

    return render(request, 'assessments/display/performance_student_edit.html', {
        'assessment':  assessment,
        'ac':          ac,
        'as_subj':     as_subj,
        'performance': performance,
        'total_mark':  total_mark,
        'mod':         mod,
        'errors':      errors,
        'post':        request.POST if request.method == 'POST' else {},
    })
