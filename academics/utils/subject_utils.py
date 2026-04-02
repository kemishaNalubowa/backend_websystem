# academics/utils/subject_utils.py
# ─────────────────────────────────────────────────────────────────────────────
# All helper functions for Subject views:
#   - Manual field validation
#   - POST data parsing
#   - Per-section statistics builders
# ─────────────────────────────────────────────────────────────────────────────

from django.db.models import Avg, Count, Q, Sum

from academics.models import Subject



from academics.models import SchoolSupportedClasses

def get_sch_supported_classes():
    return SchoolSupportedClasses.objects.all()



# ═══════════════════════════════════════════════════════════════════════════════
#  VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

# VALID_LEVELS = {'nursery', 'lower_primary', 'upper_primary', 'all'}

# LEVEL_DISPLAY = {
#     'nursery':       'Nursery (Baby – Top Class)',
#     'lower_primary': 'Lower Primary (P1 – P3)',
#     'upper_primary': 'Upper Primary (P4 – P7)',
#     'all':           'All Levels',
# }


def validate_and_parse_subject(post: dict, instance: Subject | None = None) -> tuple[dict, dict]:
    """
    Manually validate all Subject POST fields.

    Returns:
        (cleaned_data, errors)

    cleaned_data — ready for Subject(**cleaned) or setattr loop on edit
    errors       — dict of field_name → error message string
                   Empty dict = validation passed.
    """
    errors:  dict = {}
    cleaned: dict = {}

    # ── name ──────────────────────────────────────────────────────────────────
    name = (post.get('name') or '').strip()
    if not name:
        errors['name'] = 'Subject name is required.'
    elif len(name) > 100:
        errors['name'] = 'Subject name must not exceed 100 characters.'
    else:
        cleaned['name'] = name

    # ── code ──────────────────────────────────────────────────────────────────
    code = (post.get('code') or '').strip().upper()
    if not code:
        errors['code'] = 'Subject code is required (e.g. ENG, MAT, SCI).'
    elif len(code) > 10:
        errors['code'] = 'Subject code must not exceed 10 characters.'
    else:
        # Uniqueness check
        qs = Subject.objects.filter(code=code)
        if instance and instance.pk:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            errors['code'] = f'A subject with code "{code}" already exists.'
        else:
            cleaned['code'] = code

    # ── level ─────────────────────────────────────────────────────────────────

    supported_classes = get_sch_supported_classes()
    submitted_classes = []

    for sc in supported_classes:
        key = sc.supported_class.key

        class_ = (post.get(f"class_{key}") or '').strip()

        if class_:
            submitted_classes.append({f"class_{key}":class_})
    
    if not submitted_classes:
        errors['classes'] = f'Subject Class is required.'
    else:
        cleaned['classes'] = submitted_classes


    # ── description ───────────────────────────────────────────────────────────
    cleaned['description'] = (post.get('description') or '').strip()


    # ── is_active ─────────────────────────────────────────────────────────────
    cleaned['is_active'] = str(post.get('is_active', '')).strip().lower() in (
        '1', 'true', 'on', 'yes'
    )

    # ── sort_order ────────────────────────────────────────────────────────────


    if not errors:
        submitted_keys = [v for d in cleaned['classes'] for v in d.values()]
        cleaned['classes'] = [
            sc for sc in supported_classes
            if sc.supported_class.key in submitted_keys
        ]

    return cleaned, errors


# ═══════════════════════════════════════════════════════════════════════════════
#  LIST STATS
# ═══════════════════════════════════════════════════════════════════════════════

