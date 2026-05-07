# academics/urls.py
# ─────────────────────────────────────────────────────────────────────────────
# All URL patterns for the academics app.
# Namespace: 'academics'
#
# Term URL structure:
#
#   /terms/                          → term_list
#   /terms/add/                      → term_add
#   /terms/<pk>/edit/                → term_edit
#   /terms/<pk>/delete/              → term_delete
#   /terms/<pk>/set-current/         → term_set_current  (POST only)
#
#   /terms/<pk>/                     → term_detail_overview
#   /terms/<pk>/calendar/            → term_detail_calendar
#   /terms/<pk>/admissions/          → term_detail_admissions
#   /terms/<pk>/requirements/        → term_detail_requirements
#   /terms/<pk>/fees/                → term_detail_fees
#   /terms/<pk>/payments/            → term_detail_payments
#   /terms/<pk>/assessment-fees/     → term_detail_assessment_fees
#   /terms/<pk>/assessments/         → term_detail_assessments
#
# Include in root urls.py as:
#   path('academics/', include('academics.urls', namespace='academics'))
# ─────────────────────────────────────────────────────────────────────────────

from django.urls import path

from academics.views.term_views import (
    terms_list,
    term_delete,
    term_update,
)
from academics.views.subject_views import (
    subject_list,
    subject_add,
    subject_edit,
    subject_delete,
    subject_toggle_active,
    subject_detail_info,
    subject_detail_teachers,
    subject_detail_classes,

    assign_subject_to_class,
    assign_subject_to_teacher,
)

from academics.views.academic_yr_views import (
    academic_year_list,
    academic_year_create,
    academic_year_update,
    academic_year_delete
)


from academics.views import views

app_name = 'academics'

urlpatterns = [

    path("supported-classes/add/", views.school_supported_classes_manage, name="school_supported_classes_manage"),
    path("class-teachers/", views.assign_class_teacher, name="assign_class_teacher" ),





    # ── Term CRUD ─────────────────────────────────────────────────────────────
    path(
        "terms/",
        terms_list,
        name="terms_list"
    ),

    path(
        "terms/update/<int:pk>/",
        term_update,
        name="term_update"
    ),

    path(
        "terms/delete/<int:pk>/",
        term_delete,
        name="term_delete"
    ),

    # ════════════════════════════════════════════════════════════════════════
    # SUBJECT URLs
    # ════════════════════════════════════════════════════════════════════════
    #
    #   /subjects/                          → subject_list
    #   /subjects/add/                      → subject_add
    #   /subjects/<pk>/edit/                → subject_edit
    #   /subjects/<pk>/delete/              → subject_delete
    #   /subjects/<pk>/toggle-active/       → subject_toggle_active (POST)
    #
    #   /subjects/<pk>/                     → subject_detail_info
    #   /subjects/<pk>/teachers/            → subject_detail_teachers
    #   /subjects/<pk>/classes/             → subject_detail_classes
    #
    # ─────────────────────────────────────────────────────────────────────────

    path(
        'subjects/',
        subject_list,
        name='subject_list'
    ),
    path(
        'subjects/add/',
        subject_add,
        name='subject_add'
    ),
    path(
        'subjects/<int:pk>/edit/',
        subject_edit,
        name='subject_edit'
    ),
    path(
        'subjects/<int:pk>/delete/',
        subject_delete,
        name='subject_delete'
    ),
    path(
        'subjects/<int:pk>/toggle-active/',
        subject_toggle_active,
        name='subject_toggle_active'
    ),

    # Subject detail — standalone pages
    path(
        'subjects/<int:pk>/',
        subject_detail_info,
        name='subject_detail_info'
    ),
    path(
        'subjects/<int:pk>/teachers/',
        subject_detail_teachers,
        name='subject_detail_teachers'
    ),
    path(
        'subjects/<int:pk>/classes/',
        subject_detail_classes,
        name='subject_detail_classes'
    ),








    path(
        "academic-years/",
        academic_year_list,
        name="academic_year_list"
    ),

    path(
        "academic-years/create/",
        academic_year_create,
        name="academic_year_create"
    ),

    path(
        "academic-years/update/<int:pk>/",
        academic_year_update,
        name="academic_year_update"
    ),

    path(
        "academic-years/delete/<int:pk>/",
        academic_year_delete,
        name="academic_year_delete"
    ),



    # ── Assignments ───────────────────────────────────────────────────────────
    path(
        'subjects/<int:pk>/assign-classes/',
        assign_subject_to_class,
        name='assign_subject_to_class',
    ),
    path(
        'subjects/<int:pk>/assign-teacher/',
        assign_subject_to_teacher,
        name='assign_subject_to_teacher',
    ),



]
