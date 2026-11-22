import base64
import json
from datetime import timedelta
from urllib.parse import unquote

import requests
from django.conf import settings

from .exceptions import MoodleAPIError, MoodleTokenError, MoodleUnavailable


def parse_launch_token(raw: str) -> str:
    """
    Parses a Moodle launch token string into the actual token.
    Accepts:
    - moodlemobile://token=<base64>
    - bare base64 string
    - plain 32-character token
    Strips whitespace, URL-unquotes, extracts token part.
    Raises ValueError for empty or malformed strings.
    """
    raw = raw.strip()
    if not raw:
        raise ValueError("Token is empty")

    # Remove prefix if present
    if "token=" in raw:
        raw = raw.split("token=", 1)[1]

    # URL unquote
    raw = unquote(raw)

    # Try base64 decode
    try:
        # Add padding if needed
        padding = 4 - len(raw) % 4
        if padding != 4:
            raw += "=" * padding
        decoded = base64.b64decode(raw).decode()
        # Split on :::
        parts = decoded.split(":::")
        if len(parts) >= 2:
            return parts[1]
    except Exception:
        pass

    # If base64 decoding failed or didn't yield the expected format,
    # treat the input as the plain token
    if " " in raw:
        raise ValueError("Token contains whitespace")

    return raw


def call(token, function, **params):
    """
    Makes a POST request to the Moodle REST API.
    Raises MoodleUnavailable for network errors or invalid responses.
    Raises MoodleTokenError for invalid token responses.
    Raises MoodleAPIError for other Moodle error responses.
    Returns the parsed JSON response on success.
    """
    url = f"{settings.MOODLE_BASE_URL}/webservice/rest/server.php"
    payload = {
        "wstoken": token,
        "wsfunction": function,
        "moodlewsrestformat": "json",
        **params,
    }

    try:
        response = requests.post(
            url,
            data=payload,
            timeout=getattr(settings, "MOODLE_TIMEOUT_SECONDS", 20),
        )
    except requests.RequestException as e:
        raise MoodleUnavailable(f"Network error: {e}")

    if response.status_code != 200:
        raise MoodleUnavailable(f"HTTP {response.status_code}")

    try:
        data = response.json()
    except ValueError:
        raise MoodleUnavailable("Non-JSON response")

    if isinstance(data, dict) and "exception" in data:
        errorcode = data.get("errorcode", "")
        message = data.get("message", "Unknown error")
        if errorcode == "invalidtoken":
            raise MoodleTokenError(message)
        raise MoodleAPIError(errorcode, message)

    return data


def get_site_info(token) -> dict:
    """
    Calls core_webservice_get_site_info to validate the token.
    """
    return call(token, "core_webservice_get_site_info")


def fetch_month(token, year, month) -> list:
    """
    Fetches calendar events for a specific month.
    Returns a flat list of raw events from weeks → days → events.
    """
    data = call(
        token,
        "core_calendar_get_calendar_monthly_view",
        year=year,
        month=month,
        includenavigation=0,
        mini=0,
    )

    events = []
    weeks = data.get("weeks", [])
    for week in weeks:
        days = week.get("days", [])
        for day in days:
            day_events = day.get("events", [])
            events.extend(day_events)

    return events


def fetch_events(token, months):
    """
    Fetches events for multiple months and de-duplicates by event ID.
    months is a list of (year, month) tuples.
    Raises if any month fails (no partial results).
    """
    all_events = []
    seen_ids = set()

    for year, month in months:
        month_events = fetch_month(token, year, month)
        for event in month_events:
            event_id = event.get("id")
            if event_id and event_id not in seen_ids:
                seen_ids.add(event_id)
                all_events.append(event)

    return all_events


def fetch_enrolled_courses(token) -> list:
    """
    Fetches the user's enrolled courses from Moodle.
    Returns a list of course objects with id, shortname, fullname.
    """
    data = call(token, "core_enrol_get_users_courses", userid=0)
    return data if isinstance(data, list) else []
