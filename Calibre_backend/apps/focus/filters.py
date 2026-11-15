from datetime import datetime
from django_filters import rest_framework as filters
from rest_framework.exceptions import ValidationError

from apps.common.timeutils import local_day_window

from .models import FocusSession


class FocusSessionFilter(filters.FilterSet):
    status = filters.ChoiceFilter(choices=FocusSession.Status.choices)
    kind = filters.ChoiceFilter(choices=FocusSession.Kind.choices)
    task = filters.NumberFilter(field_name="task__id")
    category = filters.NumberFilter(field_name="category__id")
    event = filters.NumberFilter(field_name="event__id")

    def filter_start_date(self, queryset, name, value):
        if not value:
            return queryset
        try:
            start_date = datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            raise ValidationError({"start_date": ["Invalid date format. Use YYYY-MM-DD."]})
        user = self.request.user
        start_utc, _ = local_day_window(user.timezone, start_date)
        return queryset.filter(started_at__gte=start_utc)

    def filter_end_date(self, queryset, name, value):
        if not value:
            return queryset
        try:
            end_date = datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            raise ValidationError({"end_date": ["Invalid date format. Use YYYY-MM-DD."]})
        user = self.request.user
        _, end_utc = local_day_window(user.timezone, end_date)
        return queryset.filter(started_at__lt=end_utc)

    start_date = filters.CharFilter(method="filter_start_date")
    end_date = filters.CharFilter(method="filter_end_date")

    class Meta:
        model = FocusSession
        fields = ["status", "kind", "task", "category", "event", "start_date", "end_date"]
