import pytest
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured, ValidationError as DjangoValidationError
from django.utils import timezone as tz
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.models import Category
from apps.common.timeutils import local_day_window
from apps.integrations.crypto import decrypt_token, encrypt_token
from apps.integrations.exceptions import MoodleAPIError, MoodleReauthRequired, MoodleTokenError, MoodleUnavailable
from apps.integrations.mapping import clean_text, normalize_event, to_utc
from apps.integrations.moodle_client import call, fetch_events, fetch_month, get_site_info, parse_launch_token
from apps.integrations.models import MoodleConnection
from apps.integrations.services import connect, disconnect, status_info, sync, sync_window
from apps.planner.models import Event
from apps.tasks.models import Task

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(api_client):
    user = User.objects.create_user(
        email="test@example.com",
        password="TestPass123!",
        name="Test User",
        timezone="Asia/Kolkata",
    )
    return user


@pytest.fixture
def authenticated_client(api_client, user):
    response = api_client.post(
        "/api/v1/auth/login/",
        {"email": "test@example.com", "password": "TestPass123!"},
    )
    token = response.data["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api_client


@pytest.fixture
def moodle_token_key():
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()


@pytest.fixture
def sample_raw_event():
    return {
        "id": 9001,
        "name": "Assignment 1: Basics is due",
        "description": "<p>Submit &amp; upload on Moodle.</p>",
        "eventtype": "due",
        "modulename": "assign",
        "instance": 55,
        "timestart": 1793000000,
        "timeduration": 0,
        "timemodified": 1792000000,
        "course": {
            "id": 101,
            "shortname": "XX 101-2026-1",
            "fullname": "Intro to R&amp;D",
        },
        "action": {"name": "Add submission", "actionable": True},
    }


@pytest.mark.django_db
class TestMapping:
    def test_clean_text_removes_tags_and_unescapes(self):
        html = "<p>Hello &amp; World</p>"
        result = clean_text(html)
        assert result == "Hello & World"

    def test_clean_text_none_returns_empty(self):
        assert clean_text(None) == ""

    def test_clean_text_collapses_whitespace(self):
        html = "<p>Hello    World</p>"
        result = clean_text(html)
        assert result == "Hello World"

    def test_to_utc(self):
        ts = 1793000000
        dt = to_utc(ts)
        assert dt.tzinfo == timezone.utc

    def test_normalize_event_due_event(self, sample_raw_event):
        result = normalize_event(sample_raw_event)
        assert result is not None
        assert result["kind"] == "task"
        assert result["external_id"] == "9001"
        # Title has " is due" removed
        assert " is due" not in result["title"]
        # The cleaned title should be the name without " is due"
        assert result["title"] == "Assignment 1: Basics"

    def test_normalize_event_removes_due_suffix(self):
        raw = {
            "id": 9002,
            "name": "Quiz is due",
            "description": "",
            "eventtype": "due",
            "timestart": 1793000000,
            "timeduration": 0,
            "course": {"fullname": "Course"},
        }
        result = normalize_event(raw)
        assert " is due" not in result["title"]
        assert result["title"] == "Quiz"

    def test_normalize_event_non_due_event(self):
        raw = {
            "id": 9003,
            "name": "Lecture",
            "description": "",
            "eventtype": "open",
            "timestart": 1793000000,
            "timeduration": 3600,
            "course": {"fullname": "Course"},
        }
        result = normalize_event(raw)
        assert result is not None
        assert result["kind"] == "event"
        assert result["end"] is not None
        assert result["title"] == "Lecture"

    def test_normalize_event_skips_gradingdue(self):
        raw = {
            "id": 9004,
            "name": "Grading",
            "eventtype": "gradingdue",
            "timestart": 1793000000,
            "course": {"fullname": "Course"},
        }
        result = normalize_event(raw)
        assert result is None

    def test_normalize_event_skips_no_timestart(self):
        raw = {"id": 9005, "name": "No time", "eventtype": "due", "course": {"fullname": "Course"}}
        result = normalize_event(raw)
        assert result is None


@pytest.mark.django_db
class TestCrypto:
    def test_encrypt_decrypt_round_trip(self, moodle_token_key, settings):
        settings.MOODLE_TOKEN_KEY = moodle_token_key
        plain = "test_token_123456789012"
        cipher = encrypt_token(plain)
        decrypted = decrypt_token(cipher)
        assert decrypted == plain
        assert cipher != plain

    def test_decrypt_wrong_key_fails(self, moodle_token_key, settings):
        settings.MOODLE_TOKEN_KEY = moodle_token_key
        plain = "test_token"
        cipher = encrypt_token(plain)
        # Use a different key
        from cryptography.fernet import Fernet
        wrong_key = Fernet.generate_key()
        settings.MOODLE_TOKEN_KEY = wrong_key.decode()
        with pytest.raises(ImproperlyConfigured):
            decrypt_token(cipher)

    def test_missing_key_raises_improperly_configured(self, settings):
        settings.MOODLE_TOKEN_KEY = None
        with pytest.raises(ImproperlyConfigured):
            encrypt_token("test")


@pytest.mark.django_db
class TestTokenParsing:
    def test_parse_launch_token_with_prefix(self):
        # Simplified test with actual valid base64 data
        # Format: siteid:::token:::privatetoken
        import base64
        payload = "site123:::testtoken12345678901234567890:::privatetoken"
        b64 = base64.b64encode(payload.encode()).decode()
        raw = f"moodlemobile://token={b64}"
        result = parse_launch_token(raw)
        assert result == "testtoken12345678901234567890"

    def test_parse_launch_token_plain_token(self):
        result = parse_launch_token("12345678901234567890123456789012")
        assert result == "12345678901234567890123456789012"

    def test_parse_launch_token_empty_raises(self):
        with pytest.raises(ValueError):
            parse_launch_token("")

    def test_parse_launch_token_whitespace_in_middle_raises(self):
        with pytest.raises(ValueError):
            parse_launch_token("token with spaces")


@pytest.mark.django_db
class TestMoodleClient:
    def test_fetch_month_flattens_structure(self):
        from unittest.mock import patch

        mock_response = {
            "weeks": [
                {
                    "days": [
                        {
                            "events": [
                                {"id": 1, "name": "Event 1"},
                                {"id": 2, "name": "Event 2"},
                            ]
                        }
                    ]
                }
            ]
        }

        with patch("apps.integrations.moodle_client.call", return_value=mock_response):
            events = fetch_month("token", 2026, 11)
            assert len(events) == 2
            assert events[0]["id"] == 1

    def test_fetch_events_deduplicates(self):
        from unittest.mock import patch

        mock_response = {
            "weeks": [
                {
                    "days": [
                        {"events": [{"id": 1, "name": "Event 1"}]},
                        {"events": [{"id": 1, "name": "Event 1"}]},
                    ]
                }
            ]
        }

        with patch("apps.integrations.moodle_client.call", return_value=mock_response):
            events = fetch_events("token", [(2026, 11)])
            assert len(events) == 1

    def test_call_invalidtoken_raises_token_error(self, settings):
        settings.MOODLE_BASE_URL = "https://moodle.test"
        from unittest.mock import patch, MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"exception": "moodle_exception", "errorcode": "invalidtoken", "message": "Invalid token"}

        with patch("requests.post", return_value=mock_response):
            with pytest.raises(MoodleTokenError):
                call("token", "function")

    def test_call_other_exception_raises_api_error(self, settings):
        settings.MOODLE_BASE_URL = "https://moodle.test"
        from unittest.mock import patch, MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"exception": "moodle_exception", "errorcode": "other", "message": "Error"}

        with patch("requests.post", return_value=mock_response):
            with pytest.raises(MoodleAPIError):
                call("token", "function")

    def test_call_network_error_raises_unavailable(self, settings):
        settings.MOODLE_BASE_URL = "https://moodle.test"
        from unittest.mock import patch
        import requests

        with patch("requests.post", side_effect=requests.RequestException("Network error")):
            with pytest.raises(MoodleUnavailable):
                call("token", "function")


