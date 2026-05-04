# assessments/assessment_performance_entry_views.py
# ─────────────────────────────────────────────────────────────────────────────
# Views:
#   enable_assessment_performance_entry  (pk = assessment pk)
#   disable_assessment_performance_entry (pk = assessment pk)
#   assessment_performance_list          (pk = assessment pk)
#   assessment_performance_detail        (pk = assessment pk, student = student_id str)
#
# Rules followed:
#   • Function-based views only
#   • No Django Forms / forms.py
#   • No class-based views
#   • No JSON responses
#   • @login_required on every view
#   • transaction.atomic() wrapping all saves
#   • django.contrib.messages for all feedback
# ─────────────────────────────────────────────────────────────────────────────

from django.shortcuts               import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib                 import messages
from django.db                      import transaction
from django.urls                    import reverse
from django.contrib.auth import authenticate

from students.models import Student

from .models import (
    Assessment,
    AssessmentClass,
    AssessmentSubject,
    AssessmentPerformance,
    AssessmentModification,
    AssessmentPerformanceEntryStatus,
)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helper — reused across all four views
# ─────────────────────────────────────────────────────────────────────────────

def _get_or_create_mod(assessment):
    mod, _ = AssessmentModification.objects.get_or_create(
        assessment=assessment,
        defaults={'modify_class': True},
    )
    return mod


# =============================================================================
# 1. Enable Performance Entry
# =============================================================================

@login_required
def enable_assessment_performance_entry(request, pk):
    """
    GET  → renders a password-confirmation page before enabling entry.
    POST → validates password, then opens performance entry by setting
           mod.modify_performance = True.

    Guards:
      • Assessment must have at least one class assigned (Step 1 done).
      • Assessment must have at least one subject assigned (Step 2 done).
      • Entry must not already be open.
    """
    assessment = get_object_or_404(Assessment, pk=pk)

    # ── Guard: classes must be assigned ──────────────────────────────────────
    has_classes = AssessmentClass.objects.filter(assessment=assessment).exists()
    if not has_classes:
        messages.error(
            request,
            'Cannot enable performance entry: no classes have been assigned to this assessment yet.'
        )
        return redirect(reverse('assessments:detail', args=[pk]))

    # ── Guard: subjects must be assigned ─────────────────────────────────────
    has_subjects = AssessmentSubject.objects.filter(assessment=assessment).exists()
    if not has_subjects:
        messages.error(
            request,
            'Cannot enable performance entry: no subjects have been assigned to this assessment yet.'
        )
        return redirect(reverse('assessments:detail', args=[pk]))

    mod = _get_or_create_mod(assessment)

    # ── Guard: already open ───────────────────────────────────────────────────
    if mod.modify_performance:
        messages.info(request, 'Performance entry is already open for this assessment.')
        return redirect(reverse('assessments:performance_list', args=[pk]))

    # ── GET: show confirmation + auth page ────────────────────────────────────
    if request.method == 'GET':
        return render(request, 'assessments/confirm_performance_entry.html', {
            'assessment': assessment,
            'action': 'enable',
            'action_label': 'Enable Performance Entry',
            'action_description': f'This will open mark entry for "{assessment.title}". Teachers will be able to begin entering marks immediately.',
            'confirm_url': reverse('assessments:performance_enable', args=[pk]),
            'cancel_url': reverse('assessments:detail', args=[pk]),
            'danger': False,
        })

    # ── POST: validate password then execute ──────────────────────────────────
    password = request.POST.get('password', '')
    user = authenticate(request, username=request.user.username, password=password)
    if user is None:
        messages.error(request, 'Incorrect password. Please try again.')
        return render(request, 'assessments/confirm_performance_entry.html', {
            'assessment': assessment,
            'action': 'enable',
            'action_label': 'Enable Performance Entry',
            'action_description': f'This will open mark entry for "{assessment.title}". Teachers will be able to begin entering marks immediately.',
            'confirm_url': reverse('assessments:performance_enable', args=[pk]),
            'cancel_url': reverse('assessments:detail', args=[pk]),
            'danger': False,
            'auth_error': True,
        })

    with transaction.atomic():
        mod.modify_performance = True
        mod.save(update_fields=['modify_performance'])

    messages.success(
        request,
        f'Performance entry is now OPEN for "{assessment.title}". '
        f'Teachers can begin entering marks.'
    )
    return redirect(reverse('assessments:performance_list', args=[pk]))


