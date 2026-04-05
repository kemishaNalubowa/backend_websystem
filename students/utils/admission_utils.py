# students/utils/admission_utils.py
# ─────────────────────────────────────────────────────────────────────────────
# Helpers for Admission views:
#
#   ID / token generation
#       generate_admission_number()
#       suggest_student_id()
#       generate_parent_id()
#       generate_access_token()
#
#   Date parsing
#       _parse_date()
#
#   Session helpers (3-step add flow)
#       session_set_student_data()
#       session_get_student_data()
#       session_set_parents_data()
#       session_get_parents_data()
#       session_clear_admission()
#
#   Validation — admission add flow
#       validate_admission_student_step()
#       validate_admission_parents_step()
#       validate_admission_confirm_step()
#
#   Validation — status update
#       validate_status_update()
#
#   Validation — verify flow helpers
#       validate_verify_student_step()
#       validate_verify_enrol_step()
#
#   Parent data helpers
#       parse_parent_form_data()          single parent from POST
#       parse_parents_form_data()         all parents from POST (multi-parent)
#       validate_single_parent_dict()     validate one parent dict
#
#   DB operations
#       create_student_from_admission()
#       create_parent_objects()           create user + profile + relationship
#       link_existing_parent()            re-use a ParentProfile, add relationship
#       get_or_create_student_token()     fetch or generate the shared token
#
#   Stats
#       get_admission_list_stats()
#       get_admission_detail_stats()
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import secrets
import string
from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Count, Max, Q
from academics.models import SchoolSupportedClasses

User = get_user_model()


# ═══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

VALID_STATUSES = {
    'pending', 'shortlisted', 'approved', 'rejected', 'waitlisted', 'enrolled',
}

STATUS_LABELS = {
    'pending':     'Pending Review',
    'shortlisted': 'Shortlisted',
    'approved':    'Approved',
    'rejected':    'Rejected',
    'waitlisted':  'Waitlisted',
    'enrolled':    'Enrolled',
}

STATUS_TRANSITIONS = {
    'pending':     {'shortlisted', 'approved', 'rejected', 'waitlisted'},
    'shortlisted': {'approved', 'rejected', 'waitlisted'},
    'waitlisted':  {'approved', 'rejected'},
    'approved':    {'enrolled', 'rejected'},
    'rejected':    {'pending'},
    'enrolled':    set(),
}

VALID_GENDERS = {'male', 'female'}

RELATIONSHIP_CHOICES = [
    ('father',         'Father'),
    ('mother',         'Mother'),
    ('legal_guardian', 'Legal Guardian'),
    ('uncle',          'Uncle'),
    ('aunt',           'Aunt'),
    ('grandparent',    'Grandparent'),
    ('sibling',        'Elder Sibling'),
    ('other',          'Other'),
]
VALID_RELATIONSHIPS = {r[0] for r in RELATIONSHIP_CHOICES}

# Session keys
_SESSION_STUDENT  = 'adm_student_data'
_SESSION_PARENTS  = 'adm_parents_data'


# ═══════════════════════════════════════════════════════════════════════════════
#  ID / TOKEN GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def generate_admission_number() -> str:
    """ADM<YEAR><SEQ:04>  e.g. ADM20250001. Call inside transaction.atomic()."""
    from students.models import Admission
    year   = date.today().year
    prefix = f'ADM{year}'
    last   = (
        Admission.objects
        .filter(admission_number__startswith=prefix)
        .aggregate(m=Max('admission_number'))['m']
    )
    if last:
        try:
            seq = int(last.replace(prefix, '')) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1
    return f'{prefix}{seq:04d}'


def suggest_student_id() -> str:
    """STD<YEAR><SEQ:04>  e.g. STD20250001."""
    from students.models import Student
    year   = date.today().year
    prefix = f'STD{year}'
    last   = (
        Student.objects
        .filter(student_id__startswith=prefix)
        .aggregate(m=Max('student_id'))['m']
    )
    if last:
        try:
            seq = int(last.replace(prefix, '')) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1
    return f'{prefix}{seq:04d}'


