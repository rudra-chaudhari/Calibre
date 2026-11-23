from datetime import datetime, timedelta, timezone as stdlib_tz
from zoneinfo import ZoneInfo

from django.utils import timezone as tz


def local_today(tz_name, now=None):
    """
    Returns the current local date in the given timezone.
    Uses stdlib ZoneInfo (Python 3.9+). No pytz needed.
    """
    if now is None:
        now = tz.now()
    zone = ZoneInfo(tz_name)
    local_now = now.astimezone(zone)
    return local_now.date()


def local_day_window(tz_name, day):
    """
    Returns (start_utc, end_utc) for a local calendar day.

    The window runs from local midnight to the next local midnight, both
    converted to UTC as timezone-aware datetimes.

    We use datetime(..., tzinfo=ZoneInfo(...)) directly — this is the correct
    stdlib approach. pytz's zone.localize() is NOT available on ZoneInfo objects.
    """
    zone = ZoneInfo(tz_name)
    local_midnight = datetime(day.year, day.month, day.day, 0, 0, 0, tzinfo=zone)
    local_next_midnight = local_midnight + timedelta(days=1)
    # Convert to UTC using stdlib's UTC sentinel (not Django's tz.utc which doesn't exist).
    return local_midnight.astimezone(stdlib_tz.utc), local_next_midnight.astimezone(stdlib_tz.utc)


def local_to_utc(tz_name, day, time_of_day):
    """
    Returns a UTC-aware datetime for a local date + wall-clock time.

    time_of_day may arrive as a Python datetime.time object (normal ORM access)
    or as a string like '09:00' or '09:00:00' when SQLite returns raw strings.
    We handle both cases so the function is safe in tests and in production.
    """
    # Normalise time_of_day: accept time objects or HH:MM / HH:MM:SS strings.
    if isinstance(time_of_day, str):
        parts = time_of_day.split(":")
        hour, minute = int(parts[0]), int(parts[1])
    else:
        hour, minute = time_of_day.hour, time_of_day.minute

    zone = ZoneInfo(tz_name)
    local_dt = datetime(day.year, day.month, day.day, hour, minute, 0, tzinfo=zone)
    return local_dt.astimezone(stdlib_tz.utc)
