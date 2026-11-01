from django.db import connection
from django.utils import timezone as tz
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from .mixins import OwnedQuerysetMixin
from .models import Category
from .serializers import CategorySerializer


class NoThrottle(AnonRateThrottle):
    rate = "1000/min"


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([NoThrottle])
def health_view(request):
    """
    GET /health/ (public, no auth, no throttling)
    Checks if the database is responsive.
    Response 200: {"status": "ok", "db": "ok", "time": "<UTC ISO>"}
    Response 503: {"status": "degraded", "db": "error", "time": "..."}
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return Response(
            {"status": "ok", "db": "ok", "time": tz.now().isoformat()},
            status=status.HTTP_200_OK,
        )
    except Exception:
        return Response(
            {"status": "degraded", "db": "error", "time": tz.now().isoformat()},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class CategoryViewSet(OwnedQuerysetMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing user categories.
    Allows GET, POST, PATCH, DELETE (PUT is disabled).
    No pagination: the list is small and the client needs all categories at once.
    This is an exception to the global pagination convention.
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    pagination_class = None

    def http_method_not_allowed(self, request, *args, **kwargs):
        """
        Disable PUT by returning 405 for PUT requests.
        Only GET, POST, PATCH, DELETE are allowed.
        """
        if request.method == "PUT":
            return Response(
                {"detail": 'Method "PUT" is not allowed. Use PATCH instead.'},
                status=status.HTTP_405_METHOD_NOT_ALLOWED,
            )
        return super().http_method_not_allowed(request, *args, **kwargs)