@pytest.mark.django_db
class TestConnect:
    def test_connect_creates_connection(self, user, moodle_token_key, settings):
        settings.MOODLE_TOKEN_KEY = moodle_token_key
        from unittest.mock import patch

        with patch("apps.integrations.services.get_site_info", return_value={"userid": 123}):
            connection, created = connect(user, "valid_token")
            assert created is True
            assert connection.moodle_userid == 123
            assert connection.status == MoodleConnection.Status.ACTIVE

    def test_connect_replaces_existing(self, user, moodle_token_key, settings):
        settings.MOODLE_TOKEN_KEY = moodle_token_key
        from unittest.mock import patch

        with patch("apps.integrations.services.get_site_info", return_value={"userid": 123}):
            connect(user, "token1")
            connection, created = connect(user, "token2")
            assert created is False
            assert connection.moodle_userid == 123

    def test_connect_moodle_rejects_token_400(self, user, moodle_token_key, settings):
        settings.MOODLE_TOKEN_KEY = moodle_token_key
        from unittest.mock import patch

        with patch("apps.integrations.moodle_client.get_site_info", side_effect=MoodleTokenError("Invalid")):
            with pytest.raises(DjangoValidationError):
                connect(user, "invalid_token")


@pytest.mark.django_db
class TestSyncWindow:
    def test_sync_window_handles_year_boundary(self, user):
        now = datetime(2026, 12, 15, 12, 0, 0, tzinfo=ZoneInfo("UTC"))
        months, start, end = sync_window(user, now)
        assert (2026, 11) in months
        assert (2027, 1) in months