# =============================================================================
# 2. Disable Performance Entry
# =============================================================================

@login_required
def disable_assessment_performance_entry(request, pk):
    """
    GET  → renders a password-confirmation page before disabling entry.
    POST → validates password, then closes performance entry by setting
           mod.modify_performance = False.

    Also clears is_edit_allowed on every EntryStatus row that still has it
    set, so no stray edit windows remain open.
    """
    assessment = get_object_or_404(Assessment, pk=pk)

    mod = _get_or_create_mod(assessment)

    if not mod.modify_performance:
        messages.info(request, 'Performance entry is already closed for this assessment.')
        return redirect(reverse('assessments:performance_list', args=[pk]))

    # ── GET: show confirmation + auth page ────────────────────────────────────
    if request.method == 'GET':
        return render(request, 'assessments/confirm_performance_entry.html', {
            'assessment': assessment,
            'action': 'disable',
            'action_label': 'Disable Performance Entry',
            'action_description': f'This will CLOSE mark entry for "{assessment.title}". All open per-subject edit windows will also be closed. Teachers will no longer be able to enter marks.',
            'confirm_url': reverse('assessments:performance_disable', args=[pk]),
            'cancel_url': reverse('assessments:performance_list', args=[pk]),
            'danger': True,
        })

    # ── POST: validate password then execute ──────────────────────────────────
    password = request.POST.get('password', '')
    user = authenticate(request, username=request.user.username, password=password)
    if user is None:
        messages.error(request, 'Incorrect password. Please try again.')
        return render(request, 'assessments/confirm_performance_entry.html', {
            'assessment': assessment,
            'action': 'disable',
            'action_label': 'Disable Performance Entry',
            'action_description': f'This will CLOSE mark entry for "{assessment.title}". All open per-subject edit windows will also be closed. Teachers will no longer be able to enter marks.',
            'confirm_url': reverse('assessments:performance_disable', args=[pk]),
            'cancel_url': reverse('assessments:performance_list', args=[pk]),
            'danger': True,
            'auth_error': True,
        })

    with transaction.atomic():
        mod.modify_performance = False
        mod.save(update_fields=['modify_performance'])

        # Close any lingering per-subject edit windows
        AssessmentPerformanceEntryStatus.objects.filter(
            assessment=assessment,
            is_edit_allowed=True,
        ).update(is_edit_allowed=False)

    messages.success(
        request,
        f'Performance entry is now CLOSED for "{assessment.title}".'
    )
    return redirect(reverse('assessments:performance_list', args=[pk]))

# =============================================================================
# 3. Performance Entry Status List
# =============================================================================

@login_required
def assessment_performance_list(request, pk):
    """
    Displays a progress overview for performance entry:

      • Groups AssessmentPerformanceEntryStatus rows by class.
      • For each class → each subject: shows students_entered / students_attended,
        is_done flag, is_edit_allowed flag.
      • Provides summary totals per class (total subjects, done subjects).
      • Shows whether performance entry is currently open (mod.modify_performance).

    No POST handling — all actions (enable/disable) hit their own views.
    """
    assessment = get_object_or_404(Assessment, pk=pk)
    mod        = _get_or_create_mod(assessment)

    # ── Fetch all classes for this assessment ─────────────────────────────────
    assessment_classes = list(
        AssessmentClass.objects
        .filter(assessment=assessment)
        .select_related('school_class__supported_class')
        .order_by('school_class__supported_class__order')
    )

    # ── Build grouped data: one row per class, listing subject statuses ───────
    class_groups = []

    for ac in assessment_classes:

        # All entry-status rows for this class
        statuses = list(
            AssessmentPerformanceEntryStatus.objects
            .filter(assessment=assessment, school_class=ac)
            .select_related('subject__subject')          # subject → AssessmentSubject → Subject
            .order_by('subject__subject__name')
        )

        total_subjects = len(statuses)
        done_subjects  = sum(1 for s in statuses if s.is_done)
        total_attended = sum(s.students_attended for s in statuses)
        total_entered  = sum(s.students_entered  for s in statuses)

        # Progress percentage for the class (avoid division by zero)
        if total_attended > 0:
            class_progress_pct = int((total_entered / total_attended) * 100)
        else:
            class_progress_pct = 0

        class_groups.append({
            'ac':                ac,
            'class_name':        ac.school_class.supported_class.name,
            'statuses':          statuses,
            'total_subjects':    total_subjects,
            'done_subjects':     done_subjects,
            'total_attended':    total_attended,
            'total_entered':     total_entered,
            'class_progress_pct': class_progress_pct,
            'all_done':          total_subjects > 0 and done_subjects == total_subjects,
        })

    # ── Overall assessment-level totals ───────────────────────────────────────
    all_statuses   = AssessmentPerformanceEntryStatus.objects.filter(assessment=assessment)
    overall_total  = all_statuses.count()
    overall_done   = all_statuses.filter(is_done=True).count()
    overall_pct    = int((overall_done / overall_total) * 100) if overall_total else 0

    ctx = {
        'assessment':    assessment,
        'mod':           mod,
        'class_groups':  class_groups,
        'overall_total': overall_total,
        'overall_done':  overall_done,
        'overall_pct':   overall_pct,
    }
    return render(request, 'assessments/assessment_performance_list.html', ctx)


