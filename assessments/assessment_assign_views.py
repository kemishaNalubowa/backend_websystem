# assessments/assessment_assign_views.py  ── step-gated assignment views
# ─────────────────────────────────────────────────────────────────────────────
# Step flow (all guarded so each step requires the previous one to be done):
#   1. add_assessment_class          → which classes sit this assessment
#   2. add_assessment_subject        → which subjects (per class) + pass mark
#   3. add_assessment_total_marks    → max marks per subject
#   4. add_assessment_teacher        → link a teacher per subject per class
#   5. activate_performance_entry    → open the assessment for mark entry
#   6. enter_student_performance     → redirect to the performance entry wizard
#   7. publish_assessment            → publish results to parents
# ─────────────────────────────────────────────────────────────────────────────

from django.shortcuts               import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib                 import messages
from django.db                      import transaction
from django.urls                    import reverse

from academics.models   import ClassSubject, SchoolSupportedClasses
from accounts.models    import StaffProfile
from authentication.models import CustomUser
from academics.base     import TEACHING_STAFF_ROLES
from academics.models   import TeacherSubject, TeacherClass
from permissions.decorators import has_permission

from .models import (
    Assessment,
    AssessmentClass,
    AssessmentSubject,
    AssessmentTeacher,
    AssessmentModification,
)
from academics.utils.subject_utils import get_sch_supported_classes


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_teaching_staff():
    """Return CustomUser objects for every teaching-role staff member."""
    result = []
    for sp in StaffProfile.objects.select_related('user').filter(role__in=TEACHING_STAFF_ROLES):
        result.append(sp.user)
    return result


def _parse_pos_int(raw, label, errors, key):
    """Parse a positive integer; append to errors dict on failure."""
    raw = (raw or '').strip()
    if not raw:
        errors[key] = f'{label} is required.'
        return None
    try:
        val = int(raw)
        if val < 0:
            raise ValueError
        return val
    except (ValueError, TypeError):
        errors[key] = f'{label} must be a valid whole number.'
        return None


def _parse_pos_decimal(raw, label, errors, key):
    """Parse a positive decimal; append to errors dict on failure."""
    from decimal import Decimal, InvalidOperation
    raw = (raw or '').strip()
    if not raw:
        errors[key] = f'{label} is required.'
        return None
    try:
        val = Decimal(raw)
        if val <= 0:
            raise ValueError
        return val
    except (InvalidOperation, ValueError):
        errors[key] = f'{label} must be a valid positive number.'
        return None


# =============================================================================
# STEP 1 — Assign Classes
# =============================================================================

@login_required
@has_permission('assign_class_to_assessment', action='create')
def add_assessment_class(request, pk):
    """
    Show every school-supported class as a card with a checkbox and an
    attendance-count input.  On POST validate and create AssessmentClass rows.

    Re-visiting this page is allowed: existing records are shown and
    the form pre-excludes already-linked classes so duplicates are impossible.
    """
    assessment = get_object_or_404(Assessment, pk=pk)

    supported_classes   = get_sch_supported_classes()
    already_linked_pks  = set(
        AssessmentClass.objects
        .filter(assessment=assessment)
        .values_list('school_class_id', flat=True)
    )

    # Only offer classes not already linked
    available_classes = [sc for sc in supported_classes
                         if sc.pk not in already_linked_pks]

    # Current links (for display)
    existing_classes = (
        AssessmentClass.objects
        .filter(assessment=assessment)
        .select_related('school_class__supported_class')
        .order_by('school_class__supported_class__order')
    )

    if request.method == 'POST':
        errors   = {}
        selected = []  # list of { 'sc': SchoolSupportedClasses, 'attended': int }

        for sc in available_classes:
            key      = sc.supported_class.key.lower()
            checked  = request.POST.get(f'class_{key}')          # checkbox value = sc.pk
            attended = request.POST.get(f'attended_{key}', '')

            if not checked:
                continue   # not selected — skip

            attended_val = _parse_pos_int(
                attended,
                f'{sc.supported_class.name} — Students Attended',
                errors,
                f'attended_{key}',
            )
            if attended_val is None:
                continue

            selected.append({'sc': sc, 'attended': attended_val})

        if not selected and not errors:
            messages.error(request, 'Please select at least one class.')
            return redirect(reverse('assessments:add_class', args=[pk]))

        if errors:
            messages.error(request, 'Please correct the highlighted errors.')
            ctx = {
                'assessment':       assessment,
                'available_classes': available_classes,
                'existing_classes': existing_classes,
                'errors':           errors,
                'post':             request.POST,
            }
            return render(request, 'assessments/add_assessment_class.html', ctx)

        with transaction.atomic():
            for item in selected:
                AssessmentClass.objects.create(
                    assessment        = assessment,
                    school_class      = item['sc'],
                    students_attended = item['attended'],
                )

        total = len(selected)
        messages.success(
            request,
            f'{total} class{"es" if total != 1 else ""} added to "{assessment.title}".'
        )
        return redirect(reverse('assessments:add_subject', args=[pk]))

    ctx = {
        'assessment':        assessment,
        'available_classes': available_classes,
        'existing_classes':  existing_classes,
        'errors':            {},
        'post':              {},
    }
    return render(request, 'assessments/add_assessment_class.html', ctx)


