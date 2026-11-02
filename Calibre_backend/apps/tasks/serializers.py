from rest_framework import serializers

from apps.common.models import Category
from .models import Task
from .services import is_overdue, is_urgent


class TaskSerializer(serializers.ModelSerializer):
    is_overdue = serializers.SerializerMethodField()
    is_urgent = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "notes",
            "category",
            "due_at",
            "estimate_min",
            "is_important",
            "status",
            "completed_at",
            "remind_at",
            "source",
            "external_id",
            "is_overdue",
            "is_urgent",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "completed_at",
            "source",
            "external_id",
            "is_overdue",
            "is_urgent",
            "created_at",
            "updated_at",
        ]

    def get_is_overdue(self, obj):
        return is_overdue(obj)

    def get_is_urgent(self, obj):
        return is_urgent(obj)

    def validate_title(self, value):
        title = value.strip()
        if not title:
            raise serializers.ValidationError("Title cannot be empty.")
        if len(title) > 200:
            raise serializers.ValidationError("Title cannot exceed 200 characters.")
        return title

    def validate_estimate_min(self, value):
        if value is not None and (value < 1 or value > 1440):
            raise serializers.ValidationError(
                "Estimate must be between 1 and 1440 minutes."
            )
        return value

    def validate_category(self, value):
        if value is not None:
            user = self.context["request"].user
            if value.user_id != user.id:
                raise serializers.ValidationError("Category does not belong to you.")
        return value
