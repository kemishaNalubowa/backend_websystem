# students/urls.py  (complete — replaces the Part 2/3 version)
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
from students.views.student_views import (
    student_create_step1,
    student_create_step2,
    student_create_step3,
    student_detail,
    student_list,
    student_toggle_active,


    admin_student_history,
    admin_student_class_terms,
    admin_student_class_term_overview,
    admin_student_class_term_fees,
    admin_student_class_term_scholastic,
    admin_student_class_term_performance,
)

app_name = 'students'

urlpatterns = [

    # ── Student list + direct create ──────────────────────────────────────────
    path('',
         student_list,
         name='student_list'),

    path('enrol/',
         student_create_step1,
         name='student_create_step1'),

    path('enrol/parents/',
         student_create_step2,
         name='student_create_step2'),

    path('enrol/confirm/',
         student_create_step3,
         name='student_create_step3'),

    path('<int:pk>/',
         student_detail,
         name='student_detail'),

    path('<int:pk>/toggle-active/',
         student_toggle_active,
         name='student_toggle_active'),

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




     # Add to urlpatterns:
     path('<int:pk>/history/',
          admin_student_history,
          name='admin_student_history'),

     path('<int:pk>/history/<int:class_id>/',
          admin_student_class_terms,
          name='admin_student_class_terms'),

     path('<int:pk>/history/<int:class_id>/term/<int:term_id>/',
          admin_student_class_term_overview,
          name='admin_student_class_term_overview'),

     path('<int:pk>/history/<int:class_id>/term/<int:term_id>/fees/',
          admin_student_class_term_fees,
          name='admin_student_class_term_fees'),

     path('<int:pk>/history/<int:class_id>/term/<int:term_id>/scholastic/',
          admin_student_class_term_scholastic,
          name='admin_student_class_term_scholastic'),

     path('<int:pk>/history/<int:class_id>/term/<int:term_id>/performance/',
          admin_student_class_term_performance,
          name='admin_student_class_term_performance'),
]




# students/urls.py  ← ADD THIS AT THE VERY END
from django.urls import path, include

# ... [all your existing urlpatterns above] ...

# ── NEW: API routes for React (isolated) ───────────────
urlpatterns += [
    path('api/students/', include('students.api.urls', namespace='students_api')),
]