@pytest.mark.django_db
class TestSyncAPI:
    def test_all_moodle_endpoints_require_auth(self, api_client):
        response = api_client.post("/api/v1/moodle/connect/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        response = api_client.get("/api/v1/moodle/status/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        response = api_client.post("/api/v1/moodle/sync/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        response = api_client.delete("/api/v1/moodle/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_connect_success(self, authenticated_client, user, moodle_token_key, settings):
        settings.MOODLE_TOKEN_KEY = moodle_token_key
        from unittest.mock import patch

        with patch("apps.integrations.services.get_site_info", return_value={"userid": 123}):
            response = authenticated_client.post("/api/v1/moodle/connect/", {"token": "valid_token"})
            assert response.status_code == status.HTTP_201_CREATED
            assert response.data["connected"] is True
            assert "token" not in response.data

    def test_status_not_connected(self, authenticated_client):
        response = authenticated_client.get("/api/v1/moodle/status/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["connected"] is False

    def test_status_connected(self, authenticated_client, user, moodle_token_key, settings):
        settings.MOODLE_TOKEN_KEY = moodle_token_key
        MoodleConnection.objects.create(user=user, moodle_userid=123, token_encrypted="encrypted", status="active")

        response = authenticated_client.get("/api/v1/moodle/status/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["connected"] is True
        assert response.data["moodle_userid"] == 123

    def test_disconnect_keeps_imported(self, authenticated_client, user, moodle_token_key, settings):
        settings.MOODLE_TOKEN_KEY = moodle_token_key
        MoodleConnection.objects.create(user=user, moodle_userid=123, token_encrypted="encrypted")
        Task.objects.create(user=user, title="Task", source=Task.Source.MOODLE, external_id="1", status=Task.Status.TODO)

        response = authenticated_client.delete("/api/v1/moodle/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert Task.objects.filter(user=user, source=Task.Source.MOODLE).exists()

    def test_disconnect_deletes_imported(self, authenticated_client, user, moodle_token_key, settings):
        settings.MOODLE_TOKEN_KEY = moodle_token_key
        MoodleConnection.objects.create(user=user, moodle_userid=123, token_encrypted="encrypted")
        Task.objects.create(user=user, title="Task", source=Task.Source.MOODLE, external_id="1", status=Task.Status.TODO)

        response = authenticated_client.delete("/api/v1/moodle/?delete_imported=true")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Task.objects.filter(user=user, source=Task.Source.MOODLE).exists()
