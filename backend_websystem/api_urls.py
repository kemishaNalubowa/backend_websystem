from django.urls import path
from . import api_views

app_name = 'parent_portal_api'

urlpatterns = [
    # Parent authentication
    path('login/', api_views.parent_login, name='login'),
    path('register/', api_views.parent_register, name='register'),
    
    # Staff/Teacher authentication
    path('staff/login/', api_views.staff_teacher_login, name='staff_login'),
    
    # Admin authentication
    path('admin/login/', api_views.admin_login, name='admin_login'),
    
    # Parent portal data
    path('parent/dashboard/', api_views.get_dashboard_data, name='dashboard_data'),
    path('parent/requests/', api_views.parent_requests, name='requests'),
    path('parent/requests/<int:request_id>/reply/', api_views.submit_request_reply, name='request_reply'),
]