def generate_parent_id() -> str:
    """PAR<YEAR><SEQ:04>  e.g. PAR20250001. Call inside transaction.atomic()."""
    year   = date.today().year
    prefix = f'PAR{year}'
    last   = (
        User.objects
        .filter(parent_id__startswith=prefix)
        .aggregate(m=Max('parent_id'))['m']
    )
    if last:
        try:
            seq = int(last.replace(prefix, '')) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1
    return f'{prefix}{seq:04d}'


def generate_access_token() -> str:
    """
    Generate a cryptographically random 12-character access token.
    Format: 4 alpha-upper + dash + 4 digits + dash + 4 alpha-lower
    Example: AXKP-7392-mnvq
    """
    upper  = ''.join(secrets.choice(string.ascii_uppercase) for _ in range(4))
    digits = ''.join(secrets.choice(string.digits) for _ in range(4))
    lower  = ''.join(secrets.choice(string.ascii_lowercase) for _ in range(4))
    return f'{upper}-{digits}-{lower}'


# ═══════════════════════════════════════════════════════════════════════════════
#  DATE PARSING
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_date(
    value: str,
    field_label: str,
    errors: dict,
    required: bool = False,
) -> date | None:
    value = (value or '').strip()
    if not value:
        if required:
            errors[field_label] = f'{field_label} is required.'
        return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    errors[field_label] = f'{field_label} is not a valid date (use YYYY-MM-DD).'
    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  SESSION HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def session_set_student_data(request, data: dict) -> None:
    # class_applied = data.get('applied_class')
    # if class_applied:
    #     class_ = SchoolSupportedClasses.objects.filter(pk=class_applied).first()
    #     if class_:
    #         data["applied_cls"] = {
    #             "key":class_.supported_class.key.upper(),
    #             "name":class_.supported_class.name.capitalize()}
            

    request.session[_SESSION_STUDENT] = data
    request.session.modified = True


def session_get_student_data(request) -> dict:
    return dict(request.session.get(_SESSION_STUDENT, {}))


def session_set_parents_data(request, data: list) -> None:
    request.session[_SESSION_PARENTS] = data
    request.session.modified = True


def session_get_parents_data(request) -> list:
    return list(request.session.get(_SESSION_PARENTS, []))


def session_clear_admission(request) -> None:
    for key in (_SESSION_STUDENT, _SESSION_PARENTS):
        request.session.pop(key, None)
    request.session.modified = True


# ═══════════════════════════════════════════════════════════════════════════════
#  VALIDATION — ADMISSION ADD FLOW
# ═══════════════════════════════════════════════════════════════════════════════

