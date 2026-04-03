# accounts/urls.py
# ─────────────────────────────────────────────────────────────────────────────
# URL patterns for the accounts app.
# Namespace: 'accounts'
#
# Include in root urls.py as:
#   path('accounts/', include('accounts.urls', namespace='accounts'))
#
# Django's built-in auth (login / logout) should be wired separately:
#   path('auth/', include('django.contrib.auth.urls'))
# ─────────────────────────────────────────────────────────────────────────────

from django.urls import path

from accounts.views import (
    user_list,
    # register_parent,
    register_staff,
    user_detail,
    user_toggle_active,
    edit_staff,
)

app_name = 'accounts'

urlpatterns = [

    # ── User management ───────────────────────────────────────────────────────
    #   /accounts/users/                       → all users + stats
    #   /accounts/users/<pk>/                  → user detail / profile
    #   /accounts/users/<pk>/toggle-active/    → POST activate/deactivate
    path('users/',                          user_list,          name='user_list'),
    path('users/<int:pk>/',                 user_detail,        name='user_detail'),
    path('users/<int:pk>/toggle-active/',   user_toggle_active, name='user_toggle_active'),

    # ── Registration ──────────────────────────────────────────────────────────
    #   /accounts/register/parent/   → register parent (user_type=parent)
    #   /accounts/register/staff/    → register teacher/staff/admin
    # path('register/parent/', register_parent, name='register_parent'),
    path('register/staff/',  register_staff,  name='register_staff'),
    path('users/<int:pk>/edit/', edit_staff, name='edit_staff'),
]
