from django.shortcuts               import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib                 import messages
from django.db                      import transaction

from authentication.models import CustomUser
from accounts.models import StaffProfile
from academics.base import TEACHING_STAFF_ROLES
from academics.models import ClassSubject, AcademicYear
from academics.models import TeacherClass, TeacherSubject
from django.utils.timezone import now

from .models import (
    Assessment,
    AssessmentClass,
    AssessmentSubject,
    AssessmentTeacher,
    AssessmentTotalMark,
    AssessmentPerformance,
    AssessmentModification,
    AssessmentPerformanceEntryStatus,
    
    ASSESSMENT_TYPE_CHOICES,
    MONTH_CHOICES,
)
from .utils import (
    validate_assessment,
    validate_assessment_class,
    validate_assessment_subject,
    # validate_assessment_teacher,
    # validate_assessment_passmark,
    # validate_performance,
    build_performance_summary,
    # VALID_VENUE_CHOICES,
    # VALID_TEACHER_ROLES,
    # VALID_PASS_TYPES,
    # VALID_NURSERY_RATINGS,
)

from assessments.utils import is_month_in_range, is_range_overlaps_year, period_range_check
from academics.utils.subject_utils import get_sch_supported_classes
from django.urls import reverse
from students.models import Student



# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────
def get_teachers():
    staffs = StaffProfile.objects.all()
    teaching_staffs = [t for t in staffs if t.role in TEACHING_STAFF_ROLES]
    teachers = []
    for ts in teaching_staffs:
        tr = CustomUser.objects.filter(pk=ts.user.pk)
        for t in tr:
            teachers.append(t)
    return teachers




def get_select_context():
    """
    Returns context data needed across multiple add forms
    (dropdown lists for FK fields).
    """
    from academics.models import Term, SchoolSupportedClasses, Subject


    from accounts.models  import CustomUser

    return {
        'terms':         Term.objects.all(),
        'classes':       get_sch_supported_classes(),
        'subjects':      Subject.objects.all(),
        'teachers':      get_teachers(),
        'type_choices':  ASSESSMENT_TYPE_CHOICES,
        'month_choices': MONTH_CHOICES,
        # 'venue_choices': AssessmentClass.VENUE_CHOICES,
        # 'role_choices':  AssessmentTeacher.ROLE_CHOICES,
        # 'pass_types':    AssessmentPassMark.PASS_TYPE_CHOICES,
        # 'nursery_ratings': AssessmentPerformance.NURSERY_RATING_CHOICES,
    }


# =============================================================================
# 1. Assessment List
# =============================================================================

@login_required
def assessment_list(request):
    qs = Assessment.objects.select_related('term', 'created_by')

    # Filters
    type_filter   = request.GET.get('assessment_type', '').strip()
    status_filter = request.GET.get('status', '').strip()
    term_filter   = request.GET.get('term', '').strip()
    search        = request.GET.get('q', '').strip()

    if type_filter and type_filter in dict(ASSESSMENT_TYPE_CHOICES):
        qs = qs.filter(assessment_type=type_filter)

    if status_filter == 'published':
        qs = qs.filter(is_published=True)
    elif status_filter == 'unpublished':
        qs = qs.filter(is_published=False)
    elif status_filter == 'results_out':
        qs = qs.filter(results_published=True)

    if term_filter:
        qs = qs.filter(term_id=term_filter)

    if search:
        qs = qs.filter(title__icontains=search)

    from academics.models import Term
    return render(request, 'assessments/assessment_list.html', {
        'assessments':    qs,
        'type_choices':   ASSESSMENT_TYPE_CHOICES,
        'terms':          Term.objects.all(),
        'filter_type':    type_filter,
        'filter_status':  status_filter,
        'filter_term':    term_filter,
        'search':         search,
        'total':          qs.count(),
    })


# =============================================================================
# 2. Add Assessment
# =============================================================================
@login_required
def add_assessment(request):

    if request.method == 'POST':


        if request.POST.get('cancel') and request.POST.get('cancel') == 'true':
            request.session.pop('add_assessment_data', None)
            return redirect('assessments:list')
        
        
        title                 = request.POST.get('title', '').strip()
        assessment_type       = request.POST.get('assessment_type', '').strip()
        description           = request.POST.get('description', '').strip()
        term                  = request.POST.get('term', '').strip()
        month                 = request.POST.get('month', '').strip()
        date_given            = request.POST.get('date_given', '').strip()
        date_due              = request.POST.get('date_due', '').strip()
        date_results_released = request.POST.get('date_results_released', '').strip()

        request.session['add_assessment_data'] = {
            'title': title,
            'assessment_type': assessment_type,
            'description': description,
            'term': term,
            'month': month,
            'date_given': date_given,
            'date_due': date_due,
            'date_results_released': date_results_released,
        }

        # FIX 1: was `if not (title, ...)` — a tuple is always truthy; use all() instead
        if not all([title, assessment_type, term, month, date_given, date_due]):
            messages.error(request, 'Please fill in all required fields.')
            return redirect('assessments:add')
        
        if assessment_type not in dict(ASSESSMENT_TYPE_CHOICES):
            messages.error(request, 'Invalid assessment type selected.')
            return redirect('assessments:add')
        
        if int(month) not in dict(MONTH_CHOICES):
            messages.error(request, 'Invalid month selected.')
            return redirect('assessments:add')


        with transaction.atomic():
            assessment = Assessment.objects.create(
                title=title,
                assessment_type=assessment_type,
                description=description,
                term_id=term,
                month=month,
                date_given=date_given,
                date_due=date_due,
                date_results_released=date_results_released or None,
                created_by=request.user,
            )
            assessment.is_published = False
            assessment.results_published = False
            assessment.created_by = request.user
            assessment.save()


            # ← Create modification record with only class step open
            AssessmentModification.objects.create(
                assessment        = assessment,
                modify_class      = True,   # first step open
                modify_subject    = False,
                modify_total_mark = False,
                modify_teacher    = False,
                modify_performance = False,
                edit_once         = False,
            )

            request.session.pop('add_assessment_data', None)
            messages.success(request, f'Assessment "{assessment.title}" created successfully.')
            return redirect('assessments:detail', pk=assessment.pk)


    session_data = request.session.get('add_assessment_data', {})
    ctx = get_select_context()
    ctx.update({
        'post': session_data,
    })
    return render(request, 'assessments/add_assessment.html', ctx)
#=============================================================================
# 3. Edit Assessment
# =============================================================================

# @login_required
# def edit_assessment(request, pk):
#     assessment = get_object_or_404(Assessment, pk=pk)
#     ctx = _get_select_context()
#     ctx['assessment'] = assessment

