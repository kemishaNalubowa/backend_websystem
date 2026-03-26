from decimal import Decimal, InvalidOperation
from .models import (
    ASSESSMENT_TYPE_CHOICES,
    MONTH_CHOICES,
    AssessmentClass,
    AssessmentTeacher,
    AssessmentPassMark,
    AssessmentPerformance,
)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

VALID_ASSESSMENT_TYPES = [c[0] for c in ASSESSMENT_TYPE_CHOICES]
VALID_MONTHS           = [c[0] for c in MONTH_CHOICES]
VALID_VENUE_CHOICES    = [c[0] for c in AssessmentClass.VENUE_CHOICES]
VALID_TEACHER_ROLES    = [c[0] for c in AssessmentTeacher.ROLE_CHOICES]
VALID_PASS_TYPES       = [c[0] for c in AssessmentPassMark.PASS_TYPE_CHOICES]
VALID_GRADES           = [c[0] for c in AssessmentPerformance.GRADE_CHOICES]
VALID_NURSERY_RATINGS  = [c[0] for c in AssessmentPerformance.NURSERY_RATING_CHOICES]

ALLOWED_FILE_EXTENSIONS = {'.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png', '.webp'}
MAX_FILE_MB = 10


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def _validate_file(files, field_name, errors):
    """Validates an optional uploaded file. Returns the file object or None."""
    f = files.get(field_name) if files else None
    if not f:
        return None
    ext = ('.' + f.name.rsplit('.', 1)[-1].lower()) if '.' in f.name else ''
    if ext not in ALLOWED_FILE_EXTENSIONS:
        errors[field_name] = (
            f'Invalid file type. Allowed: {", ".join(sorted(ALLOWED_FILE_EXTENSIONS))}'
        )
        return None
    if f.size > MAX_FILE_MB * 1024 * 1024:
        errors[field_name] = f'File must not exceed {MAX_FILE_MB} MB.'
        return None
    return f


def _parse_decimal(raw, field_name, errors, label='Value',
                   min_val=None, max_val=None, required=True):
    """
    Parses a decimal from a raw string.
    Returns Decimal on success, None on failure (errors dict is populated).
    """
    raw = (raw or '').strip()
    if not raw:
        if required:
            errors[field_name] = f'{label} is required.'
        return None
    try:
        val = Decimal(raw)
    except InvalidOperation:
        errors[field_name] = f'{label} must be a valid number.'
        return None
    if min_val is not None and val < Decimal(str(min_val)):
        errors[field_name] = f'{label} must be at least {min_val}.'
        return None
    if max_val is not None and val > Decimal(str(max_val)):
        errors[field_name] = f'{label} must not exceed {max_val}.'
        return None
    return val


def _parse_int(raw, field_name, errors, label='Value',
               min_val=None, max_val=None, required=True):
    raw = (raw or '').strip()
    if not raw:
        if required:
            errors[field_name] = f'{label} is required.'
        return None
    try:
        val = int(raw)
    except (ValueError, TypeError):
        errors[field_name] = f'{label} must be a whole number.'
        return None
    if min_val is not None and val < min_val:
        errors[field_name] = f'{label} must be at least {min_val}.'
        return None
    if max_val is not None and val > max_val:
        errors[field_name] = f'{label} must not exceed {max_val}.'
        return None
    return val


def _parse_date(raw, field_name, errors, label='Date', required=True):
    from datetime import date
    raw = (raw or '').strip()
    if not raw:
        if required:
            errors[field_name] = f'{label} is required.'
        return None
    try:
        return date.fromisoformat(raw)        # expects YYYY-MM-DD from <input type="date">
    except ValueError:
        errors[field_name] = f'{label} must be a valid date (YYYY-MM-DD).'
        return None


def _parse_time(raw, field_name, errors, label='Time', required=True):
    from datetime import time as dt_time
    raw = (raw or '').strip()
    if not raw:
        if required:
            errors[field_name] = f'{label} is required.'
        return None
    try:
        parts = raw.split(':')
        if len(parts) < 2:
            raise ValueError
        h, m = int(parts[0]), int(parts[1])
        return dt_time(h, m)
    except (ValueError, TypeError):
        errors[field_name] = f'{label} must be a valid time (HH:MM).'
        return None


def _resolve_fk(model, pk_raw, field_name, errors, label):
    """Resolve a foreign key from a raw pk string. Returns instance or None."""
    pk_raw = (pk_raw or '').strip()
    if not pk_raw:
        errors[field_name] = f'{label} is required.'
        return None
    try:
        return model.objects.get(pk=pk_raw)
    except model.DoesNotExist:
        errors[field_name] = f'Selected {label} does not exist.'
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 1. Validate Assessment (add / edit)
# ─────────────────────────────────────────────────────────────────────────────