def validate_admission_student_step(post: dict) -> tuple[dict, dict]:
    """
    Step 1 validation: student / applicant details.

    Returns (cleaned, errors).

    cleaned keys:
        first_name, last_name, other_names, date_of_birth, gender,
        nationality, district_of_origin, religion, birth_certificate_no,
        previous_school, previous_class, last_result,
        academic_year, applied_class_id (int|None),
        parent_already_exists (bool)
    """
    errors:  dict = {}
    cleaned: dict = {}

    # Names
    first_name = (post.get('first_name') or '').strip()
    if not first_name:
        errors['first_name'] = 'First name is required.'
    elif len(first_name) > 50:
        errors['first_name'] = 'First name must not exceed 50 characters.'
    else:
        cleaned['first_name'] = first_name

    last_name = (post.get('last_name') or '').strip()
    if not last_name:
        errors['last_name'] = 'Last name is required.'
    elif len(last_name) > 50:
        errors['last_name'] = 'Last name must not exceed 50 characters.'
    else:
        cleaned['last_name'] = last_name

    other_names = (post.get('other_names') or '').strip()
    if len(other_names) > 50:
        errors['other_names'] = 'Other names must not exceed 50 characters.'
    else:
        cleaned['other_names'] = other_names

    # Date of birth
    dob = _parse_date(post.get('date_of_birth', ''), 'Date of birth', errors, required=True)
    if dob:
        today = date.today()
        age   = (today - dob).days // 365
        if dob > today:
            errors['date_of_birth'] = 'Date of birth cannot be in the future.'
        elif age > 20:
            errors['date_of_birth'] = (
                f'Date of birth gives an age of {age} years — please verify.'
            )
        else:
            cleaned['date_of_birth'] = dob.isoformat()

    # Gender
    gender = (post.get('gender') or '').strip()
    if not gender:
        errors['gender'] = 'Gender is required.'
    elif gender not in VALID_GENDERS:
        errors['gender'] = 'Invalid gender selected.'
    else:
        cleaned['gender'] = gender

    # Optional identity fields
    cleaned['nationality']         = (post.get('nationality') or 'Ugandan').strip()
    cleaned['district_of_origin']  = (post.get('district_of_origin') or '').strip()
    cleaned['religion']            = (post.get('religion') or '').strip()

    bc = (post.get('birth_certificate_no') or '').strip()
    if len(bc) > 50:
        errors['birth_certificate_no'] = 'Birth certificate number must not exceed 50 characters.'
    else:
        cleaned['birth_certificate_no'] = bc

    # Previous schooling
    cleaned['previous_school'] = (post.get('previous_school') or '').strip()
    cleaned['previous_class']  = (post.get('previous_class') or '').strip()
    cleaned['last_result']     = (post.get('last_result') or '').strip()

    # Academic year
    academic_year = (post.get('academic_year') or '').strip()
    if not academic_year:
        errors['academic_year'] = 'Academic year is required (e.g. 2025).'
    else:
        try:
            yr  = int(academic_year)
            now = date.today().year
            if yr < 2000 or yr > now + 5:
                errors['academic_year'] = (
                    f'Academic year must be between 2000 and {now + 5}.'
                )
            else:
                cleaned['academic_year'] = str(yr)
        except ValueError:
            errors['academic_year'] = 'Academic year must be a 4-digit year.'

    # Applied class (optional FK)
    class_id = (post.get('applied_class') or '').strip()
    if class_id:
        try:
            cleaned['applied_class_id'] = int(class_id)
        except ValueError:
            errors['applied_class'] = 'Invalid class selected.'
    else:
        cleaned['applied_class_id'] = None

    # Flag: does the parent already have a student in this school?
    cleaned['parent_already_exists'] = (
        post.get('parent_already_exists', '') in ('1', 'on', 'true', 'yes')
    )

    return cleaned, errors


