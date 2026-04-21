# Add these to your fees/urls.py (or wherever you keep fees URLs)

from django.urls import path
from fees.views.scholastic_requirements_views import (
    scholastic_requirements_list,
    add_scholastic_requirements,
    scholastic_requirements_detail,
    delete_scholastic_requirement,
    toggle_scholastic_requirement,
)

urlpatterns += [
    path('scholastic-requirements/',                              scholastic_requirements_list,      name='scholastic_requirements_list'),
    path('scholastic-requirements/add/',                          add_scholastic_requirements,       name='add_scholastic_requirements'),
    path('scholastic-requirements/<int:pk>/edit/',                add_scholastic_requirements,       name='edit_scholastic_requirements'),
    path('scholastic-requirements/<int:pk>/',                     scholastic_requirements_detail,    name='scholastic_requirements_detail'),
    path('scholastic-requirements/<int:pk>/delete/',              delete_scholastic_requirement,     name='delete_scholastic_requirement'),
    path('scholastic-requirements/<int:pk>/toggle/',              toggle_scholastic_requirement,     name='toggle_scholastic_requirement'),
]
