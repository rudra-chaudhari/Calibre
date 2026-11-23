from datetime import datetime

from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import NotFound

from apps.common.mixins import OwnedQuerysetMixin
from apps.common.timeutils import local_today, local_to_utc
from .filters import EventFilter
from .models import Event, Routine, ExternalEvent, TimetableEntry
from .pagination import LargePageNumberPagination
from .serializers import (
    AgendaItemSerializer,
    AgendaQuerySerializer,
    CheckinSerializer,
    EventSerializer,
    ExternalEventSerializer,
    ExternalEventQuerySerializer,
    FreeSlotsQuerySerializer,
    RoutineSerializer,
    TimetableEntrySerializer,
    TimetableImportSerializer,
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
    Supports filtering by kind, category, source, external_id, and date range.
    Uses larger pagination (up to 200) for repeated events.
    Supports repeat rule for creating recurring events.
    Supports scope parameter for PATCH/DELETE on series.
    """
    queryset = Event.objects.select_related("category", "task").all()
    serializer_class = EventSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = EventFilter
    pagination_class = LargePageNumberPagination

    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def create(self, request, *args, **kwargs):
        """
        Handle repeat rule for creating recurring events.
        Without repeat: single event (existing behavior).
        With repeat: create series of events in one transaction.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        repeat_rule = serializer.validated_data.pop("repeat", None)
        
        if not repeat_rule:
            # Single event creation (existing behavior)
            return super().create(request, *args, **kwargs)
        
        # Handle repeat rule
        import uuid
        from datetime import datetime, timedelta
        from django.db import transaction
        from zoneinfo import ZoneInfo
        
        freq = repeat_rule["freq"]
        weekdays = repeat_rule.get("weekdays", [])
        until = datetime.strptime(repeat_rule["until"], "%Y-%m-%d").date()
        
        start_at = serializer.validated_data["start_at"]
        end_at = serializer.validated_data["end_at"]
        duration = end_at - start_at
        remind_at = serializer.validated_data.get("remind_at")
        
        series_id = uuid.uuid4()
        occurrences = []
        
        # Validate weekday for weekly
        if freq == "weekly":
            if start_at.weekday() not in weekdays:
                return Response(
                    {"repeat": {"weekdays": "start_at weekday must be in weekdays list"}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        
        # Generate occurrences
        current = start_at
        while current.date() <= until:
            if freq == "daily" or (freq == "weekly" and current.weekday() in weekdays):
                occ_end = current + duration
                occ_remind = remind_at + (current - start_at) if remind_at else None
                
                occ = Event(
                    user=request.user,
                    title=serializer.validated_data["title"],
                    notes=serializer.validated_data.get("notes", ""),
                    location=serializer.validated_data.get("location", ""),
                    category=serializer.validated_data.get("category"),
                    kind=serializer.validated_data.get("kind", Event.Kind.EVENT),
                    task=serializer.validated_data.get("task"),
                    start_at=current,
                    end_at=occ_end,
                    remind_at=occ_remind,
                    source=Event.Source.MANUAL,
                    series_id=series_id,
                )
                occurrences.append(occ)
            
            current += timedelta(days=1)
        
        # Create all occurrences in one transaction
        with transaction.atomic():
            Event.objects.bulk_create(occurrences)
        
        # Return first event with series info
        first_event = occurrences[0]
        first_event.refresh_from_db()
        serializer = self.get_serializer(first_event)
        
        return Response(
            {
                "series_id": str(series_id),
                "count": len(occurrences),
                "first": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        """
        Handle scope parameter for updating series.
        scope=this: update only this event (default)
        scope=following: update this and all later events in series
        scope=all: update all events in series
        """
        scope = request.query_params.get("scope", "this")
        event = self.get_object()
        
        if not event.series_id or scope == "this":
            # Single event update (existing behavior)
            return super().update(request, *args, **kwargs)
        
        if scope not in ("following", "all"):
            return Response(
                {"scope": "Invalid scope. Must be 'this', 'following', or 'all'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Prevent date changes with scope
        if "start_at" in request.data or "end_at" in request.data:
            return Response(
                {"detail": "Cannot change dates with scope=following or scope=all."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Get all events in scope
        if scope == "all":
            events_to_update = Event.objects.filter(
                user=request.user, series_id=event.series_id
            )
        else:  # following
            events_to_update = Event.objects.filter(
                user=request.user, series_id=event.series_id, start_at__gte=event.start_at
            )
        
        # Apply changes to all events in scope
        serializer = self.get_serializer(event, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        # Only update safe fields
        allowed_fields = ["title", "notes", "location", "category", "kind", "task"]
        update_data = {k: v for k, v in serializer.validated_data.items() if k in allowed_fields}
        
        events_to_update.update(**update_data)
        
        # Return updated first event
        event.refresh_from_db()
        serializer = self.get_serializer(event)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        """
        Handle scope parameter for deleting series.
        scope=this: delete only this event (default)
        scope=following: delete this and all later events in series
        scope=all: delete all events in series
        """
        scope = request.query_params.get("scope", "this")
        event = self.get_object()
        
        if not event.series_id or scope == "this":
            # Single event delete (existing behavior)
            # Track deletion for course events
            if event.source == Event.Source.COURSE and event.external_id:
                from .models import DeletedEvent
                DeletedEvent.objects.get_or_create(
                    user=request.user,
                    source=event.source,
                    external_id=event.external_id,
                )
            return super().destroy(request, *args, **kwargs)
        
        if scope not in ("following", "all"):
            return Response(
                {"scope": "Invalid scope. Must be 'this', 'following', or 'all'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Delete events in scope
        if scope == "all":
            events_to_delete = Event.objects.filter(user=request.user, series_id=event.series_id)
        else:  # following
            events_to_delete = Event.objects.filter(
                user=request.user, series_id=event.series_id, start_at__gte=event.start_at
            )
        
        # Track deletions for course events
        from .models import DeletedEvent
        for e in events_to_delete:
            if e.source == Event.Source.COURSE and e.external_id:
                DeletedEvent.objects.get_or_create(
                    user=request.user,
                    source=e.source,
                    external_id=e.external_id,
                )
        
        events_to_delete.delete()
        
        return Response(status=status.HTTP_204_NO_CONTENT)


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


class ExternalEventViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for reading shared external events from CSE/Institute feeds.
    GET /external-events/ - list with source and date range filtering
    POST /external-events/{id}/add/ - add to user's own events
    """
    queryset = ExternalEvent.objects.filter(removed_at__isnull=True)
    serializer_class = ExternalEventSerializer
    pagination_class = LargePageNumberPagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        source = self.request.query_params.get("source")
        if source:
            queryset = queryset.filter(source=source)
        
        # Date range filtering (same overlap rules as events)
        from apps.common.timeutils import local_day_window
        from datetime import datetime, timedelta
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        
        if start_date:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
                start_utc, _ = local_day_window(self.request.user.timezone, start_dt)
                queryset = queryset.filter(end_at__gt=start_utc)
            except ValueError:
                pass
        
        if end_date:
            try:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
                next_day = end_dt + timedelta(days=1)
                _, end_utc = local_day_window(self.request.user.timezone, next_day)
                queryset = queryset.filter(start_at__lt=end_utc)
            except ValueError:
                pass
        
        return queryset

    def list(self, request, *args, **kwargs):
        """Validate query parameters before listing."""
        query_serializer = ExternalEventQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        return super().list(request, *args, **kwargs)

    @extend_schema(responses={201: EventSerializer, 200: EventSerializer})
    @action(detail=True, methods=["post"])
    def add(self, request, pk=None):
        """
        POST /external-events/{id}/add/
        Creates a user event from an external event.
        Returns 201 if new, 200 if already added.
        """
        external_event = self.get_object()
        
        # Check if user already has this event
        existing = Event.objects.filter(
            user=request.user,
            source=external_event.source,
            external_id=external_event.external_id,
        ).first()
        
        if existing:
            serializer = EventSerializer(existing)
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        # Get user's Personal category
        from apps.common.models import Category
        personal = Category.objects.filter(
            user=request.user, name__iexact="Personal"
        ).first()
        
        # Create new event
        event = Event.objects.create(
            user=request.user,
            title=external_event.title,
            notes=external_event.description,
            location=external_event.location,
            category=personal,
            kind=Event.Kind.EVENT,
            start_at=external_event.start_at,
            end_at=external_event.end_at,
            source=external_event.source,
            external_id=external_event.external_id,
        )
        
        serializer = EventSerializer(event)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


DAY_NAME_TO_WEEKDAY = {
    "mon": 0, "monday": 0,
    "tue": 1, "tuesday": 1,
    "wed": 2, "wednesday": 2,
    "thu": 3, "thursday": 3,
    "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
}


class TimetableViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for the shared department timetable.
    GET /timetable/ - list slots with filters (department, course_code, weekday, q)
    POST /timetable/import/ - replace the whole timetable from a JSON payload
    """
    queryset = TimetableEntry.objects.all()
    serializer_class = TimetableEntrySerializer
    pagination_class = LargePageNumberPagination
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        department = params.get("department")
        if department:
            queryset = queryset.filter(department__iexact=department)

        course_code = params.get("course_code")
        if course_code:
            queryset = queryset.filter(course_code__icontains=course_code)

        weekday = params.get("weekday")
        if weekday is not None:
            try:
                queryset = queryset.filter(weekday=int(weekday))
            except ValueError:
                pass

        q = params.get("q")
        if q:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(course_code__icontains=q)
                | Q(instructor__icontains=q)
                | Q(room__icontains=q)
            )

        return queryset

    @action(detail=False, methods=["post"], url_path="import")
    def import_timetable(self, request):
        """
        POST /timetable/import/
        Replaces the entire timetable with the rows in the payload.
        Accepts {"timetable": [...]} or a bare list of row objects.
        """
        serializer = TimetableImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rows = serializer.validated_data["timetable"]

        entries = []
        errors = []
        for idx, row in enumerate(rows):
            weekday = self._weekday_for(row)
            start_time = self._parse_time(row.get("start_time"))
            end_time = self._parse_time(row.get("end_time"))

            if weekday is None or start_time is None or end_time is None:
                errors.append({"index": idx, "detail": "Invalid day or time."})
                continue
            if end_time <= start_time:
                errors.append({"index": idx, "detail": "end_time must be after start_time."})
                continue

            entries.append(
                TimetableEntry(
                    department=row["department"].strip().upper(),
                    course_code=row["course_code"].strip(),
                    section=(row.get("section") or "").strip(),
                    weekday=weekday,
                    start_time=start_time,
                    end_time=end_time,
                    room=(row.get("room") or "").strip(),
                    instructor=(row.get("instructor") or "").strip(),
                    marker=(row.get("marker") or "").strip(),
                )
            )

        if errors and not entries:
            return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            TimetableEntry.objects.all().delete()
            TimetableEntry.objects.bulk_create(entries, ignore_conflicts=True)

        return Response(
            {
                "imported": len(entries),
                "skipped": len(errors),
                "errors": errors[:20],
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _weekday_for(row):
        day_no = row.get("day_no")
        if day_no:
            return day_no - 1  # 1=Mon -> 0
        for key in ("day", "day_name"):
            value = (row.get(key) or "").strip().lower()
            if value in DAY_NAME_TO_WEEKDAY:
                return DAY_NAME_TO_WEEKDAY[value]
        return None

    @staticmethod
    def _parse_time(value):
        if not value:
            return None
        try:
            return datetime.strptime(value.strip(), "%H:%M").time()
        except (ValueError, AttributeError):
            return None


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
