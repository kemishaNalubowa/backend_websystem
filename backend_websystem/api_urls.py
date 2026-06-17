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
    
    # Teacher portal data
    path('teacher/dashboard/', api_views.get_teacher_dashboard, name='teacher_dashboard'),
    
    # Public Admissions
    path('supported-classes/', api_views.get_supported_classes, name='supported_classes'),
    path('media/images/', api_views.get_dynamic_images, name='dynamic_images'),
    path('fees/structure/', api_views.get_fees_structure, name='fees_structure'),
    path('students/admissions/apply/', api_views.submit_admission_application, name='submit_admission_application'),
]
