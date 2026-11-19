from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone as tz
from rest_framework.exceptions import ValidationError

from .exceptions import SessionAlreadyRunning
from .models import FocusSession


def get_running_session(user):
    """
    Returns the user's currently running session, or None if none exists.
    """
    try:
        return FocusSession.objects.get(user=user, status=FocusSession.Status.RUNNING)
    except FocusSession.DoesNotExist:
        return None


@transaction.atomic
def start_session(user, data, now=None):
    """
    Start a new focus session. Raises SessionAlreadyRunning if one is already running.
    Resolves task, event, and category links in a priority chain.
    """
    if now is None:
        now = tz.now()

    # Check for existing running session (service-level guard)
    existing = get_running_session(user)
    if existing:
        raise SessionAlreadyRunning(existing.id)

    # Link resolution: explicit values take priority, then fall back through the chain
    # Priority: explicit task > event's task > none
    # Category: explicit category > resolved task's category > event's category > none
    task = data.get("task")
    event = data.get("event")
    category = data.get("category")

    if not task and event:
        task = event.task

    if not category:
        if task and task.category:
            category = task.category
        elif event and event.category:
            category = event.category

    try:
        session = FocusSession.objects.create(
            user=user,
            task=task,
            event=event,
            category=category,
            kind=data.get("kind", FocusSession.Kind.POMODORO),
            planned_min=data.get("planned_min"),
            status=FocusSession.Status.RUNNING,
            started_at=now,
        )
    except IntegrityError:
        # Race condition: another request started a session between our check and create
        # Fetch the running session and raise the same exception
        existing = get_running_session(user)
        if existing:
            raise SessionAlreadyRunning(existing.id)
        raise

    return session


def elapsed_minutes(session, now=None):
    """
    Returns whole minutes between started_at and now (or ended_at), rounded down.
    """
    if now is None:
        now = tz.now()
    end = session.ended_at if session.ended_at else now
    delta = end - session.started_at
    return int(delta.total_seconds() // 60)


def end_session(session, outcome, actual_min=None, feedback=None, now=None):
    """
    End a focus session. Idempotent: if already ended, returns unchanged.
    Validates actual_min against elapsed time if provided.
    """
    if now is None:
        now = tz.now()

    # Idempotent: if already ended, return unchanged
    if session.status != FocusSession.Status.RUNNING:
        return session

    # Compute elapsed time for validation
    elapsed = elapsed_minutes(session, now)
    elapsed_rounded_up = (elapsed + 59) // 60 if elapsed > 0 else 0

    # Validate actual_min if provided
    if actual_min is not None:
        if actual_min < 0:
            raise ValidationError({"actual_min": ["Actual minutes cannot be negative."]})
        if actual_min > elapsed_rounded_up:
            raise ValidationError(
                {
                    "actual_min": [
                        f"Actual minutes ({actual_min}) cannot exceed elapsed time ({elapsed_rounded_up})."
                    ]
                }
            )
    else:
        actual_min = elapsed

    # Update session
    session.status = outcome
    session.ended_at = now
    session.actual_min = actual_min

    if feedback:
        if feedback.get("rating") is not None:
            session.rating = feedback["rating"]
        if feedback.get("what_worked") is not None:
            session.what_worked = feedback["what_worked"]
        if feedback.get("what_didnt") is not None:
            session.what_didnt = feedback["what_didnt"]

    session.save()
    return session
