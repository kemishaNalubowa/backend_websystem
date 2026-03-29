# school/views/setting_views.py
# ─────────────────────────────────────────────────────────────────────────────
# SchoolSetting views — singleton pattern (only one record ever exists).
#
# Views:
#   school_profile        — full read-only profile page
#   school_profile_edit   — edit the full profile (GET / POST)
#   school_profile_mini   — compact summary card (for dashboards / headers)
#   school_settings       — academic & report-card configuration only
#
# Rules:
#   - Function-based views only
#   - No Django Forms / forms.py
#   - No Class-based Views
#   - No JSON responses
#   - Manual validation via setting_utils
#   - django.contrib.messages for all feedback
#   - login_required on every view
#   - Image uploads handled via request.FILES
# ─────────────────────────────────────────────────────────────────────────────

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render

from school.models import SchoolSetting
from school.utils.setting_utils import (
    CURRICULUM_LABELS,
    OWNERSHIP_LABELS,
    REGION_LABELS,
    SCHOOL_TYPE_LABELS,
    get_display_labels,
    get_profile_completeness,
    get_school_setting,
    validate_and_parse_setting,
    validate_and_parse_settings_only,
)

_T = 'school/settings/'

# ── Choice lists passed to templates ─────────────────────────────────────────
_OWNERSHIP_CHOICES  = list(OWNERSHIP_LABELS.items())
_TYPE_CHOICES       = list(SCHOOL_TYPE_LABELS.items())
_REGION_CHOICES     = list(REGION_LABELS.items())
_CURRICULUM_CHOICES = list(CURRICULUM_LABELS.items())


# ═══════════════════════════════════════════════════════════════════════════════
#  1. FULL SCHOOL PROFILE  (read-only display)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def school_profile(request):
    """
    Full read-only school profile page.

    Displays every field on SchoolSetting grouped into sections:
        Identity       — name, motto, logo, stamp, signature
        Registration   — MoES number, year, ownership, type, curriculum
        Location       — address, district, region, county, sub-county,
                         village, P.O. Box
        Contact        — phone, alt phone, email, website
        Academic       — nursery, primary, report footer

    Also shows:
        - Profile completeness score with list of missing fields
        - Quick links to Edit Profile and Settings
    """
    setting = get_school_setting()

    if not setting:
        messages.warning(
            request,
            'No school profile has been set up yet. '
            'Please complete the school profile before continuing.'
        )
        return redirect('school:school_profile_edit')

    completeness = get_profile_completeness(setting)
    labels       = get_display_labels(setting)

    # Summary stats for the header strip
    from students.models import Student
    from accounts.models import CustomUser
    from academics.models import SchoolClass, Term

    current_term   = Term.objects.filter(is_current=True).first()
    student_count  = Student.objects.filter(is_active=True).count()
    teacher_count  = CustomUser.objects.filter(is_active=True, user_type="teacher").count()
    class_count    = SchoolClass.objects.filter(is_active=True).count()

    context = {
        'setting':        setting,
        'completeness':   completeness,
        'current_term':   current_term,
        'student_count':  student_count,
        'teacher_count':  teacher_count,
        'class_count':    class_count,
        'page_title':     setting.school_name,
        **labels,
    }
    return render(request, f'{_T}profile.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  2. EDIT SCHOOL PROFILE
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def school_profile_edit(request):
    """
    Edit (or initially create) the school profile.

    GET  — render form pre-filled with existing values, or blank if none.
    POST — validate all fields manually; save on success with success message;
           re-render with per-field error highlights on failure.

    Image handling:
        school_logo, school_stamp, head_teacher_signature are uploaded via
        request.FILES. Each is validated for extension and size.
        A 'clear_X' checkbox in POST ('clear_logo', 'clear_stamp',
        'clear_signature') deletes the existing image for that field
        without requiring a new upload.

    Singleton logic:
        If no record exists, create one.
        If one exists, update it.
        A second record is never created.
    """
    setting = get_school_setting()
    is_new  = setting is None

    _form_ctx = lambda post, errors: {
        'setting':           setting,
        'is_new':            is_new,
        'post':              post,
        'errors':            errors,
        'page_title':        'Set Up School Profile' if is_new else 'Edit School Profile',
        'ownership_choices': _OWNERSHIP_CHOICES,
        'type_choices':      _TYPE_CHOICES,
        'region_choices':    _REGION_CHOICES,
        'curriculum_choices': _CURRICULUM_CHOICES,
    }

    if request.method == 'GET':
        return render(request, f'{_T}edit.html', _form_ctx({}, {}))

    # ── POST ──────────────────────────────────────────────────────────────────
    cleaned, errors = validate_and_parse_setting(request.POST, request.FILES)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}edit.html', _form_ctx(request.POST, errors))

    try:
        with transaction.atomic():
            if is_new:
                setting = SchoolSetting()

            # Apply all scalar cleaned fields
            for field, value in cleaned.items():
                setattr(setting, field, value)

            # ── Image fields ──────────────────────────────────────────────────
            # Pattern per image field:
            #   1. If clear checkbox ticked → delete old file, set to None
            #   2. If new file uploaded     → assign new file
            #   3. Otherwise               → leave existing file untouched

            # School Logo
            if request.POST.get('clear_logo'):
                if setting.school_logo:
                    setting.school_logo.delete(save=False)
                setting.school_logo = None
            elif request.FILES.get('school_logo'):
                setting.school_logo = request.FILES['school_logo']

            # School Stamp
            if request.POST.get('clear_stamp'):
                if setting.school_stamp:
                    setting.school_stamp.delete(save=False)
                setting.school_stamp = None
            elif request.FILES.get('school_stamp'):
                setting.school_stamp = request.FILES['school_stamp']

            # Head Teacher Signature
            if request.POST.get('clear_signature'):
                if setting.head_teacher_signature:
                    setting.head_teacher_signature.delete(save=False)
                setting.head_teacher_signature = None
            elif request.FILES.get('head_teacher_signature'):
                setting.head_teacher_signature = request.FILES['head_teacher_signature']

            setting.save()

    except Exception as exc:
        messages.error(request, f'Could not save school profile: {exc}')
        return render(request, f'{_T}edit.html', _form_ctx(request.POST, {}))

    action = 'created' if is_new else 'updated'
    messages.success(
        request,
        f'School profile for "{setting.school_name}" has been {action} successfully.'
    )
    return redirect('school:school_profile')


