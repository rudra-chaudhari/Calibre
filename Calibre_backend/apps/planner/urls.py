from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    EventViewSet,
    RoutineViewSet,
    TimetableViewSet,
    agenda_view,
    free_slots_view,
    ExternalEventViewSet,
)

router = SimpleRouter()
router.register("events", EventViewSet, basename="event")
router.register("routines", RoutineViewSet, basename="routine")
router.register("external-events", ExternalEventViewSet, basename="externalevent")
router.register("timetable", TimetableViewSet, basename="timetable")

urlpatterns = [
    path("calendar/agenda/", agenda_view, name="agenda"),
    path("free-slots/", free_slots_view, name="free_slots"),
] + router.urls
