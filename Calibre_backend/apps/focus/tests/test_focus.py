from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone as tz
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.models import Category
from apps.focus.exceptions import SessionAlreadyRunning
from apps.focus.models import FocusSession
from apps.focus.services import elapsed_minutes, end_session, get_running_session, start_session
from apps.planner.models import Event
from apps.tasks.models import Task

User = get_user_model()


@pytest.mark.django_db
class TestFocusAuth:
    def test_focus_without_token(self, api_client):
        response = api_client.get("/api/v1/focus/sessions/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestStartSession:
    def test_start_pomodoro_success(self, authenticated_client, test_user):
        response = authenticated_client.post(
            "/api/v1/focus/sessions/", {"kind": "pomodoro", "planned_min": 25}
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "running"
        assert response.data["kind"] == "pomodoro"
        assert response.data["planned_min"] == 25
        assert response.data["ended_at"] is None
        assert response.data["actual_min"] is None
        assert "user" not in response.data

    def test_start_ignores_user_status_started_at_actual_min(self, authenticated_client, test_user):
        other_user = User.objects.create_user(
            email="other@example.com", password="TestPass123!"
        )
        response = authenticated_client.post(
            "/api/v1/focus/sessions/",
            {
                "kind": "pomodoro",
                "planned_min": 25,
                "user": other_user.id,
                "status": "completed",
                "started_at": "2024-01-01T00:00:00Z",
                "actual_min": 30,
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "running"
        assert response.data["started_at"] != "2024-01-01T00:00:00Z"
        assert response.data["actual_min"] is None

    def test_pomodoro_without_planned_min(self, authenticated_client, test_user):
        response = authenticated_client.post(
            "/api/v1/focus/sessions/", {"kind": "pomodoro"}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "planned_min" in response.data

    def test_free_without_planned_min(self, authenticated_client, test_user):
        response = authenticated_client.post(
            "/api/v1/focus/sessions/", {"kind": "free"}
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["kind"] == "free"
        assert response.data["planned_min"] is None

    def test_planned_min_zero(self, authenticated_client, test_user):
        response = authenticated_client.post(
            "/api/v1/focus/sessions/", {"kind": "pomodoro", "planned_min": 0}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "planned_min" in response.data

    def test_planned_min_481(self, authenticated_client, test_user):
        response = authenticated_client.post(
            "/api/v1/focus/sessions/", {"kind": "pomodoro", "planned_min": 481}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "planned_min" in response.data

    def test_invalid_kind(self, authenticated_client, test_user):
        response = authenticated_client.post(
            "/api/v1/focus/sessions/", {"kind": "invalid", "planned_min": 25}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "kind" in response.data

    def test_another_user_task(self, authenticated_client, test_user):
        other_user = User.objects.create_user(
            email="other@example.com", password="TestPass123!"
        )
        task = Task.objects.create(user=other_user, title="Other Task")
        response = authenticated_client.post(
            "/api/v1/focus/sessions/", {"kind": "pomodoro", "planned_min": 25, "task": task.id}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "task" in response.data

    def test_own_task(self, authenticated_client, test_user):
        task = Task.objects.create(user=test_user, title="My Task")
        response = authenticated_client.post(
            "/api/v1/focus/sessions/", {"kind": "pomodoro", "planned_min": 25, "task": task.id}
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["task"] == task.id

    def test_another_user_event(self, authenticated_client, test_user):
        other_user = User.objects.create_user(
            email="other@example.com", password="TestPass123!"
        )
        event = Event.objects.create(
            user=other_user,
            title="Other Event",
            start_at=tz.now(),
            end_at=tz.now() + timedelta(hours=1),
        )
        response = authenticated_client.post(
            "/api/v1/focus/sessions/", {"kind": "pomodoro", "planned_min": 25, "event": event.id}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "event" in response.data

    def test_own_event(self, authenticated_client, test_user):
        event = Event.objects.create(
            user=test_user,
            title="My Event",
            start_at=tz.now(),
            end_at=tz.now() + timedelta(hours=1),
        )
        response = authenticated_client.post(
            "/api/v1/focus/sessions/", {"kind": "pomodoro", "planned_min": 25, "event": event.id}
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["event"] == event.id

    def test_another_user_category(self, authenticated_client, test_user):
        other_user = User.objects.create_user(
            email="other@example.com", password="TestPass123!"
        )
        category = Category.objects.create(user=other_user, name="Other", color="#000000")
        response = authenticated_client.post(
            "/api/v1/focus/sessions/",
            {"kind": "pomodoro", "planned_min": 25, "category": category.id},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "category" in response.data

    def test_own_category(self, authenticated_client, test_user):
        category = Category.objects.create(user=test_user, name="My Cat", color="#000000")
        response = authenticated_client.post(
            "/api/v1/focus/sessions/",
            {"kind": "pomodoro", "planned_min": 25, "category": category.id},
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["category"] == category.id

    def test_link_resolution_category_from_task(self, authenticated_client, test_user):
        category = Category.objects.create(user=test_user, name="Cat", color="#000000")
        task = Task.objects.create(user=test_user, title="Task", category=category)
        response = authenticated_client.post(
            "/api/v1/focus/sessions/", {"kind": "pomodoro", "planned_min": 25, "task": task.id}
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["category"] == category.id

    def test_link_resolution_explicit_category_wins(self, authenticated_client, test_user):
        cat1 = Category.objects.create(user=test_user, name="Cat1", color="#000000")
        cat2 = Category.objects.create(user=test_user, name="Cat2", color="#000000")
        task = Task.objects.create(user=test_user, title="Task", category=cat1)
        response = authenticated_client.post(
            "/api/v1/focus/sessions/",
            {"kind": "pomodoro", "planned_min": 25, "task": task.id, "category": cat2.id},
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["category"] == cat2.id

    def test_link_resolution_event_task(self, authenticated_client, test_user):
        task = Task.objects.create(user=test_user, title="Task")
        event = Event.objects.create(
            user=test_user,
            title="Event",
            start_at=tz.now(),
            end_at=tz.now() + timedelta(hours=1),
            task=task,
        )
        response = authenticated_client.post(
            "/api/v1/focus/sessions/", {"kind": "pomodoro", "planned_min": 25, "event": event.id}
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["task"] == task.id

    def test_link_resolution_explicit_task_wins_event_task(self, authenticated_client, test_user):
        task1 = Task.objects.create(user=test_user, title="Task1")
        task2 = Task.objects.create(user=test_user, title="Task2")
        event = Event.objects.create(
            user=test_user,
            title="Event",
            start_at=tz.now(),
            end_at=tz.now() + timedelta(hours=1),
            task=task1,
        )
        response = authenticated_client.post(
            "/api/v1/focus/sessions/",
            {"kind": "pomodoro", "planned_min": 25, "event": event.id, "task": task2.id},
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["task"] == task2.id

    def test_link_resolution_event_category(self, authenticated_client, test_user):
        category = Category.objects.create(user=test_user, name="Cat", color="#000000")
        event = Event.objects.create(
            user=test_user,
            title="Event",
            start_at=tz.now(),
            end_at=tz.now() + timedelta(hours=1),
            category=category,
        )
        response = authenticated_client.post(
            "/api/v1/focus/sessions/", {"kind": "pomodoro", "planned_min": 25, "event": event.id}
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["category"] == category.id

    def test_link_resolution_all_nulls(self, authenticated_client, test_user):
        response = authenticated_client.post(
            "/api/v1/focus/sessions/", {"kind": "pomodoro", "planned_min": 25}
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["task"] is None
        assert response.data["event"] is None
        assert response.data["category"] is None

    def test_second_start_while_running_409(self, authenticated_client, test_user):
        authenticated_client.post(
            "/api/v1/focus/sessions/", {"kind": "pomodoro", "planned_min": 25}
        )
        response = authenticated_client.post(
            "/api/v1/focus/sessions/", {"kind": "pomodoro", "planned_min": 25}
        )
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["code"] == "session_already_running"
        assert "session_id" in response.data

    def test_second_start_after_end_works(self, authenticated_client, test_user):
        first = authenticated_client.post(
            "/api/v1/focus/sessions/", {"kind": "pomodoro", "planned_min": 25}
        )
        session_id = first.data["id"]
        authenticated_client.post(
            f"/api/v1/focus/sessions/{session_id}/end/", {"outcome": "completed"}
        )
        response = authenticated_client.post(
            "/api/v1/focus/sessions/", {"kind": "pomodoro", "planned_min": 25}
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_two_users_can_have_running_sessions(self, api_client):
        user1 = User.objects.create_user(
            email="user1@example.com", password="TestPass123!"
        )
        user2 = User.objects.create_user(
            email="user2@example.com", password="TestPass123!"
        )
        token1 = api_client.post("/api/v1/auth/login/", {"email": "user1@example.com", "password": "TestPass123!"}).data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token1}")
        api_client.post("/api/v1/focus/sessions/", {"kind": "pomodoro", "planned_min": 25})

        token2 = api_client.post("/api/v1/auth/login/", {"email": "user2@example.com", "password": "TestPass123!"}).data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token2}")
        response = api_client.post("/api/v1/focus/sessions/", {"kind": "pomodoro", "planned_min": 25})
        assert response.status_code == status.HTTP_201_CREATED

    def test_db_level_unique_constraint(self, test_user):
        now = tz.now()
        FocusSession.objects.create(
            user=test_user,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.RUNNING,
            started_at=now,
        )
        with pytest.raises(IntegrityError):
            FocusSession.objects.create(
                user=test_user,
                kind=FocusSession.Kind.POMODORO,
                planned_min=25,
                status=FocusSession.Status.RUNNING,
                started_at=now,
            )


@pytest.mark.django_db
class TestActive:
    def test_active_returns_running_session(self, authenticated_client, test_user):
        authenticated_client.post(
            "/api/v1/focus/sessions/", {"kind": "pomodoro", "planned_min": 25}
        )
        response = authenticated_client.get("/api/v1/focus/sessions/active/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "running"

    def test_active_returns_204_when_none(self, authenticated_client, test_user):
        response = authenticated_client.get("/api/v1/focus/sessions/active/")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_active_never_returns_other_user_session(self, api_client):
        user1 = User.objects.create_user(
            email="user1@example.com", password="TestPass123!"
        )
        user2 = User.objects.create_user(
            email="user2@example.com", password="TestPass123!"
        )
        token1 = api_client.post("/api/v1/auth/login/", {"email": "user1@example.com", "password": "TestPass123!"}).data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token1}")
        api_client.post("/api/v1/focus/sessions/", {"kind": "pomodoro", "planned_min": 25})

        token2 = api_client.post("/api/v1/auth/login/", {"email": "user2@example.com", "password": "TestPass123!"}).data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token2}")
        response = api_client.get("/api/v1/focus/sessions/active/")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_active_routed_as_action_not_404(self, authenticated_client, test_user):
        response = authenticated_client.get("/api/v1/focus/sessions/active/")
        assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
class TestEndSession:
    def test_end_completed(self, authenticated_client, test_user):
        session = FocusSession.objects.create(
            user=test_user,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.RUNNING,
            started_at=tz.now(),
        )
        response = authenticated_client.post(
            f"/api/v1/focus/sessions/{session.id}/end/", {"outcome": "completed"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "completed"
        assert response.data["ended_at"] is not None
        assert response.data["actual_min"] is not None

    def test_end_abandoned(self, authenticated_client, test_user):
        session = FocusSession.objects.create(
            user=test_user,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.RUNNING,
            started_at=tz.now(),
        )
        response = authenticated_client.post(
            f"/api/v1/focus/sessions/{session.id}/end/", {"outcome": "abandoned"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "abandoned"

    def test_end_with_actual_min_smaller_accepted(self, authenticated_client, test_user):
        from datetime import datetime
        now = datetime(2024, 1, 15, 10, 26, 30, tzinfo=tz.UTC)
        start = datetime(2024, 1, 15, 10, 0, 0, tzinfo=tz.UTC)

        session = FocusSession.objects.create(
            user=test_user,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.RUNNING,
            started_at=start,
        )
        response = authenticated_client.post(
            f"/api/v1/focus/sessions/{session.id}/end/",
            {"outcome": "completed", "actual_min": 20},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["actual_min"] == 20

    def test_end_with_actual_min_larger_than_elapsed_400(self, authenticated_client, test_user):
        from datetime import datetime
        now = datetime(2024, 1, 15, 10, 26, 30, tzinfo=tz.UTC)
        start = datetime(2024, 1, 15, 10, 0, 0, tzinfo=tz.UTC)

        session = FocusSession.objects.create(
            user=test_user,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.RUNNING,
            started_at=start,
        )
        response = authenticated_client.post(
            f"/api/v1/focus/sessions/{session.id}/end/?now={now.isoformat()}",
            {"outcome": "completed", "actual_min": 30},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "actual_min" in response.data

    def test_end_with_negative_actual_min_400(self, authenticated_client, test_user):
        session = FocusSession.objects.create(
            user=test_user,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.RUNNING,
            started_at=tz.now(),
        )
        response = authenticated_client.post(
            f"/api/v1/focus/sessions/{session.id}/end/",
            {"outcome": "completed", "actual_min": -5},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "actual_min" in response.data

    def test_end_with_feedback_stored(self, authenticated_client, test_user):
        session = FocusSession.objects.create(
            user=test_user,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.RUNNING,
            started_at=tz.now(),
        )
        response = authenticated_client.post(
            f"/api/v1/focus/sessions/{session.id}/end/",
            {
                "outcome": "completed",
                "rating": 5,
                "what_worked": "Good focus",
                "what_didnt": "Distractions",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["rating"] == 5
        assert response.data["what_worked"] == "Good focus"
        assert response.data["what_didnt"] == "Distractions"

    def test_end_rating_0_400(self, authenticated_client, test_user):
        session = FocusSession.objects.create(
            user=test_user,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.RUNNING,
            started_at=tz.now(),
        )
        response = authenticated_client.post(
            f"/api/v1/focus/sessions/{session.id}/end/",
            {"outcome": "completed", "rating": 0},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "rating" in response.data

    def test_end_rating_6_400(self, authenticated_client, test_user):
        session = FocusSession.objects.create(
            user=test_user,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.RUNNING,
            started_at=tz.now(),
        )
        response = authenticated_client.post(
            f"/api/v1/focus/sessions/{session.id}/end/",
            {"outcome": "completed", "rating": 6},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "rating" in response.data

    def test_end_already_ended_idempotent(self, authenticated_client, test_user):
        session = FocusSession.objects.create(
            user=test_user,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.RUNNING,
            started_at=tz.now(),
        )
        authenticated_client.post(
            f"/api/v1/focus/sessions/{session.id}/end/",
            {"outcome": "completed", "rating": 5},
        )
        session.refresh_from_db()
        first_ended_at = session.ended_at
        first_actual_min = session.actual_min

        response = authenticated_client.post(
            f"/api/v1/focus/sessions/{session.id}/end/",
            {"outcome": "abandoned", "rating": 1},
        )
        assert response.status_code == status.HTTP_200_OK
        session.refresh_from_db()
        assert session.ended_at == first_ended_at
        assert session.actual_min == first_actual_min
        assert session.status == FocusSession.Status.COMPLETED
        assert session.rating == 5

    def test_end_other_user_session_404(self, api_client):
        user1 = User.objects.create_user(
            email="user1@example.com", password="TestPass123!"
        )
        user2 = User.objects.create_user(
            email="user2@example.com", password="TestPass123!"
        )
        session = FocusSession.objects.create(
            user=user1,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.RUNNING,
            started_at=tz.now(),
        )
        token = api_client.post("/api/v1/auth/login/", {"email": "user2@example.com", "password": "TestPass123!"}).data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = api_client.post(f"/api/v1/focus/sessions/{session.id}/end/", {"outcome": "completed"})
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestPatchListDelete:
    def test_patch_updates_feedback(self, authenticated_client, test_user):
        session = FocusSession.objects.create(
            user=test_user,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.RUNNING,
            started_at=tz.now(),
        )
        response = authenticated_client.patch(
            f"/api/v1/focus/sessions/{session.id}/",
            {"rating": 4, "what_worked": "Good"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["rating"] == 4
        assert response.data["what_worked"] == "Good"

    def test_patch_updates_on_ended_session(self, authenticated_client, test_user):
        session = FocusSession.objects.create(
            user=test_user,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.COMPLETED,
            started_at=tz.now() - timedelta(minutes=30),
            ended_at=tz.now(),
            actual_min=30,
        )
        response = authenticated_client.patch(
            f"/api/v1/focus/sessions/{session.id}/",
            {"rating": 5, "what_didnt": "Interruptions"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["rating"] == 5
        assert response.data["what_didnt"] == "Interruptions"

    def test_patch_ignores_status_kind_started_at_ended_at_actual_min_planned_min(
        self, authenticated_client, test_user
    ):
        session = FocusSession.objects.create(
            user=test_user,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.RUNNING,
            started_at=tz.now(),
        )
        response = authenticated_client.patch(
            f"/api/v1/focus/sessions/{session.id}/",
            {
                "status": "completed",
                "kind": "free",
                "started_at": "2024-01-01T00:00:00Z",
                "ended_at": "2024-01-01T01:00:00Z",
                "actual_min": 60,
                "planned_min": 60,
            },
        )
        assert response.status_code == status.HTTP_200_OK
        session.refresh_from_db()
        assert session.status == FocusSession.Status.RUNNING
        assert session.kind == FocusSession.Kind.POMODORO
        assert session.planned_min == 25
        assert response.data["planned_min"] == 25
        assert response.data["ended_at"] is None
        assert response.data["actual_min"] is None

    def test_patch_task_category_ownership(self, authenticated_client, test_user):
        other_user = User.objects.create_user(
            email="other@example.com", password="TestPass123!"
        )
        task = Task.objects.create(user=other_user, title="Other Task")
        category = Category.objects.create(user=other_user, name="Other", color="#000000")
        session = FocusSession.objects.create(
            user=test_user,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.RUNNING,
            started_at=tz.now(),
        )
        response = authenticated_client.patch(
            f"/api/v1/focus/sessions/{session.id}/", {"task": task.id, "category": category.id}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_isolation(self, api_client):
        user1 = User.objects.create_user(
            email="user1@example.com", password="TestPass123!"
        )
        user2 = User.objects.create_user(
            email="user2@example.com", password="TestPass123!"
        )
        FocusSession.objects.create(
            user=user1,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.RUNNING,
            started_at=tz.now(),
        )
        FocusSession.objects.create(
            user=user2,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.RUNNING,
            started_at=tz.now(),
        )
        token = api_client.post("/api/v1/auth/login/", {"email": "user1@example.com", "password": "TestPass123!"}).data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = api_client.get("/api/v1/focus/sessions/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_list_newest_first(self, authenticated_client, test_user):
        now = tz.now()
        FocusSession.objects.create(
            user=test_user,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.COMPLETED,
            started_at=now - timedelta(hours=2),
            ended_at=now - timedelta(hours=1),
            actual_min=60,
        )
        FocusSession.objects.create(
            user=test_user,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.COMPLETED,
            started_at=now - timedelta(hours=1),
            ended_at=now,
            actual_min=60,
        )
        response = authenticated_client.get("/api/v1/focus/sessions/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"][0]["started_at"] > response.data["results"][1]["started_at"]

    def test_list_paginated(self, authenticated_client, test_user):
        for i in range(25):
            FocusSession.objects.create(
                user=test_user,
                kind=FocusSession.Kind.POMODORO,
                planned_min=25,
                status=FocusSession.Status.COMPLETED,
                started_at=tz.now() - timedelta(hours=i),
                ended_at=tz.now() - timedelta(hours=i) + timedelta(minutes=25),
                actual_min=25,
            )
        response = authenticated_client.get("/api/v1/focus/sessions/")
        assert response.status_code == status.HTTP_200_OK
        assert "count" in response.data
        assert "next" in response.data
        assert "results" in response.data
        assert len(response.data["results"]) == 20

    def test_filters_status_kind_task_category_event(self, authenticated_client, test_user):
        task = Task.objects.create(user=test_user, title="Task")
        category = Category.objects.create(user=test_user, name="Cat", color="#000000")
        event = Event.objects.create(
            user=test_user,
            title="Event",
            start_at=tz.now(),
            end_at=tz.now() + timedelta(hours=1),
        )
        FocusSession.objects.create(
            user=test_user,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.COMPLETED,
            started_at=tz.now(),
            ended_at=tz.now() + timedelta(minutes=25),
            actual_min=25,
            task=task,
            category=category,
            event=event,
        )
        response = authenticated_client.get(
            f"/api/v1/focus/sessions/?status=completed&kind=pomodoro&task={task.id}&category={category.id}&event={event.id}"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_filter_start_date_end_date_local_timezone(self, authenticated_client, test_user):
        # Use the authenticated user instead of creating a new one
        test_user.timezone = "Asia/Kolkata"
        test_user.save()
        
        # Session at 18:45 UTC on Jan 15 = 00:15+1 day in IST (Jan 16)
        session_utc = datetime(2024, 1, 15, 18, 45, 0, tzinfo=tz.UTC)
        FocusSession.objects.create(
            user=test_user,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.COMPLETED,
            started_at=session_utc,
            ended_at=session_utc + timedelta(minutes=25),
            actual_min=25,
        )
        # Query for Jan 16 in IST (should include the session)
        response = authenticated_client.get("/api/v1/focus/sessions/?start_date=2024-01-16&end_date=2024-01-16")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_filter_invalid_date(self, authenticated_client, test_user):
        response = authenticated_client.get("/api/v1/focus/sessions/?start_date=invalid")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "start_date" in response.data

    def test_filter_invalid_status(self, authenticated_client, test_user):
        response = authenticated_client.get("/api/v1/focus/sessions/?status=invalid")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_other_user_session_404(self, api_client):
        user1 = User.objects.create_user(
            email="user1@example.com", password="TestPass123!"
        )
        user2 = User.objects.create_user(
            email="user2@example.com", password="TestPass123!"
        )
        session = FocusSession.objects.create(
            user=user1,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.RUNNING,
            started_at=tz.now(),
        )
        token = api_client.post("/api/v1/auth/login/", {"email": "user2@example.com", "password": "TestPass123!"}).data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = api_client.get(f"/api/v1/focus/sessions/{session.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_other_user_session_patch_404(self, api_client):
        user1 = User.objects.create_user(
            email="user1@example.com", password="TestPass123!"
        )
        user2 = User.objects.create_user(
            email="user2@example.com", password="TestPass123!"
        )
        session = FocusSession.objects.create(
            user=user1,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.RUNNING,
            started_at=tz.now(),
        )
        token = api_client.post("/api/v1/auth/login/", {"email": "user2@example.com", "password": "TestPass123!"}).data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = api_client.patch(f"/api/v1/focus/sessions/{session.id}/", {"rating": 5})
        assert response.status_code == status.HTTP_404_NOT_FOUND
        session.refresh_from_db()
        assert session.rating is None

    def test_other_user_session_delete_404(self, api_client):
        user1 = User.objects.create_user(
            email="user1@example.com", password="TestPass123!"
        )
        user2 = User.objects.create_user(
            email="user2@example.com", password="TestPass123!"
        )
        session = FocusSession.objects.create(
            user=user1,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.RUNNING,
            started_at=tz.now(),
        )
        token = api_client.post("/api/v1/auth/login/", {"email": "user2@example.com", "password": "TestPass123!"}).data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = api_client.delete(f"/api/v1/focus/sessions/{session.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert FocusSession.objects.filter(id=session.id).exists()

    def test_delete_success(self, authenticated_client, test_user):
        session = FocusSession.objects.create(
            user=test_user,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.RUNNING,
            started_at=tz.now(),
        )
        response = authenticated_client.delete(f"/api/v1/focus/sessions/{session.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not FocusSession.objects.filter(id=session.id).exists()

    def test_delete_running_session_allows_new_start(self, authenticated_client, test_user):
        session = FocusSession.objects.create(
            user=test_user,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.RUNNING,
            started_at=tz.now(),
        )
        authenticated_client.delete(f"/api/v1/focus/sessions/{session.id}/")
        response = authenticated_client.post(
            "/api/v1/focus/sessions/", {"kind": "pomodoro", "planned_min": 25}
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_delete_task_sets_session_task_null(self, authenticated_client, test_user):
        task = Task.objects.create(user=test_user, title="Task")
        session = FocusSession.objects.create(
            user=test_user,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.COMPLETED,
            started_at=tz.now() - timedelta(minutes=30),
            ended_at=tz.now(),
            actual_min=30,
            task=task,
        )
        task.delete()
        session.refresh_from_db()
        assert session.task is None
        assert FocusSession.objects.filter(id=session.id).exists()

    def test_delete_event_sets_session_event_null(self, authenticated_client, test_user):
        event = Event.objects.create(
            user=test_user,
            title="Event",
            start_at=tz.now(),
            end_at=tz.now() + timedelta(hours=1),
        )
        session = FocusSession.objects.create(
            user=test_user,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.COMPLETED,
            started_at=tz.now() - timedelta(minutes=30),
            ended_at=tz.now(),
            actual_min=30,
            event=event,
        )
        event.delete()
        session.refresh_from_db()
        assert session.event is None
        assert FocusSession.objects.filter(id=session.id).exists()

    def test_delete_category_session_keeps_category(self, authenticated_client, test_user):
        category = Category.objects.create(user=test_user, name="Cat", color="#000000")
        session = FocusSession.objects.create(
            user=test_user,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.COMPLETED,
            started_at=tz.now() - timedelta(minutes=30),
            ended_at=tz.now(),
            actual_min=30,
            category=category,
        )
        category.delete()
        session.refresh_from_db()
        assert session.category is None
        assert FocusSession.objects.filter(id=session.id).exists()


@pytest.mark.django_db
class TestServiceLogic:
    def test_elapsed_minutes_rounds_down(self):
        user = User.objects.create_user(email="test@example.com", password="TestPass123!")
        from datetime import datetime
        start = datetime(2024, 1, 15, 10, 0, 0, tzinfo=tz.UTC)
        now = datetime(2024, 1, 15, 10, 26, 30, tzinfo=tz.UTC)
        session = FocusSession.objects.create(
            user=user,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.RUNNING,
            started_at=start,
        )
        assert elapsed_minutes(session, now) == 26

    def test_end_session_deterministic(self):
        user = User.objects.create_user(email="test@example.com", password="TestPass123!")
        from datetime import datetime
        start = datetime(2024, 1, 15, 10, 0, 0, tzinfo=tz.UTC)
        now = datetime(2024, 1, 15, 10, 26, 30, tzinfo=tz.UTC)
        session = FocusSession.objects.create(
            user=user,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.RUNNING,
            started_at=start,
        )
        end_session(session, FocusSession.Status.COMPLETED, now=now)
        session.refresh_from_db()
        assert session.actual_min == 26
        assert session.ended_at == now

    def test_get_running_session(self, test_user):
        session = FocusSession.objects.create(
            user=test_user,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.RUNNING,
            started_at=tz.now(),
        )
        running = get_running_session(test_user)
        assert running.id == session.id

    def test_get_running_session_none(self, test_user):
        running = get_running_session(test_user)
        assert running is None

    def test_start_session_raises_session_already_running(self, test_user):
        FocusSession.objects.create(
            user=test_user,
            kind=FocusSession.Kind.POMODORO,
            planned_min=25,
            status=FocusSession.Status.RUNNING,
            started_at=tz.now(),
        )
        with pytest.raises(SessionAlreadyRunning):
            start_session(test_user, {"kind": "pomodoro", "planned_min": 25})