#     if request.method == 'POST':
#         errors, cleaned = validate_assessment(request.POST, request.FILES)

#         if errors:
#             messages.error(request, 'Please correct the errors below.')
#             ctx.update({'errors': errors, 'post': request.POST})
#             return render(request, 'assessments/edit_assessment.html', ctx)

#         update_fields = [
#             'title', 'assessment_type', 'description', 'term',
#             'month', 'date_given', 'date_due', 'date_results_released',
#             'results_published', 'notes',
#         ]
#         with transaction.atomic():
#             for field in update_fields:
#                 if field in cleaned:
#                     setattr(assessment, field, cleaned[field])
#             for ffile in ('paper_file', 'marking_scheme'):
#                 if ffile in cleaned:
#                     setattr(assessment, ffile, cleaned[ffile])
#             assessment.save()

#         messages.success(request, f'Assessment "{assessment.title}" updated successfully.')
#         return redirect('assessments:detail', pk=assessment.pk)

#     ctx.update({'errors': {}, 'post': {}})
#     return render(request, 'assessments/edit_assessment.html', ctx)

# =============================================================================
# 4. Assessment Detail
# =============================================================================

@login_required
def assessment_detail(request, pk):
    assessment = get_object_or_404(
        Assessment.objects.select_related('term', 'term__academic_year', 'created_by'),
        pk=pk,
    )

    classes = assessment.assessment_classes.select_related(
        'school_class__supported_class'
    ).order_by('school_class__supported_class__order')

    subjects = assessment.assessment_subjects.select_related(
        'subject'
    ).order_by('subject__name')

    teachers = assessment.assessment_teachers.select_related(
        'teacher', 'subject', 'school_class'
    ).order_by('teacher__last_name')

    performances = assessment.performances.select_related(
        'student', 'subject', 'school_class',
        'entered_by', 'verified_by',
    ).order_by('student__last_name', 'student__first_name')

    summary = build_performance_summary(assessment)

    return render(request, 'assessments/assessment_detail.html', {
        'assessment':   assessment,
        'classes':      classes,
        'subjects':     subjects,
        'teachers':     teachers,
        'performances': performances,
        'summary':      summary,
    })

# =============================================================================
# 5. Delete Assessment
# =============================================================================

@login_required
def delete_assessment(request, pk):
    assessment = get_object_or_404(Assessment, pk=pk)

    if request.method == 'POST':
        title = assessment.title
        with transaction.atomic():
            assessment.delete()
        messages.success(request, f'Assessment "{title}" has been deleted.')
        return redirect('assessments:list')

    return render(request, 'assessments/confirm_delete_assessment.html', {
        'assessment': assessment,
    })


# =============================================================================
# 6. Change Assessment Status (publish / unpublish / release results)
# =============================================================================

@login_required
def change_assessment_status(request, pk):
    """
    Toggles is_published and/or results_published via a POST form.
    Expects POST fields: is_published ('on'/absent), results_published ('on'/absent)
    """
    if request.method != 'POST':
        return redirect('assessments:detail', pk=pk)

    assessment = get_object_or_404(Assessment, pk=pk)

    action = request.POST.get('action', '').strip()

    with transaction.atomic():
        if action == 'publish':
            assessment.is_published = True
            messages.success(request, f'"{assessment.title}" is now published to teachers.')
        elif action == 'unpublish':
            assessment.is_published = False
            messages.warning(request, f'"{assessment.title}" has been unpublished.')
        elif action == 'release_results':
            assessment.results_published = True
            messages.success(request, f'Results for "{assessment.title}" are now visible to parents.')
        elif action == 'hide_results':
            assessment.results_published = False
            messages.warning(request, f'Results for "{assessment.title}" have been hidden.')
        else:
            messages.error(request, 'Invalid status action.')
            return redirect('assessments:detail', pk=pk)
        assessment.save(update_fields=['is_published', 'results_published'])

    return redirect('assessments:detail', pk=pk)







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



def _get_or_create_mod(assessment):
    """Get or create the modification record for an assessment."""
    mod, _ = AssessmentModification.objects.get_or_create(
        assessment=assessment,
        defaults={'modify_class': True},
    )
    return mod

# =============================================================================
# STEP 1 — Assign Classes
# =============================================================================

# @login_required
# def add_assessment_class(request, pk):
#     """
#     Show every school-supported class as a card with a checkbox and an
#     attendance-count input.  On POST validate and create AssessmentClass rows.

#     Re-visiting this page is allowed: existing records are shown and
#     the form pre-excludes already-linked classes so duplicates are impossible.
#     """
#     assessment = get_object_or_404(Assessment, pk=pk)

#     supported_classes   = get_sch_supported_classes()
#     already_linked_pks  = set(
#         AssessmentClass.objects
#         .filter(assessment=assessment)
#         .values_list('school_class_id', flat=True)
#     )

#     # Only offer classes not already linked
#     available_classes = [sc for sc in supported_classes
#                          if sc.pk not in already_linked_pks]

#     # Current links (for display)
#     existing_classes = (
#         AssessmentClass.objects
#         .filter(assessment=assessment)
#         .select_related('school_class__supported_class')
#         .order_by('school_class__supported_class__order')
#     )

#     if request.method == 'POST':
#         errors   = {}
#         selected = []  # list of { 'sc': SchoolSupportedClasses, 'attended': int }

#         for sc in available_classes:
#             key      = sc.supported_class.key.lower()
#             checked  = request.POST.get(f'class_{key}')          # checkbox value = sc.pk
#             attended = request.POST.get(f'attended_{key}', '')

#             if not checked:
#                 continue   # not selected — skip

#             attended_val = _parse_pos_int(
#                 attended,
#                 f'{sc.supported_class.name} — Students Attended',
#                 errors,
#                 f'attended_{key}',
#             )
#             if attended_val is None:
#                 continue

#             selected.append({'sc': sc, 'attended': attended_val})

#         if not selected and not errors:
#             messages.error(request, 'Please select at least one class.')
#             return redirect(reverse('assessments:add_class', args=[pk]))

#         if errors:
#             messages.error(request, 'Please correct the highlighted errors.')
#             ctx = {
#                 'assessment':       assessment,
#                 'available_classes': available_classes,
#                 'existing_classes': existing_classes,
#                 'errors':           errors,
#                 'post':             request.POST,
#             }
#             return render(request, 'assessments/add_assessment_class.html', ctx)

