from django.urls import path
from . import views

from . import performance_views as pv

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

    # path(
    #     '<int:pk>/edit/',
    #     views.edit_assessment,
    #     name='edit'
    # ),
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
        '<int:pk>/total-marks/add/',
        views.add_assessment_total_marks,
        name='add_total_marks'
    ),
    path(
        '<int:pk>/teachers/add/',
        views.add_assessment_teacher,
        name='add_teacher'
    ),

    # ── Student Performance ───────────────────────────────────────────────────
    # path(
    #     '<int:pk>/performance/add/',
    #     views.add_student_performance,
    #     name='add_performance'
    # ),
    # path(
    #     '<int:pk>/performance/<int:perf_pk>/',
    #     views.student_performance_detail,
    #     name='performance_detail'
    # ),
    # path(
    #     '<int:pk>/performance/<int:perf_pk>/edit/',
    #     views.edit_student_performance,
    #     name='edit_performance'
    # ),
    # path(
    #     '<int:pk>/performance/<int:perf_pk>/delete/',
    #     views.delete_student_performance,
    #     name='delete_performance'
    # ),




    # ── ADD FLOW ──────────────────────────────────────────────────────────────
    path(
        '<int:pk>/performance/entry/step1/',
        pv.perf_entry_part1,
        name='perf_entry_part1',
    ),
    path(
        '<int:pk>/performance/entry/step2/',
        pv.perf_entry_part2,
        name='perf_entry_part2',
    ),
    path(
        '<int:pk>/performance/entry/step3/',
        pv.perf_entry_part3,
        name='perf_entry_part3',
    ),
    path(
        '<int:pk>/performance/entry/step4/',
        pv.perf_entry_part4,
        name='perf_entry_part4',
    ),
 
    # ── ENABLE EDIT ───────────────────────────────────────────────────────────
    path(
        '<int:pk>/performance/enable-edit/',
        pv.enable_edit_part1,
        name='enable_edit',
    ),
 
    # ── EDIT FLOW ─────────────────────────────────────────────────────────────
    path(
        '<int:pk>/performance/edit/step1/',
        pv.perf_edit_part1,
        name='perf_edit_part1',
    ),
    path(
        '<int:pk>/performance/edit/step2/',
        pv.perf_edit_part2,
        name='perf_edit_part2',
    ),
    path(
        '<int:pk>/performance/edit/step3/',
        pv.perf_edit_part3,
        name='perf_edit_part3',
    ),
    path(
        '<int:pk>/performance/edit/step4/',
        pv.perf_edit_part4,
        name='perf_edit_part4',
    ),
]
