from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db.models import Prefetch
from django.utils import timezone as tz

from apps.common.timeutils import local_day_window, local_today, local_to_utc
from apps.tasks.models import Task
from apps.tasks.services import priority_rank

from .models import Event, Routine, RoutineCheckin


def window_for_dates(user, start_date, end_date):
    """
    Returns (start_utc, end_utc) for a date range in the user's timezone.
    The window spans from local midnight of start_date to local midnight of
    the day after end_date — both converted to UTC.
    """
    start = local_day_window(user.timezone, start_date)[0]
    end = local_day_window(user.timezone, end_date)[1]
    return start, end


def routine_occurs_on(routine, day):
    """
    Returns True if the routine is scheduled on the given local date.
    Checks: is_active, weekday membership, date within start/end bounds.
    """
    if not routine.is_active:
        return False
    if day.weekday() not in routine.weekdays:
        return False
    if day < routine.start_date:
        return False
    if routine.end_date and day > routine.end_date:
        return False
    return True


def routine_occurrences(user, start_date, end_date):
    """
    Generates routine occurrences for a date range.

    Two-query strategy: one query for all active routines, one prefetch for
    check-ins in the date range (using a filtered Prefetch), so the loop
    below performs no extra DB hits regardless of the number of routines.

    Returns a list of dicts. start_at / end_at are aware UTC datetimes
    (not strings) so callers can do arithmetic on them directly.
    """
    # Query 1: active routines for this user.
    # Query 2 (prefetch): check-ins filtered to the requested date range.
    routines = Routine.objects.filter(user=user, is_active=True).prefetch_related(
        Prefetch(
            "checkins",
            queryset=RoutineCheckin.objects.filter(
                date__gte=start_date, date__lte=end_date
            ),
            to_attr="range_checkins",
        )
    )

    occurrences = []
    current = start_date
    while current <= end_date:
        for routine in routines:
            if routine_occurs_on(routine, current):
                # Resolve status from the prefetched check-ins (no extra query).
                checkin = next(
                    (c for c in routine.range_checkins if c.date == current), None
                )
                if checkin:
                    status = "done" if checkin.done else "skipped"
                else:
                    status = "pending"

                # Convert local wall-clock time to UTC; keep as datetime objects
                # so callers (busy_intervals, agenda) can compare them directly.
                start_at = local_to_utc(user.timezone, current, routine.start_time)
                end_at = local_to_utc(user.timezone, current, routine.end_time)

                occurrences.append(
                    {
                        "routine": routine.id,
                        "title": routine.title,
                        "category": routine.category_id,
                        "date": current.isoformat(),  # local YYYY-MM-DD string
                        "start_at": start_at,          # aware UTC datetime
                        "end_at": end_at,              # aware UTC datetime
                        "status": status,
                    }
                )
        current += timedelta(days=1)

    return occurrences


def record_checkin(routine, day, done):
    """
    Records or updates a check-in for a routine on a given local date.
    Raises ValidationError if the routine doesn't occur on that date.
    Returns (checkin, created).
    """
    if not routine_occurs_on(routine, day):
        raise ValidationError({"date": ["The routine does not occur on this date."]})

    checkin, created = RoutineCheckin.objects.update_or_create(
        routine=routine,
        date=day,
        defaults={"user": routine.user, "done": done},
    )
    return checkin, created


def remove_checkin(routine, day):
    """
    Deletes the check-in for a routine on a given date (idempotent).
    After this call the occurrence reverts to 'pending'.
    """
    RoutineCheckin.objects.filter(routine=routine, date=day).delete()


def agenda(user, start_date, end_date):
    """
    Builds a merged calendar view of events, routine occurrences, and due tasks.
    Items are sorted by (start_at, type_order, id) where type_order is:
        event=0, routine=1, task=2.

    # TODO(revision): add due revision topics here once the revision app exists
    """
    start_utc, end_utc = window_for_dates(user, start_date, end_date)

    # --- Events overlapping the window ---
    events = Event.objects.filter(
        user=user, start_at__lt=end_utc, end_at__gt=start_utc
    ).select_related("category", "task")

    event_items = [
        {
            "type": "event",
            "id": event.id,
            "title": event.title,
            "start_at": event.start_at.isoformat(),
            "end_at": event.end_at.isoformat(),
            "category": event.category_id,
            "status": None,
            "details": {
                "kind": event.kind,
                "task": event.task_id,
                "location": event.location,
            },
        }
        for event in events
    ]

    # --- Routine occurrences in the range ---
    routine_occ_list = routine_occurrences(user, start_date, end_date)
    routine_items = [
        {
            "type": "routine",
            "id": occ["routine"],
            "title": occ["title"],
            # Serialize to ISO string here; internally start_at is a datetime.
            "start_at": occ["start_at"].isoformat(),
            "end_at": occ["end_at"].isoformat(),
            "category": occ["category"],
            "status": occ["status"],
            "details": {"date": occ["date"]},
        }
        for occ in routine_occ_list
    ]

    # --- Tasks whose due_at falls inside the window ---
    tasks = Task.objects.filter(
        user=user, due_at__gte=start_utc, due_at__lt=end_utc
    ).select_related("category")

    task_items = [
        {
            "type": "task",
            "id": task.id,
            "title": task.title,
            "start_at": task.due_at.isoformat() if task.due_at else None,
            "end_at": None,
            "category": task.category_id,
            "status": task.status,
            "details": {
                "estimate_min": task.estimate_min,
                "is_important": task.is_important,
            },
        }
        for task in tasks
    ]

    all_items = event_items + routine_items + task_items
    # Sort by start_at (nulls last), then type_order (event<routine<task), then id.
    type_order = {"event": 0, "routine": 1, "task": 2}
    all_items.sort(
        key=lambda x: (x["start_at"] or "9999", type_order[x["type"]], x["id"])
    )

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "timezone": user.timezone,
        "items": all_items,
    }


