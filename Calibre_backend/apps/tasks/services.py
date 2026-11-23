from datetime import timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone as tz

from apps.common.timeutils import local_day_window, local_today
from .models import Task

URGENT_WITHIN = timedelta(hours=48)


def is_overdue(task, now=None):
    """
    A task is overdue if it's still todo and has a due date in the past.
    """
    if now is None:
        now = tz.now()
    if task.status != Task.Status.TODO or not task.due_at:
        return False
    return task.due_at < now


def is_urgent(task, now=None):
    """
    A task is urgent if it's still todo and due within 48 hours (including overdue).
    Tasks without a due date are never urgent.
    """
    if now is None:
        now = tz.now()
    if task.status != Task.Status.TODO or not task.due_at:
        return False
    return task.due_at <= now + URGENT_WITHIN


def complete_task(task, now=None):
    """
    Mark a task as done. Idempotent: if already done, returns unchanged.
    Sets completed_at to the current time.
    """
    if now is None:
        now = tz.now()
    if task.status == Task.Status.DONE:
        return task
    task.status = Task.Status.DONE
    task.completed_at = now
    task.save()
    return task


def reopen_task(task):
    """
    Reopen a completed task. Idempotent: if already todo, returns unchanged.
    Clears completed_at.
    """
    if task.status == Task.Status.TODO:
        return task
    task.status = Task.Status.TODO
    task.completed_at = None
    task.save()
    return task


def today_range(user, now=None):
    """
    Returns (start, end) as UTC datetimes covering the user's local calendar day.
    Delegates to common.timeutils.local_day_window for the conversion.
    """
    if now is None:
        now = tz.now()
    day = local_today(user.timezone, now)
    return local_day_window(user.timezone, day)


def tasks_due_today(user, now=None):
    """
    Returns the user's todo tasks due today, ordered by due_at.
    Uses today_range to convert the user's timezone to UTC.
    """
    start, end = today_range(user, now)
    return (
        Task.objects.filter(
            user=user,
            status=Task.Status.TODO,
            due_at__gte=start,
            due_at__lt=end,
        )
        .order_by("due_at")
        .select_related("category")
    )


def overdue_tasks(user, now=None):
    """
    Returns the user's todo tasks that are overdue, ordered by due_at ascending.
    """
    if now is None:
        now = tz.now()
    return (
        Task.objects.filter(
            user=user,
            status=Task.Status.TODO,
            due_at__lt=now,
        )
        .order_by("due_at")
        .select_related("category")
    )


def quadrant(task, now=None):
    """
    Classifies a todo task into an Eisenhower matrix quadrant.
    Returns: "do_first" (important & urgent), "schedule" (important, not urgent),
    "delegate" (not important, urgent), "eliminate" (neither).
    """
    if task.status != Task.Status.TODO:
        return None
    urgent = is_urgent(task, now)
    important = task.is_important
    if important and urgent:
        return "do_first"
    if important and not urgent:
        return "schedule"
    if not important and urgent:
        return "delegate"
    return "eliminate"


def matrix(user, now=None):
    """
    Groups the user's todo tasks by quadrant into an object with four arrays.
    Each array contains tasks in the TaskSerializer shape.
    """
    tasks = Task.objects.filter(user=user, status=Task.Status.TODO).select_related(
        "category"
    )
    result = {"do_first": [], "schedule": [], "delegate": [], "eliminate": []}
    for task in tasks:
        q = quadrant(task, now)
        if q:
            result[q].append(task)
    return result


def priority_rank(task, now=None):
    """
    Returns a numeric rank for sorting tasks by priority.
    Rank 0: overdue
    Rank 1: important and urgent
    Rank 2: urgent only
    Rank 3: important only
    Rank 4: everything else
    """
    if now is None:
        now = tz.now()
    if is_overdue(task, now):
        return 0
    urgent = is_urgent(task, now)
    important = task.is_important
    if important and urgent:
        return 1
    if urgent:
        return 2
    if important:
        return 3
    return 4


def now_tasks(user, limit, now=None):
    """
    Returns the user's todo tasks sorted by priority, capped at limit.
    Sort key: (rank, due_at or far-future, id).
    Default limit is 10, max is 50.
    """
    if now is None:
        now = tz.now()
    limit = min(limit, 50)
    tasks = list(
        Task.objects.filter(user=user, status=Task.Status.TODO).select_related("category")
    )
    far_future = now + timedelta(days=365 * 10)
    tasks.sort(key=lambda t: (priority_rank(t, now), t.due_at or far_future, t.id))
    return tasks[:limit]