# =============================================================================
# 4. Performance Detail — per student
# =============================================================================

@login_required
def assessment_performance_detail(request, pk, student):
    """
    Shows all AssessmentPerformance records for a single student
    within a given assessment.

    URL kwarg `student` is the student_id string (uppercased before lookup).

    Displays:
      • Student card (name, ID, current class)
      • One row per subject: subject name, marks obtained, total mark,
        pass mark, passed/failed, comment, entered_by, entered_at
      • Aggregate: total marks obtained, average, subjects passed
    """
    assessment = get_object_or_404(Assessment, pk=pk)

    # ── Resolve student ───────────────────────────────────────────────────────
    student_id = (student or '').strip().upper()
    student_obj = Student.objects.filter(student_id=student_id).first()

    if not student_obj:
        messages.error(request, f'No student found with ID "{student_id}".')
        return redirect(reverse('assessments:performance_list', args=[pk]))

    # ── Guard: student must be in one of this assessment's classes ────────────
    assessment_class_pks = set(
        AssessmentClass.objects
        .filter(assessment=assessment)
        .values_list('school_class_id', flat=True)
    )
    if student_obj.current_class_id not in assessment_class_pks:
        messages.error(
            request,
            f'Student {student_id} is not enrolled in any class that sits this assessment.'
        )
        return redirect(reverse('assessments:performance_list', args=[pk]))

    # ── Fetch performance records ─────────────────────────────────────────────
    performances = list(
        AssessmentPerformance.objects
        .filter(assessment=assessment, student=student_obj)
        .select_related('subject', 'assessment_subject', 'school_class__supported_class', 'entered_by')
        .order_by('subject__name')
    )

    # ── Build subject rows with pass/fail context ─────────────────────────────
    # We pull the AssessmentSubject for each record to get the passmark
    subject_rows = []
    total_obtained = 0
    subjects_passed = 0

    # Build a map: subject_id → AssessmentSubject (for passmark lookup)
    student_class_subjects = AssessmentSubject.objects.filter(
        assessment=assessment,
        assessment_class=student_obj.current_class,
    ).select_related('subject')

    passmark_map = {asub.subject_id: asub for asub in student_class_subjects}

    for perf in performances:
        asub     = passmark_map.get(perf.subject_id)
        passmark = asub.passmark if asub else None

        try:
            from decimal import Decimal
            obtained = Decimal(str(perf.marks_obtained)) if perf.marks_obtained is not None else None
        except Exception:
            obtained = None

        passed = None
        if obtained is not None and passmark is not None:
            passed = obtained >= passmark

        if obtained is not None:
            total_obtained += obtained
        if passed:
            subjects_passed += 1

        subject_rows.append({
            'perf':         perf,
            'subject_name': perf.subject.name,
            'subject_code': perf.subject.code,
            'obtained':     obtained,
            'passmark':     passmark,
            'passed':       passed,
        })

    # ── Aggregate ─────────────────────────────────────────────────────────────
    total_subjects = len(subject_rows)
    average = (total_obtained / total_subjects) if total_subjects else 0

    ctx = {
        'assessment':      assessment,
        'student':         student_obj,
        'subject_rows':    subject_rows,
        'total_subjects':  total_subjects,
        'subjects_passed': subjects_passed,
        'total_obtained':  total_obtained,
        'average':         round(average, 1),
    }
    return render(request, 'assessments/assessment_performance_detail.html', ctx)
