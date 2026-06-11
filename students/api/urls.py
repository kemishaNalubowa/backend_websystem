# students/api/urls.py
from django.urls import path
from . import views

app_name = 'students_api'

urlpatterns = [
    path('ping/', views.ping_api, name='ping'),  # GET /api/students/ping/
]