#         with transaction.atomic():
#             for item in selected:
#                 AssessmentClass.objects.create(
#                     assessment        = assessment,
#                     school_class      = item['sc'],
#                     students_attended = item['attended'],
#                 )

#         total = len(selected)
#         messages.success(
#             request,
#             f'{total} class{"es" if total != 1 else ""} added to "{assessment.title}".'
#         )
#         return redirect(reverse('assessments:add_subject', args=[pk]))

#     ctx = {
#         'assessment':        assessment,
#         'available_classes': available_classes,
#         'existing_classes':  existing_classes,
#         'errors':            {},
#         'post':              {},
#     }
#     return render(request, 'assessments/add_assessment_class.html', ctx)


@login_required
def add_assessment_class(request, pk):
    assessment = get_object_or_404(Assessment, pk=pk)
    mod        = _get_or_create_mod(assessment)

    if not mod.modify_class:
        messages.error(request, 'Class assignment is not currently open for editing.')
        return redirect(reverse('assessments:detail', args=[pk]))

    supported_classes  = get_sch_supported_classes()

    # existing linked classes — for both display AND editing
    existing_classes = (
        AssessmentClass.objects
        .filter(assessment=assessment)
        .select_related('school_class__supported_class')
        .order_by('school_class__supported_class__order')
    )
    already_linked_pks = {ac.school_class_id for ac in existing_classes}

    # classes not yet linked — for adding new ones
    available_classes = [sc for sc in supported_classes
                         if sc.pk not in already_linked_pks]

    if request.method == 'POST':
        errors       = {}
        to_create    = []   # new AssessmentClass rows
        to_update    = []   # existing rows with updated attendance

        # ── Edit existing linked classes ───────────────────────────────
        for ac in existing_classes:
            key      = ac.school_class.supported_class.key.lower()
            attended = request.POST.get(f'edit_attended_{key}', '').strip()
            if not attended:
                continue   # left blank — skip, keep old value
            val = _parse_pos_int(
                attended,
                f'{ac.school_class.supported_class.name} — Students Attended',
                errors,
                f'edit_attended_{key}',
            )
            if val is not None:
                to_update.append({'ac': ac, 'attended': val})

        # ── Add new classes ────────────────────────────────────────────
        for sc in available_classes:
            key     = sc.supported_class.key.lower()
            checked = request.POST.get(f'class_{key}')
            if not checked:
                continue
            attended = request.POST.get(f'attended_{key}', '')
            val = _parse_pos_int(
                attended,
                f'{sc.supported_class.name} — Students Attended',
                errors,
                f'attended_{key}',
            )
            if val is not None:
                to_create.append({'sc': sc, 'attended': val})

        if not to_create and not to_update and not errors:
            messages.error(request, 'No changes were made.')
            return redirect(reverse('assessments:add_class', args=[pk]))

        if errors:
            messages.error(request, 'Please correct the highlighted errors.')
            ctx = {
                'assessment':        assessment,
                'available_classes': available_classes,
                'existing_classes':  existing_classes,
                'errors':            errors,
                'post':              request.POST,
                'mod':               mod,
            }
            return render(request, 'assessments/add_assessment_class.html', ctx)

        with transaction.atomic():
            for item in to_create:
                AssessmentClass.objects.create(
                    assessment        = assessment,
                    school_class      = item['sc'],
                    students_attended = item['attended'],
                )
            for item in to_update:
                item['ac'].students_attended = item['attended']
                item['ac'].save(update_fields=['students_attended'])

            # ── Modification state transition ──────────────────────────
            mod.modify_class = False
            if mod.edit_once:
                mod.close_edit_once_if_done()
                mod.save()
                messages.success(request, 'Classes updated.')
                return redirect(reverse('assessments:detail', args=[pk]))
            else:
                mod.modify_subject = True
                mod.save()

        total_changed = len(to_create) + len(to_update)
        messages.success(request, f'{total_changed} class record(s) saved.')
        return redirect(reverse('assessments:add_subject', args=[pk]))

    ctx = {
        'assessment':        assessment,
        'available_classes': available_classes,
        'existing_classes':  existing_classes,
        'errors':            {},
        'post':              {},
        'mod':               mod,
    }
    return render(request, 'assessments/add_assessment_class.html', ctx)

# =============================================================================
# STEP 2 — Assign Subjects
# =============================================================================

# @login_required
# def add_assessment_subject(request, pk):
#     """
#     For each class already linked to the assessment, show that class's
#     curriculum subjects (from ClassSubject).  Staff tick which subjects
#     are being assessed and set a pass mark for each.

#     Guard: assessment must have at least one class linked first.
#     """
#     assessment = get_object_or_404(Assessment, pk=pk)

#     assessment_classes = (
#         AssessmentClass.objects
#         .filter(assessment=assessment)
#         .select_related('school_class__supported_class')
#         .order_by('school_class__supported_class__order')
#     )

#     if not assessment_classes.exists():
#         messages.error(
#             request,
#             'Please assign classes to this assessment first (Step 1).'
#         )
#         return redirect(reverse('assessments:add_class', args=[pk]))



#     already_linked_subject_pks = set(
#         AssessmentSubject.objects
#         .filter(assessment=assessment)
#         .values_list('subject_id', flat=True)
#     )

#     class_subject_groups = []
#     for ac in assessment_classes:
#         subjects = (
#             ClassSubject.objects
#             .filter(school_class=ac.school_class)
#             .select_related('subject')
#             .order_by('subject__name')
#         )
#         class_subject_groups.append({          # ← uncomment this
#             'ac':       ac,
#             'subjects': list(subjects),        # ← no filtering, show ALL
#         })

#     # Existing assessment subjects (for display)
#     existing_subjects = (
#         AssessmentSubject.objects
#         .filter(assessment=assessment)
#         .select_related('subject')
#         .order_by('subject__name')
#     )

#     if request.method == 'POST':
#         print("POST DATA:", dict(request.POST))
#         errors  = {}
#         to_save = []

#         # print("class_subject_groups: ", class_subject_groups)
#         # messages.error(request, f'{class_subject_groups}')
#         # return redirect(reverse('assessments:add_subject', args=[pk]))


#         for group in class_subject_groups:
#             ac = group['ac']
#             print("GROUP AC:", ac, "| school_class:", ac.school_class, "| supported_class key:", ac.school_class.supported_class.key)


#             for cs in group['subjects']:
#                 subj     = cs.subject
#                 key      = f'{group["ac"].school_class.supported_class.key}_{subj.code}'.lower()
#                 passmark_raw = request.POST.get(f'passmark_{key}', '').strip()



