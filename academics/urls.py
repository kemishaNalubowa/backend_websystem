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
    term_add,
    term_delete,
    term_detail_admissions,
    term_detail_assessment_fees,
    term_detail_assessments,
    term_detail_calendar,
    term_detail_fees,
    term_detail_overview,
    term_detail_payments,
    term_detail_requirements,
    term_edit,
    term_list,
    term_set_current,
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
)


from academics.views import views

app_name = 'academics'

urlpatterns = [

    path("supported-classes/add/", views.school_supported_classes_form, name="school_supported_classes_form"),




    # ── Term CRUD ─────────────────────────────────────────────────────────────
    path(
        'terms/',
        term_list,
        name='term_list'
    ),
    path(
        'terms/add/',
        term_add,
        name='term_add'
    ),
    path(
        'terms/<int:pk>/edit/',
        term_edit,
        name='term_edit'
    ),
    path(
        'terms/<int:pk>/delete/',
        term_delete,
        name='term_delete'
    ),
    path(
        'terms/<int:pk>/set-current/',
        term_set_current,
        name='term_set_current'
    ),

    # ── Term Detail sections ──────────────────────────────────────────────────
    path(
        'terms/<int:pk>/',
        term_detail_overview,
        name='term_detail_overview'
    ),
    path(
        'terms/<int:pk>/calendar/',
        term_detail_calendar,
        name='term_detail_calendar'
    ),
    path(
        'terms/<int:pk>/admissions/',
        term_detail_admissions,
        name='term_detail_admissions'
    ),
    path(
        'terms/<int:pk>/requirements/',
        term_detail_requirements,
        name='term_detail_requirements'
    ),
    path(
        'terms/<int:pk>/fees/',
        term_detail_fees,
        name='term_detail_fees'
    ),
    path(
        'terms/<int:pk>/payments/',
        term_detail_payments,
        name='term_detail_payments'
    ),
    path(
        'terms/<int:pk>/assessment-fees/',
        term_detail_assessment_fees,
        name='term_detail_assessment_fees'
    ),
    path(
        'terms/<int:pk>/assessments/',
        term_detail_assessments,
        name='term_detail_assessments'
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
]
