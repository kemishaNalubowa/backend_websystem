# dashboard/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # Cover / landing
    path('',                                      views.cover_page,               name='cover_page'),

    # Parent portal home
    path('parent/',                               views.parent_dashboard,          name='parent_dashboard'),

    # Per-student detail
    path('parent/student/<int:student_id>/',      views.parent_dashboard_student,  name='parent_dashboard_student'),

    # Communication
    path('parent/communication/',                 views.parent_communication,      name='parent_communication'),
    path('parent/request/<int:request_id>/',      views.parent_request_detail,     name='parent_request_detail'),

    # New request — can be reached with or without a pre-selected student
    path('parent/request/new/',                   views.parent_new_request,        name='parent_new_request'),
    path('parent/request/new/<int:student_id>/',  views.parent_new_request,        name='parent_new_request_student'),
]
