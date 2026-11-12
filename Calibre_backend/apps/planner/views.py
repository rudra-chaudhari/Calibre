from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.mixins import OwnedQuerysetMixin
from apps.common.timeutils import local_today, local_to_utc
from .filters import EventFilter
from .models import Event, Routine
from .serializers import (
    AgendaItemSerializer,
    AgendaQuerySerializer,
    CheckinSerializer,
    EventSerializer,
    FreeSlotsQuerySerializer,
    RoutineSerializer,
)
from .services import (
    agenda,
    free_slots,
    record_checkin,
    remove_checkin,
    suggest_tasks,
)


class EventViewSet(OwnedQuerysetMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing user events and time blocks.
    Allows GET, POST, PATCH, DELETE (PUT is disabled).
    Supports filtering by kind, category, source, and date range.
    """
    queryset = Event.objects.select_related("category", "task").all()
    serializer_class = EventSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = EventFilter

    http_method_names = ["get", "post", "patch", "delete", "head", "options"]


class RoutineViewSet(OwnedQuerysetMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing user routines (weekly habits).
    Allows GET, POST, PATCH, DELETE (PUT is disabled).
    Supports check-in actions to track habit completion.
    """
    queryset = Routine.objects.select_related("category").all()
    serializer_class = RoutineSerializer
    ordering = ["title", "id"]

    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    @extend_schema(
        request=CheckinSerializer,
        responses={201: CheckinSerializer, 200: CheckinSerializer},
    )
    @action(detail=True, methods=["post", "delete"], url_path="checkin")
    def checkin(self, request, pk=None):
        """
        POST  /routines/{id}/checkin/ — Record or update a check-in for a routine occurrence.
        DELETE /routines/{id}/checkin/?date=YYYY-MM-DD — Remove a check-in (idempotent).
        get_object() enforces the per-user ownership rule from OwnedQuerysetMixin.
        """
        routine = self.get_object()

        if request.method == "POST":
            serializer = CheckinSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            try:
                checkin, created = record_checkin(
                    routine,
                    serializer.validated_data["date"],
                    serializer.validated_data["done"],
                )
            except Exception as exc:
                # record_checkin raises django.core.exceptions.ValidationError;
                # convert it to a DRF-style 400 response.
                from django.core.exceptions import ValidationError as DjangoValidationError
                from rest_framework.exceptions import ValidationError as DRFValidationError
                if isinstance(exc, DjangoValidationError):
                    raise DRFValidationError(exc.message_dict if hasattr(exc, "message_dict") else {"detail": exc.messages})
                raise
            response_serializer = CheckinSerializer(checkin)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )

        # DELETE
        date_str = request.query_params.get("date")
        if not date_str:
            return Response(
                {"date": ["Date query parameter is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            from datetime import datetime
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"date": ["Invalid date format. Use YYYY-MM-DD."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        remove_checkin(routine, date)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    parameters=[AgendaQuerySerializer],
    responses={
        200: {
            "type": "object",
            "properties": {
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
                "timezone": {"type": "string"},
                "items": {"type": "array", "items": {"$ref": "#/components/schemas/AgendaItem"}},
            },
        }
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def agenda_view(request):
    """
    GET /calendar/agenda/?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
    Returns a merged calendar view: events, routine occurrences, and tasks due in the range.
    """
    # Validate query params with a DRF serializer so bad input gives a standard 400.
    query_serializer = AgendaQuerySerializer(data=request.query_params)
    query_serializer.is_valid(raise_exception=True)

    result = agenda(
        request.user,
        query_serializer.validated_data["start_date"],
        query_serializer.validated_data["end_date"],
    )
    return Response(result, status=status.HTTP_200_OK)


@extend_schema(
    parameters=[FreeSlotsQuerySerializer],
    responses={
        200: {
            "type": "object",
            "properties": {
                "date": {"type": "string"},
                "timezone": {"type": "string"},
                "work_window": {"type": "object"},
                "slots": {"type": "array"},
            },
        }
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def free_slots_view(request):
    """
    GET /free-slots/?date=YYYY-MM-DD&min_minutes=15
    Returns free time slots in the user's work window with greedy task suggestions.
    """
    query_serializer = FreeSlotsQuerySerializer(data=request.query_params)
    query_serializer.is_valid(raise_exception=True)

    # Default date = today in the user's local timezone.
    date = query_serializer.validated_data.get(
        "date", local_today(request.user.timezone)
    )
    min_minutes = query_serializer.validated_data["min_minutes"]

    slots = free_slots(request.user, date, min_minutes)
    slots_with_suggestions = suggest_tasks(request.user, slots)

    work_window = {
        "start_at": local_to_utc(request.user.timezone, date, request.user.work_start).isoformat(),
        "end_at": local_to_utc(request.user.timezone, date, request.user.work_end).isoformat(),
    }

    return Response(
        {
            "date": date.isoformat(),
            "timezone": request.user.timezone,
            "work_window": work_window,
            "slots": slots_with_suggestions,
        },
        status=status.HTTP_200_OK,
    )