#                 if AssessmentSubject.objects.filter(
#                     assessment=assessment,
#                     assessment_class=ac.school_class,
#                     subject=subj
#                     ).exists():
#                     continue


#                 if not passmark_raw:
#                     continue

#                 passmark = _parse_pos_decimal(
#                     passmark_raw,
#                     f'{subj.code} — Pass Mark',
#                     errors,
#                     f'passmark_{key}',
#                 )
#                 notes = (request.POST.get(f'notes_{key}', '') or '').strip()[:200]

#                 if passmark is not None:
#                     to_save.append({
#                         'ac':       ac,
#                         'subject':  subj,
#                         'passmark': passmark,
#                         'notes':    notes,
#                     })



#         # print("To Save: ", to_save)
#         # return redirect(reverse('assessments:add_subject', args=[pk]))


#         # print ('TO SAVE: ',to_save)
#         # messages.error(request, f'{to_save}')
#         # return redirect(reverse('assessments:add_subject', args=[pk]))


#         if not to_save and not errors:
#             messages.error(request, 'Please fill in a pass mark for at least one subject.')
#             return redirect(reverse('assessments:add_subject', args=[pk]))

#         if errors:
#             messages.error(request, 'Please correct the highlighted errors.')
#             ctx = {
#                 'assessment':                 assessment,
#                 'class_subject_groups':       class_subject_groups,
#                 'existing_subjects':          existing_subjects,
#                 'errors':                     errors,
#                 'post':                       request.POST,
#                 'already_linked_subject_pks': already_linked_subject_pks,
#             }
#             return render(request, 'assessments/add_assessment_subject.html', ctx)

#         with transaction.atomic():
#             for item in to_save:                          # ← no .values()
#                 AssessmentSubject.objects.get_or_create(
#                     assessment       = assessment,
#                     assessment_class = item['ac'].school_class,  # ← per class
#                     subject          = item['subject'],
#                     defaults={
#                         'passmark': item['passmark'],
#                         'notes':    item['notes'],
#                     },
#                 )

#         total = len(to_save)
#         messages.success(
#             request,
#             f'{total} subject{"s" if total != 1 else ""} added to "{assessment.title}".'
#         )
#         return redirect(reverse('assessments:add_total_marks', args=[pk]))


#     ctx = {
#         'assessment':           assessment,
#         'class_subject_groups': class_subject_groups,
#         'existing_subjects':    existing_subjects,
#         'errors':               {},
#         'post':                 {},
#         'already_linked_subject_pks': already_linked_subject_pks, 
#     }
#     return render(request, 'assessments/add_assessment_subject.html', ctx)

@login_required
def add_assessment_subject(request, pk):
    assessment = get_object_or_404(Assessment, pk=pk)
    mod        = _get_or_create_mod(assessment)

    if not mod.modify_subject:
        messages.error(request, 'Subject assignment is not currently open for editing.')
        return redirect(reverse('assessments:detail', args=[pk]))

    assessment_classes = list(
        AssessmentClass.objects
        .filter(assessment=assessment)
        .select_related('school_class__supported_class')
        .order_by('school_class__supported_class__order')
    )

    if not assessment_classes:
        messages.error(request, 'Please assign classes first (Step 1).')
        return redirect(reverse('assessments:add_class', args=[pk]))

    # Build groups — each class shows ALL its curriculum subjects
    # existing AssessmentSubject rows are included for editing
    class_subject_groups = []
    for ac in assessment_classes:
        curriculum_subjects = list(
            ClassSubject.objects
            .filter(school_class=ac.school_class)
            .select_related('subject')
            .order_by('subject__name')
        )
        # Map existing saved subjects for this class: subject_id → AssessmentSubject
        existing_map = {
            asub.subject_id: asub
            for asub in AssessmentSubject.objects.filter(
                assessment=assessment,
                assessment_class=ac.school_class,
            ).select_related('subject')
        }
        class_subject_groups.append({
            'ac':           ac,
            'subjects':     curriculum_subjects,
            'existing_map': existing_map,   # ← for pre-filling edit values
        })

    already_linked_subject_pks = set(
        AssessmentSubject.objects
        .filter(assessment=assessment)
        .values_list('subject_id', flat=True)
    )

    existing_subjects = (
        AssessmentSubject.objects
        .filter(assessment=assessment)
        .select_related('subject')
        .order_by('subject__name')
    )

    if request.method == 'POST':
        errors    = {}
        to_create = []
        to_update = []   # existing AssessmentSubject rows to update

        for group in class_subject_groups:
            ac           = group['ac']
            existing_map = group['existing_map']

            for cs in group['subjects']:
                subj         = cs.subject
                key          = f'{ac.school_class.supported_class.key}_{subj.code}'.lower()
                passmark_raw = request.POST.get(f'passmark_{key}', '').strip()
                notes        = (request.POST.get(f'notes_{key}', '') or '').strip()[:200]

                if not passmark_raw:
                    continue   # blank = not selected / no change

                passmark = _parse_pos_decimal(
                    passmark_raw, f'{subj.code} — Pass Mark',
                    errors, f'passmark_{key}',
                )
                if passmark is None:
                    continue

                if subj.pk in existing_map:
                    # ── Edit existing ──────────────────────────────────
                    asub = existing_map[subj.pk]
                    to_update.append({
                        'asub':     asub,
                        'passmark': passmark,
                        'notes':    notes,
                    })
                else:
                    # ── Add new ────────────────────────────────────────
                    to_create.append({
                        'ac':       ac,
                        'subject':  subj,
                        'passmark': passmark,
                        'notes':    notes,
                    })

        if not to_create and not to_update and not errors:
            messages.error(request, 'No changes were made.')
            return redirect(reverse('assessments:add_subject', args=[pk]))

        if errors:
            messages.error(request, 'Please correct the highlighted errors.')
            ctx = {
                'assessment':                 assessment,
                'class_subject_groups':       class_subject_groups,
                'existing_subjects':          existing_subjects,
                'already_linked_subject_pks': already_linked_subject_pks,
                'errors':                     errors,
                'post':                       request.POST,
                'mod':                        mod,
            }
            return render(request, 'assessments/add_assessment_subject.html', ctx)

        with transaction.atomic():


            for item in to_create:
                subject_obj,_ = AssessmentSubject.objects.get_or_create(
                    assessment       = assessment,
                    assessment_class = item['ac'].school_class,
                    subject          = item['subject'],
                    defaults={
                        'passmark': item['passmark'],
                        'notes':    item['notes'],
                    },
                )
                AssessmentPerformanceEntryStatus.objects.get_or_create(
                    assessment          =   assessment,
                    school_class        =   item['ac'],
                    subject             =   subject_obj,
                    students_attended   =   item['ac'].students_attended,  
                )
                

            for item in to_update:
                item['asub'].passmark = item['passmark']
                item['asub'].notes    = item['notes']
                item['asub'].save(update_fields=['passmark', 'notes'])

            mod.modify_subject = False
            if mod.edit_once:
                mod.close_edit_once_if_done()
                mod.save()
                total = len(to_create) + len(to_update)
                messages.success(request, f'{total} subject(s) saved.')
                return redirect(reverse('assessments:detail', args=[pk]))
            else:
                mod.modify_total_mark = True
                mod.save()

        total = len(to_create) + len(to_update)
        messages.success(request, f'{total} subject(s) saved.')
        return redirect(reverse('assessments:add_total_marks', args=[pk]))

    ctx = {
        'assessment':                 assessment,
        'class_subject_groups':       class_subject_groups,
        'existing_subjects':          existing_subjects,
        'already_linked_subject_pks': already_linked_subject_pks,
        'errors':                     {},
        'post':                       {},
        'mod':                        mod,
    }
    return render(request, 'assessments/add_assessment_subject.html', ctx)

