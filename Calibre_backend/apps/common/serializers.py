import re
from rest_framework import serializers

from .models import Category


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "color",
            "sort_order",
            "is_default",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_default", "created_at", "updated_at"]

    def validate_name(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError("Name cannot be empty.")
        if len(name) > 50:
            raise serializers.ValidationError("Name cannot exceed 50 characters.")

        user = self.context["request"].user
        queryset = Category.objects.filter(user=user, name__iexact=name)

        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)

        if queryset.exists():
            raise serializers.ValidationError(
                "A category with this name already exists."
            )

        return name

    def validate_color(self, value):
        if not re.match(r"^#[0-9A-Fa-f]{6}$", value):
            raise serializers.ValidationError(
                "Color must be a valid hex code (e.g., #3B82F6)."
            )
        return value
