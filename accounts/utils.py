# accounts/utils/accounts_utils.py
# ─────────────────────────────────────────────────────────────────────────────
# Helpers for accounts views:
#   - Parent ID and Employee ID generation
#   - Registration validation (parent / staff / admin)
#   - Profile edit validation (shared fields + type-specific fields)
# ─────────────────────────────────────────────────────────────────────────────

from datetime import date
from django.contrib.auth import get_user_model
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db.models import Max

User = get_user_model()


# ═══════════════════════════════════════════════════════════════════════════════
#  ID GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def generate_parent_id() -> str:
    """Auto-generate PAR<YEAR><SEQ>  e.g. PAR20250001. Call inside atomic()."""
    year   = date.today().year
    prefix = f'PAR{year}'
    last   = User.objects.filter(parent_id__startswith=prefix).aggregate(
        m=Max('parent_id')
    )['m']
    seq = (int(last.replace(prefix, '')) + 1) if last else 1
    return f'{prefix}{seq:04d}'


def generate_employee_id() -> str:
    """Auto-generate EMP<YEAR><SEQ>  e.g. EMP20250001. Call inside atomic()."""
    from accounts.models import StaffProfile
    year   = date.today().year
    prefix = f'EMP{year}'
    last   = StaffProfile.objects.filter(employee_id__startswith=prefix).aggregate(
        m=Max('employee_id')
    )['m']
    seq = (int(last.replace(prefix, '')) + 1) if last else 1
    return f'{prefix}{seq:04d}'


import random
import string
def generate_temp_key(length=12):
    characters = string.ascii_letters + string.digits

    # Ensure at least one lowercase, one uppercase, one digit
    password = [
        random.choice(string.ascii_lowercase),
        random.choice(string.ascii_uppercase),
        random.choice(string.digits),
    ]

    # Fill remaining characters
    password += [random.choice(characters) for _ in range(length - 3)]

    # Shuffle for randomness
    random.shuffle(password)

    return "".join(password)




# ═══════════════════════════════════════════════════════════════════════════════
#  SHARED FIELD VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def _validate_phone(value: str, field_label: str, errors: dict) -> str | None:
    v = value.strip()
    if not v:
        return ''
    if len(v) > 15:
        errors[field_label] = f'{field_label} must not exceed 15 characters.'
        return None
    digits = v.replace('+', '').replace(' ', '').replace('-', '')
    if not digits.isdigit():
        errors[field_label] = (
            f'{field_label} must contain only digits, spaces, hyphens, '
            f'or a leading +.'
        )
        return None
    return v


def _validate_name(value: str, field_label: str, errors: dict,
                   required: bool = True, max_len: int = 50) -> str | None:
    v = (value or '').strip()
    if required and not v:
        errors[field_label] = f'{field_label} is required.'
        return None
    if len(v) > max_len:
        errors[field_label] = f'{field_label} must not exceed {max_len} characters.'
        return None
    return v


def _validate_shared_user_fields(post: dict, errors: dict, cleaned: dict) -> None:
    """
    Validate fields that are the same for every user type:
    first_name, last_name, other_names, gender, email, phone, alt_phone, address, nin.
    Writes directly into errors and cleaned dicts.
    """
    first = _validate_name(post.get('first_name'), 'First name', errors, required=True)
    if first is not None:
        cleaned['first_name'] = first

    last = _validate_name(post.get('last_name'), 'Last name', errors, required=True)
    if last is not None:
        cleaned['last_name'] = last

    cleaned['other_names'] = (post.get('other_names') or '').strip()

    gender = (post.get('gender') or '').strip()
    if gender not in ('male', 'female', 'other', 'prefer_not_to_say', ''):
        errors['gender'] = 'Invalid gender selected.'
    else:
        cleaned['gender'] = gender

    email = (post.get('email') or '').strip()
    if email:
        try:
            validate_email(email)
            cleaned['email'] = email
        except ValidationError:
            errors['email'] = 'Enter a valid email address.'
    else:
        cleaned['email'] = ''

    phone = _validate_phone(post.get('phone', ''), 'Phone', errors)
    if phone is not None:
        cleaned['phone'] = phone

    alt = _validate_phone(post.get('alt_phone', ''), 'Alternative phone', errors)
    if alt is not None:
        cleaned['alt_phone'] = alt

    cleaned['address'] = (post.get('address') or '').strip()

    # nin = (post.get('nin') or '').strip()
    # if len(nin) > 20:
    #     errors['nin'] = 'NIN must not exceed 20 characters.'
    # else:
    #     cleaned['nin'] = nin