def validate_assessment(data, files=None):
    """
    Validates POST data for Assessment create/edit.
    Returns (errors dict, cleaned dict).
    """
    from academics.models import Term

    errors  = {}
    cleaned = {}

    # title
    title = data.get('title', '').strip()
    if not title:
        errors['title'] = 'Title is required.'
    elif len(title) < 3:
        errors['title'] = 'Title must be at least 3 characters.'
    elif len(title) > 200:
        errors['title'] = 'Title cannot exceed 200 characters.'
    else:
        cleaned['title'] = title

    # assessment_type
    atype = data.get('assessment_type', '').strip()
    if not atype:
        errors['assessment_type'] = 'Assessment type is required.'
    elif atype not in VALID_ASSESSMENT_TYPES:
        errors['assessment_type'] = 'Invalid assessment type.'
    else:
        cleaned['assessment_type'] = atype

    # description (optional)
    cleaned['description'] = data.get('description', '').strip()

    # term
    term = _resolve_fk(Term, data.get('term'), 'term', errors, 'Term')
    if term:
        cleaned['term'] = term

    # academic_year
    ay = data.get('academic_year', '').strip()
    if not ay:
        errors['academic_year'] = 'Academic year is required.'
    else:
        cleaned['academic_year'] = ay

    # month
    month_raw = data.get('month', '').strip()
    if not month_raw:
        errors['month'] = 'Month is required.'
    else:
        try:
            month_int = int(month_raw)
            if month_int not in VALID_MONTHS:
                raise ValueError
            cleaned['month'] = month_int
        except (ValueError, TypeError):
            errors['month'] = 'Invalid month selected.'

    # date_given
    dg = _parse_date(data.get('date_given'), 'date_given', errors, 'Date given')
    if dg:
        cleaned['date_given'] = dg

    # date_due (optional)
    dd = _parse_date(data.get('date_due'), 'date_due', errors, 'Due date', required=False)
    if dd:
        cleaned['date_due'] = dd

    # date_results_released (optional)
    dr = _parse_date(data.get('date_results_released'), 'date_results_released',
                     errors, 'Results release date', required=False)
    if dr:
        cleaned['date_results_released'] = dr

    # total_marks
    tm = _parse_decimal(data.get('total_marks'), 'total_marks', errors,
                        'Total marks', min_val=1)
    if tm is not None:
        cleaned['total_marks'] = tm

    # duration_minutes (optional)
    dur = _parse_int(data.get('duration_minutes'), 'duration_minutes', errors,
                     'Duration (minutes)', min_val=1, required=False)
    if dur is not None:
        cleaned['duration_minutes'] = dur

    # boolean flags
    cleaned['is_published']      = data.get('is_published')      == 'on'
    cleaned['results_published'] = data.get('results_published') == 'on'

    # notes (optional)
    cleaned['notes'] = data.get('notes', '').strip()

    # paper_file and marking_scheme (optional files)
    for fname in ('paper_file', 'marking_scheme'):
        f = _validate_file(files, fname, errors)
        if f:
            cleaned[fname] = f

    return errors, cleaned


# ─────────────────────────────────────────────────────────────────────────────
# 2. Validate AssessmentClass
# ─────────────────────────────────────────────────────────────────────────────

def validate_assessment_class(data, assessment):
    from academics.models import SchoolClass
    from accounts.models  import CustomUser

    errors  = {}
    cleaned = {}

    school_class = _resolve_fk(SchoolClass, data.get('school_class'),
                                'school_class', errors, 'Class')
    if school_class:
        if AssessmentClass.objects.filter(
                assessment=assessment, school_class=school_class).exists():
            errors['school_class'] = 'This class is already linked to this assessment.'
        else:
            cleaned['school_class'] = school_class

    si = _parse_int(data.get('students_invited'), 'students_invited', errors,
                    'Students invited', min_val=0)
    if si is not None:
        cleaned['students_invited'] = si

    ss = _parse_int(data.get('students_sat'), 'students_sat', errors,
                    'Students sat', min_val=0)
    if ss is not None:
        cleaned['students_sat'] = ss

    sa = _parse_int(data.get('students_absent'), 'students_absent', errors,
                    'Students absent', min_val=0, required=False)
    if sa is not None:
        cleaned['students_absent'] = sa

    venue = data.get('venue', '').strip()
    if venue and venue not in VALID_VENUE_CHOICES:
        errors['venue'] = 'Invalid venue selected.'
    else:
        cleaned['venue'] = venue

    invig_pk = data.get('invigilator', '').strip()
    if invig_pk:
        invig = _resolve_fk(CustomUser, invig_pk, 'invigilator', errors, 'Invigilator')
        if invig:
            cleaned['invigilator'] = invig

    start = _parse_time(data.get('start_time'), 'start_time', errors,
                        'Start time', required=False)
    if start:
        cleaned['start_time'] = start

    end = _parse_time(data.get('end_time'), 'end_time', errors,
                      'End time', required=False)
    if end:
        cleaned['end_time'] = end

    cleaned['class_remarks'] = data.get('class_remarks', '').strip()[:300]

    return errors, cleaned


