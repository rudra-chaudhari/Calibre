from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone as tz
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.common.timeutils import local_day_window, local_today
from apps.common.models import Category
from apps.tasks.models import Task
from apps.planner.models import Event

from .crypto import decrypt_token, encrypt_token
from .exceptions import MoodleReauthRequired, MoodleTokenError
from .mapping import normalize_event
from .moodle_client import fetch_events, get_site_info, parse_launch_token
from .models import MoodleConnection


def connect(user, raw_token):
    """
    Connects a user to Moodle by validating their token and storing it encrypted.
    Returns (connection, created).
    Raises ValueError or MoodleTokenError as ValidationError for 400 responses.
    """
    try:
        token = parse_launch_token(raw_token)
    except ValueError as e:
        raise DjangoValidationError({"token": [str(e)]})

    try:
        site_info = get_site_info(token)
    except MoodleTokenError as e:
        raise DjangoValidationError({"token": [str(e)]})
    # MoodleAPIError and MoodleUnavailable propagate (view maps to 502)

    moodle_userid = site_info["userid"]
    token_encrypted = encrypt_token(token)

    connection, created = MoodleConnection.objects.update_or_create(
        user=user,
        defaults={
            "moodle_userid": moodle_userid,
            "token_encrypted": token_encrypted,
            "status": MoodleConnection.Status.ACTIVE,
            "last_error": "",
        },
    )

    return connection, created


def sync_window(user, now=None):
    """
    Returns (months, window_start, window_end) for the sync date range.
    months is a list of (year, month) tuples.
    window_start and window_end are UTC datetimes covering the range.
    """
    if now is None:
        now = tz.now()

    local_now = local_today(user.timezone, now)
    current_year = local_now.year
    current_month = local_now.month

    months_back = getattr(tz.settings, "MOODLE_SYNC_MONTHS_BACK", 1)
    months_forward = getattr(tz.settings, "MOODLE_SYNC_MONTHS_FORWARD", 6)

    months = []
    for offset in range(-months_back, months_forward + 1):
        # Compute target month with year boundary handling
        target_month = current_month + offset
        target_year = current_year
        while target_month < 1:
            target_month += 12
            target_year -= 1
        while target_month > 12:
            target_month -= 12
            target_year += 1
        months.append((target_year, target_month))

    # Remove duplicates (can happen if months_back + months_forward spans a year)
    months = sorted(set(months))

    # Compute UTC window bounds
    first_month = months[0]
    last_month = months[-1]
    window_start = local_day_window(user.timezone, date(first_month[0], first_month[1], 1))[0]
    next_month_date = date(last_month[0], last_month[1], 1) + timedelta(days=32)
    next_month_date = next_month_date.replace(day=1)
    window_end = local_day_window(user.timezone, next_month_date)[0]

    return months, window_start, window_end


