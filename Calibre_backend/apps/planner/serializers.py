from rest_framework import serializers

from apps.common.timeutils import local_today
from apps.common.models import Category
from apps.tasks.models import Task

from .models import Event, Routine, RoutineCheckin


class EventSerializer(serializers.ModelSerializer):
    """
    Handles read/write for Event instances.
    user, source, and external_id are read-only — callers cannot supply them.
    Ownership of linked category and task is validated inline.
    """
    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "notes",
            "location",
            "category",
            "kind",
            "task",
            "start_at",
            "end_at",
            "remind_at",
            "source",
            "external_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "source", "external_id", "created_at", "updated_at"]

    def validate_title(self, value):
        # Strip whitespace; empty string after stripping is invalid.
        title = value.strip()
        if not title:
            raise serializers.ValidationError("Title cannot be empty.")
        return title

    def validate(self, attrs):
        # On PATCH one or both of start_at/end_at may be missing; fall back to
        # the stored instance values so the constraint is always checked.
        instance = self.instance
        start_at = attrs.get("start_at", instance.start_at if instance else None)
        end_at = attrs.get("end_at", instance.end_at if instance else None)

        if start_at and end_at and end_at < start_at:
            raise serializers.ValidationError(
                {"end_at": "end_at must be later than or equal to start_at."}
            )
        return attrs

    def validate_category(self, value):
        # Prevent attaching another user's category by guessing its id.
        if value and value.user != self.context["request"].user:
            raise serializers.ValidationError("Category does not belong to the user.")
        return value

    def validate_task(self, value):
        # Same ownership check for the linked task.
        if value and value.user != self.context["request"].user:
            raise serializers.ValidationError("Task does not belong to the user.")
        return value


class RoutineSerializer(serializers.ModelSerializer):
    """
    Handles read/write for Routine instances.
    start_date defaults to the user's local today when omitted on create.
    """
    start_date = serializers.DateField(required=False)

    class Meta:
        model = Routine
        fields = [
            "id",
            "title",
            "category",
            "weekdays",
            "start_time",
            "end_time",
            "start_date",
            "end_date",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_title(self, value):
        title = value.strip()
        if not title:
            raise serializers.ValidationError("Title cannot be empty.")
        return title

    def validate_weekdays(self, value):
        # Must be a non-empty list of unique integers 0–6.
        if not value:
            raise serializers.ValidationError("Weekdays cannot be empty.")
        if not all(isinstance(d, int) and 0 <= d <= 6 for d in value):
            raise serializers.ValidationError("Weekdays must be integers between 0 and 6.")
        if len(set(value)) != len(value):
            raise serializers.ValidationError("Weekdays must be unique.")
        return sorted(value)

    def validate(self, attrs):
        instance = self.instance

        # On PATCH, fall back to the instance's stored times/dates.
        start_time = attrs.get("start_time", instance.start_time if instance else None)
        end_time = attrs.get("end_time", instance.end_time if instance else None)
        start_date = attrs.get("start_date", instance.start_date if instance else None)
        end_date = attrs.get("end_date", instance.end_date if instance else None)

        if start_time and end_time and end_time <= start_time:
            raise serializers.ValidationError(
                {"end_time": "end_time must be later than start_time."}
            )
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "end_date must be on or after start_date."}
            )
        return attrs

    def validate_category(self, value):
        if value and value.user != self.context["request"].user:
            raise serializers.ValidationError("Category does not belong to the user.")
        return value

    def create(self, validated_data):
        # Default start_date to the user's local today when not supplied.
        if "start_date" not in validated_data:
            validated_data["start_date"] = local_today(
                self.context["request"].user.timezone
            )
        return super().create(validated_data)


class CheckinSerializer(serializers.Serializer):
    """
    Input: {date, done}.  Output: {routine, date, done} using RoutineCheckin fields.
    Used for both the request body (POST) and the response body.
    """
    routine = serializers.IntegerField(source="routine_id", read_only=True)
    date = serializers.DateField()
    done = serializers.BooleanField(default=True)


class AgendaQuerySerializer(serializers.Serializer):
    """Validates query parameters for GET /calendar/agenda/."""
    start_date = serializers.DateField()
    end_date = serializers.DateField()

    def validate(self, attrs):
        start_date = attrs["start_date"]
        end_date = attrs["end_date"]

        if end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "end_date must be on or after start_date."}
            )
        if (end_date - start_date).days > 62:
            raise serializers.ValidationError(
                {"end_date": "Date range cannot exceed 62 days."}
            )
        return attrs


class FreeSlotsQuerySerializer(serializers.Serializer):
    """Validates query parameters for GET /free-slots/."""
    date = serializers.DateField(required=False)
    min_minutes = serializers.IntegerField(default=15, min_value=5, max_value=480)


class AgendaItemSerializer(serializers.Serializer):
    """
    Output shape for a single agenda item (event, routine, or task).
    Used only for schema documentation.
    """
    type = serializers.CharField()
    id = serializers.IntegerField()
    title = serializers.CharField()
    start_at = serializers.CharField(allow_null=True)  # ISO string; null for tasks without due_at
    end_at = serializers.CharField(allow_null=True)
    category = serializers.IntegerField(allow_null=True)
    status = serializers.CharField(allow_null=True)
    details = serializers.DictField()