# ═══════════════════════════════════════════════════════════════════════════════
#  3. MINI SCHOOL PROFILE  (compact card — for dashboards, report headers)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def school_profile_mini(request):
    """
    Compact school profile summary page.

    Shows only the most essential identity and contact fields:
        - Logo + school name + motto
        - District / region
        - Phone + email
        - Has nursery / primary flags
        - Current academic term
        - Profile completeness score (with nudge to complete if < 100%)

    Designed to be referenced from dashboards or rendered as a widget-like
    standalone page (e.g. in a modal or sidebar).
    """
    setting = get_school_setting()

    if not setting:
        messages.warning(
            request,
            'School profile is not set up yet.'
        )
        return redirect('school:school_profile_edit')

    completeness  = get_profile_completeness(setting)
    labels        = get_display_labels(setting)

    from academics.models import Term
    current_term = Term.objects.filter(is_current=True).first()

    context = {
        'setting':       setting,
        'completeness':  completeness,
        'current_term':  current_term,
        'page_title':    setting.school_name,
        **labels,
    }
    return render(request, f'{_T}mini.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  4. SCHOOL SETTINGS  (academic config + report card settings only)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def school_settings(request):
    """
    Settings page — edits only the academic configuration subset:
        - School type (Day / Boarding / Mixed)
        - Ownership (Government / Private / Community / Faith-based)
        - Curriculum
        - Has Nursery / Has Primary sections
        - Report card footer text

    This is intentionally separate from the full profile edit so that
    the head teacher can tweak academic settings without navigating
    through the full profile form.

    GET  — render settings form pre-filled with current values.
    POST — validate; save; redirect back to settings with a success message.

    Guard: if no school profile exists yet, redirects to the full edit form.
    """
    setting = get_school_setting()

    if not setting:
        messages.warning(
            request,
            'Please complete the school profile setup before adjusting settings.'
        )
        return redirect('school:school_profile_edit')

    _form_ctx = lambda post, errors: {
        'setting':            setting,
        'post':               post,
        'errors':             errors,
        'page_title':         'School Settings',
        'ownership_choices':  _OWNERSHIP_CHOICES,
        'type_choices':       _TYPE_CHOICES,
        'curriculum_choices': _CURRICULUM_CHOICES,
        **get_display_labels(setting),
    }

    if request.method == 'GET':
        return render(request, f'{_T}settings.html', _form_ctx({}, {}))

    # ── POST ──────────────────────────────────────────────────────────────────
    cleaned, errors = validate_and_parse_settings_only(request.POST)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}settings.html', _form_ctx(request.POST, errors))

    try:
        with transaction.atomic():
            for field, value in cleaned.items():
                setattr(setting, field, value)
            setting.save(
                update_fields=list(cleaned.keys()) + ['updated_at']
                if hasattr(setting, 'updated_at') else list(cleaned.keys())
            )
    except Exception as exc:
        messages.error(request, f'Could not save settings: {exc}')
        return render(request, f'{_T}settings.html', _form_ctx(request.POST, {}))

    messages.success(request, 'School settings have been saved successfully.')
    return redirect('school:school_settings')
