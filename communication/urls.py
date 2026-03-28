from django.urls import path
from . import views

app_name = 'communication'

urlpatterns = [
    # List all requests (filtered by role automatically in the view)
    path(
        '',
        views.parent_requests_list,
        name='list'
    ),

    # Open a new request (parent or staff)
    path(
        'add/',
        views.add_parent_request,
        name='add'
    ),

    # Full request thread / detail
    path(
        '<str:ref>/',
        views.parent_request_detail,
        name='detail'
    ),

    # Post a reply to a specific request
    path(
        '<str:ref>/reply/',
        views.add_parent_request_reply,
        name='reply'
    ),
]
