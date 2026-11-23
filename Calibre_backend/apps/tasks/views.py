from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.common.mixins import OwnedQuerysetMixin
from .filters import TaskFilter
from .models import Task
from .serializers import TaskSerializer
from .services import (
    complete_task,
    matrix,
    now_tasks,
    overdue_tasks,
    reopen_task,
    tasks_due_today,
)


class TaskViewSet(OwnedQuerysetMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing user tasks.
    Allows GET, POST, PATCH, DELETE (PUT is disabled).
    Supports filtering by status, category, important, source, due_before, due_after.
    Supports ordering by due_at, created_at (with - for descending).
    Default ordering: due_at ascending (nulls last), then newest first.
    """
    queryset = Task.objects.select_related("category").all()
    serializer_class = TaskSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = TaskFilter
    ordering_fields = ["due_at", "created_at"]
    ordering = ["due_at", "-created_at"]

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

    @extend_schema(
        description="Mark a task as done. Idempotent: calling on an already done task is fine.",
        responses={200: TaskSerializer},
    )
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """
        POST /tasks/{id}/complete/
        Marks the task as done. Returns the updated task.
        """
        task = self.get_object()
        complete_task(task)
        serializer = self.get_serializer(task)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        description="Reopen a completed task. Idempotent: calling on a todo task is fine.",
        responses={200: TaskSerializer},
    )
    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        """
        POST /tasks/{id}/reopen/
        Reopens a completed task. Returns the updated task.
        """
        task = self.get_object()
        reopen_task(task)
        serializer = self.get_serializer(task)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        description="Get tasks due today (in the user's timezone). Returns a plain array, no pagination.",
        responses={200: TaskSerializer(many=True)},
    )
    @action(detail=False, methods=["get"])
    def today(self, request):
        """
        GET /tasks/today/
        Returns the user's tasks due today as a plain JSON array.
        Bounded by one day, so no pagination is needed.
        """
        tasks = tasks_due_today(request.user)
        serializer = self.get_serializer(tasks, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        description="Get overdue tasks. Paginated like the main list.",
        responses={200: TaskSerializer(many=True)},
    )
    @action(detail=False, methods=["get"])
    def overdue(self, request):
        """
        GET /tasks/overdue/
        Returns the user's overdue tasks with pagination.
        """
        queryset = overdue_tasks(request.user)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        description="Get tasks that matter right now, sorted by priority. Limit defaults to 10, max 50.",
        responses={200: TaskSerializer(many=True)},
    )
    @action(detail=False, methods=["get"])
    def now(self, request):
        """
        GET /tasks/now/?limit=10
        Returns the user's tasks sorted by priority, capped at limit.
        """
        try:
            limit = int(request.query_params.get("limit", 10))
        except (ValueError, TypeError):
            return Response(
                {"limit": "Limit must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if limit < 0:
            return Response(
                {"limit": "Limit must be non-negative."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tasks = now_tasks(request.user, limit)
        serializer = self.get_serializer(tasks, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        description="Get tasks grouped by Eisenhower matrix quadrant (do_first, schedule, delegate, eliminate).",
    )
    @action(detail=False, methods=["get"])
    def matrix(self, request):
        """
        GET /tasks/matrix/
        Returns the user's todo tasks grouped by quadrant.
        """
        grouped = matrix(request.user)
        serializer = self.get_serializer
        result = {
            "do_first": serializer(grouped["do_first"], many=True).data,
            "schedule": serializer(grouped["schedule"], many=True).data,
            "delegate": serializer(grouped["delegate"], many=True).data,
            "eliminate": serializer(grouped["eliminate"], many=True).data,
        }
        return Response(result, status=status.HTTP_200_OK)