def sync(user, now=None):
    """
    Syncs Moodle events and tasks for a user.
    Steps:
    1. Load connection; if missing raise NotFound, if expired raise MoodleReauthRequired.
    2. Decrypt token and compute sync window.
    3. Fetch all events from Moodle (nothing written yet).
    4. On MoodleTokenError: mark expired, raise MoodleReauthRequired.
    5. On other Moodle errors: set last_error, re-raise (view maps to 502).
    6. Normalize events, split into tasks and events.
    7. In one transaction.atomic():
       - Load existing Moodle-sourced tasks and events.
       - Create, update, or delete based on fetched set.
       - Field ownership: Moodle owns title and time fields; user owns everything else.
       - Never change task status.
    8. Set last_synced_at, clear last_error, set status active.
    9. Return summary counts.
    """
    if now is None:
        now = tz.now()

    # Step 1: Load connection
    try:
        connection = user.moodle_connection
    except MoodleConnection.DoesNotExist:
        raise MoodleConnection.DoesNotExist("Moodle is not connected.")

    # Step 2: If expired, raise without calling Moodle
    if connection.status == MoodleConnection.Status.EXPIRED:
        raise MoodleReauthRequired()

    # Step 2 (continued): Decrypt token and compute window
    try:
        token = decrypt_token(connection.token_encrypted)
    except Exception:
        connection.status = MoodleConnection.Status.EXPIRED
        connection.last_error = "Token decryption failed"
        connection.save()
        raise MoodleReauthRequired()

    months, window_start, window_end = sync_window(user, now)

    # Step 3: Fetch everything first
    try:
        raw_events = fetch_events(token, months)
    except MoodleTokenError:
        connection.status = MoodleConnection.Status.EXPIRED
        connection.last_error = "Moodle token expired"
        connection.save()
        raise MoodleReauthRequired()
    except (MoodleAPIError, Exception) as e:
        connection.last_error = str(e)[:255]
        connection.save()
        raise  # View maps to 502

    # Step 6: Normalize events
    normalized = [normalize_event(e) for e in raw_events]
    normalized = [n for n in normalized if n is not None]

    task_items = [n for n in normalized if n["kind"] == "task"]
    event_items = [n for n in normalized if n["kind"] == "event"]

    # Step 7: Write in one transaction
    with transaction.atomic():
        # Load Academics category
        academics = Category.objects.filter(user=user, name__iexact="Academics").first()

        # Load existing Moodle-sourced items
        existing_tasks = {
            t.external_id: t
            for t in Task.objects.filter(
                user=user, source=Task.Source.MOODLE
            ).select_related("category")
        }
        existing_events = {
            e.external_id: e
            for e in Event.objects.filter(
                user=user, source=Event.Source.MOODLE
            ).select_related("category")
        }

        fetched_task_ids = {item["external_id"] for item in task_items}
        fetched_event_ids = {item["external_id"] for item in event_items}

        tasks_created = 0
        tasks_updated = 0
        tasks_deleted = 0
        events_created = 0
        events_updated = 0
        events_deleted = 0

        # Process tasks
        for item in task_items:
            external_id = item["external_id"]
            if external_id in existing_tasks:
                task = existing_tasks[external_id]
                # Field ownership: only update Moodle-owned fields
                if task.title != item["title"] or task.due_at != item["start"]:
                    task.title = item["title"]
                    task.due_at = item["start"]
                    task.save()
                    tasks_updated += 1
            else:
                Task.objects.create(
                    user=user,
                    title=item["title"],
                    notes=item["notes"],
                    category=academics,
                    due_at=item["start"],
                    source=Task.Source.MOODLE,
                    external_id=external_id,
                    status=Task.Status.TODO,
                )
                tasks_created += 1

        # Delete tasks that are in window but not in fetched set (only todo tasks)
        for external_id, task in existing_tasks.items():
            if external_id not in fetched_task_ids:
                if task.status == Task.Status.TODO and window_start <= task.due_at < window_end:
                    task.delete()
                    tasks_deleted += 1

        # Process events
        for item in event_items:
            external_id = item["external_id"]
            if external_id in existing_events:
                event = existing_events[external_id]
                # Field ownership: only update Moodle-owned fields
                if (
                    event.title != item["title"]
                    or event.start_at != item["start"]
                    or event.end_at != item["end"]
                ):
                    event.title = item["title"]
                    event.start_at = item["start"]
                    event.end_at = item["end"]
                    event.save()
                    events_updated += 1
            else:
                Event.objects.create(
                    user=user,
                    title=item["title"],
                    notes=item["notes"],
                    category=academics,
                    kind=Event.Kind.EVENT,
                    start_at=item["start"],
                    end_at=item["end"],
                    source=Event.Source.MOODLE,
                    external_id=external_id,
                )
                events_created += 1

        # Delete events that are in window but not in fetched set
        for external_id, event in existing_events.items():
            if external_id not in fetched_event_ids:
                if window_start <= event.start_at < window_end:
                    event.delete()
                    events_deleted += 1

    # Step 8: Update connection
    connection.last_synced_at = now
    connection.last_error = ""
    connection.status = MoodleConnection.Status.ACTIVE
    connection.save()

    return {
        "tasks": {"created": tasks_created, "updated": tasks_updated, "deleted": tasks_deleted},
        "events": {"created": events_created, "updated": events_updated, "deleted": events_deleted},
        "synced_at": now.isoformat(),
        "window": {"start": window_start.isoformat(), "end": window_end.isoformat()},
    }


def disconnect(user, delete_imported=False):
    """
    Disconnects the user from Moodle.
    With delete_imported=True, also deletes Moodle-sourced todo tasks and all Moodle events.
    Completed Moodle tasks are always kept.
    Idempotent: nothing to delete is fine.
    """
    try:
        connection = user.moodle_connection
    except MoodleConnection.DoesNotExist:
        # Nothing to do
        if delete_imported:
            _delete_imported(user)
        return

    connection.delete()

    if delete_imported:
        _delete_imported(user)


def _delete_imported(user):
    """
    Helper to delete Moodle-sourced items.
    Deletes all Moodle events and todo Moodle tasks.
    Keeps done Moodle tasks and all manual items.
    """
    Event.objects.filter(user=user, source=Event.Source.MOODLE).delete()
    Task.objects.filter(user=user, source=Task.Source.MOODLE, status=Task.Status.TODO).delete()


def status_info(user):
    """
    Returns status information for the user's Moodle connection.
    """
    try:
        connection = user.moodle_connection
    except MoodleConnection.DoesNotExist:
        return {
            "connected": False,
            "status": None,
            "moodle_userid": None,
            "last_synced_at": None,
            "last_error": "",
            "imported": {"tasks": 0, "events": 0},
        }

    imported_tasks = Task.objects.filter(user=user, source=Task.Source.MOODLE).count()
    imported_events = Event.objects.filter(user=user, source=Event.Source.MOODLE).count()

    return {
        "connected": True,
        "status": connection.status,
        "moodle_userid": connection.moodle_userid,
        "last_synced_at": connection.last_synced_at.isoformat() if connection.last_synced_at else None,
        "last_error": connection.last_error,
        "imported": {"tasks": imported_tasks, "events": imported_events},
    }
