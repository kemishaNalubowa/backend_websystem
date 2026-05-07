from .models import UserTypePermission


def user_permissions(request):
    """
    Injects into every template context:

        user_perms  — dict keyed by permission_code
        perm_denied — dict or None (consumed once, triggers modal)
    """
    user_perms = {}

    if request.user.is_authenticated:

        if not hasattr(request, '_user_perms_cache'):
            role = _get_user_role(request.user)

            if role:
                qs = (
                    UserTypePermission.objects
                    .filter(role=role, is_active=True)
                    .select_related('permission')
                )
                request._user_perms_cache = {
                    utp.permission.permission_code: {
                        'permission_title': utp.permission.permission_title,  # ← stored so modal shows proper name
                        'can_create':       utp.can_create,
                        'can_read':         utp.can_read,
                        'can_edit':         utp.can_edit,
                        'can_delete':       utp.can_delete,
                        'can_toggle':       utp.can_toggle,
                        'action_effect':    utp.action_effect,
                    }
                    for utp in qs
                }
            else:
                request._user_perms_cache = {}

        user_perms = request._user_perms_cache

    perm_denied = request.session.pop('perm_denied', None)
    if perm_denied:
        request.session.modified = True

    return {
        'user_perms':  user_perms,
        'perm_denied': perm_denied,
    }


# ─────────────────────────────────────────────────────────────────────────────

def _get_user_role(user):
    """
    Reads role from StaffProfile (accounts.models).
    related_name='staff_profile' → accessed as user.staff_profile
    Returns None for superusers or users with no staff profile.
    """
    if user.is_superuser:
        return None

    try:
        # related_name on the OneToOneField is 'staff_profile'
        return user.staff_profile.role
    except Exception:
        return None