def validate_admission_parents_step(
    post: dict,
    parent_already_exists: bool,
) -> tuple[list, dict]:
    """
    Step 2 validation: parent / guardian data.

    If parent_already_exists=True:
        Expect a single existing parent_id field.
        Returns a list with one dict: {existing: True, parent_id: str, relationship: str}

    If parent_already_exists=False:
        Expect multi-parent POST fields.
        Each parent is indexed: parent_0_*, parent_1_*, …
        Returns a list of raw parent dicts ready to be stored in Admission.parents_data.

    Returns (parents_list, errors).
    """
    errors: dict       = {}
    parents: list[dict] = []

    if parent_already_exists:
        parent_id_val = (post.get('existing_parent_id') or '').strip().upper()
        if not parent_id_val:
            errors['existing_parent_id'] = 'Parent ID is required.'
        else:
            # Verify the parent_id exists in the system
            from accounts.models import ParentProfile
            try:
                pp = ParentProfile.objects.select_related('user').get(
                    user__parent_id=parent_id_val
                )
                rel = (post.get('existing_parent_relationship') or 'other').strip()
                if rel not in VALID_RELATIONSHIPS:
                    rel = 'other'
                parents.append({
                    'existing':      True,
                    'parent_id':     parent_id_val,
                    'full_name':     pp.full_name,
                    'relationship':  rel,
                })
            except ParentProfile.DoesNotExist:
                errors['existing_parent_id'] = (
                    f'No parent with ID "{parent_id_val}" found in the system.'
                )
        return parents, errors

    # ── Multi-parent mode ─────────────────────────────────────────────────────
    # Count how many parent forms were submitted (by looking for parent_N_full_name)
    index = 0
    while True:
        prefix = f'parent_{index}_'
        if not post.get(f'{prefix}full_name', '').strip():
            # No data for this index — stop if we already have at least one
            if index > 0:
                break
            # index 0 must have data
            if index == 0 and not post.get(f'{prefix}full_name', '').strip():
                errors['parents'] = 'At least one parent / guardian is required.'
                break
        p_errors: dict = {}
        p_cleaned = validate_single_parent_dict(post, prefix, p_errors)
        if p_errors:
            for k, v in p_errors.items():
                errors[f'parent_{index}_{k}'] = v
        else:
            parents.append(p_cleaned)
        index += 1

    if not parents and 'parents' not in errors:
        errors['parents'] = 'At least one parent / guardian is required.'

    return parents, errors


def validate_single_parent_dict(
    post: dict,
    prefix: str,
    errors: dict,
) -> dict:
    """
    Validate one parent block from POST (keyed by prefix e.g. 'parent_0_').
    Writes errors into the provided errors dict.
    Returns a cleaned dict ready for Admission.parents_data.
    """
    cleaned: dict = {'existing': False}

    full_name = (post.get(f'{prefix}full_name') or '').strip()
    if not full_name:
        errors['full_name'] = 'Full name is required.'
    elif len(full_name) > 100:
        errors['full_name'] = 'Full name must not exceed 100 characters.'
    else:
        cleaned['full_name'] = full_name

    rel = (post.get(f'{prefix}relationship') or '').strip()
    if not rel:
        errors['relationship'] = 'Relationship is required.'
    elif rel not in VALID_RELATIONSHIPS:
        errors['relationship'] = 'Invalid relationship selected.'
    else:
        cleaned['relationship'] = rel

    phone = (post.get(f'{prefix}phone') or '').strip()
    if not phone:
        errors['phone'] = 'Phone number is required.'
    elif len(phone) > 15:
        errors['phone'] = 'Phone must not exceed 15 characters.'
    elif not phone.replace('+', '').replace(' ', '').replace('-', '').isdigit():
        errors['phone'] = 'Phone must contain only digits, spaces, hyphens or a leading +.'
    else:
        cleaned['phone'] = phone

    email = (post.get(f'{prefix}email') or '').strip()
    if email:
        try:
            validate_email(email)
            cleaned['email'] = email
        except ValidationError:
            errors['email'] = 'Enter a valid email address.'
    else:
        cleaned['email'] = ''

    cleaned['occupation'] = (post.get(f'{prefix}occupation') or '').strip()
    cleaned['employer']   = (post.get(f'{prefix}employer') or '').strip()
    cleaned['nin']        = (post.get(f'{prefix}nin') or '').strip()

    address = (post.get(f'{prefix}address') or '').strip()
    if not address:
        errors['address'] = 'Address is required.'
    else:
        cleaned['address'] = address

    return cleaned


def validate_admission_confirm_step(post: dict) -> tuple[dict, dict]:
    """
    Step 3 validation: confirm and save.
    Checks the submitting user's password.
    Returns (cleaned={'password': str}, errors).
    """
    errors:  dict = {}
    cleaned: dict = {}

    password = (post.get('confirm_password') or '').strip()
    if not password:
        errors['confirm_password'] = 'Password is required to save the application.'
    else:
        cleaned['password'] = password

    return cleaned, errors


# ═══════════════════════════════════════════════════════════════════════════════
#  VALIDATION — STATUS UPDATE
# ═══════════════════════════════════════════════════════════════════════════════

