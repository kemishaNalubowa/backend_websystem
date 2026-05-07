from functools import wraps
from django.shortcuts import redirect
from .context_processors import _get_user_role
from .models import UserTypePermission

_ACTION_MAP = {
    'create': ('can_create', 'Add'),
    'read':   ('can_read',   'Read / View'),
    'edit':   ('can_edit',   'Edit'),
    'delete': ('can_delete', 'Delete'),
    'toggle': ('can_toggle', 'Toggle'),
}


def has_permission(permission_code, action='read'):
    """
    @login_required
    @has_permission('school_fee', action='edit')
    def edit_fee(request, pk): ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):

            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            field_name, action_label = _ACTION_MAP.get(action, ('can_read', 'Read / View'))

            # ── use cache if context processor already loaded it this request ──
            user_perms = getattr(request, '_user_perms_cache', None)

            if user_perms is not None:
                # fast path — cache already built by context processor
                perm       = user_perms.get(permission_code)
                allowed    = perm.get(field_name, False) if perm else False
                perm_title = perm.get('permission_title', permission_code) if perm else permission_code

            else:
                # slow path — cache not yet built (e.g. decorator runs before template render)
                role = _get_user_role(request.user)

                if not role:
                    # no staff profile at all — let the view decide
                    return view_func(request, *args, **kwargs)

                try:
                    utp = (
                        UserTypePermission.objects
                        .select_related('permission')
                        .get(
                            role=role,
                            permission__permission_code=permission_code,
                            is_active=True,
                        )
                    )
                    allowed    = getattr(utp, field_name, False)
                    perm_title = utp.permission.permission_title
                except UserTypePermission.DoesNotExist:
                    allowed    = False
                    perm_title = permission_code

            if not allowed:
                request.session['perm_denied'] = {
                    'permission_title': perm_title,
                    'action_label':     action_label,
                }
                request.session.modified = True
                referer = request.META.get('HTTP_REFERER')
                return redirect(referer) if referer else redirect('dashboard')

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator