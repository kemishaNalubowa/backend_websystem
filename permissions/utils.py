# permissions/utils.py
# ─────────────────────────────────────────────────────────────────────────────
# Utility helpers for Permission and UserTypePermission views.
#
# Functions:
#   get_permission_list_stats()       — stats for list page
#   get_permission_detail_stats()     — stats + role rows for detail page
#   validate_and_parse_permission()   — manual POST validation for Permission
#   validate_and_parse_assignment()   — manual POST validation for one role accordion
#   get_role_label()                  — human-readable label from role key
#   get_all_roles()                   — ordered list of (key, label) tuples
#   get_session_roles()               — load role keys stored in session
#   set_session_roles()               — write role keys into session
#   clear_session_roles()             — delete assignment session data
#   get_session_saved_roles()         — roles already saved in the session flow
#   mark_session_role_saved()         — mark one role as saved in session
#   build_role_accordion_data()       — build per-role data dict for accordion page
#   confirm_all_assignments()         — flip is_active=True for pending assignments
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from typing import Any

from django.db.models import Count, Q

from permissions.models import Permission, UserTypePermission


# ═══════════════════════════════════════════════════════════════════════════════
#  ROLE CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

ALL_ROLES: list[tuple[str, str]] = [
    # Teaching
    ('head_teacher',    'Head Teacher'),
    ('deputy_head',     'Deputy Head Teacher'),
    ('teacher',         'Class Teacher'),
    ('subject_teacher', 'Subject Teacher'),
    # Non-teaching
    ('bursar',          'Bursar'),
    ('secretary',       'School Secretary'),
    ('librarian',       'Librarian'),
    ('lab_technician',  'Lab Technician'),
    ('nurse',           'School Nurse / Health Worker'),
    ('security',        'Security Personnel'),
    ('cleaner',         'Cleaner / Janitor'),
    ('driver',          'Driver'),
    ('cook',            'Cook / Catering Staff'),
    ('it_officer',      'IT Officer'),
    ('other',           'Other'),
    # Parent
    ('parent',          'Parent'),
    # Admin
    ('admin',           'Admin'),
]

_ROLE_LABEL_MAP: dict[str, str] = dict(ALL_ROLES)


def get_role_label(role_key: str) -> str:
    """Return the human-readable label for a role key."""
    return _ROLE_LABEL_MAP.get(role_key, role_key)


def get_all_roles() -> list[tuple[str, str]]:
    """Return the full ordered list of (key, label) role tuples."""
    return ALL_ROLES


# ═══════════════════════════════════════════════════════════════════════════════
#  SESSION HELPERS  (assignment flow state)
# ═══════════════════════════════════════════════════════════════════════════════

_SESSION_CHOSEN_KEY   = 'perm_assign_chosen_roles'    # list of role keys chosen
_SESSION_SAVED_KEY    = 'perm_assign_saved_roles'      # list of role keys already saved
_SESSION_PENDING_KEY  = 'perm_assign_pending_ids'      # list of UserTypePermission PKs pending confirm


def get_session_roles(request) -> list[str]:
    """Load the list of chosen role keys from the session."""
    return list(request.session.get(_SESSION_CHOSEN_KEY, []))


def set_session_roles(request, roles: list[str]) -> None:
    """Persist chosen role keys into the session."""
    request.session[_SESSION_CHOSEN_KEY] = roles
    request.session.modified = True


def get_session_saved_roles(request) -> list[str]:
    """Return the list of role keys that have been saved in this flow."""
    return list(request.session.get(_SESSION_SAVED_KEY, []))


def mark_session_role_saved(request, role_key: str) -> None:
    """Mark one role as saved in the session."""
    saved = get_session_saved_roles(request)
    if role_key not in saved:
        saved.append(role_key)
    request.session[_SESSION_SAVED_KEY] = saved
    request.session.modified = True