def busy_intervals(user, day):
    """
    Returns a list of (start_utc, end_utc) datetime tuples occupying the
    user's time on the given local day.

    Includes: all events overlapping the day (any kind); routine occurrences
    whose status is 'pending' or 'done' (a 'skipped' occurrence frees the time).
    """
    start_utc, end_utc = local_day_window(user.timezone, day)

    # Events come back as datetime tuples directly from values_list.
    events = Event.objects.filter(
        user=user, start_at__lt=end_utc, end_at__gt=start_utc
    ).values_list("start_at", "end_at")

    intervals = list(events)

    # routine_occurrences now returns datetime objects for start_at/end_at.
    occs = routine_occurrences(user, day, day)
    for occ in occs:
        if occ["status"] in ("pending", "done"):
            intervals.append((occ["start_at"], occ["end_at"]))

    return intervals


def merge_intervals(intervals):
    """
    Sorts and merges overlapping or touching intervals.
    Pure function — no DB access. Works with any comparable pair type.
    """
    if not intervals:
        return []

    sorted_intervals = sorted(intervals, key=lambda x: x[0])
    merged = [sorted_intervals[0]]

    for current in sorted_intervals[1:]:
        last = merged[-1]
        if current[0] <= last[1]:
            # Overlapping or touching — extend the last interval.
            merged[-1] = (last[0], max(last[1], current[1]))
        else:
            merged.append(current)

    return merged


# ---------------------------------------------------------------------------
# Free slots
# Steps:
#   1. Build the work window (user.work_start → work_end on local 'day', in UTC).
#   2. If 'day' is today, advance the window start to max(window_start, now).
#   3. Collect busy intervals (events + non-skipped routine occurrences).
#   4. Merge overlapping/touching busy intervals.
#   5. Subtract merged busy intervals from the window → list of free gaps.
#   6. Keep gaps whose duration >= min_minutes.
#   7. Fill each gap greedily with task suggestions (see suggest_tasks).
# ---------------------------------------------------------------------------

def free_slots(user, day, min_minutes, now=None):
    """
    Returns free time slots inside the user's work window on local date 'day'.
    Each slot is a dict: {start_at, end_at, minutes}.
    Callers should follow up with suggest_tasks to populate suggestions.
    """
    if now is None:
        now = tz.now()

    # Step 1: work window in UTC.
    zone_start = local_to_utc(user.timezone, day, user.work_start)
    zone_end = local_to_utc(user.timezone, day, user.work_end)

    # Step 2: if today, start no earlier than now.
    if local_today(user.timezone, now) == day:
        window_start = max(zone_start, now)
    else:
        window_start = zone_start

    window_end = zone_end

    if window_start >= window_end:
        return []

    # Steps 3-4: busy intervals, merged and clipped to the work window.
    busy = busy_intervals(user, day)
    merged_busy = merge_intervals(busy)

    # Clip merged busy intervals to [window_start, window_end]
    clipped_busy = []
    for b_start, b_end in merged_busy:
        c_start = max(b_start, window_start)
        c_end = min(b_end, window_end)
        if c_start < c_end:
            clipped_busy.append((c_start, c_end))

    # Step 5-6: walk the clipped busy intervals and collect gaps.
    slots = []
    current = window_start

    for busy_start, busy_end in clipped_busy:
        if current < busy_start:
            gap_minutes = (busy_start - current).total_seconds() / 60
            if gap_minutes >= min_minutes:
                slots.append(
                    {
                        "start_at": current.isoformat(),
                        "end_at": busy_start.isoformat(),
                        "minutes": int(gap_minutes),
                    }
                )
        # Move past the busy interval (but don't go backwards).
        current = max(current, busy_end)

    # Final gap between last busy interval and window end.
    if current < window_end:
        gap_minutes = (window_end - current).total_seconds() / 60
        if gap_minutes >= min_minutes:
            slots.append(
                {
                    "start_at": current.isoformat(),
                    "end_at": window_end.isoformat(),
                    "minutes": int(gap_minutes),
                }
            )

    return slots


def suggest_tasks(user, slots, now=None):
    """
    Fills time slots with task suggestions using a greedy first-fit strategy.

    Candidate tasks: todo, have estimate_min set.
    Order: priority_rank (from tasks.services) → due_at (nulls last) → id.
    A task is placed in the first slot where it fits and is never reused.
    Returns the same slots list with a 'suggestions' key added to each.
    """
    if now is None:
        now = tz.now()

    # Load all eligible tasks once; sort client-side to reuse priority_rank.
    tasks = list(
        Task.objects.filter(
            user=user, status=Task.Status.TODO, estimate_min__isnull=False
        ).select_related("category")
    )

    far_future = now + timedelta(days=365 * 10)
    tasks.sort(
        key=lambda t: (priority_rank(t, now), t.due_at or far_future, t.id)
    )

    used_task_ids = set()

    for slot in slots:
        slot["suggestions"] = []
        remaining_minutes = slot["minutes"]

        for task in tasks:
            if task.id in used_task_ids:
                continue
            if task.estimate_min <= remaining_minutes:
                slot["suggestions"].append(
                    {
                        "id": task.id,
                        "title": task.title,
                        "estimate_min": task.estimate_min,
                        "due_at": task.due_at.isoformat() if task.due_at else None,
                        "is_important": task.is_important,
                    }
                )
                remaining_minutes -= task.estimate_min
                used_task_ids.add(task.id)

    return slots
