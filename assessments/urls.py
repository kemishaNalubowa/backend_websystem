from django.urls import path
from . import views

from . import performance_views as pv

from . import assessment_performance_entry_views as apev

from . import assessment_assign_views as aav

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

    # ── Assessment bridge records (all posted from the detail page) ───────────────
    path(
        '<int:pk>/classes/add/',
        aav.add_assessment_class,
        name='add_class'
    ),
    path(
        '<int:pk>/subjects/add/',
        aav.add_assessment_subject,
        name='add_subject'
    ),
    path(
        '<int:pk>/total-marks/add/',
        aav.add_assessment_total_marks,
        name='add_total_marks'
    ),
    path(
        '<int:pk>/teachers/add/',
        aav.add_assessment_teacher,
        name='add_teacher'
    ),

    # ── New workflow steps (Steps 5–7) ──────────────────────────────────────────
    path(
        '<int:pk>/activate-entry/',
        aav.activate_performance_entry,
        name='activate_entry'
    ),
    path(
        '<int:pk>/enter-performance/',
        aav.enter_student_performance,
        name='enter_performance'
    ),
    path(
        '<int:pk>/publish/',
        aav.publish_assessment,
        name='publish'
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

    # ── EDIT PERFOMANCE ─────────────────────────────────────────────────────────────
    # path('<int:pk>/performance/',                    apev.assessment_performance_list,             name='performance_list'),
    path('<int:pk>/performance/enable/',             apev.enable_assessment_performance_entry,      name='performance_enable'),
    path('<int:pk>/performance/disable/',            apev.disable_assessment_performance_entry,     name='performance_disable'),
    path('<int:pk>/performance/<str:student>/',      apev.assessment_performance_detail,            name='performance_detail'),
]







from . import performance_display_views as pdv
 
urlpatterns += [
    # 1. Overview — replaces the old performance_list view
    path(
        '<int:pk>/performance/',
        pdv.performance_overview,
        name='performance_overview',
    ),
 
    # 2. Class detail
    path(
        '<int:pk>/performance/class/<int:ac_pk>/',
        pdv.performance_class,
        name='performance_class',
    ),
 
    # 3. Class subject detail + student list
    path(
        '<int:pk>/performance/class/<int:ac_pk>/subject/<int:as_pk>/',
        pdv.performance_class_subject,
        name='performance_class_subject',
    ),
 
    # 4. Single student performance edit
    path(
        '<int:pk>/performance/class/<int:ac_pk>/subject/<int:as_pk>/student/<int:perf_pk>/edit/',
        pdv.performance_student_edit,
        name='performance_student_edit',
    ),
]