# =============================================================================
# STEP 3 — Set Total Marks     
# =============================================================================

# @login_required
# def add_assessment_total_marks(request, pk):
#     """
#     For each AssessmentSubject already linked to this assessment, allow
#     staff to set the maximum (total) marks available.

#     This updates the AssessmentSubject.total_marks field.
#     NOTE: your AssessmentSubject model needs a `total_marks` DecimalField.
#     If you are reusing `passmark` as total_marks (as per your model's help_text)
#     then swap the field name below.

#     Guard: assessment must have at least one subject linked first.
#     """
#     assessment = get_object_or_404(Assessment, pk=pk)

#     assessment_subjects = (
#         AssessmentSubject.objects
#         .filter(assessment=assessment)
#         .select_related('subject')
#         .order_by('subject__name')
#     )

#     if not assessment_subjects.exists():
#         messages.error(
#             request,
#             'Please assign subjects to this assessment first (Step 2).'
#         )
#         return redirect(reverse('assessments:add_subject', args=[pk]))

#     if request.method == 'POST':
#         errors  = {}
#         to_save = []

#         for as_subj in assessment_subjects:
#             field_key = f'total_mark_{as_subj.pk}'
#             total = _parse_pos_decimal(
#                 request.POST.get(field_key, ''),
#                 f'{as_subj.subject.code} — Total Marks',
#                 errors,
#                 field_key,
#             )
#             if total is not None:
#                 # Total mark must be >= passmark
#                 if as_subj.passmark and total < as_subj.passmark:
#                     errors[field_key] = (
#                         f'Total marks ({total}) cannot be less than the pass mark ({as_subj.passmark}).'
#                     )
#                 else:
#                     to_save.append({'as_subj': as_subj, 'total': total})


#         # messages.error(request, f'{to_save}')
#         # return redirect(reverse('assessments:add_total_marks', args=[pk]))
    



#         if errors:
#             messages.error(request, 'Please correct the highlighted errors.')
#             ctx = {
#                 'assessment':          assessment,
#                 'assessment_subjects': assessment_subjects,
#                 'errors':              errors,
#                 'post':                request.POST,
#             }
#             return render(request, 'assessments/add_assessment_total_marks.html', ctx)

#         with transaction.atomic():
#             for item in to_save:
#                 AssessmentTotalMark.objects.get_or_create(
#                     assessment = assessment,
#                     subject    = item['as_subj'],
#                     defaults   = {
#                         'total_mark': item['total'],
#                     },
#                 )

#         messages.success(
#             request,
#             f'Total marks set for {len(to_save)} subject(s) in "{assessment.title}".'
#         )
#         return redirect(reverse('assessments:add_teacher', args=[pk]))

#     ctx = {
#         'assessment':          assessment,
#         'assessment_subjects': assessment_subjects,
#         'errors':              {},
#         'post':                {},
#     }
#     return render(request, 'assessments/add_assessment_total_marks.html', ctx)


@login_required
def add_assessment_total_marks(request, pk):
    assessment = get_object_or_404(Assessment, pk=pk)
    mod        = _get_or_create_mod(assessment)

    if not mod.modify_total_mark:
        messages.error(request, 'Total marks entry is not currently open for editing.')
        return redirect(reverse('assessments:detail', args=[pk]))

    assessment_subjects = list(
        AssessmentSubject.objects
        .filter(assessment=assessment)
        .select_related('subject', 'assessment_class')
        .order_by('subject__name')
    )

    if not assessment_subjects:
        messages.error(request, 'Please assign subjects first (Step 2).')
        return redirect(reverse('assessments:add_subject', args=[pk]))

    # Map existing total marks: AssessmentSubject pk → AssessmentTotalMark
    existing_total_marks = {
        tm.subject_id: tm
        for tm in AssessmentTotalMark.objects.filter(assessment=assessment)
    }

    if request.method == 'POST':
        errors    = {}
        to_create = []
        to_update = []

        for as_subj in assessment_subjects:
            field_key = f'total_mark_{as_subj.pk}'
            raw       = request.POST.get(field_key, '').strip()

            if not raw:
                continue   # blank — no change

            total = _parse_pos_decimal(
                raw, f'{as_subj.subject.code} — Total Marks',
                errors, field_key,
            )
            if total is None:
                continue

            if as_subj.passmark and total < as_subj.passmark:
                errors[field_key] = (
                    f'Total marks ({total}) cannot be less than '
                    f'the pass mark ({as_subj.passmark}).'
                )
                continue

            if as_subj.pk in existing_total_marks:
                # ── Edit existing ──────────────────────────────────────
                to_update.append({
                    'tm':    existing_total_marks[as_subj.pk],
                    'total': total,
                })
            else:
                # ── Add new ────────────────────────────────────────────
                to_create.append({'as_subj': as_subj, 'total': total})

        if not to_create and not to_update and not errors:
            messages.error(request, 'No changes were made.')
            return redirect(reverse('assessments:add_total_marks', args=[pk]))

        if errors:
            messages.error(request, 'Please correct the highlighted errors.')
            ctx = {
                'assessment':          assessment,
                'assessment_subjects': assessment_subjects,
                'existing_total_marks': existing_total_marks,
                'errors':              errors,
                'post':                request.POST,
                'mod':                 mod,
            }
            return render(request, 'assessments/add_assessment_total_marks.html', ctx)

        with transaction.atomic():
            for item in to_create:
                AssessmentTotalMark.objects.create(
                    assessment = assessment,
                    subject    = item['as_subj'],
                    total_mark = item['total'],
                )
            for item in to_update:
                item['tm'].total_mark = item['total']
                item['tm'].save(update_fields=['total_mark'])

            mod.modify_total_mark = False
            if mod.edit_once:
                mod.close_edit_once_if_done()
                mod.save()
                total_changed = len(to_create) + len(to_update)
                messages.success(request, f'Total marks updated for {total_changed} subject(s).')
                return redirect(reverse('assessments:detail', args=[pk]))
            else:
                mod.modify_teacher = True
                mod.save()

        total_changed = len(to_create) + len(to_update)
        messages.success(request, f'Total marks set for {total_changed} subject(s).')
        return redirect(reverse('assessments:add_teacher', args=[pk]))

    ctx = {
        'assessment':           assessment,
        'assessment_subjects':  assessment_subjects,
        'existing_total_marks': existing_total_marks,
        'errors':               {},
        'post':                 {},
        'mod':                  mod,
    }
    return render(request, 'assessments/add_assessment_total_marks.html', ctx)




