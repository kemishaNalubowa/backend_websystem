from django.shortcuts import render

# Create your views here.
# permissions/views.py
# ─────────────────────────────────────────────────────────────────────────────
# All Permission and UserTypePermission views.
#
# Views:
#   permission_list           — list + stats + active/inactive filter
#   permission_add            — add a new Permission record
#   permission_detail         — full detail: info, roles, task toggles, scope
#   permission_toggle_active  — POST-only: flip is_active on a Permission
#   permission_remove_role    — POST-only: revoke one role's assignment entirely
#   permission_update_role    — POST-only: patch tasks / action_effect on one role
#
#   assign_choose_roles       — Step 1 — choose roles to assign; write to session
#   assign_edit_roles         — Step 2 — accordion per role; POST saves one role at a time
#   assign_save_role          — POST-only sub-action inside Step 2 (one accordion)
#   assign_review             — Step 3 — review + password confirm
#   assign_confirm            — POST-only: validate password, flip is_active, summary
#   assign_summary            — Step 4 — read-only success summary
#
# Rules:
#   - Function-based views only
#   - No Django Forms / forms.py
#   - No Class-based Views
#   - No JSON responses
#   - Manual validation via permissions.utils
#   - django.contrib.messages for all feedback
#   - login_required on every view
#   - transaction.atomic() on all saves
# ─────────────────────────────────────────────────────────────────────────────

from django.contrib import messages
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from permissions.models import Permission, UserTypePermission
from permissions.utils import (
    add_session_pending_ids,
    build_role_accordion_data,
    clear_session_assignment,
    confirm_all_assignments,
    get_all_roles,
    get_permission_detail_stats,
    get_permission_list_stats,
    get_role_label,
    get_session_pending_ids,
    get_session_roles,
    get_session_saved_roles,
    mark_session_role_saved,
    set_session_roles,
    validate_and_parse_assignment,
    validate_and_parse_permission,
)

_T = 'permissions/'


