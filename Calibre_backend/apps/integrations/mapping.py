import html
import re
from datetime import datetime, timedelta, timezone


def clean_text(html_text):
    """
    Removes HTML tags, unescapes entities, collapses whitespace, and strips.
    Returns empty string for None input.
    """
    if html_text is None:
        return ""
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", html_text)
    # Unescape HTML entities
    text = html.unescape(text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def to_utc(timestamp):
    """
    Converts a Unix timestamp to a UTC-aware datetime.
    """
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def normalize_event(raw):
    """
    Normalizes a raw Moodle event into a Calibre dict or None (to skip).
    Returns None for events without timestart or for teacher-side gradingdue events.
    """
    timestart = raw.get("timestart")
    if not timestart:
        return None

    eventtype = raw.get("eventtype")
    if eventtype == "gradingdue":
        return None

    # Determine kind
    kind = "task" if eventtype == "due" else "event"

    # External ID
    external_id = str(raw["id"])

    # Title: clean HTML, remove " is due" suffix for tasks, then truncate to 200
    title = clean_text(raw.get("name", ""))
    if kind == "task" and title.endswith(" is due"):
        title = title[:-7].strip()
    # Truncate to 200 characters after all processing
    if len(title) > 200:
        title = title[:200]

    # Notes: course full name, blank line, description
    course = raw.get("course", {})
    course_name = clean_text(course.get("fullname", ""))
    description = clean_text(raw.get("description", ""))

    notes_parts = []
    if course_name:
        notes_parts.append(course_name)
    if description:
        notes_parts.append(description)
    notes = "\n\n".join(notes_parts) if notes_parts else ""

    # Start time
    start = to_utc(timestart)

    # End time for events (tasks have no duration)
    end = None
    if kind == "event":
        duration = raw.get("timeduration", 0)
        end = start.replace(microsecond=0) + timedelta(seconds=duration)

    return {
        "kind": kind,
        "external_id": external_id,
        "title": title,
        "notes": notes,
        "start": start,
        "end": end,
    }
