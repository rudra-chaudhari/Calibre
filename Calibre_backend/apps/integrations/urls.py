from django.urls import path

from .views import connect_view, disconnect_view, status_view, sync_view

urlpatterns = [
    path("moodle/connect/", connect_view, name="moodle_connect"),
    path("moodle/status/", status_view, name="moodle_status"),
    path("moodle/sync/", sync_view, name="moodle_sync"),
    path("moodle/", disconnect_view, name="moodle_disconnect"),
]