def validate_status_update(
    post: dict,
    current_status: str,
) -> tuple[dict, dict]:
    """Validate a status-change POST."""
    errors:  dict = {}
    cleaned: dict = {}

    new_status = (post.get('status') or '').strip()
    if not new_status:
        errors['status'] = 'New status is required.'
        return cleaned, errors

    if new_status not in VALID_STATUSES:
        errors['status'] = 'Invalid status selected.'
        return cleaned, errors

    allowed = STATUS_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        errors['status'] = (
            f'Cannot move from "{STATUS_LABELS[current_status]}" '
            f'to "{STATUS_LABELS[new_status]}". '
            f'Allowed: {", ".join(STATUS_LABELS[s] for s in allowed) or "none"}.'
        )
        return cleaned, errors

    cleaned['status'] = new_status

    if new_status == 'rejected':
        reason = (post.get('rejection_reason') or '').strip()
        if not reason:
            errors['rejection_reason'] = 'Rejection reason is required.'
        else:
            cleaned['rejection_reason'] = reason

    if new_status == 'approved':
        ad = _parse_date(post.get('admission_date', ''), 'Admission date', errors)
        if not ad:
            errors.setdefault('admission_date', 'Admission date is required when approving.')
        else:
            cleaned['admission_date'] = ad

    if new_status == 'shortlisted':
        id_ = _parse_date(post.get('interview_date', ''), 'Interview date', errors)
        cleaned['interview_date'] = id_

    cleaned['notes']           = (post.get('notes') or '').strip()
    cleaned['interview_notes'] = (post.get('interview_notes') or '').strip()

    return cleaned, errors


# ═══════════════════════════════════════════════════════════════════════════════
#  VALIDATION — VERIFY FLOW
# ═══════════════════════════════════════════════════════════════════════════════

def validate_verify_student_step(post: dict) -> tuple[dict, dict]:
    """
    Verify flow Step 2: validate enrolment data for the Student record.

    Returns (cleaned, errors).
    cleaned keys: student_id, current_class_id, academic_year, date_enrolled
    """
    errors:  dict = {}
    cleaned: dict = {}

    student_id_val = (post.get('student_id') or '').strip()
    if not student_id_val:
        errors['student_id'] = 'Student ID is required.'
    elif len(student_id_val) > 20:
        errors['student_id'] = 'Student ID must not exceed 20 characters.'
    else:
        from students.models import Student
        if Student.objects.filter(student_id=student_id_val).exists():
            errors['student_id'] = f'Student ID "{student_id_val}" is already in use.'
        else:
            cleaned['student_id'] = student_id_val

    class_id = (post.get('current_class') or '').strip()
    if not class_id:
        errors['current_class'] = 'Class is required.'
    else:
        try:
            cleaned['current_class_id'] = int(class_id)
        except ValueError:
            errors['current_class'] = 'Invalid class selected.'

    academic_year = (post.get('academic_year') or '').strip()
    if not academic_year:
        errors['academic_year'] = 'Academic year is required.'
    else:
        cleaned['academic_year'] = academic_year

    date_enrolled = _parse_date(
        post.get('date_enrolled', ''), 'Date enrolled', errors, required=True
    )
    if date_enrolled:
        cleaned['date_enrolled'] = date_enrolled

    return cleaned, errors


# ═══════════════════════════════════════════════════════════════════════════════
#  DB OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_or_create_student_token(student) -> str:
    """
    Return the shared access token for a student's family.
    If the student already has at least one parent relationship, reuse that token.
    Otherwise generate a new token.
    """
    from students.models import StudentParentRelationship
    existing = StudentParentRelationship.objects.filter(
        student=student
    ).values_list('access_token', flat=True).first()

    if existing:
        return existing
    return generate_access_token()


