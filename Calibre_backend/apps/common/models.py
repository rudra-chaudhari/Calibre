from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    """
    Abstract base model that adds created_at and updated_at timestamps.
    Every model that needs to track when it was created/modified should inherit from this.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class OwnedModel(TimeStampedModel):
    """
    Abstract base model for user-owned entities.
    Every model that belongs to a user should inherit from this.
    The related_name uses app_label and class_name to avoid clashes.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)s_set",
    )

    class Meta:
        abstract = True


class Category(OwnedModel):
    """
    User-defined categories for organizing tasks, events, and focus sessions.
    Examples: Academics, Fitness, Work, Personal, etc.
    """
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=7, default="#6B7280")
    sort_order = models.IntegerField(default=0)
    is_default = models.BooleanField(default=False)

    class Meta:
        db_table = "common_category"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"], name="unique_user_category_name"
            )
        ]
        ordering = ["sort_order", "name"]

    def save(self, *args, **kwargs):
        self.name = self.name.strip()
        super().save(*args, **kwargs)