# =============================================================================
# STEP 2 — Assign Subjects
# =============================================================================

@login_required
@has_permission('assign_subject_to_assessment', action='create')
def add_assessment_subject(request, pk):
    """
    For each class already linked to the assessment, show that class's
    curriculum subjects (from ClassSubject).  Staff tick which subjects
    are being assessed and set a pass mark for each.

    Guard: assessment must have at least one class linked first.
    """
    assessment = get_object_or_404(Assessment, pk=pk)

    assessment_classes = (
        AssessmentClass.objects
        .filter(assessment=assessment)
        .select_related('school_class__supported_class')
        .order_by('school_class__supported_class__order')
    )

    if not assessment_classes.exists():
        messages.error(
            request,
            'Please assign classes to this assessment first (Step 1).'
        )
        return redirect(reverse('assessments:add_class', args=[pk]))

    # Build the structure: list of { 'ac': AssessmentClass, 'subjects': [...Subject...] }
    already_linked_subject_pks = set(
        AssessmentSubject.objects
        .filter(assessment=assessment)
        .values_list('subject_id', flat=True)
    )

    class_subject_groups = []
    for ac in assessment_classes:
        subjects = (
            ClassSubject.objects
            .filter(school_class=ac.school_class)
            .select_related('subject')
            .order_by('subject__name')
        )
        available = [cs for cs in subjects
                     if cs.subject_id not in already_linked_subject_pks]
        class_subject_groups.append({
            'ac':       ac,
            'subjects': available,
        })

    # Existing assessment subjects (for display)
    existing_subjects = (
        AssessmentSubject.objects
        .filter(assessment=assessment)
        .select_related('subject')
        .order_by('subject__name')
    )

    if request.method == 'POST':
        errors  = {}
        to_save = []   # list of { 'subject': Subject, 'passmark': Decimal, 'notes': str }

        for group in class_subject_groups:
            for cs in group['subjects']:
                subj    = cs.subject
                key     = f'{group["ac"].school_class.supported_class.key}_{subj.code}'.lower()
                checked = request.POST.get(f'subject_{key}')

                if not checked:
                    continue   # not selected

                passmark = _parse_pos_decimal(
                    request.POST.get(f'passmark_{key}', ''),
                    f'{subj.code} — Pass Mark',
                    errors,
                    f'passmark_{key}',
                )
                notes = (request.POST.get(f'notes_{key}', '') or '').strip()[:200]

                if passmark is not None:
                    to_save.append({
                        'subject':  subj,
                        'passmark': passmark,
                        'notes':    notes,
                    })

        if not to_save and not errors:
            messages.error(request, 'Please select at least one subject.')
            return redirect(reverse('assessments:add_subject', args=[pk]))

        if errors:
            messages.error(request, 'Please correct the highlighted errors.')
            ctx = {
                'assessment':          assessment,
                'class_subject_groups': class_subject_groups,
                'existing_subjects':   existing_subjects,
                'errors':              errors,
                'post':                request.POST,
            }
            return render(request, 'assessments/add_assessment_subject.html', ctx)

        with transaction.atomic():
            for item in to_save:
                # Guard against concurrent duplicates
                AssessmentSubject.objects.get_or_create(
                    assessment = assessment,
                    subject    = item['subject'],
                    defaults   = {
                        'passmark': item['passmark'],
                        'notes':    item['notes'],
                    },
                )

        total = len(to_save)
        messages.success(
            request,
            f'{total} subject{"s" if total != 1 else ""} added to "{assessment.title}".'
        )
        return redirect(reverse('assessments:add_total_marks', args=[pk]))

    ctx = {
        'assessment':           assessment,
        'class_subject_groups': class_subject_groups,
        'existing_subjects':    existing_subjects,
        'errors':               {},
        'post':                 {},
    }
    return render(request, 'assessments/add_assessment_subject.html', ctx)


# =============================================================================
# STEP 3 — Set Total Marks
# =============================================================================