# ─────────────────────────────────────────────────────────────────────────────
# 3. Validate AssessmentSubject
# ─────────────────────────────────────────────────────────────────────────────

def validate_assessment_subject(data, files=None, assessment=None):
    from academics.models import Subject
    from .models import AssessmentSubject

    errors  = {}
    cleaned = {}

    subject = _resolve_fk(Subject, data.get('subject'), 'subject', errors, 'Subject')
    if subject:
        if assessment and AssessmentSubject.objects.filter(
                assessment=assessment, subject=subject).exists():
            errors['subject'] = 'This subject is already linked to this assessment.'
        else:
            cleaned['subject'] = subject

    tm = _parse_decimal(data.get('total_marks'), 'total_marks', errors,
                        'Total marks', min_val=1)
    if tm is not None:
        cleaned['total_marks'] = tm

    so = _parse_int(data.get('sort_order'), 'sort_order', errors,
                    'Sort order', min_val=0, required=False)
    if so is not None:
        cleaned['sort_order'] = so

    cleaned['notes'] = data.get('notes', '').strip()[:200]

    f = _validate_file(files, 'paper_file', errors)
    if f:
        cleaned['paper_file'] = f

    return errors, cleaned


# ─────────────────────────────────────────────────────────────────────────────
# 4. Validate AssessmentTeacher
# ─────────────────────────────────────────────────────────────────────────────

def validate_assessment_teacher(data, assessment):
    from accounts.models  import Teacher
    from academics.models import Subject, SchoolClass

    errors  = {}
    cleaned = {}

    teacher = _resolve_fk(Teacher, data.get('teacher'), 'teacher', errors, 'Teacher')
    if teacher:
        cleaned['teacher'] = teacher

    role = data.get('role', '').strip()
    if not role:
        errors['role'] = 'Role is required.'
    elif role not in VALID_TEACHER_ROLES:
        errors['role'] = 'Invalid role selected.'
    else:
        cleaned['role'] = role

    # unique_together: assessment + teacher + role
    if teacher and role:
        if AssessmentTeacher.objects.filter(
                assessment=assessment, teacher=teacher, role=role).exists():
            errors['role'] = (
                'This teacher already has this role in the assessment.'
            )

    subj_pk = data.get('subject', '').strip()
    if subj_pk:
        subj = _resolve_fk(Subject, subj_pk, 'subject', errors, 'Subject')
        if subj:
            cleaned['subject'] = subj

    class_pk = data.get('school_class', '').strip()
    if class_pk:
        sc = _resolve_fk(SchoolClass, class_pk, 'school_class', errors, 'Class')
        if sc:
            cleaned['school_class'] = sc

    cleaned['notes'] = data.get('notes', '').strip()[:200]

    return errors, cleaned


# ─────────────────────────────────────────────────────────────────────────────
# 5. Validate AssessmentPassMark
# ─────────────────────────────────────────────────────────────────────────────

def validate_assessment_passmark(data, assessment):
    from accounts.models  import Teacher
    from academics.models import Subject

    errors  = {}
    cleaned = {}

    subject = _resolve_fk(Subject, data.get('subject'), 'subject', errors, 'Subject')
    if subject:
        if AssessmentPassMark.objects.filter(
                assessment=assessment, subject=subject).exists():
            errors['subject'] = (
                'A passmark for this subject already exists. Edit the existing one instead.'
            )
        else:
            cleaned['subject'] = subject

    pass_type = data.get('pass_type', '').strip()
    if not pass_type:
        errors['pass_type'] = 'Pass type is required.'
    elif pass_type not in VALID_PASS_TYPES:
        errors['pass_type'] = 'Invalid pass type.'
    else:
        cleaned['pass_type'] = pass_type

    if pass_type == 'percentage':
        pv = _parse_decimal(data.get('pass_value'), 'pass_value', errors,
                            'Pass value', min_val=1, max_val=100)
    else:
        pv = _parse_decimal(data.get('pass_value'), 'pass_value', errors,
                            'Pass value', min_val=1)
    if pv is not None:
        cleaned['pass_value'] = pv

    set_by_pk = data.get('set_by', '').strip()
    if set_by_pk:
        teacher = _resolve_fk(Teacher, set_by_pk, 'set_by', errors, 'Teacher')
        if teacher:
            cleaned['set_by'] = teacher

    cleaned['notes'] = data.get('notes', '').strip()[:200]

    return errors, cleaned