def create_student_from_admission(admission, enrol_data: dict):
    """
    Create a Student record from an Admission + enrolment form data.
    Sets admission.student and saves the admission.

    enrol_data keys: student_id, current_class_id, academic_year, date_enrolled

    Returns the created Student.
    """
    from students.models import Student

    student = Student.objects.create(
        student_id          = enrol_data['student_id'],
        first_name          = admission.first_name,
        last_name           = admission.last_name,
        other_names         = admission.other_names,
        date_of_birth       = admission.date_of_birth,
        gender              = admission.gender,
        nationality         = admission.nationality,
        district_of_origin  = admission.district_of_origin,
        religion            = admission.religion,
        birth_certificate_no = admission.birth_certificate_no,
        current_class_id    = enrol_data['current_class_id'],
        academic_year       = enrol_data['academic_year'],
        date_enrolled       = enrol_data['date_enrolled'],
        previous_school     = admission.previous_school,
        previous_class      = admission.previous_class,
        is_active           = True,
        admission           = admission,
    )
    return student


def create_parent_objects(
    parent_dict: dict,
    student,
    relationship: str,
    verified_by,
    access_token: str,
    is_primary: bool = False,
):
    """
    Create CustomUser + ParentProfile for one new parent dict,
    then create the StudentParentRelationship row.

    parent_dict — one element from Admission.parents_data (existing=False).
    student     — Student instance.
    access_token — the shared token for this student's family.

    Returns (CustomUser, ParentProfile, StudentParentRelationship).
    """
    from accounts.models import ParentProfile
    from students.models import StudentParentRelationship

    parent_id = generate_parent_id()

    # Create the CustomUser (username = parent_id, password = access_token)
    user = User.objects.create_parent_user(
        parent_id   = parent_id,
        password    = access_token,
        first_name  = _split_name(parent_dict.get('full_name', ''))[0],
        last_name   = _split_name(parent_dict.get('full_name', ''))[1],
        email       = parent_dict.get('email', ''),
        phone       = parent_dict.get('phone', ''),
        address     = parent_dict.get('address', ''),
        nin         = parent_dict.get('nin', ''),
        is_active   = True,
    )

    # Create the ParentProfile
    profile = ParentProfile.objects.create(
        user         = user,
        access_token = access_token,
        relationship = relationship,
        occupation   = parent_dict.get('occupation', ''),
        employer     = parent_dict.get('employer', ''),
    )

    # Create the relationship row
    rel = StudentParentRelationship.objects.create(
        student      = student,
        parent       = profile,
        relationship = relationship,
        access_token = access_token,
        is_primary   = is_primary,
    )

    return user, profile, rel


def link_existing_parent(
    parent_id_str: str,
    student,
    relationship: str,
    access_token: str,
    is_primary: bool = False,
):
    """
    Link an existing ParentProfile to a student.
    Updates the parent's password to the student's access_token
    ONLY if the parent has no existing relationships yet (first child).

    Returns (ParentProfile, StudentParentRelationship).
    """
    from accounts.models import ParentProfile
    from students.models import StudentParentRelationship

    profile = ParentProfile.objects.select_related('user').get(
        user__parent_id=parent_id_str
    )

    # Only update password if this parent has no other child relationships yet
    if not StudentParentRelationship.objects.filter(parent=profile).exists():
        profile.user.set_password(access_token)
        profile.user.save(update_fields=['password'])
        profile.access_token = access_token
        profile.save(update_fields=['access_token'])

    rel, _ = StudentParentRelationship.objects.get_or_create(
        student  = student,
        parent   = profile,
        defaults = {
            'relationship': relationship,
            'access_token': access_token,
            'is_primary':   is_primary,
        },
    )

    return profile, rel


# ═══════════════════════════════════════════════════════════════════════════════
#  INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _split_name(full_name: str) -> tuple[str, str]:
    """Split 'John Mary Doe' → ('John', 'Doe'). Falls back gracefully."""
    parts = full_name.strip().split()
    if not parts:
        return ('', '')
    if len(parts) == 1:
        return (parts[0], '')
    return (parts[0], parts[-1])


