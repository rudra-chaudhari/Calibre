from rest_framework import serializers

from .models import FocusSession


class FocusSessionSerializer(serializers.ModelSerializer):
    """
    Output serializer for focus sessions. Used in all responses.
    """
    class Meta:
        model = FocusSession
        fields = [
            "id",
            "task",
            "event",
            "category",
            "kind",
            "planned_min",
            "status",
            "started_at",
            "ended_at",
            "actual_min",
            "rating",
            "what_worked",
            "what_didnt",
            "created_at",
            "updated_at",
        ]


class StartSessionSerializer(serializers.Serializer):
    """
    Input serializer for starting a focus session.
    """
    kind = serializers.ChoiceField(
        choices=FocusSession.Kind.choices, default=FocusSession.Kind.POMODORO, required=False
    )
    planned_min = serializers.IntegerField(required=False, allow_null=True)
    task = serializers.IntegerField(required=False, allow_null=True)
    event = serializers.IntegerField(required=False, allow_null=True)
    category = serializers.IntegerField(required=False, allow_null=True)

    def validate_planned_min(self, value):
        if value is not None and (value < 1 or value > 480):
            raise serializers.ValidationError("Planned minutes must be between 1 and 480.")
        return value

    def validate_task(self, value):
        if value is not None:
            from apps.tasks.models import Task

            user = self.context["request"].user
            try:
                task = Task.objects.get(id=value)
                if task.user_id != user.id:
                    raise serializers.ValidationError("Task does not belong to you.")
                return task
            except Task.DoesNotExist:
                raise serializers.ValidationError("Task not found.")

    def validate_event(self, value):
        if value is not None:
            from apps.planner.models import Event

            user = self.context["request"].user
            try:
                event = Event.objects.get(id=value)
                if event.user_id != user.id:
                    raise serializers.ValidationError("Event does not belong to you.")
                return event
            except Event.DoesNotExist:
                raise serializers.ValidationError("Event not found.")

    def validate_category(self, value):
        if value is not None:
            from apps.common.models import Category

            user = self.context["request"].user
            try:
                category = Category.objects.get(id=value)
                if category.user_id != user.id:
                    raise serializers.ValidationError("Category does not belong to you.")
                return category
            except Category.DoesNotExist:
                raise serializers.ValidationError("Category not found.")

    def validate(self, attrs):
        kind = attrs.get("kind", FocusSession.Kind.POMODORO)
        planned_min = attrs.get("planned_min")

        if kind == FocusSession.Kind.POMODORO and planned_min is None:
            raise serializers.ValidationError(
                {"planned_min": ["Planned minutes is required for pomodoro sessions."]}
            )

        return attrs


class EndSessionSerializer(serializers.Serializer):
    """
    Input serializer for ending a focus session.
    """
    outcome = serializers.ChoiceField(
        choices=[FocusSession.Status.COMPLETED, FocusSession.Status.ABANDONED],
        default=FocusSession.Status.COMPLETED,
    )
    actual_min = serializers.IntegerField(required=False, allow_null=True)
    rating = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=5)
    what_worked = serializers.CharField(required=False, allow_blank=True)
    what_didnt = serializers.CharField(required=False, allow_blank=True)


class SessionUpdateSerializer(serializers.ModelSerializer):
    """
    Input serializer for PATCH updates to a focus session.
    Allows updating task, category, and feedback fields on both running and ended sessions.
    """
    class Meta:
        model = FocusSession
        fields = ["task", "category", "rating", "what_worked", "what_didnt"]

    def validate_task(self, value):
        if value is not None:
            user = self.context["request"].user
            if hasattr(value, 'user_id'):
                if value.user_id != user.id:
                    raise serializers.ValidationError("Task does not belong to you.")
            else:
                from apps.tasks.models import Task
                try:
                    task = Task.objects.get(id=value)
                    if task.user_id != user.id:
                        raise serializers.ValidationError("Task does not belong to you.")
                except Task.DoesNotExist:
                    raise serializers.ValidationError("Task not found.")
        return value

    def validate_category(self, value):
        if value is not None:
            user = self.context["request"].user
            if hasattr(value, 'user_id'):
                if value.user_id != user.id:
                    raise serializers.ValidationError("Category does not belong to you.")
            else:
                from apps.common.models import Category
                try:
                    category = Category.objects.get(id=value)
                    if category.user_id != user.id:
                        raise serializers.ValidationError("Category does not belong to you.")
                except Category.DoesNotExist:
                    raise serializers.ValidationError("Category not found.")
        return value