# =============================================================================
# STEP 4 — Assign Teachers
# =============================================================================

# @login_required
# def add_assessment_teacher(request, pk):
#     """
#     For each (class × subject) pair in the assessment, allow staff to
#     assign the responsible teacher from the pool of teachers who are
#     already linked to that class via TeacherClass and TeacherSubject.

#     Guard: assessment must have subjects linked first.
#     """
#     assessment = get_object_or_404(Assessment, pk=pk)

#     assessment_classes = (
#         AssessmentClass.objects
#         .filter(assessment=assessment)
#         .select_related('school_class__supported_class')
#         .order_by('school_class__supported_class__order')
#     )
#     assessment_subjects = (
#         AssessmentSubject.objects
#         .filter(assessment=assessment)
#         .select_related('subject')
#     )

#     if not assessment_subjects.exists():
#         messages.error(
#             request,
#             'Please assign subjects to this assessment first (Step 2).'
#         )
#         return redirect(reverse('assessments:add_subject', args=[pk]))

#     # Already assigned pairs (assessment + teacher + subject + class)
#     already_assigned = set(
#         AssessmentTeacher.objects
#         .filter(assessment=assessment)
#         .values_list('teacher_id', 'subject_id', 'school_class_id')
#     )

#     # Build slot grid: one slot per (class, subject) pair
#     # Each slot holds the candidate teachers for that pairing.


#     slots = []
#     for ac in assessment_classes:
#         class_teacher_links = (
#             TeacherClass.objects
#             .filter(school_class=ac.school_class, is_active=True)
#             .select_related('teacher')
#         )
#         class_teacher_users = {tc.teacher for tc in class_teacher_links}

#         # ← Filter subjects for THIS class only, not all assessment subjects
#         class_subjects = AssessmentSubject.objects.filter(
#             assessment=assessment,
#             assessment_class=ac.school_class,
#         ).select_related('subject')

#         for as_subj in class_subjects:  # ← use class_subjects, not assessment_subjects
#             subject_teacher_links = (
#                 TeacherSubject.objects
#                 .filter(
#                     school_class = ac.school_class,
#                     subject      = as_subj.subject,
#                 )
#                 .select_related('teacher')
#             )
#             candidates = [
#                 ts.teacher for ts in subject_teacher_links
#                 if ts.teacher in class_teacher_users
#             ]

#             if not candidates:
#                 candidates = list(class_teacher_users)

#             slot_key = (
#                 f'{ac.school_class.supported_class.key}_'
#                 f'{as_subj.subject.code}'
#             ).lower()

#             slots.append({
#                 'ac':         ac,
#                 'as_subj':    as_subj,
#                 'candidates': candidates,
#                 'slot_key':   slot_key,
#             })



#     if request.method == 'POST':
#         errors  = {}
#         to_save = []

#         for slot in slots:
#             print(type(slot['ac'].school_class), slot['ac'].school_class)
#             messages.error(request, f'{slot['ac'].school_class}')
            

#             field_key  = f'teacher_{slot["slot_key"]}'
#             teacher_pk = (request.POST.get(field_key) or '').strip()

#             if not teacher_pk:
#                 # Optional: skip unselected slots (admin may leave some blank)
#                 continue

#             try:
#                 teacher = CustomUser.objects.get(pk=teacher_pk, is_active=True)
#             except CustomUser.DoesNotExist:
#                 errors[field_key] = 'Selected teacher not found or is inactive.'
#                 continue

#             triple = (teacher.pk, slot['as_subj'].subject_id, slot['ac'].school_class_id)
#             if triple in already_assigned:
#                 continue   # already linked — silently skip

#             to_save.append({
#                 'teacher':      teacher,
#                 'subject':      slot['as_subj'].subject,
#                 'school_class': slot['ac'].school_class,
#             })



#         # return redirect(reverse('assessments:add_teacher', args=[pk]))

#         if errors:
#             messages.error(request, 'Please correct the highlighted errors.')
#             ctx = {
#                 'assessment': assessment,
#                 'slots':      slots,
#                 'errors':     errors,
#                 'post':       request.POST,
#             }
#             return render(request, 'assessments/add_assessment_teacher.html', ctx)

#         if not to_save:
#             messages.warning(request, 'No new teacher assignments were submitted.')
#             return redirect(reverse('assessments:detail', args=[pk]))

#         with transaction.atomic():
#             for item in to_save:
#                 AssessmentTeacher.objects.create(
#                     assessment   = assessment,
#                     teacher      = item['teacher'],
#                     subject      = item['subject'],
#                     school_class = item['school_class'],
#                 )

#         messages.success(
#             request,
#             f'{len(to_save)} teacher assignment(s) saved for "{assessment.title}".'
#         )
#         return redirect(reverse('assessments:detail', args=[pk]))

#     ctx = {
#         'assessment': assessment,
#         'slots':      slots,
#         'errors':     {},
#         'post':       {},
#     }
#     return render(request, 'assessments/add_assessment_teacher.html', ctx)


