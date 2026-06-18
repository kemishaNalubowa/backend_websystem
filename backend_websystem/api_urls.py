from django.urls import path
from . import api_views

app_name = 'parent_portal_api'

urlpatterns = [
    # Unified Authentication (Parent/Teacher/Staff)
    path('login/', api_views.parent_login, name='login'),
    path('auth/set-initial-password/', api_views.set_initial_password, name='set_initial_password'),
    path('auth/forgot-password/', api_views.forgot_password_request, name='forgot_password_request'),
    path('auth/reset-password/', api_views.forgot_password_reset, name='forgot_password_reset'),
    
    path('register/', api_views.parent_register, name='register'),
    
    # Staff/Teacher authentication (deprecated, use unified login)
    path('staff/login/', api_views.staff_teacher_login, name='staff_login'),
    
    # Admin authentication
    path('admin/login/', api_views.admin_login, name='admin_login'),
    
    # Parent portal data
    path('parent/dashboard/', api_views.get_dashboard_data, name='dashboard_data'),
    path('parent/requests/', api_views.parent_requests, name='requests'),
    path('parent/requests/<int:request_id>/reply/', api_views.submit_request_reply, name='request_reply'),
    path('parent/marks/', api_views.parent_child_marks, name='parent_marks'),
    
    # Teacher portal data
    path('teacher/dashboard/', api_views.get_teacher_dashboard, name='teacher_dashboard'),
    path('teacher/classes/students/', api_views.teacher_classes_students, name='teacher_classes_students'),

    # Announcements & Events (shared — read for all, create for staff)
    path('announcements/', api_views.api_announcements, name='announcements'),
    path('events/', api_views.api_events, name='events'),

    # Staff — Parent request management
    path('staff/requests/', api_views.staff_requests_list, name='staff_requests'),
    path('staff/requests/<int:request_id>/update-status/', api_views.staff_request_update_status, name='staff_request_update'),

    # Staff — Assessment workflow actions
    path('staff/assessment/<int:pk>/activate-entry/', api_views.api_assessment_activate_entry, name='staff_activate_entry'),
    path('staff/assessment/<int:pk>/publish/', api_views.api_assessment_publish, name='staff_publish'),

    # Auth — Resolved permissions
    path('auth/permissions/resolved/', api_views.resolved_permissions, name='resolved_permissions'),
    
    # Public Admissions
    path('supported-classes/', api_views.get_supported_classes, name='supported_classes'),
    path('media/images/', api_views.get_dynamic_images, name='dynamic_images'),
    path('fees/structure/', api_views.get_fees_structure, name='fees_structure'),
    path('students/admissions/apply/', api_views.submit_admission_application, name='submit_admission_application'),

    # Admin — Broadcast notification
    path('admin/broadcast/', api_views.admin_broadcast, name='admin_broadcast'),
]
