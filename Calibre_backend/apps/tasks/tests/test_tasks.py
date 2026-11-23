from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone as tz
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.models import Category
from apps.tasks.models import Task
from apps.tasks.services import (
    is_overdue,
    is_urgent,
    matrix,
    now_tasks,
    overdue_tasks,
    priority_rank,
    quadrant,
    tasks_due_today,
    today_range,
)

User = get_user_model()


@pytest.mark.django_db
class TestTasksAuth:
    def test_tasks_without_token(self, api_client):
        response = api_client.get("/api/v1/tasks/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestCreateTask:
    def test_create_task_success(self, authenticated_client, test_user):
        response = authenticated_client.post("/api/v1/tasks/", {"title": "Test Task"})
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == "Test Task"
        assert response.data["status"] == "todo"
        assert response.data["source"] == "manual"
        assert "user" not in response.data

        task = Task.objects.get(id=response.data["id"])
        assert task.user == test_user

    def test_create_task_with_user_field_ignored(self, authenticated_client, test_user):
        other_user = User.objects.create_user(
            email="other@example.com", password="TestPass123!"
        )
        response = authenticated_client.post(
            "/api/v1/tasks/", {"title": "Test Task", "user": other_user.id}
        )
        assert response.status_code == status.HTTP_201_CREATED

        task = Task.objects.get(id=response.data["id"])
        assert task.user == test_user

    def test_create_task_with_status_ignored(self, authenticated_client, test_user):
        response = authenticated_client.post(
            "/api/v1/tasks/", {"title": "Test Task", "status": "done"}
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "todo"

    def test_create_task_with_completed_at_ignored(self, authenticated_client, test_user):
        response = authenticated_client.post(
            "/api/v1/tasks/",
            {"title": "Test Task", "completed_at": "2024-01-01T00:00:00Z"},
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["completed_at"] is None


@pytest.mark.django_db
class TestTaskValidation:
    def test_empty_title(self, authenticated_client):
        response = authenticated_client.post("/api/v1/tasks/", {"title": "   "})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "title" in response.data

    def test_title_over_200_characters(self, authenticated_client):
        response = authenticated_client.post(
            "/api/v1/tasks/", {"title": "a" * 201}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "title" in response.data

    def test_estimate_min_zero(self, authenticated_client):
        response = authenticated_client.post(
            "/api/v1/tasks/", {"title": "Test", "estimate_min": 0}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "estimate_min" in response.data

    def test_estimate_min_1441(self, authenticated_client):
        response = authenticated_client.post(
            "/api/v1/tasks/", {"title": "Test", "estimate_min": 1441}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "estimate_min" in response.data

    def test_estimate_min_valid(self, authenticated_client):
        response = authenticated_client.post(
            "/api/v1/tasks/", {"title": "Test", "estimate_min": 60}
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["estimate_min"] == 60

    def test_category_belongs_to_user(self, authenticated_client, test_user):
        other_user = User.objects.create_user(
            email="other@example.com", password="TestPass123!"
        )
        cat = Category.objects.create(user=other_user, name="Other", color="#000000")
        response = authenticated_client.post(
            "/api/v1/tasks/", {"title": "Test", "category": cat.id}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "category" in response.data

    def test_category_own_user(self, authenticated_client, test_user):
        cat = Category.objects.create(user=test_user, name="My Cat", color="#000000")
        response = authenticated_client.post(
            "/api/v1/tasks/", {"title": "Test", "category": cat.id}
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["category"] == cat.id


@pytest.mark.django_db
class TestTaskIsolation:
    def test_list_returns_only_user_tasks(self, api_client):
        user1 = User.objects.create_user(
            email="user1@example.com", password="TestPass123!"
        )
        user2 = User.objects.create_user(
            email="user2@example.com", password="TestPass123!"
        )
        Task.objects.create(user=user1, title="Task1")
        Task.objects.create(user=user2, title="Task2")

        token = api_client.post("/api/v1/auth/login/", {"email": "user1@example.com", "password": "TestPass123!"}).data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = api_client.get("/api/v1/tasks/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["title"] == "Task1"

    def test_other_user_task_returns_404(self, api_client):
        user1 = User.objects.create_user(
            email="user1@example.com", password="TestPass123!"
        )
        user2 = User.objects.create_user(
            email="user2@example.com", password="TestPass123!"
        )
        task = Task.objects.create(user=user1, title="Task1")

        token = api_client.post("/api/v1/auth/login/", {"email": "user2@example.com", "password": "TestPass123!"}).data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = api_client.get(f"/api/v1/tasks/{task.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_other_user_task_patch_404(self, api_client):
        user1 = User.objects.create_user(
            email="user1@example.com", password="TestPass123!"
        )
        user2 = User.objects.create_user(
            email="user2@example.com", password="TestPass123!"
        )
        task = Task.objects.create(user=user1, title="Task1")

        token = api_client.post("/api/v1/auth/login/", {"email": "user2@example.com", "password": "TestPass123!"}).data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = api_client.patch(f"/api/v1/tasks/{task.id}/", {"title": "New"})
        assert response.status_code == status.HTTP_404_NOT_FOUND
        task.refresh_from_db()
        assert task.title == "Task1"

    def test_other_user_task_delete_404(self, api_client):
        user1 = User.objects.create_user(
            email="user1@example.com", password="TestPass123!"
        )
        user2 = User.objects.create_user(
            email="user2@example.com", password="TestPass123!"
        )
        task = Task.objects.create(user=user1, title="Task1")

        token = api_client.post("/api/v1/auth/login/", {"email": "user2@example.com", "password": "TestPass123!"}).data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = api_client.delete(f"/api/v1/tasks/{task.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert Task.objects.filter(id=task.id).exists()


@pytest.mark.django_db
class TestUpdateTask:
    def test_patch_updates_fields(self, authenticated_client, test_user):
        task = Task.objects.create(user=test_user, title="Old Title")
        response = authenticated_client.patch(
            f"/api/v1/tasks/{task.id}/", {"title": "New Title"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == "New Title"

    def test_patch_ignores_status(self, authenticated_client, test_user):
        task = Task.objects.create(user=test_user, title="Task")
        response = authenticated_client.patch(
            f"/api/v1/tasks/{task.id}/", {"status": "done"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "todo"


@pytest.mark.django_db
class TestDeleteTask:
    def test_delete_success(self, authenticated_client, test_user):
        task = Task.objects.create(user=test_user, title="To Delete")
        response = authenticated_client.delete(f"/api/v1/tasks/{task.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Task.objects.filter(id=task.id).exists()


@pytest.mark.django_db
class TestDeleteCategory:
    def test_delete_category_sets_task_category_null(self, authenticated_client, test_user):
        cat = Category.objects.create(user=test_user, name="Cat", color="#000000")
        task = Task.objects.create(user=test_user, title="Task", category=cat)
        response = authenticated_client.delete(f"/api/v1/categories/{cat.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        task.refresh_from_db()
        assert task.category is None
        assert Task.objects.filter(id=task.id).exists()


@pytest.mark.django_db
class TestTaskFilters:
    def test_filter_status(self, authenticated_client, test_user):
        Task.objects.create(user=test_user, title="Task1", status=Task.Status.TODO)
        Task.objects.create(user=test_user, title="Task2", status=Task.Status.DONE)
        response = authenticated_client.get("/api/v1/tasks/?status=todo")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["status"] == "todo"

    def test_filter_invalid_status(self, authenticated_client, test_user):
        response = authenticated_client.get("/api/v1/tasks/?status=invalid")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_filter_category(self, authenticated_client, test_user):
        cat1 = Category.objects.create(user=test_user, name="Cat1", color="#000000")
        cat2 = Category.objects.create(user=test_user, name="Cat2", color="#000000")
        Task.objects.create(user=test_user, title="Task1", category=cat1)
        Task.objects.create(user=test_user, title="Task2", category=cat2)
        response = authenticated_client.get(f"/api/v1/tasks/?category={cat1.id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_filter_important(self, authenticated_client, test_user):
        Task.objects.create(user=test_user, title="Task1", is_important=True)
        Task.objects.create(user=test_user, title="Task2", is_important=False)
        response = authenticated_client.get("/api/v1/tasks/?important=true")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_filter_source(self, authenticated_client, test_user):
        Task.objects.create(user=test_user, title="Task1", source=Task.Source.MANUAL)
        Task.objects.create(user=test_user, title="Task2", source=Task.Source.MOODLE)
        response = authenticated_client.get("/api/v1/tasks/?source=manual")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_filter_due_before(self, authenticated_client, test_user):
        from datetime import datetime
        now = datetime.now(tz.UTC)
        Task.objects.create(user=test_user, title="Task1", due_at=now - timedelta(days=1))
        Task.objects.create(user=test_user, title="Task2", due_at=now + timedelta(days=1))
        # Use ISO format with Z for UTC
        iso_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        response = authenticated_client.get(f"/api/v1/tasks/?due_before={iso_time}")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_filter_due_after(self, authenticated_client, test_user):
        from datetime import datetime
        now = datetime.now(tz.UTC)
        Task.objects.create(user=test_user, title="Task1", due_at=now - timedelta(days=1))
        Task.objects.create(user=test_user, title="Task2", due_at=now + timedelta(days=1))
        # Use ISO format with Z for UTC
        iso_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        response = authenticated_client.get(f"/api/v1/tasks/?due_after={iso_time}")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_filter_invalid_datetime(self, authenticated_client, test_user):
        response = authenticated_client.get("/api/v1/tasks/?due_before=invalid")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_ordering_due_at_desc(self, authenticated_client, test_user):
        now = tz.now()
        Task.objects.create(user=test_user, title="Task1", due_at=now - timedelta(days=1))
        Task.objects.create(user=test_user, title="Task2", due_at=now + timedelta(days=1))
        response = authenticated_client.get("/api/v1/tasks/?ordering=-due_at")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"][0]["title"] == "Task2"


@pytest.mark.django_db
class TestStateChanges:
    def test_complete_sets_status_and_completed_at(self, authenticated_client, test_user):
        task = Task.objects.create(user=test_user, title="Task")
        response = authenticated_client.post(f"/api/v1/tasks/{task.id}/complete/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "done"
        assert response.data["completed_at"] is not None
        task.refresh_from_db()
        assert task.status == Task.Status.DONE
        assert task.completed_at is not None

    def test_complete_idempotent(self, authenticated_client, test_user):
        now = tz.now()
        task = Task.objects.create(
            user=test_user, title="Task", status=Task.Status.DONE, completed_at=now
        )
        authenticated_client.post(f"/api/v1/tasks/{task.id}/complete/")
        task.refresh_from_db()
        assert task.completed_at == now

    def test_reopen_clears_status_and_completed_at(self, authenticated_client, test_user):
        task = Task.objects.create(
            user=test_user, title="Task", status=Task.Status.DONE, completed_at=tz.now()
        )
        response = authenticated_client.post(f"/api/v1/tasks/{task.id}/reopen/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "todo"
        assert response.data["completed_at"] is None
        task.refresh_from_db()
        assert task.status == Task.Status.TODO
        assert task.completed_at is None

    def test_reopen_idempotent(self, authenticated_client, test_user):
        task = Task.objects.create(user=test_user, title="Task", status=Task.Status.TODO)
        authenticated_client.post(f"/api/v1/tasks/{task.id}/reopen/")
        task.refresh_from_db()
        assert task.status == Task.Status.TODO


@pytest.mark.django_db
class TestServiceLogic:
    def test_is_overdue_todo_past_due(self):
        user = User.objects.create_user(email="test@example.com", password="TestPass123!")
        now = tz.now()
        task = Task.objects.create(
            user=user, title="Task", status=Task.Status.TODO, due_at=now - timedelta(hours=1)
        )
        assert is_overdue(task, now) is True

    def test_is_overdue_todo_future_due(self):
        user = User.objects.create_user(email="test@example.com", password="TestPass123!")
        now = tz.now()
        task = Task.objects.create(
            user=user, title="Task", status=Task.Status.TODO, due_at=now + timedelta(hours=1)
        )
        assert is_overdue(task, now) is False

    def test_is_overdue_done_task(self):
        user = User.objects.create_user(email="test@example.com", password="TestPass123!")
        now = tz.now()
        task = Task.objects.create(
            user=user, title="Task", status=Task.Status.DONE, due_at=now - timedelta(hours=1)
        )
        assert is_overdue(task, now) is False

    def test_is_overdue_no_due_date(self):
        user = User.objects.create_user(email="test@example.com", password="TestPass123!")
        now = tz.now()
        task = Task.objects.create(user=user, title="Task", status=Task.Status.TODO, due_at=None)
        assert is_overdue(task, now) is False

    def test_is_urgent_within_48h(self):
        user = User.objects.create_user(email="test@example.com", password="TestPass123!")
        now = tz.now()
        task = Task.objects.create(
            user=user, title="Task", status=Task.Status.TODO, due_at=now + timedelta(hours=47)
        )
        assert is_urgent(task, now) is True

    def test_is_urgent_exactly_48h(self):
        user = User.objects.create_user(email="test@example.com", password="TestPass123!")
        now = tz.now()
        task = Task.objects.create(
            user=user, title="Task", status=Task.Status.TODO, due_at=now + timedelta(hours=48)
        )
        assert is_urgent(task, now) is True

    def test_is_urgent_overdue(self):
        user = User.objects.create_user(email="test@example.com", password="TestPass123!")
        now = tz.now()
        task = Task.objects.create(
            user=user, title="Task", status=Task.Status.TODO, due_at=now - timedelta(hours=1)
        )
        assert is_urgent(task, now) is True

    def test_is_urgent_no_due_date(self):
        user = User.objects.create_user(email="test@example.com", password="TestPass123!")
        now = tz.now()
        task = Task.objects.create(user=user, title="Task", status=Task.Status.TODO, due_at=None)
        assert is_urgent(task, now) is False

    def test_today_range_asia_kolkata(self):
        user = User.objects.create_user(
            email="test@example.com", password="TestPass123!", timezone="Asia/Kolkata"
        )
        from datetime import datetime
        now = datetime(2024, 1, 15, 18, 30, 0, tzinfo=tz.UTC)
        start, end = today_range(user, now)
        local_start = start.astimezone(ZoneInfo("Asia/Kolkata"))
        local_end = end.astimezone(ZoneInfo("Asia/Kolkata"))
        assert local_start.hour == 0
        assert local_start.day == 16  # 18:30 UTC is 00:00 next day in IST
        assert local_end.hour == 0
        assert local_end.day == 17

    def test_tasks_due_today_includes_boundary(self):
        user = User.objects.create_user(
            email="test@example.com", password="TestPass123!", timezone="Asia/Kolkata"
        )
        from datetime import datetime
        now = datetime(2024, 1, 15, 18, 30, 0, tzinfo=tz.UTC)
        # now = 00:00 on Jan 16 in IST
        # task at 12:00 IST on Jan 16 = 06:30 UTC on Jan 16
        task_due_1200_ist = datetime(2024, 1, 16, 6, 30, 0, tzinfo=tz.UTC)
        # task at 23:30 IST on Jan 15 = 18:00 UTC on Jan 15 (should not be included)
        task_due_2330_yesterday_ist = datetime(2024, 1, 15, 18, 0, 0, tzinfo=tz.UTC)
        # task at 00:30 IST on Jan 17 = 19:00 UTC on Jan 16 (should not be included)
        task_due_0030_tomorrow_ist = datetime(2024, 1, 16, 19, 0, 0, tzinfo=tz.UTC)
        Task.objects.create(user=user, title="TaskToday", due_at=task_due_1200_ist)
        Task.objects.create(user=user, title="TaskYesterday", due_at=task_due_2330_yesterday_ist)
        Task.objects.create(user=user, title="TaskTomorrow", due_at=task_due_0030_tomorrow_ist)
        tasks = tasks_due_today(user, now)
        assert len(tasks) == 1
        assert tasks[0].title == "TaskToday"

    def test_tasks_due_today_utc_tomorrow_ist_today(self):
        user = User.objects.create_user(
            email="test@example.com", password="TestPass123!", timezone="Asia/Kolkata"
        )
        from datetime import datetime
        now = datetime(2024, 1, 15, 18, 30, 0, tzinfo=tz.UTC)
        task_utc_tomorrow_ist_today = datetime(2024, 1, 15, 20, 0, 0, tzinfo=tz.UTC)
        Task.objects.create(user=user, title="Task", due_at=task_utc_tomorrow_ist_today)
        tasks = tasks_due_today(user, now)
        assert len(tasks) == 1

    def test_overdue_tasks_excludes_done_and_future(self):
        user = User.objects.create_user(email="test@example.com", password="TestPass123!")
        now = tz.now()
        Task.objects.create(
            user=user, title="Overdue", status=Task.Status.TODO, due_at=now - timedelta(hours=1)
        )
        Task.objects.create(
            user=user, title="Done", status=Task.Status.DONE, due_at=now - timedelta(hours=1)
        )
        Task.objects.create(
            user=user, title="Future", status=Task.Status.TODO, due_at=now + timedelta(hours=1)
        )
        tasks = overdue_tasks(user, now)
        assert len(tasks) == 1
        assert tasks[0].title == "Overdue"

    def test_priority_rank_levels(self):
        user = User.objects.create_user(email="test@example.com", password="TestPass123!")
        now = tz.now()
        overdue = Task.objects.create(
            user=user, title="Overdue", status=Task.Status.TODO, due_at=now - timedelta(hours=1)
        )
        important_urgent = Task.objects.create(
            user=user,
            title="IU",
            status=Task.Status.TODO,
            due_at=now + timedelta(hours=1),
            is_important=True,
        )
        urgent_only = Task.objects.create(
            user=user, title="U", status=Task.Status.TODO, due_at=now + timedelta(hours=1)
        )
        important_only = Task.objects.create(
            user=user, title="I", status=Task.Status.TODO, is_important=True
        )
        other = Task.objects.create(user=user, title="Other", status=Task.Status.TODO)
        assert priority_rank(overdue, now) == 0
        assert priority_rank(important_urgent, now) == 1
        assert priority_rank(urgent_only, now) == 2
        assert priority_rank(important_only, now) == 3
        assert priority_rank(other, now) == 4

    def test_now_tasks_respects_limit(self):
        user = User.objects.create_user(email="test@example.com", password="TestPass123!")
        for i in range(20):
            Task.objects.create(user=user, title=f"Task{i}")
        tasks = now_tasks(user, 5)
        assert len(tasks) == 5

    def test_now_tasks_capped_at_50(self):
        user = User.objects.create_user(email="test@example.com", password="TestPass123!")
        for i in range(100):
            Task.objects.create(user=user, title=f"Task{i}")
        tasks = now_tasks(user, 100)
        assert len(tasks) == 50

    def test_matrix_quadrants(self):
        user = User.objects.create_user(email="test@example.com", password="TestPass123!")
        now = tz.now()
        Task.objects.create(
            user=user,
            title="Do First",
            status=Task.Status.TODO,
            due_at=now + timedelta(hours=1),
            is_important=True,
        )
        Task.objects.create(
            user=user, title="Schedule", status=Task.Status.TODO, is_important=True
        )
        Task.objects.create(
            user=user, title="Delegate", status=Task.Status.TODO, due_at=now + timedelta(hours=1)
        )
        Task.objects.create(user=user, title="Eliminate", status=Task.Status.TODO)
        Task.objects.create(
            user=user, title="Done", status=Task.Status.DONE, is_important=True
        )
        grouped = matrix(user, now)
        assert len(grouped["do_first"]) == 1
        assert len(grouped["schedule"]) == 1
        assert len(grouped["delegate"]) == 1
        assert len(grouped["eliminate"]) == 1
        assert grouped["do_first"][0].title == "Do First"

    def test_matrix_no_due_date_not_urgent(self):
        user = User.objects.create_user(email="test@example.com", password="TestPass123!")
        now = tz.now()
        Task.objects.create(
            user=user, title="Important No Due", status=Task.Status.TODO, is_important=True
        )
        grouped = matrix(user, now)
        assert len(grouped["schedule"]) == 1
        assert len(grouped["do_first"]) == 0


@pytest.mark.django_db
class TestTaskEndpoints:
    def test_today_returns_plain_array(self, authenticated_client, test_user):
        Task.objects.create(user=test_user, title="Task")
        response = authenticated_client.get("/api/v1/tasks/today/")
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)
        assert "count" not in response.data

    def test_today_not_404(self, authenticated_client, test_user):
        response = authenticated_client.get("/api/v1/tasks/today/")
        assert response.status_code == status.HTTP_200_OK

    def test_overdue_paginated(self, authenticated_client, test_user):
        now = tz.now()
        for i in range(25):
            Task.objects.create(
                user=test_user, title=f"Task{i}", due_at=now - timedelta(days=1)
            )
        response = authenticated_client.get("/api/v1/tasks/overdue/")
        assert response.status_code == status.HTTP_200_OK
        assert "count" in response.data
        assert "results" in response.data

    def test_now_default_limit(self, authenticated_client, test_user):
        for i in range(20):
            Task.objects.create(user=test_user, title=f"Task{i}")
        response = authenticated_client.get("/api/v1/tasks/now/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 10

    def test_now_custom_limit(self, authenticated_client, test_user):
        for i in range(20):
            Task.objects.create(user=test_user, title=f"Task{i}")
        response = authenticated_client.get("/api/v1/tasks/now/?limit=5")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 5

    def test_now_invalid_limit(self, authenticated_client, test_user):
        response = authenticated_client.get("/api/v1/tasks/now/?limit=invalid")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_matrix_returns_object(self, authenticated_client, test_user):
        response = authenticated_client.get("/api/v1/tasks/matrix/")
        assert response.status_code == status.HTTP_200_OK
        assert "do_first" in response.data
        assert "schedule" in response.data
        assert "delegate" in response.data
        assert "eliminate" in response.data


@pytest.mark.django_db
class TestUniqueConstraint:
    def test_duplicate_external_id_fails(self):
        user = User.objects.create_user(email="test@example.com", password="TestPass123!")
        Task.objects.create(
            user=user,
            title="Task1",
            source=Task.Source.MOODLE,
            external_id="123",
        )
        with pytest.raises(Exception):
            Task.objects.create(
                user=user,
                title="Task2",
                source=Task.Source.MOODLE,
                external_id="123",
            )

    def test_empty_external_id_allowed_duplicates(self):
        user = User.objects.create_user(email="test@example.com", password="TestPass123!")
        Task.objects.create(
            user=user,
            title="Task1",
            source=Task.Source.MANUAL,
            external_id="",
        )
        Task.objects.create(
            user=user,
            title="Task2",
            source=Task.Source.MANUAL,
            external_id="",
        )
        assert Task.objects.filter(user=user).count() == 2