@login_required
def add_assessment_teacher(request, pk):
    assessment = get_object_or_404(Assessment, pk=pk)
    mod        = _get_or_create_mod(assessment)

    if not mod.modify_teacher:
        messages.error(request, 'Teacher assignment is not currently open for editing.')
        return redirect(reverse('assessments:detail', args=[pk]))

    assessment_classes = list(
        AssessmentClass.objects
        .filter(assessment=assessment)
        .select_related('school_class__supported_class')
        .order_by('school_class__supported_class__order')
    )

    if not assessment_classes:
        messages.error(request, 'Please assign classes first (Step 1).')
        return redirect(reverse('assessments:add_class', args=[pk]))

    # Map existing teacher assignments: (school_class_id, subject_id) → AssessmentTeacher
    existing_teacher_map = {
        (at.school_class_id, at.subject_id): at
        for at in AssessmentTeacher.objects.filter(assessment=assessment)
        .select_related('teacher', 'subject', 'school_class')
    }

    slots = []
    for ac in assessment_classes:
        class_teacher_links  = (
            TeacherClass.objects
            .filter(school_class=ac.school_class, is_active=True)
            .select_related('teacher')
        )
        class_teacher_users = {tc.teacher for tc in class_teacher_links}

        class_subjects = AssessmentSubject.objects.filter(
            assessment       = assessment,
            assessment_class = ac.school_class,
        ).select_related('subject')

        for as_subj in class_subjects:
            subject_teacher_links = (
                TeacherSubject.objects
                .filter(school_class=ac.school_class, subject=as_subj.subject)
                .select_related('teacher')
            )
            candidates = [
                ts.teacher for ts in subject_teacher_links
                if ts.teacher in class_teacher_users
            ] or list(class_teacher_users)

            slot_key    = f'{ac.school_class.supported_class.key}_{as_subj.subject.code}'.lower()
            map_key     = (ac.school_class_id, as_subj.subject_id)
            existing_at = existing_teacher_map.get(map_key)  # None if not yet assigned

            slots.append({
                'ac':          ac,
                'as_subj':     as_subj,
                'candidates':  candidates,
                'slot_key':    slot_key,
                'existing_at': existing_at,   # ← pre-select current teacher in dropdown
            })

    if request.method == 'POST':
        errors    = {}
        to_create = []
        to_update = []

        for slot in slots:
            field_key  = f'teacher_{slot["slot_key"]}'
            teacher_pk = (request.POST.get(field_key) or '').strip()

            if not teacher_pk:
                continue   # no selection — skip

            try:
                teacher = CustomUser.objects.get(pk=teacher_pk, is_active=True)
            except CustomUser.DoesNotExist:
                errors[field_key] = 'Selected teacher not found or is inactive.'
                continue

            map_key = (slot['ac'].school_class_id, slot['as_subj'].subject_id)

            if map_key in existing_teacher_map:
                existing_at = existing_teacher_map[map_key]
                if existing_at.teacher_id != teacher.pk:
                    # Teacher changed — update
                    to_update.append({'at': existing_at, 'teacher': teacher})
                # else same teacher selected — no-op
            else:
                to_create.append({
                    'teacher':      teacher,
                    'subject':      slot['as_subj'].subject,
                    'school_class': slot['ac'].school_class,
                })

        if not to_create and not to_update and not errors:
            messages.warning(request, 'No changes were made.')
            return redirect(reverse('assessments:detail', args=[pk]))

        if errors:
            messages.error(request, 'Please correct the highlighted errors.')
            ctx = {
                'assessment': assessment,
                'slots':      slots,
                'errors':     errors,
                'post':       request.POST,
                'mod':        mod,
            }
            return render(request, 'assessments/add_assessment_teacher.html', ctx)

        with transaction.atomic():
            for item in to_create:
                AssessmentTeacher.objects.create(
                    assessment   = assessment,
                    teacher      = item['teacher'],
                    subject      = item['subject'],
                    school_class = item['school_class'],
                )
            for item in to_update:
                item['at'].teacher = item['teacher']
                item['at'].save(update_fields=['teacher'])

            mod.modify_teacher = False
            if mod.edit_once:
                mod.close_edit_once_if_done()
                mod.save()
            else:
                mod.save()  # flow complete

        total_changed = len(to_create) + len(to_update)
        messages.success(request, f'{total_changed} teacher assignment(s) saved.')
        return redirect(reverse('assessments:detail', args=[pk]))

    ctx = {
        'assessment': assessment,
        'slots':      slots,
        'errors':     {},
        'post':       {},
        'mod':        mod,
    }
    return render(request, 'assessments/add_assessment_teacher.html', ctx)











CLASSES_MAPPING = {
    "baby":["baby"],
    "middle":["baby","middle"],
    "top":["baby","middle","top"],
    "p1":["p1"],
    "p2":["p1","p2"],
    "p3":["p1","p2","p3"],
    "p4":["p1","p2","p3","p4"],
    "p5":["p1","p2","p3","p4","p5"],
    "p6":["p1","p2","p3","p4","p5","p6"],
    "p7":["p1","p2","p3","p4","p5","p6","p7"]
}

GENERAL_CLASSES_MAPPING = {
    "baby":["baby"],
    "middle":["baby","middle"],
    "top":["baby","middle","top"],
    "p1":["baby","middle","top","p1"],
    "p2":["baby","middle","top","p1","p2"],
    "p3":["baby","middle","top","p1","p2","p3"],
    "p4":["baby","middle","top","p1","p2","p3","p4"],
    "p5":["baby","middle","top","p1","p2","p3","p4","p5"],
    "p6":["baby","middle","top","p1","p2","p3","p4","p5","p6"],
    "p7":["baby","middle","top","p1","p2","p3","p4","p5","p6","p7"]
}





def get_school_start_and_stop_class(assessment):
    current_year =2026
    current_academic_year =2026
    assessment_term = 'Term 3'
    assessment_term_academic_year = 2026

    assessment_type = 'eot'

    assessment_classes = AssessmentClass.objects.filter(assessment=assessment)

    school_supported_classes = get_sch_supported_classes()

    start_class = None
    stop_class = None


    classes_mapping = CLASSES_MAPPING


    for cls in school_supported_classes:
        if not any(cls_.section == 'primary' for cls_ in school_supported_classes):

            if (cls.supported_class.key == 'baby') and not any(cls.supported_class.key in ['middle','top']):
                start_class = 'baby'
                stop_class = 'baby'
                
            else:
                other_classes = classes_mapping.get(cls.supported_class.key,[])
                start_class = other_classes[0],
                stop_class = other_classes[-1]

        elif not any(cls_.section == 'nursery' for cls_ in school_supported_classes):

            if (cls.supported_class.key == 'p1') and not any(cls.supported_class.key in ['p2','p3', 'p4','p5','p6','p7']):
                start_class = 'p1'
                stop_class = 'p1'

            else:
                other_classes = classes_mapping.get(cls.supported_class.key, [])
                start_class = other_classes[0],
                stop_class = other_classes[-1]
        
        else:
            if (
                any(
                    cls_.supported_class.key =="nursery" for cls_ in school_supported_classes
                    ) and any(
                        cls_.supported_class.key =="primary" for cls_ in school_supported_classes
                    )
                ):
                if cls.supported_class.section == 'nursery':
                    initial_class = classes_mapping.get(cls.supported_class.key, []) 
                    start_class = initial_class[0]
                
                elif cls.supported_class.section == 'primary':
                    end_class = classes_mapping.get(cls.supported_class.key, [])
                    stop_class =end_class[-1]
                
    



    school_class_range = {
        "start_class":start_class,
        "stop_class":stop_class
    }

    return school_class_range



