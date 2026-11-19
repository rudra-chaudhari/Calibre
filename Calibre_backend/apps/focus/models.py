from django.db import models

from apps.common.models import OwnedModel


class FocusSession(OwnedModel):
    """
    A work session (Pomodoro or free-running) optionally tied to a task or planner block.
    Stores start/end times, actual focused minutes, and post-session feedback.
    The category is copied at start to preserve history even if the task is re-categorized later.
    """
    class Kind(models.TextChoices):
        POMODORO = "pomodoro", "Pomodoro"
        FREE = "free", "Free"

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        ABANDONED = "abandoned", "Abandoned"

    task = models.ForeignKey(
        "tasks.Task",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="focus_sessions",
    )
    event = models.ForeignKey(
        "planner.Event",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="focus_sessions",
    )
    category = models.ForeignKey(
        "common.Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="focus_sessions",
    )
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.POMODORO)
    planned_min = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RUNNING)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    actual_min = models.PositiveIntegerField(null=True, blank=True)
    rating = models.SmallIntegerField(null=True, blank=True)
    what_worked = models.TextField(blank=True)
    what_didnt = models.TextField(blank=True)

    class Meta:
        db_table = "focus_focussession"
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(status="running"),
                name="one_running_session_per_user",
            )
        ]
        indexes = [
            models.Index(fields=["user", "started_at"]),
            models.Index(fields=["user", "status"]),
        ]
        ordering = ["-started_at", "-id"]
