from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from drf_spectacular.utils import extend_schema

from .exceptions import MoodleAPIError, MoodleUnavailable
from .serializers import ConnectSerializer, StatusSerializer, SyncSummarySerializer
from .services import connect, disconnect, status_info, sync


class MoodleErrorMixin:
    """
    Mixin to map Moodle errors to HTTP 502 responses.
    """

    def handle_moodle_error(self, e):
        if isinstance(e, (MoodleAPIError, MoodleUnavailable)):
            return Response(
                {"detail": "Moodle is unreachable or returned an error. Try again later."},
                status=status.HTTP_502_SERVICE_UNAVAILABLE,
            )
        raise  # Let other exceptions propagate


@extend_schema(
    request=ConnectSerializer,
    responses={201: StatusSerializer, 200: StatusSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def connect_view(request):
    """
    POST /api/v1/moodle/connect/
    Connects the user to Moodle with their token.
    """
    serializer = ConnectSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        connection, created = connect(request.user, serializer.validated_data["token"])
    except (MoodleAPIError, MoodleUnavailable) as e:
        return Response(
            {"detail": "Moodle is unreachable or returned an error. Try again later."},
            status=status.HTTP_502_SERVICE_UNAVAILABLE,
        )

    response_serializer = StatusSerializer(
        {
            "connected": True,
            "status": connection.status,
            "moodle_userid": connection.moodle_userid,
            "last_synced_at": connection.last_synced_at,
            "last_error": connection.last_error,
            "imported": {"tasks": 0, "events": 0},
        }
    )
    return Response(
        response_serializer.data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@extend_schema(responses={200: StatusSerializer})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def status_view(request):
    """
    GET /api/v1/moodle/status/
    Returns the user's Moodle connection status.
    """
    info = status_info(request.user)
    serializer = StatusSerializer(info)
    return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(responses={200: SyncSummarySerializer})
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([ScopedRateThrottle])
def sync_view(request):
    """
    POST /api/v1/moodle/sync/
    Syncs Moodle events and tasks for the user.
    Throttled to 10 requests per hour.
    """
    try:
        summary = sync(request.user)
    except MoodleConnection.DoesNotExist:
        return Response(
            {"detail": "Moodle is not connected."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except (MoodleAPIError, MoodleUnavailable) as e:
        return Response(
            {"detail": "Moodle is unreachable or returned an error. Try again later."},
            status=status.HTTP_502_SERVICE_UNAVAILABLE,
        )

    serializer = SyncSummarySerializer(summary)
    return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(responses={204: None})
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def disconnect_view(request):
    """
    DELETE /api/v1/moodle/?delete_imported=true
    Disconnects the user from Moodle.
    With delete_imported=true, also deletes imported Moodle tasks and events.
    """
    delete_imported = request.query_params.get("delete_imported", "false").lower() == "true"
    disconnect(request.user, delete_imported=delete_imported)
    return Response(status=status.HTTP_204_NO_CONTENT)
