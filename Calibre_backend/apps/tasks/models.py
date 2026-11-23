from django.db import models

from apps.common.models import OwnedModel


class Task(OwnedModel):
    """
    User task with title, notes, category, due date, estimate, importance flag,
    status (todo/done), completion timestamp, reminder time, and source tracking.
    The source field supports manual tasks and external integrations (e.g., Moodle).
    """
    class Status(models.TextChoices):
        TODO = "todo", "Todo"
        DONE = "done", "Done"

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        MOODLE = "moodle", "Moodle"

    title = models.CharField(max_length=200)
    notes = models.TextField(blank=True)
    category = models.ForeignKey(
        "common.Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks",
    )
    due_at = models.DateTimeField(null=True, blank=True)
    estimate_min = models.PositiveIntegerField(null=True, blank=True)
    is_important = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.TODO)
    completed_at = models.DateTimeField(null=True, blank=True)
    remind_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.MANUAL)
    external_id = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        db_table = "tasks_task"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "source", "external_id"],
                condition=~models.Q(external_id=""),
                name="uniq_task_external",
            )
        ]
        indexes = [
            models.Index(fields=["user", "status", "due_at"]),
        ]
        ordering = ["due_at", "-created_at"]

    def save(self, *args, **kwargs):
        self.title = self.title.strip()
        super().save(*args, **kwargs)
