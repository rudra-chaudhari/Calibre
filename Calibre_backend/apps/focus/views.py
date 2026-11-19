from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.mixins import (
    DestroyModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
)
from rest_framework.response import Response

from apps.common.mixins import OwnedQuerysetMixin
from .exceptions import SessionAlreadyRunning
from .filters import FocusSessionFilter
from .models import FocusSession
from .serializers import (
    EndSessionSerializer,
    FocusSessionSerializer,
    SessionUpdateSerializer,
    StartSessionSerializer,
)
from .services import end_session, get_running_session, start_session


class FocusSessionViewSet(
    OwnedQuerysetMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    ViewSet for managing user focus sessions.
    Allows GET, POST, PATCH, DELETE (PUT is disabled).
    POST creates a new session via custom create logic.
    POST /{id}/end/ ends a session with feedback.
    GET /active/ returns the running session or 204.
    """
    queryset = FocusSession.objects.select_related("task", "event", "category").all()
    filter_backends = [DjangoFilterBackend]
    filterset_class = FocusSessionFilter
    ordering = ["-started_at", "-id"]

    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.action == "create":
            return StartSessionSerializer
        if self.action == "end":
            return EndSessionSerializer
        if self.action == "partial_update":
            return SessionUpdateSerializer
        return FocusSessionSerializer

    @extend_schema(
        request=StartSessionSerializer,
        responses={201: FocusSessionSerializer, 409: {"type": "object"}},
    )
    def create(self, request):
        """
        POST /focus/sessions/
        Start a new focus session. Raises 409 if one is already running.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            session = start_session(request.user, serializer.validated_data)
        except SessionAlreadyRunning as exc:
            return Response(exc.detail, status=status.HTTP_409_CONFLICT)

        output_serializer = FocusSessionSerializer(session)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        description="Get the currently running session, or 204 if none.",
        responses={200: FocusSessionSerializer, 204: None},
    )
    @action(detail=False, methods=["get"])
    def active(self, request):
        """
        GET /focus/sessions/active/
        Returns the running session or 204 No Content.
        """
        session = get_running_session(request.user)
        if session:
            serializer = self.get_serializer(session)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        request=EndSessionSerializer,
        responses={200: FocusSessionSerializer},
    )
    @action(detail=True, methods=["post"])
    def end(self, request, pk=None):
        """
        POST /focus/sessions/{id}/end/
        End a focus session with outcome and feedback.
        Idempotent: calling on an ended session returns the stored data.
        """
        session = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        feedback = {
            "rating": serializer.validated_data.get("rating"),
            "what_worked": serializer.validated_data.get("what_worked"),
            "what_didnt": serializer.validated_data.get("what_didnt"),
        }

        # For testing: pass now from request if provided as query param
        now = request.query_params.get("now")
        if now:
            from datetime import datetime
            now = datetime.fromisoformat(now.replace(" ", "+"))

        updated = end_session(
            session,
            serializer.validated_data["outcome"],
            actual_min=serializer.validated_data.get("actual_min"),
            feedback=feedback,
            now=now if now else None,
        )

        output_serializer = FocusSessionSerializer(updated)
        return Response(output_serializer.data, status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        """
        PATCH /focus/sessions/{id}/
        Update task, category, and feedback fields on a session.
        Uses SessionUpdateSerializer for validation, then FocusSessionSerializer for response.
        """
        instance = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.update(instance, serializer.validated_data)
        output_serializer = FocusSessionSerializer(instance)
        return Response(output_serializer.data, status=status.HTTP_200_OK)