def get_subject_list_stats() -> dict:
    """
    High-level stats shown above the subjects list page.
    """
    qs = Subject.objects.all()

    total         = qs.count()
    active        = qs.filter(is_active=True).count()
    inactive      = qs.filter(is_active=False).count()
    # compulsory    = qs.filter(is_compulsory=True, is_active=True).count()
    # optional      = qs.filter(is_compulsory=False, is_active=True).count()

    # by_level = list(
    #     qs.filter(is_active=True)
    #     # .values('level')
    #     .annotate(total=Count('id'))
    #     # .order_by('level')
    # )

    # Attach display labels
    # for row in by_level:
    #     row['level_display'] = LEVEL_DISPLAY.get(row['level'], row['level'])

    # Subjects with no class assignment at all
    from academics.models import ClassSubject
    assigned_ids  = ClassSubject.objects.values_list('subject_id', flat=True).distinct()
    unassigned    = qs.filter(is_active=True).exclude(pk__in=assigned_ids).count()

    # Subjects with no teacher assignment at all
    from academics.models import TeacherSubject
    taught_ids    = TeacherSubject.objects.values_list('subject_id', flat=True).distinct()
    unteached     = qs.filter(is_active=True).exclude(pk__in=taught_ids).count()

    return {
        'total':        total,
        'active':       active,
        'inactive':     inactive,
        # 'compulsory':   compulsory,
        # 'optional':     optional,
        # 'by_level':     by_level,
        'unassigned':   unassigned,
        'unteached':    unteached,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  DETAIL STATS
# ═══════════════════════════════════════════════════════════════════════════════

def get_subject_info_stats(subject: Subject) -> dict:
    """
    Core subject metadata for the Subject Info tab.
    """
    from academics.models import ClassSubject, TeacherSubject, TeacherClass

    class_count   = ClassSubject.objects.filter(subject=subject).count()


    teacher_count = TeacherSubject.objects.filter(subject=subject).count()
    # primary_teacher = TeacherSubject.objects.filter(
    #     subject=subject, is_primary=True
    # ).select_related('teacher__user').first()

    # How many active teaching assignments exist for this subject this term
    from academics.models import Term
    current_term  = Term.objects.filter(is_current=True).first()
    active_assignments = 0
    if current_term:
        active_assignments = TeacherClass.objects.filter(
            subject=subject,
            term=current_term,
            is_active=True,
        ).count()

    return {
        'class_count':        class_count,
        'teacher_count':      teacher_count,
        # 'primary_teacher':    primary_teacher,
        'current_term':       current_term,
        'active_assignments': active_assignments,
        # 'level_display':      LEVEL_DISPLAY.get(subject.level, subject.level),
    }


def get_subject_teachers_stats(subject: Subject) -> dict:
    """
    Stats and data for the Teachers Assigned tab.
    """
    from academics.models import TeacherSubject, TeacherClass, Term

    ts_qs = TeacherSubject.objects.filter(
        subject=subject
    ).select_related('teacher__user').order_by('-is_primary', 'teacher__user__last_name')

    total         = ts_qs.count()
    primary_count = ts_qs.filter(is_primary=True).count()

    # Current term teaching assignments for this subject
    current_term = Term.objects.filter(is_current=True).first()
    active_now   = []
    if current_term:
        active_now = list(
            TeacherClass.objects.filter(
                subject=subject,
                term=current_term,
                is_active=True,
            ).select_related(
                'teacher__user', 'school_class'
            ).order_by('school_class__section', 'school_class__level')
        )

    # Historical: how many unique terms each teacher has taught this subject
    teacher_history = list(
        TeacherClass.objects.filter(subject=subject)
        .values(
            'teacher__user__first_name',
            'teacher__user__last_name',
            'teacher__employee_id',
        )
        .annotate(
            terms_taught=Count('term', distinct=True),
            classes_taught=Count('school_class', distinct=True),
            total_periods=Sum('periods_per_week'),
        )
        .order_by('-terms_taught')
    )

    # Qualification breakdown of assigned teachers
    qual_breakdown = list(
        ts_qs.values('teacher__qualification')
        .annotate(count=Count('id'))
        .order_by('teacher__qualification')
    )

    return {
        'teacher_subjects':  ts_qs,
        'total':             total,
        'primary_count':     primary_count,
        'active_now':        active_now,
        'current_term':      current_term,
        'teacher_history':   teacher_history,
        'qual_breakdown':    qual_breakdown,
    }


def get_subject_classes_stats(subject: Subject) -> dict:
    """
    Stats and data for the Classes Assigned tab.
    """
    from academics.models import ClassSubject, TeacherClass, Term
    from assessments.models import AssessmentSubject

    # supported_classes = SchoolSupportedClasses.objects.filter()

    cs_qs = ClassSubject.objects.filter(
        subject=subject
    ).select_related('school_class').order_by(
        'school_class__supported_class__section','school_class__supported_class__order'
    )

    total_assigned  = cs_qs.count()
    # active_assigned = cs_qs.filter(is_active=True).count()

    # Breakdown by school section (nursery vs primary)
    by_section = list(
        cs_qs.values('school_class__supported_class__section')
        .annotate(count=Count('id'))
    )

    # Breakdown by level
    # by_level = list(
    #     cs_qs.filter(is_active=True)
    #     .values('school_class__level')
    #     .annotate(count=Count('id'))
    #     .order_by('school_class__level')
    # )

    # Current term: which classes are actively taught this subject + by whom
    current_term = Term.objects.filter(is_current=True).first()
    current_assignments = []
    if current_term:
        current_assignments = list(
            TeacherClass.objects.filter(
                subject=subject,
                term=current_term,
                is_active=True,
            ).select_related('school_class')
            .order_by('school_class__section', )
        )

    # Performance: latest EOT average per class for this subject
    class_performance = list(
        AssessmentSubject.objects.filter(
            subject=subject,
            # exam_type='eot',
        )
        # .values(
        #     # 'school_class__level',
        #     # 'school_class__stream',
        #     'term__name',
        #     'term__start_date',
        # )
        # .annotate(
        #     avg_mark=Avg('marks_obtained'),
        #     student_count=Count('student', distinct=True),
        # )
        # .order_by(
        #     'school_class__level',
        #     '-term__start_date',
        # )[:30]
    )

    return {
        'class_subjects':       cs_qs,
        'total_assigned':       total_assigned,
        # 'active_assigned':      active_assigned,
        # 'inactive_assigned':    total_assigned - active_assigned,
        'by_section':           by_section,
        # 'by_level':             by_level,
        'current_term':         current_term,
        'current_assignments':  current_assignments,
        'class_performance':    class_performance,
    }
