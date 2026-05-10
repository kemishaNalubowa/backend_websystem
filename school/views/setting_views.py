# school/views/setting_views.py
# ─────────────────────────────────────────────────────────────────────────────
# Rules: FBV only | no Forms | no CBVs | no JSON | manual validation |
#        messages for feedback | login_required | transaction.atomic on saves
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

_OWNERSHIP_CHOICES  = list(OWNERSHIP_LABELS.items())
_TYPE_CHOICES       = list(SCHOOL_TYPE_LABELS.items())
_REGION_CHOICES     = list(REGION_LABELS.items())
_CURRICULUM_CHOICES = list(CURRICULUM_LABELS.items())

from permissions.decorators import has_permission





# ═══════════════════════════════════════════════════════════════════════════════
#  1. PROFILE  (read-only)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('school_profile', action='read')
def school_profile(request):
    setting = get_school_setting()

    if not setting:
        messages.warning(
            request,
            'No school profile set up yet. Please complete the school profile first.'
        )
        return redirect('school:school_profile_edit')

    from academics.models import Term
    current_term = Term.objects.filter(is_active=True).first()

    context = {
        'setting':      setting,
        'completeness': get_profile_completeness(setting),
        'current_term': current_term,
        'page_title':   setting.school_name,
        **get_display_labels(setting),
    }
    return render(request, f'{_T}profile.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  2. EDIT PROFILE
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('school_profile', action='edit')
def school_profile_edit(request):
    setting = get_school_setting()
    is_new  = setting is None

    def _ctx(post, errors):
        return {
            'setting':            setting,
            'is_new':             is_new,
            'post':               post,
            'errors':             errors,
            'page_title':         'Set Up School Profile' if is_new else 'Edit School Profile',
            'ownership_choices':  _OWNERSHIP_CHOICES,
            'type_choices':       _TYPE_CHOICES,
            'region_choices':     _REGION_CHOICES,
            'curriculum_choices': _CURRICULUM_CHOICES,
        }

    if request.method == 'GET':
        return render(request, f'{_T}edit.html', _ctx({}, {}))

    cleaned, errors = validate_and_parse_setting(request.POST, request.FILES)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}edit.html', _ctx(request.POST, errors))

    try:
        with transaction.atomic():
            if is_new:
                setting = SchoolSetting()

            for field, value in cleaned.items():
                setattr(setting, field, value)

            # Logo
            if request.POST.get('clear_logo'):
                if setting.school_logo:
                    setting.school_logo.delete(save=False)
                setting.school_logo = None
            elif request.FILES.get('school_logo'):
                setting.school_logo = request.FILES['school_logo']

            # Stamp
            if request.POST.get('clear_stamp'):
                if setting.school_stamp:
                    setting.school_stamp.delete(save=False)
                setting.school_stamp = None
            elif request.FILES.get('school_stamp'):
                setting.school_stamp = request.FILES['school_stamp']

            # Signature
            if request.POST.get('clear_signature'):
                if setting.head_teacher_signature:
                    setting.head_teacher_signature.delete(save=False)
                setting.head_teacher_signature = None
            elif request.FILES.get('head_teacher_signature'):
                setting.head_teacher_signature = request.FILES['head_teacher_signature']

            setting.save()

    except Exception as exc:
        messages.error(request, f'Could not save school profile: {exc}')
        return render(request, f'{_T}edit.html', _ctx(request.POST, {}))

    action = 'created' if is_new else 'updated'
    messages.success(
        request,
        f'School profile for "{setting.school_name}" has been {action} successfully.'
    )
    return redirect('school:school_profile')


# ═══════════════════════════════════════════════════════════════════════════════
#  3. MINI PROFILE  (compact card)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('school_profile', action='edit')
def school_profile_mini(request):
    setting = get_school_setting()

    if not setting:
        messages.warning(request, 'School profile is not set up yet.')
        return redirect('school:school_profile_edit')

    from academics.models import Term
    current_term = Term.objects.filter(is_current=True).first()

    context = {
        'setting':      setting,
        'completeness': get_profile_completeness(setting),
        'current_term': current_term,
        'page_title':   setting.school_name,
        **get_display_labels(setting),
    }
    return render(request, f'{_T}mini.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  4. SETTINGS  (academic config only)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('school_settings', action='ed')
def school_settings(request):
    setting = get_school_setting()

    if not setting:
        messages.warning(
            request,
            'Please complete the school profile setup before adjusting settings.'
        )
        return redirect('school:school_profile_edit')

    def _ctx(post, errors):
        return {
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
        return render(request, f'{_T}settings.html', _ctx({}, {}))

    cleaned, errors = validate_and_parse_settings_only(request.POST)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}settings.html', _ctx(request.POST, errors))

    try:
        with transaction.atomic():
            for field, value in cleaned.items():
                setattr(setting, field, value)
            update_fields = list(cleaned.keys())
            if hasattr(setting, 'updated_at'):
                update_fields.append('updated_at')
            setting.save(update_fields=update_fields)
    except Exception as exc:
        messages.error(request, f'Could not save settings: {exc}')
        return render(request, f'{_T}settings.html', _ctx(request.POST, {}))

    messages.success(request, 'School settings saved successfully.')
    return redirect('school:school_settings')
