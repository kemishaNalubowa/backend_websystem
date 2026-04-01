# students/urls.py
# ─────────────────────────────────────────────────────────────────────────────
# URL patterns for the students app.
# Namespace: 'students'
# ─────────────────────────────────────────────────────────────────────────────

from django.urls import path

from students.views.admission_views import (
    admission_add_step1,
    admission_add_step2,
    admission_add_step3,
    admission_delete,
    admission_detail,
    admission_edit_parents,
    admission_list,
    admission_update_status,
    admission_verify_step1,
    admission_verify_step2,
    admission_verify_step3,
    admission_verify_step4,
)

app_name = 'students' 

urlpatterns = [

    # ── Admissions list ───────────────────────────────────────────────────────
    path('admissions/',
         admission_list,
         name='admission_list'),

    # ── Add flow (3 steps) ────────────────────────────────────────────────────
    path('admissions/add/',
         admission_add_step1,
         name='admission_add_step1'),

    path('admissions/add/parents/',
         admission_add_step2,
         name='admission_add_step2'),

    path('admissions/add/confirm/',
         admission_add_step3,
         name='admission_add_step3'),

    # ── Single admission ──────────────────────────────────────────────────────
    path('admissions/<int:pk>/',
         admission_detail,
         name='admission_detail'),

    path('admissions/<int:pk>/delete/',
         admission_delete,
         name='admission_delete'),

    path('admissions/<int:pk>/update-status/',
         admission_update_status,
         name='admission_update_status'),

    path('admissions/<int:pk>/edit-parents/',
         admission_edit_parents,
         name='admission_edit_parents'),

    # ── Verify flow (4 steps) ─────────────────────────────────────────────────
    path('admissions/<int:pk>/verify/',
         admission_verify_step1,
         name='admission_verify_step1'),

    path('admissions/<int:pk>/verify/student/',
         admission_verify_step2,
         name='admission_verify_step2'),

    path('admissions/<int:pk>/verify/parents/',
         admission_verify_step3,
         name='admission_verify_step3'),

    path('admissions/<int:pk>/verify/summary/',
         admission_verify_step4,
         name='admission_verify_step4'),
]