# ═══════════════════════════════════════════════════════════════════════════════
#  PARENT REGISTRATION VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def validate_and_parse_parent_registration(post: dict) -> tuple[dict, dict]:
    """
    Validate registration POST for a new parent user + profile.

    Returns (user_cleaned, profile_cleaned, errors) merged into two dicts:
        user_cleaned    — fields for CustomUser
        profile_cleaned — fields for ParentProfile

    Caller unpacks as:  user_c, prof_c, errors = ...
    Returned as a tuple of three.
    """
    errors:        dict = {}
    user_cleaned:  dict = {}
    prof_cleaned:  dict = {}

    # Shared user fields
    _validate_shared_user_fields(post, errors, user_cleaned)

    # Password
    password  = (post.get('password') or '').strip()
    password2 = (post.get('password2') or '').strip()
    if not password:
        errors['password'] = 'Password is required.'
    elif len(password) < 8:
        errors['password'] = 'Password must be at least 8 characters.'
    elif password != password2:
        errors['password2'] = 'Passwords do not match.'
    else:
        user_cleaned['password'] = password

    # ParentProfile fields
    relationship = (post.get('relationship') or '').strip()
    valid_rels   = {
        'father', 'mother', 'legal_guardian', 'uncle',
        'aunt', 'grandparent', 'sibling', 'other',
    }
    if not relationship:
        errors['relationship'] = 'Relationship to student is required.'
    elif relationship not in valid_rels:
        errors['relationship'] = 'Invalid relationship selected.'
    else:
        prof_cleaned['relationship'] = relationship

    prof_cleaned['occupation']       = (post.get('occupation') or '').strip()
    prof_cleaned['employer']         = (post.get('employer') or '').strip()
    prof_cleaned['work_phone']       = (post.get('work_phone') or '').strip()
    prof_cleaned['work_address']     = (post.get('work_address') or '').strip()
    prof_cleaned['district']         = (post.get('district') or '').strip()
    prof_cleaned['sub_county']       = (post.get('sub_county') or '').strip()
    prof_cleaned['village']          = (post.get('village') or '').strip()
    prof_cleaned['religion']         = (post.get('religion') or '').strip()
    prof_cleaned['emergency_contact_name']  = (post.get('emergency_contact_name') or '').strip()
    prof_cleaned['emergency_contact_phone'] = (post.get('emergency_contact_phone') or '').strip()
    prof_cleaned['emergency_contact_rel']   = (post.get('emergency_contact_rel') or '').strip()
    prof_cleaned['notes']            = (post.get('notes') or '').strip()

    return user_cleaned, prof_cleaned, errors


# ═══════════════════════════════════════════════════════════════════════════════
#  STAFF / TEACHER REGISTRATION VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

VALID_STAFF_ROLES = {
    'head_teacher', 'deputy_head', 'teacher', 'subject_teacher',
    'bursar', 'secretary', 'librarian', 'lab_technician',
    'nurse', 'security', 'cleaner', 'driver', 'cook', 'it_officer', 'other',
}
VALID_EMPLOYMENT_TYPES = {'permanent', 'contract', 'part_time', 'volunteer', 'intern'}
VALID_QUALIFICATIONS = {
    'ptc', 'grade3', 'diploma', 'degree', 'pgde', 'masters',
    'certificate', 'diploma_other', 'bachelors', 'none', 'other', '',
}
VALID_USER_TYPES_STAFF = {'teacher', 'staff', 'admin'}


