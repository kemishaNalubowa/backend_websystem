from django.urls import path
from . import views

app_name = 'assessments'

urlpatterns = [

    # ── Assessment CRUD ───────────────────────────────────────────────────────
    path(
        '',
        views.assessment_list,
        name='list'
    ),
    path( 
        'add/',
        views.add_assessment,
        name='add'
    ),

    path(
        '<int:pk>/edit/',
        views.edit_assessment,
        name='edit'
    ),
    path(
        '<int:pk>/',
        views.assessment_detail,
        name='detail'
    ),
    path(
        '<int:pk>/delete/',
        views.delete_assessment,
        name='delete'
    ),
    path(
        '<int:pk>/status/',
        views.change_assessment_status,
        name='change_status'
    ),

    # ── Assessment bridge records (all posted from the detail page) ───────────
    path(
        '<int:pk>/classes/add/',
        views.add_assessment_class,
        name='add_class'
    ),
    path(
        '<int:pk>/subjects/add/',
        views.add_assessment_subject,
        name='add_subject'
    ),
    path(
        '<int:pk>/teachers/add/',
        views.add_assessment_teacher,
        name='add_teacher'
    ),
    path(
        '<int:pk>/passmarks/add/',
        views.add_assessment_passmark,
        name='add_passmark'
    ),

    # ── Student Performance ───────────────────────────────────────────────────
    path(
        '<int:pk>/performance/add/',
        views.add_student_performance,
        name='add_performance'
    ),
    path(
        '<int:pk>/performance/<int:perf_pk>/',
        views.student_performance_detail,
        name='performance_detail'
    ),
    path(
        '<int:pk>/performance/<int:perf_pk>/edit/',
        views.edit_student_performance,
        name='edit_performance'
    ),
    path(
        '<int:pk>/performance/<int:perf_pk>/delete/',
        views.delete_student_performance,
        name='delete_performance'
    ),
]