def get_student_upcoming_class(student, start_class,end_class):

    current_class = student.current_class

    student_upcomming_class = {
        'baby':'middle',
        'middle':'top',
        'top':'p1',
        'p1':'p2',
        'p2':'p3',
        'p3':'p4',
        'p4':'p5',
        'p5':'p6',
        'p6':'p7',
        'p7':None
    }

    nursery_classes = CLASSES_MAPPING.get('top',[])
    primary_classes = CLASSES_MAPPING.get('p7', [])

    school_class_order =[]

    if start_class in nursery_classes:
        school_class_order = GENERAL_CLASSES_MAPPING.get(end_class,[])
    else:
        school_class_order = CLASSES_MAPPING.get(end_class,[])


    upcoming_class = None
    next_upcoming_class =None
    current_class = None



    
    if school_class_order:
        if current_class in school_class_order:
            upcoming_class = student_upcomming_class.get(current_class, "")

            if upcoming_class is not None:
                next_upcoming_class = student_upcomming_class.get(upcoming_class)
            else:
                next_upcoming_class = None
            
    return {
        "upcoming_class":upcoming_class,
        "next_upcoming_class":next_upcoming_class,
    }






        # Here we can promote the student to the new class, that comming next accademic year finds him in the  already promoted
         






@login_required
def add_student_performance(request, pk):
    assessment = get_object_or_404(Assessment, pk=pk)
    assessment_classes = AssessmentClass.objects.filter(assessment=assessment)

    # term = assessment.term
    # term_academic_year = term.academic_year

    

    if request.method == 'POST':

        student_id = (request.POST.get("student_id") or '').strip()
        marks_obtained = (request.POST.get('marks_obtained') or '').strip()
        comment = (request.POST.get("comment") or '').strip()
        action = (request.POST.get('action') or '').strip()


        if not (student_id and marks_obtained):
            messages.error(request, 'Student ID and Marks Obtained is Required')
            return redirect(reverse(''))
        
        student = Student.objects.filter(student_id=student_id).first()

        if not student :
            messages.error(request, f"Invalid student ID provided ({student_id})")
            return redirect(reverse(''))
        

        assess_clasess = []
        ac__ = []

        
        for as_ in assessment_classes:
            assess_clasess.append(as_.school_class)
            ac__.append(as_.school_class.supported_class.name.capitalize())


        if not (student.current_class in assess_clasess):
            messages.info(request, f'Student with ID: {student.student_id.upper()} is not in the  supported assessment class {ac__}')
            return redirect(reverse(''))
    
        
        student_perfomance = AssessmentPerformance.objects.filter(student=student, assessment=assessment).first()

        if student_perfomance:
            messages.error(request, f'Student with ID: ({student_id.upper()}), Names: {student.first_name.upper()} {student.last_name.upper()}')
            return redirect(reverse(''))
        

        # if is_a_promational_assessment:
        #     if not is_promoted: 
        #         messages.error(request, "Please decide Whether the Student Is promoted to a New Class or Not")

        student_subject = AssessmentSubject.objects.filter(assessment=assessment, subject__code=request.session.get("performance_code")).first()


        with transaction.atomic():
            perfomance = AssessmentPerformance.objects.create(
                assessment =assessment,
                school_class=student.current_class,
                student=student,
                subject=student_subject.subject,
                marks_obtained=marks_obtained,
                comment=comment,
            )

            perfomance.entered_by = request.user
            messages.success(request, f"{student.first_name.upper()} {student.last_name.upper()} ({student.student_id.upper()}) perfomance of {marks_obtained} has been added successfully")
            if action:
                if action == 'addClose':
                    return redirect(reverse(''))
                elif action == 'add_and_add':
                    return redirect(reverse(''))
                
        messages.success(request, 'Student performance recorded successfully.')
        return redirect('assessments:detail', pk=pk)
    return render(request, "")



# =============================================================================
# 12. Edit Student Performance
# =============================================================================

@login_required
def edit_student_performance(request, pk, perf_pk):
    assessment  = get_object_or_404(Assessment, pk=pk)
    performance = get_object_or_404(AssessmentPerformance, pk=perf_pk, assessment=assessment)

    # ctx = _get_select_context()
    # ctx['assessment']  = assessment
    # ctx['performance'] = performance

    if request.method == 'POST':
        errors, cleaned = validate_performance(request.POST, assessment, instance=performance)

        if errors:
            messages.error(request, 'Please correct the errors below.')
            # ctx.update({'errors': errors, 'post': request.POST})
            return render(request, 'assessments/edit_student_performance.html', )

        with transaction.atomic():
            performance.student        = cleaned['student']
            performance.subject        = cleaned['subject']
            performance.school_class   = cleaned['school_class']
            performance.marks_obtained = cleaned.get('marks_obtained')
            performance.total_marks    = cleaned['total_marks']
            performance.nursery_rating = cleaned.get('nursery_rating', '')
            performance.is_absent      = cleaned['is_absent']
            performance.absent_reason  = cleaned.get('absent_reason', '')
            performance.remarks        = cleaned.get('remarks', '')
            performance.is_verified    = cleaned.get('is_verified', False)
            performance.save()

        messages.success(request, 'Performance record updated successfully.')
        return redirect('assessments:performance_detail', pk=pk, perf_pk=performance.pk)

    # ctx.update({'errors': {}, 'post': {}})
    return render(request, 'assessments/edit_student_performance.html')


# =============================================================================
# 13. Delete Student Performance
# =============================================================================

@login_required
def delete_student_performance(request, pk, perf_pk):
    assessment  = get_object_or_404(Assessment, pk=pk)
    performance = get_object_or_404(AssessmentPerformance, pk=perf_pk, assessment=assessment)

    if request.method == 'POST':
        with transaction.atomic():
            performance.delete()
        messages.success(request, 'Performance record deleted.')
        return redirect('assessments:detail', pk=pk)

    return render(request, 'assessments/confirm_delete_performance.html', {
        'assessment':  assessment,
        'performance': performance,
    })

