def get_session_pending_ids(request) -> list[int]:
    """Return list of UserTypePermission PKs created/updated but not yet confirmed."""
    return list(request.session.get(_SESSION_PENDING_KEY, []))


def add_session_pending_ids(request, ids: list[int]) -> None:
    """Add a batch of UserTypePermission PKs to the pending list."""
    existing = get_session_pending_ids(request)
    merged = list(set(existing) | set(ids))
    request.session[_SESSION_PENDING_KEY] = merged
    request.session.modified = True


def clear_session_assignment(request) -> None:
    """Wipe all assignment session state after the flow is complete."""
    for key in (_SESSION_CHOSEN_KEY, _SESSION_SAVED_KEY, _SESSION_PENDING_KEY):
        request.session.pop(key, None)
    request.session.modified = True


# ═══════════════════════════════════════════════════════════════════════════════
#  VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def validate_and_parse_permission(post: dict) -> tuple[dict, dict]:
    """
    Validate POST data for adding / editing a Permission record.

    Returns (cleaned, errors).
    """
    errors:  dict = {}
    cleaned: dict = {}

    title = (post.get('permission_title') or '').strip()
    if not title:
        errors['permission_title'] = 'Permission title is required.'
    elif len(title) > 255:
        errors['permission_title'] = 'Title must not exceed 255 characters.'
    else:
        cleaned['permission_title'] = title

    code = (post.get('permission_code') or '').strip().lower()
    if not code:
        errors['permission_code'] = 'Permission code is required.'
    elif len(code) > 100:
        errors['permission_code'] = 'Code must not exceed 100 characters.'
    elif not code.replace('_', '').replace('-', '').isalnum():
        errors['permission_code'] = 'Code may only contain letters, digits, hyphens and underscores.'
    else:
        cleaned['permission_code'] = code

    cleaned['description'] = (post.get('description') or '').strip()
    cleaned['is_active'] = post.get('is_active', '') in ('1', 'on', 'true', 'yes')

    return cleaned, errors

def validate_and_parse_assignment(post: dict, role_key: str, all_permissions) -> tuple[dict, dict]:
    errors:         dict       = {}
    assignments:    list[dict] = []
    missing_limit:  list[str]  = []
    missing_action: list[str]  = []

    valid_roles = {r[0] for r in ALL_ROLES}
    if role_key not in valid_roles:
        errors['role'] = f'Invalid role: {role_key}'
        return {}, errors

    for perm in all_permissions:
        pid    = perm.pk
        prefix = f'perm_{pid}_'

        # ── read each action — gated by what the permission actually supports ──
        can_create = post.get(f'{prefix}create') in ('on', '1', 'true') and perm.support_add
        can_read   = post.get(f'{prefix}read')   in ('on', '1', 'true') and perm.support_view
        can_edit   = post.get(f'{prefix}edit')   in ('on', '1', 'true') and perm.support_edit
        can_delete = post.get(f'{prefix}delete') in ('on', '1', 'true') and perm.support_delete
        can_toggle = post.get(f'{prefix}toggle') in ('on', '1', 'true') and perm.support_toggle  # ← new

        raw_limit = post.get(f'{prefix}limit') or None
        if raw_limit is not None and raw_limit not in (
            UserTypePermission.CAN_MY, UserTypePermission.CAN_ALL
        ):
            raw_limit = None

        has_action = any([can_create, can_read, can_edit, can_delete, can_toggle])  # ← toggle included
        has_limit  = raw_limit is not None
        # for permissions where limits don't apply, treat as always having limit
        limit_applies = perm.support_my_limit or perm.support_all_limit
        if not limit_applies:
            has_limit = True
            raw_limit = None  # store as None — limit not relevant for this permission

        if not has_action and not has_limit:
            continue

        if has_action and not has_limit:
            missing_limit.append(perm.permission_title)
            continue

        if has_limit and not has_action:
            missing_action.append(perm.permission_title)
            continue

        assignments.append({
            'permission_id': pid,
            'can_create':    can_create,
            'can_read':      can_read,
            'can_edit':      can_edit,
            'can_delete':    can_delete,
            'can_toggle':    can_toggle,   # ← new
            'action_effect': raw_limit,
        })

    cleaned = {
        'role':           role_key,
        'assignments':    assignments,
        'missing_limit':  missing_limit,
        'missing_action': missing_action,
    }
    return cleaned, errors