# ─────────────────────────────────────────────────────────────────────────────
# 6. Validate AssessmentPerformance (add / edit)
# ─────────────────────────────────────────────────────────────────────────────

def validate_performance(data, assessment, instance=None):
    """
    Validates performance data for add or edit.
    instance is provided on edit (so unique_together check skips self).
    """
    from students.models  import Student
    from academics.models import Subject, SchoolClass

    errors  = {}
    cleaned = {}

    # ── Core FKs ─────────────────────────────────────────────────────────────
    student = _resolve_fk(Student, data.get('student'), 'student', errors, 'Student')
    if student:
        cleaned['student'] = student

    subject = _resolve_fk(Subject, data.get('subject'), 'subject', errors, 'Subject')
    if subject:
        cleaned['subject'] = subject

    school_class = _resolve_fk(SchoolClass, data.get('school_class'),
                                'school_class', errors, 'Class')
    if school_class:
        cleaned['school_class'] = school_class

    # unique_together: assessment + student + subject
    if student and subject:
        qs = AssessmentPerformance.objects.filter(
            assessment=assessment, student=student, subject=subject
        )
        if instance:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            errors['student'] = (
                'A performance record for this student and subject already exists.'
            )

    # ── Absence ───────────────────────────────────────────────────────────────
    is_absent = data.get('is_absent') == 'on'
    cleaned['is_absent'] = is_absent
    cleaned['absent_reason'] = data.get('absent_reason', '').strip()[:200]

    # ── Nursery vs Primary ───────────────────────────────────────────────────
    nursery_rating = data.get('nursery_rating', '').strip()
    if nursery_rating:
        if nursery_rating not in VALID_NURSERY_RATINGS:
            errors['nursery_rating'] = 'Invalid nursery rating.'
        else:
            cleaned['nursery_rating'] = nursery_rating
    else:
        cleaned['nursery_rating'] = ''

    # Marks (required only if not absent and no nursery rating)
    is_nursery = bool(nursery_rating)
    if not is_absent and not is_nursery:
        mo = _parse_decimal(data.get('marks_obtained'), 'marks_obtained', errors,
                            'Marks obtained', min_val=0)
        if mo is not None:
            cleaned['marks_obtained'] = mo

        tm = _parse_decimal(data.get('total_marks'), 'total_marks', errors,
                            'Total marks', min_val=1)
        if tm is not None:
            cleaned['total_marks'] = tm

        # Cross-validate: marks_obtained ≤ total_marks
        if mo is not None and tm is not None and mo > tm:
            errors['marks_obtained'] = 'Marks obtained cannot exceed total marks.'
    else:
        # Fill defaults so model save() doesn't break
        tm_raw = data.get('total_marks', '').strip()
        tm = _parse_decimal(tm_raw, 'total_marks', errors, 'Total marks', min_val=1)
        if tm is not None:
            cleaned['total_marks'] = tm

    # ── Feedback ──────────────────────────────────────────────────────────────
    cleaned['remarks'] = data.get('remarks', '').strip()[:300]
    cleaned['is_verified'] = data.get('is_verified') == 'on'

    return errors, cleaned


# ─────────────────────────────────────────────────────────────────────────────
# 7. Performance summary for detail page
# ─────────────────────────────────────────────────────────────────────────────

def build_performance_summary(assessment):
    """
    Returns a dict of summary stats for an assessment's detail page.
    """
    perfs = AssessmentPerformance.objects.filter(assessment=assessment)

    total      = perfs.count()
    passed     = perfs.filter(is_pass=True).count()
    failed     = perfs.filter(is_pass=False).count()
    absent     = perfs.filter(is_absent=True).count()
    verified   = perfs.filter(is_verified=True).count()

    return {
        'total':    total,
        'passed':   passed,
        'failed':   failed,
        'absent':   absent,
        'verified': verified,
        'pass_rate': round((passed / total * 100), 1) if total else 0,
    }
