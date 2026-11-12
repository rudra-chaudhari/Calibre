from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import EventViewSet, RoutineViewSet, agenda_view, free_slots_view

router = SimpleRouter()
router.register("events", EventViewSet, basename="event")
router.register("routines", RoutineViewSet, basename="routine")

urlpatterns = [
    path("calendar/agenda/", agenda_view, name="agenda"),
    path("free-slots/", free_slots_view, name="free_slots"),
] + router.urls
