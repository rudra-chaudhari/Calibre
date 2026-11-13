from django.db import models

from apps.common.models import TimeStampedModel


class MoodleConnection(TimeStampedModel):
    """
    Stores a user's Moodle connection information.
    One row per user (OneToOneField). The token is encrypted at rest.
    """
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"

    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="moodle_connection",
    )
    moodle_userid = models.PositiveIntegerField()
    token_encrypted = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        db_table = "integrations_moodleconnection"