@login_required
@has_permission('assign_subject_to_assessment', action='create')
def add_assessment_total_marks(request, pk):
    """
    For each AssessmentSubject already linked to this assessment, allow
    staff to set the maximum (total) marks available.

    This updates the AssessmentSubject.total_marks field.
    NOTE: your AssessmentSubject model needs a `total_marks` DecimalField.
    If you are reusing `passmark` as total_marks (as per your model's help_text)
    then swap the field name below.

    Guard: assessment must have at least one subject linked first.
    """
    assessment = get_object_or_404(Assessment, pk=pk)

    assessment_subjects = (
        AssessmentSubject.objects
        .filter(assessment=assessment)
        .select_related('subject')
        .order_by('subject__name')
    )

    if not assessment_subjects.exists():
        messages.error(
            request,
            'Please assign subjects to this assessment first (Step 2).'
        )
        return redirect(reverse('assessments:add_subject', args=[pk]))

    if request.method == 'POST':
        errors  = {}
        to_save = []   # list of { 'as_subj': AssessmentSubject, 'total': Decimal }

        for as_subj in assessment_subjects:
            field_key = f'total_mark_{as_subj.pk}'
            total = _parse_pos_decimal(
                request.POST.get(field_key, ''),
                f'{as_subj.subject.code} — Total Marks',
                errors,
                field_key,
            )
            if total is not None:
                to_save.append({'as_subj': as_subj, 'total': total})

        if errors:
            messages.error(request, 'Please correct the highlighted errors.')
            ctx = {
                'assessment':         assessment,
                'assessment_subjects': assessment_subjects,
                'errors':             errors,
                'post':               request.POST,
            }
            return render(request, 'assessments/add_assessment_total_marks.html', ctx)

        with transaction.atomic():
            for item in to_save:
                item['as_subj'].total_marks = item['total']
                item['as_subj'].save(update_fields=['total_marks'])

        messages.success(
            request,
            f'Total marks set for {len(to_save)} subject(s) in "{assessment.title}".'
        )
        return redirect(reverse('assessments:add_teacher', args=[pk]))

    ctx = {
        'assessment':          assessment,
        'assessment_subjects': assessment_subjects,
        'errors':              {},
        'post':                {},
    }
    return render(request, 'assessments/add_assessment_total_marks.html', ctx)


# =============================================================================
# STEP 4 — Assign Teachers
# =============================================================================

@login_required
@has_permission('assign_teacher_to_assessment', action='create')
def add_assessment_teacher(request, pk):
    """
    For each (class × subject) pair in the assessment, allow staff to
    assign the responsible teacher from the pool of teachers who are
    already linked to that class via TeacherClass and TeacherSubject.

    Guard: assessment must have subjects linked first.
    """
    assessment = get_object_or_404(Assessment, pk=pk)

    assessment_classes = (
        AssessmentClass.objects
        .filter(assessment=assessment)
        .select_related('school_class__supported_class')
        .order_by('school_class__supported_class__order')
    )
    assessment_subjects = (
        AssessmentSubject.objects
        .filter(assessment=assessment)
        .select_related('subject')
    )

    if not assessment_subjects.exists():
        messages.error(
            request,
            'Please assign subjects to this assessment first (Step 2).'
        )
        return redirect(reverse('assessments:add_subject', args=[pk]))

    # Already assigned pairs (assessment + teacher + subject + class)
    already_assigned = set(
        AssessmentTeacher.objects
        .filter(assessment=assessment)
        .values_list('teacher_id', 'subject_id', 'school_class_id')
    )

    # Build slot grid: one slot per (class, subject) pair
    # Each slot holds the candidate teachers for that pairing.
    slots = []
    for ac in assessment_classes:
        # Teachers linked to this class
        class_teacher_links = (
            TeacherClass.objects
            .filter(school_class=ac.school_class, is_active=True)
            .select_related('teacher')
        )
        class_teacher_users = {tc.teacher for tc in class_teacher_links}

        for as_subj in assessment_subjects:
            # Teachers for this subject in this class
            subject_teacher_links = (
                TeacherSubject.objects
                .filter(
                    school_class = ac.school_class,
                    subject      = as_subj.subject,
                )
                .select_related('teacher')
            )
            candidates = [
                ts.teacher for ts in subject_teacher_links
                if ts.teacher in class_teacher_users
            ]

            # Fall back: any teacher linked to the class if no subject-specific found
            if not candidates:
                candidates = list(class_teacher_users)

            slot_key = (
                f'{ac.school_class.supported_class.key}_'
                f'{as_subj.subject.code}'
            ).lower()

            slots.append({
                'ac':         ac,
                'as_subj':    as_subj,
                'candidates': candidates,
                'slot_key':   slot_key,
            })

    if request.method == 'POST':
        errors  = {}
        to_save = []

        for slot in slots:
            field_key  = f'teacher_{slot["slot_key"]}'
            teacher_pk = (request.POST.get(field_key) or '').strip()

            if not teacher_pk:
                # Optional: skip unselected slots (admin may leave some blank)
                continue

            try:
                teacher = CustomUser.objects.get(pk=teacher_pk, is_active=True)
            except CustomUser.DoesNotExist:
                errors[field_key] = 'Selected teacher not found or is inactive.'
                continue

            triple = (teacher.pk, slot['as_subj'].subject_id, slot['ac'].school_class_id)
            if triple in already_assigned:
                continue   # already linked — silently skip

            to_save.append({
                'teacher':      teacher,
                'subject':      slot['as_subj'].subject,
                'school_class': slot['ac'].school_class,
            })

        if errors:
            messages.error(request, 'Please correct the highlighted errors.')
            ctx = {
                'assessment': assessment,
                'slots':      slots,
                'errors':     errors,
                'post':       request.POST,
            }
            return render(request, 'assessments/add_assessment_teacher.html', ctx)

        if not to_save:
            messages.warning(request, 'No new teacher assignments were submitted.')
            return redirect(reverse('assessments:detail', args=[pk]))

        with transaction.atomic():
            for item in to_save:
                AssessmentTeacher.objects.create(
                    assessment   = assessment,
                    teacher      = item['teacher'],
                    subject      = item['subject'],
                    school_class = item['school_class'],
                )

        messages.success(
            request,
            f'{len(to_save)} teacher assignment(s) saved for "{assessment.title}".'
        )
        return redirect(reverse('assessments:detail', args=[pk]))

    ctx = {
        'assessment': assessment,
        'slots':      slots,
        'errors':     {},
        'post':       {},
    }
    return render(request, 'assessments/add_assessment_teacher.html', ctx)


