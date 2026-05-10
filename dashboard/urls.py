from django.urls import path, include
from .import views
from django.conf import settings
from django.conf.urls.static import static
from . import parent_dashboard_views as pdv

urlpatterns = [
    path("", views.cover_page, name="cover_page"), 

    # Parent portal home
    path('parent/',                               pdv.parent_dashboard,          name='parent_dashboard'),



    path('student/<int:student_id>/',
     pdv.parent_student_overview, name='parent_student_overview'),

    path('student/<int:student_id>/class/<int:class_id>/',
        pdv.parent_student_class, name='parent_student_class'),

    path('student/<int:student_id>/class/<int:class_id>/term/<int:term_id>/',
        pdv.parent_student_class_term, name='parent_student_class_term'),

    path('student/<int:student_id>/class/<int:class_id>/term/<int:term_id>/fees/',
        pdv.parent_student_class_term_fees, name='parent_student_class_term_fees'),
    
    path('student/<int:student_id>/class/<int:class_id>/term/<int:term_id>/scholastic/',
     pdv.parent_student_class_term_scholastic, name='parent_student_class_term_scholastic'),

    path('student/<int:student_id>/class/<int:class_id>/term/<int:term_id>/performance/',
     pdv.parent_student_class_term_scholastic_performance, name='parent_student_class_term_performance'),




    # Communication
    path('parent/communication/',                 pdv.parent_communication,      name='parent_communication'),
    path('parent/request/<int:request_id>/',      pdv.parent_request_detail,     name='parent_request_detail'),

    # New request — can be reached with or without a pre-selected student
    path('parent/request/new/',                   pdv.parent_new_request,        name='parent_new_request'),
    path('parent/request/new/<int:student_id>/',  pdv.parent_new_request,        name='parent_new_request_student'),




    path("auth/", include("authentication.urls")),
    path("academics/", include("academics.urls",  namespace="academics")),
    path("accounts/", include("accounts.urls",  namespace="accounts")),
    path("assessments/", include("assessments.urls",  namespace="assessments")),
    path("communication/", include("communication.urls",  namespace="communication")),
    path("fees/", include("fees.urls",  namespace="fees")),
    path("school/", include("school.urls",  namespace="school")),
    path("permissions/", include("permissions.urls",  namespace="permissions")),
    path("students/", include("students.urls",  namespace="students")),
    path('help/', include('help_center.urls')),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