# ═══════════════════════════════════════════════════════════════════════════════
#  LIST STATS
# ═══════════════════════════════════════════════════════════════════════════════

def get_permission_list_stats() -> dict:
    """Stats for the permission list page."""
    qs = Permission.objects.all()

    total    = qs.count()
    active   = qs.filter(is_active=True).count()
    inactive = qs.filter(is_active=False).count()

    # How many permissions have at least one active role assignment?
    assigned = qs.filter(
        role_assignments__is_active=True
    ).distinct().count()

    return {
        'total':    total,
        'active':   active,
        'inactive': inactive,
        'assigned': assigned,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  DETAIL STATS
# ═══════════════════════════════════════════════════════════════════════════════

def get_permission_detail_stats(permission: Permission) -> dict:
    """
    Build all context needed for the permission detail page.

    Returns:
        assignments   — QuerySet of UserTypePermission for this permission
        assigned_roles — list of role keys that have an assignment
        total_roles   — how many roles are assigned (active or inactive)
        active_roles  — how many active assignments
    """
    assignments = UserTypePermission.objects.filter(
        permission=permission
    ).order_by('role')

    total_roles  = assignments.count()
    active_roles = assignments.filter(is_active=True).count()
    assigned_role_keys = list(assignments.values_list('role', flat=True))

    return {
        'assignments':       assignments,
        'assigned_role_keys': assigned_role_keys,
        'total_roles':       total_roles,
        'active_roles':      active_roles,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  ACCORDION BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

def build_role_accordion_data(
    role_key: str,
    all_permissions,
    saved_roles: list[str],
    pending_ids: list[int],
) -> dict:
    """
    Build the data dict for one role accordion on the assign page.

    Returns a dict with:
        role_key    — str
        role_label  — str
        is_saved    — bool (has been saved in this session)
        rows        — list of dicts, one per permission:
            {
                permission:    Permission instance,
                can_create:    bool,
                can_read:      bool,
                can_edit:      bool,
                can_delete:    bool,
                action_effect: 'can_my'|'can_all',
                is_pending:    bool (saved but not confirmed),
            }
    """
    # Load existing assignment rows for this role (including inactive/pending)
    existing_map: dict[int, UserTypePermission] = {
        utp.permission_id: utp
        for utp in UserTypePermission.objects.filter(role=role_key)
    }

    rows = []
    for perm in all_permissions:
        utp = existing_map.get(perm.pk)
        rows.append({
            'permission':    perm,
            'can_create':    utp.can_create    if utp else False,
            'can_read':      utp.can_read      if utp else False,
            'can_edit':      utp.can_edit      if utp else False,
            'can_delete':    utp.can_delete    if utp else False,
            'action_effect': utp.action_effect if utp else None,
            'is_pending':    (utp.pk in pending_ids) if utp else False,
        })

    return {
        'role_key':   role_key,
        'role_label': get_role_label(role_key),
        'is_saved':   role_key in saved_roles,
        'rows':       rows,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIRM ALL ASSIGNMENTS
# ═══════════════════════════════════════════════════════════════════════════════

def confirm_all_assignments(pending_ids: list[int]) -> int:
    """
    Flip is_active=True on all UserTypePermission rows whose PKs are in pending_ids.
    Returns the count of rows updated.
    """
    if not pending_ids:
        return 0
    updated = UserTypePermission.objects.filter(
        pk__in=pending_ids,
        is_active=False,
    ).update(is_active=True)
    return updated
