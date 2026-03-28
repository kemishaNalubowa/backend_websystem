# school/urls.py
# ─────────────────────────────────────────────────────────────────────────────
# URL patterns for the school app.
# Namespace: 'school'
#
# Include in root urls.py as:
#   path('school/', include('school.urls', namespace='school'))
# ─────────────────────────────────────────────────────────────────────────────
 
from django.urls import path

from school.views.setting_views import (
    school_profile, school_profile_edit,
    school_profile_mini, school_settings,
)
from school.views.requirement_views import (
    requirement_list, requirement_add, requirement_edit,
    requirement_delete, requirement_duplicate, requirement_toggle_published,
)
from school.views.announcement_views import (
    announcement_list, announcement_add, announcement_edit,
    announcement_delete, announcement_detail, announcement_toggle_published,
)
from school.views.event_views import (
    event_list, event_add, event_edit,
    event_delete, event_detail, event_toggle_published,
)
from school.views.calendar_views import (
    calendar_list, calendar_add, calendar_edit,
    calendar_delete, calendar_detail,
    calendar_toggle_published, calendar_toggle_active,
)

app_name = 'school'

urlpatterns = [

    # ── School Profile ────────────────────────────────────────────────────────
    path('profile/',        school_profile,      name='school_profile'),
    path('profile/edit/',   school_profile_edit, name='school_profile_edit'),
    path('profile/mini/',   school_profile_mini, name='school_profile_mini'),

    # ── School Settings ───────────────────────────────────────────────────────
    path('settings/',       school_settings,     name='school_settings'),

    # ── Requirements ─────────────────────────────────────────────────────────
    path('requirements/',                           requirement_list,             name='requirement_list'),
    path('requirements/add/',                       requirement_add,              name='requirement_add'),
    path('requirements/<int:pk>/edit/',             requirement_edit,             name='requirement_edit'),
    path('requirements/<int:pk>/delete/',           requirement_delete,           name='requirement_delete'),
    path('requirements/<int:pk>/duplicate/',        requirement_duplicate,        name='requirement_duplicate'),
    path('requirements/<int:pk>/toggle-published/', requirement_toggle_published, name='requirement_toggle_published'),

    # ── Announcements ─────────────────────────────────────────────────────────
    path('announcements/',                           announcement_list,             name='announcement_list'),
    path('announcements/add/',                       announcement_add,              name='announcement_add'),
    path('announcements/<int:pk>/',                  announcement_detail,           name='announcement_detail'),
    path('announcements/<int:pk>/edit/',             announcement_edit,             name='announcement_edit'),
    path('announcements/<int:pk>/delete/',           announcement_delete,           name='announcement_delete'),
    path('announcements/<int:pk>/toggle-published/', announcement_toggle_published, name='announcement_toggle_published'),

    # ── Events ────────────────────────────────────────────────────────────────
    path('events/',                           event_list,             name='event_list'),
    path('events/add/',                       event_add,              name='event_add'),
    path('events/<int:pk>/',                  event_detail,           name='event_detail'),
    path('events/<int:pk>/edit/',             event_edit,             name='event_edit'),
    path('events/<int:pk>/delete/',           event_delete,           name='event_delete'),
    path('events/<int:pk>/toggle-published/', event_toggle_published, name='event_toggle_published'),

    # ── Calendars ─────────────────────────────────────────────────────────────
    #   /school/calendars/                        → list + stats
    #   /school/calendars/add/                    → add form
    #   /school/calendars/<pk>/                   → detail page
    #   /school/calendars/<pk>/edit/              → edit form
    #   /school/calendars/<pk>/delete/            → confirm + delete
    #   /school/calendars/<pk>/toggle-published/  → POST publish/draft
    #   /school/calendars/<pk>/toggle-active/     → POST activate/deactivate
    path('calendars/',                           calendar_list,             name='calendar_list'),
    path('calendars/add/',                       calendar_add,              name='calendar_add'),
    path('calendars/<int:pk>/',                  calendar_detail,           name='calendar_detail'),
    path('calendars/<int:pk>/edit/',             calendar_edit,             name='calendar_edit'),
    path('calendars/<int:pk>/delete/',           calendar_delete,           name='calendar_delete'),
    path('calendars/<int:pk>/toggle-published/', calendar_toggle_published, name='calendar_toggle_published'),
    path('calendars/<int:pk>/toggle-active/',    calendar_toggle_active,    name='calendar_toggle_active'),
]