def validate_and_parse_staff_registration(post: dict) -> tuple[dict, dict, dict]:
    """
    Validate registration POST for a new staff/teacher/admin user + profile.

    Returns (user_cleaned, profile_cleaned, errors).
    """
    errors:        dict = {}
    user_cleaned:  dict = {}
    prof_cleaned:  dict = {}

    # user_type
    # user_type = (post.get('user_type') or '').strip()
    # if user_type not in VALID_USER_TYPES_STAFF:
    #     errors['user_type'] = 'User type must be Teacher, Staff, or Admin.'
    # else:
    #     user_cleaned['user_type'] = user_type

    # # username (unique)
    # username = (post.get('username') or '').strip()
    # if not username:
    #     errors['username'] = 'Username is required.'
    # elif len(username) > 50:
    #     errors['username'] = 'Username must not exceed 50 characters.'
    # elif ' ' in username:
    #     errors['username'] = 'Username must not contain spaces.'
    # elif User.objects.filter(username=username).exists():
    #     errors['username'] = f'Username "{username}" is already taken.'
    # else:
    #     user_cleaned['username'] = username

    # Shared user fields
    _validate_shared_user_fields(post, errors, user_cleaned)

    # Password
    # password  = (post.get('password') or '').strip()
    # password2 = (post.get('password2') or '').strip()
    # if not password:
    #     errors['password'] = 'Password is required.'
    # elif len(password) < 8:
    #     errors['password'] = 'Password must be at least 8 characters.'
    # elif password != password2:
    #     errors['password2'] = 'Passwords do not match.'
    # else:
    #     user_cleaned['password'] = password

    # StaffProfile fields
    role = (post.get('role') or '').strip()
    if not role:
        errors['role'] = 'Role is required.'
    elif role not in VALID_STAFF_ROLES:
        errors['role'] = 'Invalid role selected.'
    else:
        prof_cleaned['role'] = role



    # emp_type = (post.get('employment_type') or 'permanent').strip()
    # if emp_type not in VALID_EMPLOYMENT_TYPES:
    #     errors['employment_type'] = 'Invalid employment type.'
    # else:
    #     prof_cleaned['employment_type'] = emp_type

    # date_joined
    # from datetime import datetime
    # dj_raw = (post.get('date_joined') or '').strip()
    # if not dj_raw:
    #     errors['date_joined'] = 'Date joined is required.'
    # else:
    #     parsed = None
    #     for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
    #         try:
    #             parsed = datetime.strptime(dj_raw, fmt).date()
    #             break
    #         except ValueError:
    #             continue
    #     if not parsed:
    #         errors['date_joined'] = 'Date joined is not a valid date (use YYYY-MM-DD).'
    #     else:
    #         prof_cleaned['date_joined'] = parsed

    # qualification = (post.get('qualification') or '').strip()
    # if qualification not in VALID_QUALIFICATIONS:
    #     errors['qualification'] = 'Invalid qualification selected.'
    # else:
    #     prof_cleaned['qualification'] = qualification

    prof_cleaned['specialization']   = (post.get('specialization') or '').strip()
    prof_cleaned['is_class_teacher']  = (
        str(post.get('is_class_teacher', '')).lower() in ('1', 'true', 'on', 'yes')
    )

    prof_cleaned['is_a_teaching_staff']  = (
        str(post.get('is_a_teaching_staff', '')).lower() in ('1', 'true', 'on', 'yes')
    )

    # prof_cleaned['nssf_number']       = (post.get('nssf_number') or '').strip()
    # prof_cleaned['tin_number']        = (post.get('tin_number') or '').strip()
    # prof_cleaned['salary_scale']      = (post.get('salary_scale') or '').strip()
    # prof_cleaned['bank_name']         = (post.get('bank_name') or '').strip()
    # prof_cleaned['bank_account']      = (post.get('bank_account') or '').strip()
    # prof_cleaned['bio']               = (post.get('bio') or '').strip()
    # prof_cleaned['notes']             = (post.get('notes') or '').strip()

    

    # class_managed FK (optional)
    class_id = (post.get('class_managed') or '').strip()
    if class_id:
        try:
            prof_cleaned['class_managed_id'] = int(class_id)
        except ValueError:
            errors['class_managed'] = 'Invalid class selected.'
    else:
        prof_cleaned['class_managed_id'] = None


 


    return user_cleaned, prof_cleaned, errors


# ═══════════════════════════════════════════════════════════════════════════════
#  LIST STATS
# ═══════════════════════════════════════════════════════════════════════════════

def get_user_list_stats() -> dict:
    """High-level stats for the user management dashboard."""
    from django.db.models import Count
    qs = User.objects.all()

    by_type = {
        row['user_type']: row['count']
        for row in qs.values('user_type').annotate(count=Count('id'))
    }

    return {
        'total':    qs.count(),
        'parents':  by_type.get('parent', 0),
        'teachers': by_type.get('teacher', 0),
        'staff':    by_type.get('staff', 0),
        'admins':   by_type.get('admin', 0),
        'active':   qs.filter(is_active=True).count(),
        'inactive': qs.filter(is_active=False).count(),
    }




from academics.models import ClassSubject

def get_selected_clases_subjects(subjects):
    classes_subjects = []
    for s in subjects:
        for k,v in s.items():
            cls_subjects = ClassSubject.objects.filter(
                school_class__supported_class__key = v
            )

            if cls_subjects:
                class_s = []
                for cs in cls_subjects:
                    class_s.append({
                        "name":cs.subject.name,
                        "code":cs.subject.code
                    }) 
                
                classes_subjects.append({
                    "key":v,
                    "name":cs.school_class.supported_class.name,
                    "subjects":class_s
                })

    return classes_subjects