# ═══════════════════════════════════════════════════════════════════════════════
#  1. PERMISSION LIST
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def permission_list(request):
    """
    All permissions with stats and active/inactive filter.

    Filters (GET):
        ?q=       title / code search
        ?active=  1 | 0
    """
    qs = Permission.objects.all()

    search        = request.GET.get('q', '').strip()
    active_filter = request.GET.get('active', '').strip()

    if search:
        qs = qs.filter(
            Q(permission_title__icontains=search) |
            Q(permission_code__icontains=search)  |
            Q(description__icontains=search)
        )

    if active_filter == '1':
        qs = qs.filter(is_active=True)
    elif active_filter == '0':
        qs = qs.filter(is_active=False)

    qs = qs.order_by('permission_title')

    paginator = Paginator(qs, 25)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    stats = get_permission_list_stats()

    context = {
        'permissions':    page_obj.object_list,
        'page_obj':       page_obj,
        'search':         search,
        'active_filter':  active_filter,
        'page_title':     'Permissions',
        **stats,
    }
    return render(request, f'{_T}permission_list.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  2. ADD PERMISSION
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def permission_add(request):
    """
    Add a new Permission.
    GET  — blank form.
    POST — validate; save; redirect to detail.
    """
    if request.method == 'GET':
        return render(request, f'{_T}permission_form.html', {
            'form_title': 'Add Permission',
            'action':     'add',
            'post':       {},
            'errors':     {},
        })

    cleaned, errors = validate_and_parse_permission(request.POST)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}permission_form.html', {
            'form_title': 'Add Permission',
            'action':     'add',
            'post':       request.POST,
            'errors':     errors,
        })

    # Unique code check
    if Permission.objects.filter(permission_code=cleaned['permission_code']).exists():
        errors['permission_code'] = 'A permission with this code already exists.'
        messages.error(request, errors['permission_code'])
        return render(request, f'{_T}permission_form.html', {
            'form_title': 'Add Permission',
            'action':     'add',
            'post':       request.POST,
            'errors':     errors,
        })

    try:
        with transaction.atomic():
            perm = Permission(**cleaned)
            perm.save()
    except Exception as exc:
        messages.error(request, f'Could not save permission: {exc}')
        return render(request, f'{_T}permission_form.html', {
            'form_title': 'Add Permission',
            'action':     'add',
            'post':       request.POST,
            'errors':     {},
        })

    messages.success(request, f'Permission "{perm.permission_title}" created successfully.')
    return redirect('permissions:permission_detail', pk=perm.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  3. PERMISSION DETAIL
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def permission_detail(request, pk):
    """
    Full permission detail page.

    Shows:
        - Permission metadata
        - Table of roles assigned: tasks + action_effect per role
        - Deactivate / activate toggle
        - Remove role (POST)
        - Update task checkboxes + action_effect per role (POST)
    """
    perm  = get_object_or_404(Permission, pk=pk)
    stats = get_permission_detail_stats(perm)

    context = {
        'permission':  perm,
        'page_title':  perm.permission_title,
        'can_my':      UserTypePermission.CAN_MY,
        'can_all':     UserTypePermission.CAN_ALL,
        **stats,
    }
    return render(request, f'{_T}permission_detail.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  4. TOGGLE ACTIVE  (POST-only)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def permission_toggle_active(request, pk):
    """POST-only: flip is_active on a Permission."""
    if request.method != 'POST':
        messages.warning(request, 'Invalid request method.')
        return redirect('permissions:permission_list')

    perm = get_object_or_404(Permission, pk=pk)
    perm.is_active = not perm.is_active
    perm.save(update_fields=['is_active'])

    state = 'activated' if perm.is_active else 'deactivated'
    messages.success(request, f'Permission "{perm.permission_title}" has been {state}.')

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    return redirect(next_url or 'permissions:permission_detail', pk=perm.pk) \
        if not next_url else redirect(next_url)


# ═══════════════════════════════════════════════════════════════════════════════
#  5. REMOVE ROLE FROM PERMISSION  (POST-only)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def permission_remove_role(request, pk):
    """
    POST-only: delete UserTypePermission rows for the checked roles.

    POST fields:
        roles[]   — list of role keys to revoke
    """
    if request.method != 'POST':
        messages.warning(request, 'Invalid request method.')
        return redirect('permissions:permission_detail', pk=pk)

    perm = get_object_or_404(Permission, pk=pk)
    roles = request.POST.getlist('roles[]')

    if not roles:
        messages.warning(request, 'No roles selected for removal.')
        return redirect('permissions:permission_detail', pk=pk)

    with transaction.atomic():
        deleted, _ = UserTypePermission.objects.filter(
            permission=perm, role__in=roles
        ).delete()

    label_list = ', '.join(get_role_label(r) for r in roles)
    messages.success(
        request,
        f'Removed {deleted} role assignment(s) from "{perm.permission_title}": {label_list}.'
    )
    return redirect('permissions:permission_detail', pk=pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  6. UPDATE ROLE TASKS / SCOPE  (POST-only)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def permission_update_role(request, pk):
    """
    POST-only: update the tasks (can_create/read/edit/delete) and action_effect
    for one role on a permission, without revoking the role entirely.

    POST fields:
        role          — role key
        can_create    — checkbox
        can_read      — checkbox
        can_edit      — checkbox
        can_delete    — checkbox
        action_effect — 'can_my' | 'can_all'
    """
    if request.method != 'POST':
        messages.warning(request, 'Invalid request method.')
        return redirect('permissions:permission_detail', pk=pk)

    perm = get_object_or_404(Permission, pk=pk)
    role = request.POST.get('role', '').strip()

    if not role:
        messages.error(request, 'Role is required.')
        return redirect('permissions:permission_detail', pk=pk)

    utp = get_object_or_404(UserTypePermission, permission=perm, role=role)

    can_create    = request.POST.get('can_create')    in ('on', '1', 'true')
    can_read      = request.POST.get('can_read')      in ('on', '1', 'true')
    can_edit      = request.POST.get('can_edit')      in ('on', '1', 'true')
    can_delete    = request.POST.get('can_delete')    in ('on', '1', 'true')


    action_effect = request.POST.get('action_effect') or None

    if action_effect is not None and action_effect not in (
        UserTypePermission.CAN_MY, UserTypePermission.CAN_ALL
    ):
        action_effect = None   # reject garbage; don't force CAN_MY

    with transaction.atomic():
        utp.can_create    = can_create
        utp.can_read      = can_read
        utp.can_edit      = can_edit
        utp.can_delete    = can_delete
        utp.action_effect = action_effect
        utp.save(update_fields=[
            'can_create', 'can_read', 'can_edit', 'can_delete',
            'action_effect', 'updated_at',
        ])

    messages.success(
        request,
        f'Tasks updated for "{get_role_label(role)}" on "{perm.permission_title}".'
    )
    return redirect('permissions:permission_detail', pk=pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  7. ASSIGN — STEP 1: CHOOSE ROLES
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def assign_choose_roles(request):
    """
    Step 1 — Show all roles as checkboxes. On POST, persist chosen roles
    into the session and redirect to Step 2 (edit accordion page).
    """
    all_roles = get_all_roles()

    if request.method == 'GET':
        # Pre-tick roles already in session (if user is navigating back)
        current_chosen = get_session_roles(request)
        return render(request, f'{_T}assign_choose_roles.html', {
            'all_roles':      all_roles,
            'current_chosen': current_chosen,
            'page_title':     'Assign Permissions — Step 1: Choose Roles',
        })

    chosen = request.POST.getlist('roles[]')
    valid  = {r[0] for r in all_roles}
    chosen = [r for r in chosen if r in valid]

    if not chosen:
        messages.error(request, 'Please select at least one role to continue.')
        return render(request, f'{_T}assign_choose_roles.html', {
            'all_roles':      all_roles,
            'current_chosen': [],
            'page_title':     'Assign Permissions — Step 1: Choose Roles',
        })

    # Reset saved state for a fresh flow
    set_session_roles(request, chosen)
    request.session[_SESSION_SAVED_KEY] = []
    request.session[_SESSION_PENDING_KEY] = []
    request.session.modified = True

    return redirect('permissions:assign_edit_roles')


# expose session keys for the view module (used above without import)
_SESSION_SAVED_KEY   = 'perm_assign_saved_roles'
_SESSION_PENDING_KEY = 'perm_assign_pending_ids'


# ═══════════════════════════════════════════════════════════════════════════════
#  8. ASSIGN — STEP 2: EDIT ACCORDIONS
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def assign_edit_roles(request):
    """
    Step 2 — Display one accordion per chosen role. GET only.
    Saving each role is handled by assign_save_role (POST).
    """
    chosen = get_session_roles(request)
    if not chosen:
        messages.warning(request, 'No roles selected. Please choose roles first.')
        return redirect('permissions:assign_choose_roles')

    saved_roles  = get_session_saved_roles(request)
    pending_ids  = get_session_pending_ids(request)
    all_perms    = Permission.objects.filter(is_active=True).order_by('permission_title')

    accordions = [
        build_role_accordion_data(role_key, all_perms, saved_roles, pending_ids)
        for role_key in chosen
    ]

    all_saved = set(chosen) == set(saved_roles)

    context = {
        'accordions':   accordions,
        'chosen_roles': chosen,
        'saved_roles':  saved_roles,
        'all_saved':    all_saved,
        'page_title':   'Assign Permissions — Step 2: Configure Roles',
        'can_my':       UserTypePermission.CAN_MY,
        'can_all':      UserTypePermission.CAN_ALL,
    }
    return render(request, f'{_T}assign_edit_roles.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  9. ASSIGN — SAVE ONE ROLE ACCORDION  (POST-only)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def assign_save_role(request):
    """
    POST-only sub-action for Step 2.
    Saves / updates UserTypePermission rows for ONE role with is_active=False.

    POST fields:
        role                — role key
        perm_{pk}_create    — checkbox
        perm_{pk}_read      — checkbox
        perm_{pk}_edit      — checkbox
        perm_{pk}_delete    — checkbox
        perm_{pk}_toggle    — checkbox  ← new
        perm_{pk}_limit     — 'can_my' | 'can_all'
    """
    if request.method != 'POST':
        return redirect('permissions:assign_edit_roles')

    chosen = get_session_roles(request)
    if not chosen:
        messages.warning(request, 'Session expired. Please restart.')
        return redirect('permissions:assign_choose_roles')

    role_key = request.POST.get('role', '').strip()
    if role_key not in chosen:
        messages.error(request, f'Role "{role_key}" is not in the current session.')
        return redirect('permissions:assign_edit_roles')

    all_perms = Permission.objects.filter(is_active=True).order_by('permission_title')
    cleaned, errors = validate_and_parse_assignment(request.POST, role_key, all_perms)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return redirect('permissions:assign_edit_roles')

    if cleaned.get('missing_limit'):
        skipped = ', '.join(f'"{t}"' for t in cleaned['missing_limit'])
        messages.warning(
            request,
            f'Skipped {len(cleaned["missing_limit"])} permission(s) — '
            f'actions were ticked but no scope (My / All) was chosen: {skipped}.'
        )

    if cleaned.get('missing_action'):
        skipped = ', '.join(f'"{t}"' for t in cleaned['missing_action'])
        messages.warning(
            request,
            f'Skipped {len(cleaned["missing_action"])} permission(s) — '
            f'a scope was chosen but no actions were ticked: {skipped}.'
        )

    if not cleaned['assignments']:
        mark_session_role_saved(request, role_key)
        messages.info(
            request,
            f'"{get_role_label(role_key)}" saved with no permissions assigned.'
        )
        return redirect('permissions:assign_edit_roles')

    new_pending_ids: list[int] = []

    try:
        with transaction.atomic():
            for row in cleaned['assignments']:
                utp, created = UserTypePermission.objects.get_or_create(
                    permission_id=row['permission_id'],
                    role=role_key,
                    defaults={
                        'can_create':    row['can_create'],
                        'can_read':      row['can_read'],
                        'can_edit':      row['can_edit'],
                        'can_delete':    row['can_delete'],
                        'can_toggle':    row['can_toggle'],    # ← new
                        'action_effect': row['action_effect'],
                        'is_active':     False,
                    }
                )
                if not created:
                    utp.can_create    = row['can_create']
                    utp.can_read      = row['can_read']
                    utp.can_edit      = row['can_edit']
                    utp.can_delete    = row['can_delete']
                    utp.can_toggle    = row['can_toggle']      # ← new
                    utp.action_effect = row['action_effect']
                    utp.is_active     = False
                    utp.save(update_fields=[
                        'can_create', 'can_read', 'can_edit', 'can_delete',
                        'can_toggle',                          # ← new
                        'action_effect', 'is_active', 'updated_at',
                    ])
                new_pending_ids.append(utp.pk)

    except Exception as exc:
        messages.error(request, f'Could not save role assignments: {exc}')
        return redirect('permissions:assign_edit_roles')

    mark_session_role_saved(request, role_key)
    add_session_pending_ids(request, new_pending_ids)

    messages.success(
        request,
        f'"{get_role_label(role_key)}" saved — pending confirmation.'
    )
    return redirect('permissions:assign_edit_roles')

# ═══════════════════════════════════════════════════════════════════════════════
#  10. ASSIGN — STEP 3: REVIEW + PASSWORD CONFIRM
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def assign_review(request):
    """
    Step 3 — Review all pending assignments grouped by role.
    Each role shows:
        - Tab: already confirmed (is_active=True) assignments
        - Tab: pending (is_active=False) assignments (default open)
    If no confirmed tab, show pending table only (no tabs).
    """
    chosen      = get_session_roles(request)
    pending_ids = get_session_pending_ids(request)

    if not chosen or not pending_ids:
        messages.warning(request, 'Nothing to review. Please restart the assignment flow.')
        return redirect('permissions:assign_choose_roles')

    review_roles = []
    for role_key in chosen:
        pending_qs = UserTypePermission.objects.filter(
            role=role_key,
            pk__in=pending_ids,
            is_active=False,
        ).select_related('permission').order_by('permission__permission_title')

        confirmed_qs = UserTypePermission.objects.filter(
            role=role_key,
            is_active=True,
        ).exclude(pk__in=pending_ids).select_related('permission').order_by(
            'permission__permission_title'
        )

        review_roles.append({
            'role_key':    role_key,
            'role_label':  get_role_label(role_key),
            'pending':     list(pending_qs),
            'confirmed':   list(confirmed_qs),
            'has_both':    pending_qs.exists() and confirmed_qs.exists(),
        })

    context = {
        'review_roles': review_roles,
        'pending_ids':  pending_ids,
        'page_title':   'Assign Permissions — Step 3: Review & Confirm',
        'can_my':       UserTypePermission.CAN_MY,
        'can_all':      UserTypePermission.CAN_ALL,
    }
    return render(request, f'{_T}assign_review.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  11. ASSIGN — CONFIRM  (POST-only: password check → activate → summary)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def assign_confirm(request):
    """
    POST-only. Validates the confirming user's password.
    On success: flips is_active=True on all pending assignments,
    clears session, redirects to summary.
    """
    if request.method != 'POST':
        return redirect('permissions:assign_review')

    pending_ids = get_session_pending_ids(request)
    if not pending_ids:
        messages.warning(request, 'No pending assignments to confirm.')
        return redirect('permissions:assign_choose_roles')

    password = request.POST.get('confirm_password', '').strip()
    if not password:
        messages.error(request, 'Password is required to confirm assignments.')
        return redirect('permissions:assign_review')

    # Authenticate against the current user's credentials
    user = authenticate(
        request,
        username=request.user.get_username(),
        password=password,
    )
    if user is None:
        messages.error(request, 'Incorrect password. Assignments have not been activated.')
        return redirect('permissions:assign_review')

    try:
        with transaction.atomic():
            count = confirm_all_assignments(pending_ids)
    except Exception as exc:
        messages.error(request, f'Could not confirm assignments: {exc}')
        return redirect('permissions:assign_review')

    # Store summary info in session before clearing
    chosen = get_session_roles(request)
    request.session['perm_assign_summary_ids']   = pending_ids
    request.session['perm_assign_summary_roles'] = chosen
    request.session['perm_assign_summary_count'] = count
    request.session.modified = True

    clear_session_assignment(request)

    messages.success(
        request,
        f'{count} assignment(s) confirmed and activated successfully.'
    )
    return redirect('permissions:assign_summary')


# ═══════════════════════════════════════════════════════════════════════════════
#  12. ASSIGN — SUMMARY  (read-only success page)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def assign_summary(request):
    """
    Step 4 — Read-only summary of what was just confirmed.
    Reads from the summary session keys set by assign_confirm.
    """
    confirmed_ids  = request.session.pop('perm_assign_summary_ids',   [])
    summary_roles  = request.session.pop('perm_assign_summary_roles', [])
    confirmed_count = request.session.pop('perm_assign_summary_count', 0)
    request.session.modified = True

    summary_rows = []
    for role_key in summary_roles:
        assignments = UserTypePermission.objects.filter(
            role=role_key,
            pk__in=confirmed_ids,
            is_active=True,
        ).select_related('permission').order_by('permission__permission_title')

        if assignments.exists():
            summary_rows.append({
                'role_label':  get_role_label(role_key),
                'assignments': list(assignments),
            })

    context = {
        'summary_rows':    summary_rows,
        'confirmed_count': confirmed_count,
        'page_title':      'Assignments Confirmed',
        'can_my':          UserTypePermission.CAN_MY,
        'can_all':         UserTypePermission.CAN_ALL,
    }
    return render(request, f'{_T}assign_summary.html', context)
