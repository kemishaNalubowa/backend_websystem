from django.urls import path
from . import views

app_name = 'help_center'

urlpatterns = [
    path('',                          views.help_overview,      name='overview'),
    path('search/',                   views.help_search,        name='search'),
    path('category/<slug:slug>/',     views.help_category,      name='category'),
    path('article/<slug:slug>/',      views.help_article_detail, name='article_detail'),
]