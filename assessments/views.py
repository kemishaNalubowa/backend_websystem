from django.shortcuts               import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib                 import messages
from django.db                      import transaction

from authentication.models import CustomUser
from accounts.models import StaffProfile
from academics.base import TEACHING_STAFF_ROLES

from .models import (
    Assessment,
    AssessmentClass,
    AssessmentSubject,
    AssessmentTeacher,
    AssessmentPassMark,
    AssessmentPerformance,
    ASSESSMENT_TYPE_CHOICES,
    MONTH_CHOICES,
)
from .utils import (
    validate_assessment,
    validate_assessment_class,
    validate_assessment_subject,
    validate_assessment_teacher,
    validate_assessment_passmark,
    validate_performance,
    build_performance_summary,
    VALID_VENUE_CHOICES,
    VALID_TEACHER_ROLES,
    VALID_PASS_TYPES,
    VALID_NURSERY_RATINGS,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def _get_select_context():
    """
    Returns context data needed across multiple add forms
    (dropdown lists for FK fields).
    """
    from academics.models import Term, SchoolClass, Subject
    from accounts.models  import CustomUser

    return {
        'terms':         Term.objects.all(),
        'classes':       SchoolClass.objects.all(),
        'subjects':      Subject.objects.all(),
        'teachers':      CustomUser.objects.select_related('user').all(),
        'type_choices':  ASSESSMENT_TYPE_CHOICES,
        'month_choices': MONTH_CHOICES,
        'venue_choices': AssessmentClass.VENUE_CHOICES,
        'role_choices':  AssessmentTeacher.ROLE_CHOICES,
        'pass_types':    AssessmentPassMark.PASS_TYPE_CHOICES,
        'nursery_ratings': AssessmentPerformance.NURSERY_RATING_CHOICES,
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
    ctx = _get_select_context()

    if request.method == 'POST':
        errors, cleaned = validate_assessment(request.POST, request.FILES)

        if errors:
            messages.error(request, 'Please correct the errors below.')
            ctx.update({'errors': errors, 'post': request.POST})
            return render(request, 'assessments/add_assessment.html', ctx)

        with transaction.atomic():
            assessment = Assessment.objects.create(
                title                 = cleaned['title'],
                assessment_type       = cleaned['assessment_type'],
                description           = cleaned.get('description', ''),
                term                  = cleaned['term'],
                # academic_year         = cleaned['academic_year'],
                month                 = cleaned['month'],
                date_given            = cleaned['date_given'],
                date_due              = cleaned.get('date_due'),
                date_results_released = cleaned.get('date_results_released'),
                # total_marks           = cleaned['total_marks'],
                # duration_minutes      = cleaned.get('duration_minutes'),
                # is_published          = cleaned['is_published'],
                # results_published     = cleaned['results_published'],
                notes                 = cleaned.get('notes', ''),
                created_by            = request.user,
                **{k: cleaned[k] for k in ('paper_file', 'marking_scheme') if k in cleaned},
            )

        messages.success(request, f'Assessment "{assessment.title}" created successfully.')
        return redirect('assessments:detail', pk=assessment.pk)

    ctx.update({'errors': {}, 'post': {}})
    return render(request, 'assessments/add_assessment.html', ctx)



def assign_teacher_to_assessment(request):
    staffs = StaffProfile.objects.all()

    teaching_staffs = []

    for t in staffs:
        if t.role in TEACHING_STAFF_ROLES:
            teaching_staffs.append(t)

    teachers = []

    for ts in teaching_staffs:
        tr = CustomUser.objects.filter(pk=ts.user__id)
        for t in tr:
            teachers.append(t)

    return render(request, "assessments/assign_teacher_to_assessment.html")
    

    

    


# =============================================================================
# 3. Edit Assessment
# =============================================================================

@login_required
def edit_assessment(request, pk):
    assessment = get_object_or_404(Assessment, pk=pk)
    ctx = _get_select_context()
    ctx['assessment'] = assessment

    if request.method == 'POST':
        errors, cleaned = validate_assessment(request.POST, request.FILES)

        if errors:
            messages.error(request, 'Please correct the errors below.')
            ctx.update({'errors': errors, 'post': request.POST})
            return render(request, 'assessments/edit_assessment.html', ctx)

        update_fields = [
            'title', 'assessment_type', 'description', 'term',
            'month', 'date_given', 'date_due', 'date_results_released',
            'results_published', 'notes',
        ]
        with transaction.atomic():
            for field in update_fields:
                if field in cleaned:
                    setattr(assessment, field, cleaned[field])
            for ffile in ('paper_file', 'marking_scheme'):
                if ffile in cleaned:
                    setattr(assessment, ffile, cleaned[ffile])
            assessment.save()

        messages.success(request, f'Assessment "{assessment.title}" updated successfully.')
        return redirect('assessments:detail', pk=assessment.pk)

    ctx.update({'errors': {}, 'post': {}})
    return render(request, 'assessments/edit_assessment.html', ctx)


# =============================================================================
# 4. Assessment Detail
# =============================================================================

@login_required
def assessment_detail(request, pk):
    assessment = get_object_or_404(
        Assessment.objects.select_related('term', 'created_by'), pk=pk
    )

    classes      = assessment.assessment_classes.select_related('school_class')
    subjects     = assessment.assessment_subjects.select_related('subject')
    teachers     = assessment.assessment_teachers.select_related( 'subject', 'school_class')
    # pass_marks   = assessment.pass_marks.select_related('subject', 'set_by__user', 'approved_by')
    performances = assessment.performances.select_related(
        'student', 'subject', 'school_class', 'entered_by', 'verified_by'
    )

    # Performance filters
    class_filter   = request.GET.get('class', '').strip()
    subject_filter = request.GET.get('subject', '').strip()
    status_filter  = request.GET.get('perf_status', '').strip()

    if class_filter:
        performances = performances.filter(school_class_id=class_filter)
    if subject_filter:
        performances = performances.filter(subject_id=subject_filter)
    if status_filter == 'pass':
        performances = performances.filter(is_pass=True)
    elif status_filter == 'fail':
        performances = performances.filter(is_pass=False)
    elif status_filter == 'absent':
        performances = performances.filter(is_absent=True)

    summary = build_performance_summary(assessment)
    ctx     = _get_select_context()
    ctx.update({
        'assessment':      assessment,
        'classes':         classes,
        'subjects':        subjects,
        'teachers':        teachers,
        # 'pass_marks':      pass_marks,
        'performances':    performances,
        'summary':         summary,
        # form states for inline add forms
        'class_errors':    {},   'class_post':    {},
        'subject_errors':  {},   'subject_post':  {},
        'teacher_errors':  {},   'teacher_post':  {},
        'passmark_errors': {},   'passmark_post': {},
        'perf_errors':     {},   'perf_post':     {},
        # active filters
        'filter_class':    class_filter,
        'filter_subject':  subject_filter,
        'filter_perf_status': status_filter,
    })
    return render(request, 'assessments/assessment_detail.html', ctx)


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


# =============================================================================
# 7. Add Assessment Class
# =============================================================================

@login_required
def add_assessment_class(request, pk):
    assessment = get_object_or_404(Assessment, pk=pk)

    if request.method != 'POST':
        return redirect('assessments:detail', pk=pk)

    errors, cleaned = validate_assessment_class(request.POST, assessment)

    if errors:
        messages.error(request, 'Could not add class. Please fix the errors.')
        # Re-render the detail page with errors
        classes      = assessment.assessment_classes.select_related('school_class', 'invigilator__user')
        subjects     = assessment.assessment_subjects.select_related('subject')
        teachers     = assessment.assessment_teachers.select_related('teacher__user', 'subject', 'school_class')
        pass_marks   = assessment.pass_marks.select_related('subject', 'set_by__user', 'approved_by')
        performances = assessment.performances.select_related(
            'student', 'subject', 'school_class', 'entered_by', 'verified_by'
        )
        ctx = _get_select_context()
        ctx.update({
            'assessment':      assessment,
            'classes':         classes,
            'subjects':        subjects,
            'teachers':        teachers,
            'pass_marks':      pass_marks,
            'performances':    performances,
            'summary':         build_performance_summary(assessment),
            'class_errors':    errors,
            'class_post':      request.POST,
            'subject_errors':  {}, 'subject_post':  {},
            'teacher_errors':  {}, 'teacher_post':  {},
            'passmark_errors': {}, 'passmark_post': {},
            'perf_errors':     {}, 'perf_post':     {},
            'active_tab':      'classes',
        })
        return render(request, 'assessments/assessment_detail.html', ctx)

    with transaction.atomic():
        AssessmentClass.objects.create(
            assessment       = assessment,
            school_class     = cleaned['school_class'],
            students_invited = cleaned.get('students_invited', 0),
            students_sat     = cleaned.get('students_sat', 0),
            students_absent  = cleaned.get('students_absent', 0),
            venue            = cleaned.get('venue', ''),
            invigilator      = cleaned.get('invigilator'),
            start_time       = cleaned.get('start_time'),
            end_time         = cleaned.get('end_time'),
            class_remarks    = cleaned.get('class_remarks', ''),
        )

    messages.success(request, f'Class added to "{assessment.title}" successfully.')
    return redirect('assessments:detail', pk=pk)


# =============================================================================
# 8. Add Assessment Subject
# =============================================================================

@login_required
def add_assessment_subject(request, pk):
    assessment = get_object_or_404(Assessment, pk=pk)

    if request.method != 'POST':
        return redirect('assessments:detail', pk=pk)

    errors, cleaned = validate_assessment_subject(request.POST, request.FILES, assessment)

    if errors:
        messages.error(request, 'Could not add subject. Please fix the errors.')
        classes      = assessment.assessment_classes.select_related('school_class', 'invigilator__user')
        subjects     = assessment.assessment_subjects.select_related('subject')
        teachers     = assessment.assessment_teachers.select_related('teacher__user', 'subject', 'school_class')
        pass_marks   = assessment.pass_marks.select_related('subject', 'set_by__user', 'approved_by')
        performances = assessment.performances.select_related(
            'student', 'subject', 'school_class', 'entered_by', 'verified_by'
        )
        ctx = _get_select_context()
        ctx.update({
            'assessment':      assessment,
            'classes':         classes,
            'subjects':        subjects,
            'teachers':        teachers,
            'pass_marks':      pass_marks,
            'performances':    performances,
            'summary':         build_performance_summary(assessment),
            'class_errors':    {}, 'class_post':    {},
            'subject_errors':  errors,
            'subject_post':    request.POST,
            'teacher_errors':  {}, 'teacher_post':  {},
            'passmark_errors': {}, 'passmark_post': {},
            'perf_errors':     {}, 'perf_post':     {},
            'active_tab':      'subjects',
        })
        return render(request, 'assessments/assessment_detail.html', ctx)

    with transaction.atomic():
        kwargs = dict(
            assessment  = assessment,
            subject     = cleaned['subject'],
            total_marks = cleaned['total_marks'],
            sort_order  = cleaned.get('sort_order', 0),
            notes       = cleaned.get('notes', ''),
        )
        if 'paper_file' in cleaned:
            kwargs['paper_file'] = cleaned['paper_file']
        AssessmentSubject.objects.create(**kwargs)

    messages.success(request, 'Subject added to assessment successfully.')
    return redirect('assessments:detail', pk=pk)


# =============================================================================
# 9. Add Assessment Teacher
# =============================================================================

@login_required
def add_assessment_teacher(request, pk):
    assessment = get_object_or_404(Assessment, pk=pk)

    if request.method != 'POST':
        return redirect('assessments:detail', pk=pk)

    errors, cleaned = validate_assessment_teacher(request.POST, assessment)

    if errors:
        messages.error(request, 'Could not add teacher. Please fix the errors.')
        classes      = assessment.assessment_classes.select_related('school_class', 'invigilator__user')
        subjects     = assessment.assessment_subjects.select_related('subject')
        teachers     = assessment.assessment_teachers.select_related('teacher__user', 'subject', 'school_class')
        pass_marks   = assessment.pass_marks.select_related('subject', 'set_by__user', 'approved_by')
        performances = assessment.performances.select_related(
            'student', 'subject', 'school_class', 'entered_by', 'verified_by'
        )
        ctx = _get_select_context()
        ctx.update({
            'assessment':      assessment,
            'classes':         classes,
            'subjects':        subjects,
            'teachers':        teachers,
            'pass_marks':      pass_marks,
            'performances':    performances,
            'summary':         build_performance_summary(assessment),
            'class_errors':    {}, 'class_post':    {},
            'subject_errors':  {}, 'subject_post':  {},
            'teacher_errors':  errors,
            'teacher_post':    request.POST,
            'passmark_errors': {}, 'passmark_post': {},
            'perf_errors':     {}, 'perf_post':     {},
            'active_tab':      'teachers',
        })
        return render(request, 'assessments/assessment_detail.html', ctx)

    with transaction.atomic():
        AssessmentTeacher.objects.create(
            assessment   = assessment,
            teacher      = cleaned['teacher'],
            role         = cleaned['role'],
            subject      = cleaned.get('subject'),
            school_class = cleaned.get('school_class'),
            notes        = cleaned.get('notes', ''),
        )

    messages.success(request, 'Teacher linked to assessment successfully.')
    return redirect('assessments:detail', pk=pk)


# =============================================================================
# 10. Add Assessment Pass Mark
# =============================================================================

@login_required
def add_assessment_passmark(request, pk):
    assessment = get_object_or_404(Assessment, pk=pk)

    if request.method != 'POST':
        return redirect('assessments:detail', pk=pk)

    errors, cleaned = validate_assessment_passmark(request.POST, assessment)

    if errors:
        messages.error(request, 'Could not set passmark. Please fix the errors.')
        classes      = assessment.assessment_classes.select_related('school_class', 'invigilator__user')
        subjects     = assessment.assessment_subjects.select_related('subject')
        teachers     = assessment.assessment_teachers.select_related('teacher__user', 'subject', 'school_class')
        pass_marks   = assessment.pass_marks.select_related('subject', 'set_by__user', 'approved_by')
        performances = assessment.performances.select_related(
            'student', 'subject', 'school_class', 'entered_by', 'verified_by'
        )
        ctx = _get_select_context()
        ctx.update({
            'assessment':      assessment,
            'classes':         classes,
            'subjects':        subjects,
            'teachers':        teachers,
            'pass_marks':      pass_marks,
            'performances':    performances,
            'summary':         build_performance_summary(assessment),
            'class_errors':    {}, 'class_post':    {},
            'subject_errors':  {}, 'subject_post':  {},
            'teacher_errors':  {}, 'teacher_post':  {},
            'passmark_errors': errors,
            'passmark_post':   request.POST,
            'perf_errors':     {}, 'perf_post':     {},
            'active_tab':      'passmarks',
        })
        return render(request, 'assessments/assessment_detail.html', ctx)

    with transaction.atomic():
        AssessmentPassMark.objects.create(
            assessment  = assessment,
            subject     = cleaned['subject'],
            pass_type   = cleaned['pass_type'],
            pass_value  = cleaned['pass_value'],
            set_by      = cleaned.get('set_by'),
            notes       = cleaned.get('notes', ''),
        )

    messages.success(request, 'Passmark set successfully.')
    return redirect('assessments:detail', pk=pk)


# =============================================================================
# 11. Add Student Performance
# =============================================================================

@login_required
def add_student_performance(request, pk):
    assessment = get_object_or_404(Assessment, pk=pk)

    if request.method != 'POST':
        return redirect('assessments:detail', pk=pk)

    errors, cleaned = validate_performance(request.POST, assessment)

    if errors:
        messages.error(request, 'Could not record performance. Please fix the errors.')
        classes      = assessment.assessment_classes.select_related('school_class', 'invigilator__user')
        subjects     = assessment.assessment_subjects.select_related('subject')
        teachers     = assessment.assessment_teachers.select_related('teacher__user', 'subject', 'school_class')
        pass_marks   = assessment.pass_marks.select_related('subject', 'set_by__user', 'approved_by')
        performances = assessment.performances.select_related(
            'student', 'subject', 'school_class', 'entered_by', 'verified_by'
        )
        ctx = _get_select_context()
        ctx.update({
            'assessment':      assessment,
            'classes':         classes,
            'subjects':        subjects,
            'teachers':        teachers,
            'pass_marks':      pass_marks,
            'performances':    performances,
            'summary':         build_performance_summary(assessment),
            'class_errors':    {}, 'class_post':    {},
            'subject_errors':  {}, 'subject_post':  {},
            'teacher_errors':  {}, 'teacher_post':  {},
            'passmark_errors': {}, 'passmark_post': {},
            'perf_errors':     errors,
            'perf_post':       request.POST,
            'active_tab':      'performance',
        })
        return render(request, 'assessments/assessment_detail.html', ctx)

    with transaction.atomic():
        AssessmentPerformance.objects.create(
            assessment     = assessment,
            student        = cleaned['student'],
            subject        = cleaned['subject'],
            school_class   = cleaned['school_class'],
            marks_obtained = cleaned.get('marks_obtained'),
            total_marks    = cleaned['total_marks'],
            nursery_rating = cleaned.get('nursery_rating', ''),
            is_absent      = cleaned['is_absent'],
            absent_reason  = cleaned.get('absent_reason', ''),
            remarks        = cleaned.get('remarks', ''),
            is_verified    = cleaned.get('is_verified', False),
            entered_by     = request.user,
        )

    messages.success(request, 'Student performance recorded successfully.')
    return redirect('assessments:detail', pk=pk)


# =============================================================================
# 12. Edit Student Performance
# =============================================================================

@login_required
def edit_student_performance(request, pk, perf_pk):
    assessment  = get_object_or_404(Assessment, pk=pk)
    performance = get_object_or_404(AssessmentPerformance, pk=perf_pk, assessment=assessment)

    ctx = _get_select_context()
    ctx['assessment']  = assessment
    ctx['performance'] = performance

    if request.method == 'POST':
        errors, cleaned = validate_performance(request.POST, assessment, instance=performance)

        if errors:
            messages.error(request, 'Please correct the errors below.')
            ctx.update({'errors': errors, 'post': request.POST})
            return render(request, 'assessments/edit_student_performance.html', ctx)

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

    ctx.update({'errors': {}, 'post': {}})
    return render(request, 'assessments/edit_student_performance.html', ctx)


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


# =============================================================================
# 14. Student Performance Detail
# =============================================================================

@login_required
def student_performance_detail(request, pk, perf_pk):
    assessment  = get_object_or_404(Assessment, pk=pk)
    performance = get_object_or_404(
        AssessmentPerformance.objects.select_related(
            'student', 'subject', 'school_class',
            'entered_by', 'verified_by', 'assessment__term'
        ),
        pk=perf_pk,
        assessment=assessment,
    )

    # Try to find the passmark for this subject
    try:
        pass_mark = AssessmentPassMark.objects.select_related(
            'subject', 'set_by__user'
        ).get(assessment=assessment, subject=performance.subject)
    except AssessmentPassMark.DoesNotExist:
        pass_mark = None

    return render(request, 'assessments/student_performance_detail.html', {
        'assessment':  assessment,
        'performance': performance,
        'pass_mark':   pass_mark,
    })
