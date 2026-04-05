# students/utils/student_utils.py
# ─────────────────────────────────────────────────────────────────────────────
# Helpers for direct student creation (not via admission) and the student
# detail analysis page.
#
#   Session helpers (3-step direct-create flow)
#       session_set_direct_student_data()
#       session_get_direct_student_data()
#       session_set_direct_parents_data()
#       session_get_direct_parents_data()
#       session_clear_direct_create()
#
#   Validation — direct student creation
#       validate_direct_student_step()
#       validate_direct_parents_step()    (re-uses admission_utils helpers)
#       validate_direct_confirm_step()
#
#   Student creation
#       create_student_directly()
#       generate_student_id()             alias → suggest_student_id()
#
#   Analysis stats (student detail page)
#       get_student_detail_stats()
#       get_student_fees_summary()
#       get_student_assessment_summary()
#       get_student_payments()
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db.models import Avg, Count, Max, Min, Q, Sum

from students.utils.admission_utils import (
    _parse_date,
    _split_name,
    create_parent_objects,
    generate_access_token,
    generate_parent_id,
    get_or_create_student_token,
    suggest_student_id,
    validate_admission_parents_step,
    validate_single_parent_dict,
    VALID_GENDERS,
    VALID_RELATIONSHIPS,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  SESSION HELPERS — direct student creation
# ═══════════════════════════════════════════════════════════════════════════════

_SESSION_DIRECT_STUDENT  = 'direct_student_data'
_SESSION_DIRECT_PARENTS  = 'direct_parents_data'


def session_set_direct_student_data(request, data: dict) -> None:
    request.session[_SESSION_DIRECT_STUDENT] = data
    request.session.modified = True


def session_get_direct_student_data(request) -> dict:
    return dict(request.session.get(_SESSION_DIRECT_STUDENT, {}))


def session_set_direct_parents_data(request, data: list) -> None:
    request.session[_SESSION_DIRECT_PARENTS] = data
    request.session.modified = True


def session_get_direct_parents_data(request) -> list:
    return list(request.session.get(_SESSION_DIRECT_PARENTS, []))


def session_clear_direct_create(request) -> None:
    for key in (_SESSION_DIRECT_STUDENT, _SESSION_DIRECT_PARENTS):
        request.session.pop(key, None)
    request.session.modified = True


# ═══════════════════════════════════════════════════════════════════════════════
#  VALIDATION — DIRECT STUDENT CREATION
# ═══════════════════════════════════════════════════════════════════════════════

def validate_direct_student_step(post: dict) -> tuple[dict, dict]:
    """
    Step 1 validation for direct student creation.

    Validates all student identity + academic placement fields.
    Returns (cleaned, errors).

    cleaned keys:
        first_name, last_name, other_names, date_of_birth, gender,
        nationality, district_of_origin, village, religion,
        birth_certificate_no, blood_group, medical_notes,
        is_special_needs, special_needs_notes,
        student_id, current_class_id, academic_year, date_enrolled,
        previous_school, previous_class,
        secondary_guardian_name, secondary_guardian_phone,
        secondary_guardian_relationship
    """
    errors:  dict = {}
    cleaned: dict = {}

    # ── Names ────────────────────────────────────────────────────────────────
    for field, label, max_len, required in [
        ('first_name',  'First name',  50, True),
        ('last_name',   'Last name',   50, True),
        ('other_names', 'Other names', 50, False),
    ]:
        val = (post.get(field) or '').strip()
        if required and not val:
            errors[field] = f'{label} is required.'
        elif len(val) > max_len:
            errors[field] = f'{label} must not exceed {max_len} characters.'
        else:
            cleaned[field] = val

    # ── Date of birth ────────────────────────────────────────────────────────
    dob = _parse_date(post.get('date_of_birth', ''), 'Date of birth', errors, required=True)
    if dob:
        today = date.today()
        age   = (today - dob).days // 365
        if dob > today:
            errors['date_of_birth'] = 'Date of birth cannot be in the future.'
        elif age > 20:
            errors['date_of_birth'] = f'Date of birth gives age {age} — please verify.'
        else:
            cleaned['date_of_birth'] = dob.isoformat()

    # ── Gender ───────────────────────────────────────────────────────────────
    gender = (post.get('gender') or '').strip()
    if not gender:
        errors['gender'] = 'Gender is required.'
    elif gender not in VALID_GENDERS:
        errors['gender'] = 'Invalid gender selected.'
    else:
        cleaned['gender'] = gender

    # ── Identity ─────────────────────────────────────────────────────────────
    cleaned['nationality']         = (post.get('nationality') or 'Ugandan').strip()
    cleaned['district_of_origin']  = (post.get('district_of_origin') or '').strip()
    cleaned['village']             = (post.get('village') or '').strip()
    cleaned['religion']            = (post.get('religion') or '').strip()

    bc = (post.get('birth_certificate_no') or '').strip()
    if len(bc) > 50:
        errors['birth_certificate_no'] = 'Birth certificate number must not exceed 50 characters.'
    else:
        cleaned['birth_certificate_no'] = bc

    # ── Health ───────────────────────────────────────────────────────────────
    blood_group = (post.get('blood_group') or '').strip()
    valid_blood = {'A+','A-','B+','B-','O+','O-','AB+','AB-',''}
    if blood_group not in valid_blood:
        errors['blood_group'] = 'Invalid blood group.'
    else:
        cleaned['blood_group'] = blood_group

    cleaned['medical_notes']       = (post.get('medical_notes') or '').strip()
    cleaned['is_special_needs']    = post.get('is_special_needs', '') in ('1','on','true')
    cleaned['special_needs_notes'] = (post.get('special_needs_notes') or '').strip()

    # ── Student ID ───────────────────────────────────────────────────────────
    from students.models import Student
    student_id_val = (post.get('student_id') or '').strip()
    if not student_id_val:
        errors['student_id'] = 'Student ID is required.'
    elif len(student_id_val) > 20:
        errors['student_id'] = 'Student ID must not exceed 20 characters.'
    elif Student.objects.filter(student_id=student_id_val).exists():
        errors['student_id'] = f'Student ID "{student_id_val}" is already in use.'
    else:
        cleaned['student_id'] = student_id_val

    # ── Class ────────────────────────────────────────────────────────────────
    class_id = (post.get('current_class') or '').strip()
    if not class_id:
        errors['current_class'] = 'Class is required.'
    else:
        try:
            cleaned['current_class_id'] = int(class_id)
        except ValueError:
            errors['current_class'] = 'Invalid class selected.'

    # ── Academic year ─────────────────────────────────────────────────────────
    academic_year = (post.get('academic_year') or '').strip()
    if not academic_year:
        errors['academic_year'] = 'Academic year is required.'
    else:
        cleaned['academic_year'] = academic_year

    # ── Date enrolled ─────────────────────────────────────────────────────────
    date_enrolled = _parse_date(
        post.get('date_enrolled', ''), 'Date enrolled', errors, required=True
    )
    if date_enrolled:
        cleaned['date_enrolled'] = date_enrolled

    # ── Previous school ───────────────────────────────────────────────────────
    cleaned['previous_school'] = (post.get('previous_school') or '').strip()
    cleaned['previous_class']  = (post.get('previous_class') or '').strip()

    # ── Secondary guardian ────────────────────────────────────────────────────
    cleaned['secondary_guardian_name']         = (post.get('secondary_guardian_name') or '').strip()
    cleaned['secondary_guardian_phone']        = (post.get('secondary_guardian_phone') or '').strip()
    cleaned['secondary_guardian_relationship'] = (post.get('secondary_guardian_relationship') or '').strip()

    return cleaned, errors


def validate_direct_parents_step(post: dict) -> tuple[list, dict]:
    """
    Step 2 validation for direct student creation.
    Delegates to the same multi-parent validation as the admission flow.
    parent_already_exists is always False in direct creation.
    """
    return validate_admission_parents_step(post, parent_already_exists=False)


def validate_direct_confirm_step(post: dict) -> tuple[dict, dict]:
    """Step 3: just validates the confirming user's password."""
    errors:  dict = {}
    cleaned: dict = {}
    password = (post.get('confirm_password') or '').strip()
    if not password:
        errors['confirm_password'] = 'Password is required to create the student.'
    else:
        cleaned['password'] = password
    return cleaned, errors


# ═══════════════════════════════════════════════════════════════════════════════
#  STUDENT CREATION
# ═══════════════════════════════════════════════════════════════════════════════

def create_student_directly(student_data: dict, parents_data: list, created_by):
    """
    Create a Student + all parent objects in one atomic block.

    student_data  — cleaned dict from validate_direct_student_step()
    parents_data  — list of parent dicts from validate_direct_parents_step()
    created_by    — the requesting User (for audit trail)

    Returns:
        {
            'student':        Student,
            'parent_results': list of (user, profile, relationship) tuples,
            'access_token':   str,
        }
    """
    from students.models import Student, StudentParentRelationship
    from django.utils import timezone

    # Create the student
    student = Student.objects.create(
        student_id          = student_data['student_id'],
        first_name          = student_data['first_name'],
        last_name           = student_data['last_name'],
        other_names         = student_data.get('other_names', ''),
        date_of_birth       = student_data['date_of_birth'],
        gender              = student_data['gender'],
        nationality         = student_data.get('nationality', 'Ugandan'),
        district_of_origin  = student_data.get('district_of_origin', ''),
        village             = student_data.get('village', ''),
        religion            = student_data.get('religion', ''),
        birth_certificate_no = student_data.get('birth_certificate_no', ''),
        current_class_id    = student_data['current_class_id'],
        academic_year       = student_data['academic_year'],
        date_enrolled       = student_data['date_enrolled'],
        previous_school     = student_data.get('previous_school', ''),
        previous_class      = student_data.get('previous_class', ''),
        blood_group         = student_data.get('blood_group', ''),
        medical_notes       = student_data.get('medical_notes', ''),
        is_special_needs    = student_data.get('is_special_needs', False),
        special_needs_notes = student_data.get('special_needs_notes', ''),
        secondary_guardian_name         = student_data.get('secondary_guardian_name', ''),
        secondary_guardian_phone        = student_data.get('secondary_guardian_phone', ''),
        secondary_guardian_relationship = student_data.get('secondary_guardian_relationship', ''),
        is_active = True,
    )

    # Generate the shared family access token
    access_token = generate_access_token()

    # Create parent objects
    parent_results = []
    for i, p_dict in enumerate(parents_data):
        is_primary   = (i == 0)
        relationship = p_dict.get('relationship', 'other')

        user, profile, rel = create_parent_objects(
            parent_dict  = p_dict,
            student      = student,
            relationship = relationship,
            verified_by  = created_by,
            access_token = access_token,
            is_primary   = is_primary,
        )
        parent_results.append((user, profile, rel))

    return {
        'student':        student,
        'parent_results': parent_results,
        'access_token':   access_token,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  STUDENT DETAIL ANALYSIS STATS
# ═══════════════════════════════════════════════════════════════════════════════

def get_student_detail_stats(student) -> dict:
    """
    Build all context data for the student detail / analysis page.

    Returns a large dict covering:
        - parents and relationships
        - fees: structure, payments, balance
        - assessments: results per term
        - admission record (if any)
    """
    today = date.today()

    # ── Parents ───────────────────────────────────────────────────────────────
    from students.models import StudentParentRelationship
    relationships = list(
        StudentParentRelationship.objects.filter(student=student)
        .select_related('parent', 'parent__user')
        .order_by('-is_primary', 'relationship')
    )

    # ── Fees: structure ───────────────────────────────────────────────────────
    fee_stats     = get_student_fees_summary(student)

    # ── Assessments ───────────────────────────────────────────────────────────
    assessment_stats = get_student_assessment_summary(student)

    # ── Payments ──────────────────────────────────────────────────────────────
    recent_payments = get_student_payments(student, limit=10)

    # ── Admission ─────────────────────────────────────────────────────────────
    admission = getattr(student, 'admission_record', None)

    # ── Age ───────────────────────────────────────────────────────────────────
    if student.date_of_birth:
        age = (today - student.date_of_birth).days // 365
    else:
        age = None

    return {
        'relationships':     relationships,
        'age':               age,
        'today':             today,
        'admission':         admission,
        **fee_stats,
        **assessment_stats,
        'recent_payments':   recent_payments,
    }


def get_student_fees_summary(student) -> dict:
    """
    Fee structure, payments, and current balance for a student.

    Returns:
        current_fee_structure   — list of SchoolFees for current class / current term
        all_assessment_fees     — all AssessmentFees rows for this student
        current_assessment      — AssessmentFees for current term (or None)
        total_required_ever     — sum of total_required across all terms
        total_paid_ever         — sum of total_paid across all terms
        total_balance_ever      — sum of balance across all terms
        current_term_required   — total_required this term
        current_term_paid       — total_paid this term
        current_term_balance    — balance this term
        is_cleared_this_term    — bool
    """
    from academics.models import Term
    from fees.models import AssessmentFees, SchoolFees

    current_term = Term.objects.filter(is_current=True).first()

    # All fee assessment statements for this student
    assessment_fees_qs = AssessmentFees.objects.filter(
        student=student
    ).select_related('term').order_by('-term__start_date')

    agg = assessment_fees_qs.aggregate(
        sum_required = Sum('total_required'),
        sum_paid     = Sum('total_paid'),
        sum_balance  = Sum('balance'),
    )
    total_required_ever = agg['sum_required'] or Decimal('0')
    total_paid_ever     = agg['sum_paid']     or Decimal('0')
    total_balance_ever  = agg['sum_balance']  or Decimal('0')

    current_assessment = None
    current_term_required = Decimal('0')
    current_term_paid     = Decimal('0')
    current_term_balance  = Decimal('0')
    is_cleared_this_term  = False

    if current_term:
        try:
            current_assessment    = assessment_fees_qs.get(term=current_term)
            current_term_required = current_assessment.total_required
            current_term_paid     = current_assessment.total_paid
            current_term_balance  = current_assessment.balance
            is_cleared_this_term  = current_assessment.is_cleared
        except AssessmentFees.DoesNotExist:
            pass

    # Fee structure for this student's class + current term
    current_fee_structure = []
    if current_term and student.current_class:
        current_fee_structure = list(
            SchoolFees.objects.filter(
                school_class = student.current_class,
                term         = current_term,
                is_active    = True,
            ).order_by('fees_type')
        )

    return {
        'current_term':          current_term,
        'current_fee_structure': current_fee_structure,
        'all_assessment_fees':   list(assessment_fees_qs),
        'current_assessment':    current_assessment,
        'total_required_ever':   total_required_ever,
        'total_paid_ever':       total_paid_ever,
        'total_balance_ever':    total_balance_ever,
        'current_term_required': current_term_required,
        'current_term_paid':     current_term_paid,
        'current_term_balance':  current_term_balance,
        'is_cleared_this_term':  is_cleared_this_term,
    }


def get_student_assessment_summary(student) -> dict:
    """
    All academic assessment results grouped by term.

    Returns:
        assessment_terms   — ordered list of terms that have results
        performance_by_term — dict {term_pk: [StudentPerformance, …]}
        all_performances   — flat list of all StudentPerformance rows
        best_aggregate     — highest total marks in any single assessment
        subjects_sat       — distinct count of subjects
    """
    try:
        from assessments.models import StudentPerformance
    except ImportError:
        # assessments app may not be installed in all setups
        return {
            'assessment_terms':    [],
            'performance_by_term': {},
            'all_performances':    [],
            'best_aggregate':      None,
            'subjects_sat':        0,
        }

    all_perf = list(
        StudentPerformance.objects.filter(student=student)
        .select_related(
            'assessment', 'assessment__term',
            'subject',
        )
        .order_by('-assessment__term__start_date', 'subject__name')
    )

    # Group by term
    term_map: dict = {}
    for perf in all_perf:
        term = perf.assessment.term
        term_map.setdefault(term, []).append(perf)

    assessment_terms = sorted(
        term_map.keys(),
        key=lambda t: t.start_date,
        reverse=True,
    )

    agg = (
        StudentPerformance.objects
        .filter(student=student)
        .aggregate(
            best=Max('total_marks'),
            subjects=Count('subject', distinct=True),
        )
    )

    return {
        'assessment_terms':    assessment_terms,
        'performance_by_term': term_map,
        'all_performances':    all_perf,
        'best_aggregate':      agg['best'],
        'subjects_sat':        agg['subjects'] or 0,
    }


def get_student_payments(student, limit: int = 10) -> list:
    """Return the most recent FeesPayment records for a student."""
    try:
        from fees.models import FeesPayment
        return list(
            FeesPayment.objects.filter(student=student)
            .select_related('school_fees', 'term')
            .order_by('-payment_date', '-created_at')[:limit]
        )
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════════════════════
#  LIST STATS  (student list page)
# ═══════════════════════════════════════════════════════════════════════════════

def get_student_list_stats() -> dict:
    """High-level statistics for the student list page."""
    from students.models import Student
    qs = Student.objects.all()

    total   = qs.count()
    active  = qs.filter(is_active=True).count()
    inactive = qs.filter(is_active=False).count()

    by_gender = list(qs.values('gender').annotate(count=Count('id')))

    by_class = list(
        qs.filter(is_active=True)
        .values(
            'current_class__supported_class__section',
        )
        .annotate(count=Count('id'))
        .order_by('current_class__supported_class__section')
    )

    special_needs = qs.filter(is_special_needs=True, is_active=True).count()

    return {
        'total':         total,
        'active':        active,
        'inactive':      inactive,
        'special_needs': special_needs,
        'by_gender':     by_gender,
        'by_class':      by_class,
    }
