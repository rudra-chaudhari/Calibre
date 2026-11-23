from django.db import models
import uuid

from apps.common.models import OwnedModel, TimeStampedModel


class CourseSchedule(TimeStampedModel):
    """
    Stores course schedule information from Moodle.
    Used to generate course events for enrolled students.
    """
    course_code = models.CharField(max_length=50, unique=True)
    course_name = models.CharField(max_length=200)
    slot = models.CharField(max_length=20)  # e.g., "L1", "T1", "P1"
    weekdays = models.JSONField(default=list)  # List of integers 0-6 (Monday=0)
    start_time = models.TimeField()
    end_time = models.TimeField()
    venue = models.CharField(max_length=200, blank=True)
    semester_start = models.DateField()
    semester_end = models.DateField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "course_schedule"
        ordering = ["course_code", "slot"]
        indexes = [
            models.Index(fields=["course_code"]),
            models.Index(fields=["slot"]),
        ]


class TimetableEntry(TimeStampedModel):
    """
    One weekly lecture slot from the department timetable.
    Shared reference data (not user-owned): one row per course-section-day-slot.
    weekday uses Python convention: 0=Monday ... 6=Sunday (data only has Mon-Fri).
    """
    department = models.CharField(max_length=10)
    course_code = models.CharField(max_length=50)
    section = models.CharField(max_length=10, blank=True, default="")
    weekday = models.PositiveSmallIntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(max_length=100, blank=True, default="")
    instructor = models.CharField(max_length=200, blank=True, default="")
    marker = models.CharField(max_length=10, blank=True, default="")

    class Meta:
        db_table = "planner_timetableentry"
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "department", "course_code", "section",
                    "weekday", "start_time", "end_time", "instructor",
                ],
                name="uniq_timetable_slot",
            )
        ]
        indexes = [
            models.Index(fields=["course_code"]),
            models.Index(fields=["weekday", "start_time"]),
        ]
        ordering = ["weekday", "start_time", "course_code"]


class Event(OwnedModel):
    """
    A one-off calendar entry. A time block is an event with kind="block".
    Can be linked to a task (what the block is for) and a category.
    Repeating events share a series_id.
    """
    class Kind(models.TextChoices):
        EVENT = "event", "Event"
        BLOCK = "block", "Block"

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        MOODLE = "moodle", "Moodle"
        CSE = "cse", "CSE"
        INSTI = "insti", "Institute"
        COURSE = "course", "Course"

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
    series_id = models.UUIDField(null=True, blank=True)

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
            models.Index(fields=["series_id"]),
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


class ExternalEvent(models.Model):
    """
    Shared external events from CSE or Institute feeds.
    One row per unique (source, external_id) across all users.
    """
    class Source(models.TextChoices):
        CSE = "cse", "CSE"
        INSTI = "insti", "Institute"

    source = models.CharField(max_length=10, choices=Source.choices)
    external_id = models.CharField(max_length=100)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=200, blank=True)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    url = models.URLField(blank=True)
    removed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "external_event"
        constraints = [
            models.UniqueConstraint(
                fields=["source", "external_id"],
                name="uniq_external_event_source_id",
            )
        ]
        indexes = [
            models.Index(fields=["source", "start_at"]),
            models.Index(fields=["removed_at"]),
        ]
        ordering = ["start_at", "id"]


class DeletedEvent(OwnedModel):
    """
    Records of user-deleted events that would otherwise be recreated by sync.
    Used for course events: when a user deletes one class, future syncs skip it.
    """
    source = models.CharField(max_length=10)
    external_id = models.CharField(max_length=100)

    class Meta:
        db_table = "planner_deletedevent"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "source", "external_id"],
                name="uniq_deleted_event",
            )
        ]
        indexes = [
            models.Index(fields=["user", "source"]),
        ]
