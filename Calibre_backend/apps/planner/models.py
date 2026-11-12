from django.db import models

from apps.common.models import OwnedModel


class Event(OwnedModel):
    """
    A one-off calendar entry. A time block is an event with kind="block".
    Can be linked to a task (what the block is for) and a category.
    """
    class Kind(models.TextChoices):
        EVENT = "event", "Event"
        BLOCK = "block", "Block"

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        MOODLE = "moodle", "Moodle"

    title = models.CharField(max_length=200)
    notes = models.TextField(blank=True)
    location = models.CharField(max_length=200, blank=True)
    category = models.ForeignKey(
        "common.Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.EVENT)
    task = models.ForeignKey(
        "tasks.Task",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    remind_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.MANUAL)
    external_id = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        db_table = "planner_event"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "source", "external_id"],
                condition=~models.Q(external_id=""),
                name="uniq_event_external",
            )
        ]
        indexes = [
            models.Index(fields=["user", "start_at"]),
        ]
        ordering = ["start_at", "id"]

    def save(self, *args, **kwargs):
        self.title = self.title.strip()
        super().save(*args, **kwargs)


class Routine(OwnedModel):
    """
    A habit that repeats on chosen weekdays at a fixed local time.
    Occurrences are generated on demand; only check-ins are stored.
    """
    title = models.CharField(max_length=200)
    category = models.ForeignKey(
        "common.Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="routines",
    )
    weekdays = models.JSONField(default=list)
    start_time = models.TimeField()
    end_time = models.TimeField()
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "planner_routine"
        ordering = ["title", "id"]

    def save(self, *args, **kwargs):
        self.title = self.title.strip()
        super().save(*args, **kwargs)


class RoutineCheckin(OwnedModel):
    """
    Records what happened on one routine occurrence date.
    One row per (routine, date). done=True means completed, False means skipped.
    """
    routine = models.ForeignKey(
        Routine,
        on_delete=models.CASCADE,
        related_name="checkins",
    )
    date = models.DateField()
    done = models.BooleanField(default=True)

    class Meta:
        db_table = "planner_routinecheckin"
        constraints = [
            models.UniqueConstraint(
                fields=["routine", "date"], name="uniq_checkin_per_day"
            )
        ]
        ordering = ["-date", "-created_at"]
