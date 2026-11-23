from django_filters import rest_framework as filters
from django.utils import timezone as tz

from .models import Task


class TaskFilter(filters.FilterSet):
    status = filters.ChoiceFilter(choices=Task.Status.choices)
    category = filters.NumberFilter(field_name="category")
    important = filters.BooleanFilter(field_name="is_important")
    source = filters.ChoiceFilter(choices=Task.Source.choices)
    due_before = filters.DateTimeFilter(field_name="due_at", lookup_expr="lte")
    due_after = filters.DateTimeFilter(field_name="due_at", lookup_expr="gte")

    class Meta:
        model = Task
        fields = ["status", "category", "important", "source", "due_before", "due_after"]