# =============================================================================
# STEP 5 — Activate Performance Entry
# =============================================================================

@login_required
@has_permission('open_performance_entry', action='toggle')
def activate_performance_entry(request, pk):
    """
    Toggle is_entry_active on the Assessment so teachers can begin
    entering student marks.

    Guard: assessment must have at least one teacher assigned (Step 4 done).
    POST-only action.
    """
    assessment = get_object_or_404(Assessment, pk=pk)

    has_teachers = (
        AssessmentTeacher.objects
        .filter(assessment=assessment)
        .exists()
    )
    if not has_teachers:
        messages.error(
            request,
            'Please assign teachers to this assessment first (Step 4).'
        )
        return redirect(reverse('assessments:add_teacher', args=[pk]))

    if request.method == 'POST':
        # Toggle the flag
        assessment.is_entry_active = not assessment.is_entry_active
        assessment.save(update_fields=['is_entry_active'])

        state = 'activated' if assessment.is_entry_active else 'deactivated'
        messages.success(
            request,
            f'Performance entry {state} for "{assessment.title}".'
        )
        return redirect(reverse('assessments:detail', args=[pk]))

    # GET — show a confirmation page
    return render(request, 'assessments/activate_performance_entry.html', {
        'assessment': assessment,
    })


# =============================================================================
# STEP 6 — Enter Student Performance (redirect to wizard)
# =============================================================================

@login_required
@has_permission('add_performance_entry', action='create')
def enter_student_performance(request, pk):
    """
    Gateway view that checks pre-conditions then redirects staff into
    the existing performance entry wizard (perf_entry_part1).

    Guard: assessment must have is_entry_active = True.
    """
    assessment = get_object_or_404(Assessment, pk=pk)

    if not assessment.is_entry_active:
        messages.error(
            request,
            'Performance entry is not active for this assessment. '
            'Please activate it first (Step 5).'
        )
        return redirect(reverse('assessments:detail', args=[pk]))

    # Redirect into the existing performance entry wizard
    return redirect(reverse('assessments:perf_entry_part1', args=[pk]))


# =============================================================================
# STEP 7 — Publish Assessment Results
# =============================================================================

@login_required
@has_permission('publish_assessment', action='toggle')
def publish_assessment(request, pk):
    """
    Toggle results_published so parent portal can see the marks.

    Guard: assessment should have at least one performance record entered.
    POST-only action.
    """
    from .models import AssessmentPerformance

    assessment = get_object_or_404(Assessment, pk=pk)

    has_performance = (
        AssessmentPerformance.objects
        .filter(assessment=assessment)
        .exists()
    )
    if not has_performance:
        messages.error(
            request,
            'No student performance records exist for this assessment. '
            'Please enter marks first (Step 6).'
        )
        return redirect(reverse('assessments:detail', args=[pk]))

    if request.method == 'POST':
        assessment.results_published = not assessment.results_published
        assessment.save(update_fields=['results_published'])

        state = 'published' if assessment.results_published else 'unpublished'
        messages.success(
            request,
            f'Results {state} for "{assessment.title}".'
        )
        return redirect(reverse('assessments:detail', args=[pk]))

    # GET — show a confirmation page
    return render(request, 'assessments/publish_assessment.html', {
        'assessment': assessment,
    })