# ═══════════════════════════════════════════════════════════════════════════════
#  LIST STATS
# ═══════════════════════════════════════════════════════════════════════════════

def get_admission_list_stats() -> dict:
    """High-level statistics for the admissions list page."""
    from students.models import Admission
    today = date.today()
    qs    = Admission.objects.all()

    total       = qs.count()
    by_status   = {
        item['status']: item['count']
        for item in qs.values('status').annotate(count=Count('id'))
    }

    pending     = by_status.get('pending', 0)
    shortlisted = by_status.get('shortlisted', 0)
    approved    = by_status.get('approved', 0)
    rejected    = by_status.get('rejected', 0)
    waitlisted  = by_status.get('waitlisted', 0)
    enrolled    = by_status.get('enrolled', 0)

    verified    = qs.filter(is_verified=True).count()
    unverified  = approved - verified if approved > verified else 0

    approval_rate  = round((approved + enrolled) / total * 100, 1) if total else 0
    enrolment_rate = (
        round(enrolled / (approved + enrolled) * 100, 1)
        if (approved + enrolled) else 0
    )

    by_gender = list(qs.values('gender').annotate(count=Count('id')))

    by_year = list(
        qs.values('academic_year')
        .annotate(count=Count('id'))
        .order_by('-academic_year')
    )

    upcoming_interviews = list(
        qs.filter(
            interview_date__gte=today,
            status__in=('pending', 'shortlisted'),
        )
        .select_related('applied_class')
        .order_by('interview_date')[:5]
    )

    recent = list(
        qs.select_related('applied_class', 'reviewed_by')
        .order_by('-application_date')[:10]
    )

    years = list(
        qs.values_list('academic_year', flat=True)
        .distinct()
        .order_by('-academic_year')
    )

    return {
        'total':                total,
        'pending':              pending,
        'shortlisted':          shortlisted,
        'approved':             approved,
        'rejected':             rejected,
        'waitlisted':           waitlisted,
        'enrolled':             enrolled,
        'verified':             verified,
        'unverified':           unverified,
        'approval_rate':        approval_rate,
        'enrolment_rate':       enrolment_rate,
        'by_gender':            by_gender,
        'by_year':              by_year,
        'upcoming_interviews':  upcoming_interviews,
        'recent':               recent,
        'years':                years,
        'status_labels':        STATUS_LABELS,
        'today':                today,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  DETAIL STATS
# ═══════════════════════════════════════════════════════════════════════════════

def get_admission_detail_stats(admission) -> dict:
    """Stats and context for the single admission detail page."""
    from students.models import Admission
    today = date.today()

    days_since_application = (today - admission.application_date).days

    days_until_interview = None
    if admission.interview_date:
        days_until_interview = (admission.interview_date - today).days

    allowed_transitions = [
        (s, STATUS_LABELS[s])
        for s in STATUS_TRANSITIONS.get(admission.status, set())
    ]

    siblings = list(
        Admission.objects.filter(
            academic_year=admission.academic_year,
            applied_class=admission.applied_class,
        )
        .exclude(pk=admission.pk)
        .order_by('-application_date')[:5]
    )

    # Parse the parents_data JSON for display
    parents_list = admission.get_parents_data()

    can_verify = (
        admission.status == 'approved'
        and not admission.is_verified
    )
    is_enrolled = (
        admission.status == 'enrolled'
        and admission.student_id is not None
    )

    return {
        'days_since_application': days_since_application,
        'days_until_interview':   days_until_interview,
        'allowed_transitions':    allowed_transitions,
        'siblings':               siblings,
        'parents_list':           parents_list,
        'status_label':           STATUS_LABELS.get(admission.status, admission.status),
        'can_verify':             can_verify,
        'is_enrolled':            is_enrolled,
        'today':                  today,
    }
