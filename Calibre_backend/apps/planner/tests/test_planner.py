import pytest
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.models import Category
from apps.common.timeutils import local_day_window, local_today, local_to_utc
from apps.planner.models import Event, Routine, RoutineCheckin
from apps.planner.services import (
    agenda,
    busy_intervals,
    free_slots,
    merge_intervals,
    record_checkin,
    remove_checkin,
    routine_occurs_on,
    routine_occurrences,
    suggest_tasks,
)
from apps.tasks.models import Task

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
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


# ---------------------------------------------------------------------------
# 1. Auth tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPlannerAuth:
    def test_planner_endpoints_require_auth(self, api_client):
        """All planner endpoints return 401 without a token."""
        response = api_client.get("/api/v1/events/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        response = api_client.get("/api/v1/routines/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        response = api_client.get(
            "/api/v1/calendar/agenda/?start_date=2026-11-02&end_date=2026-11-02"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        response = api_client.get("/api/v1/free-slots/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# 2. Events tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestEvents:
    def test_create_event_success_and_ignored_fields(self, authenticated_client, user):
        """
        Create with title, start_at, end_at -> 201, correct owner, kind='event', source='manual';
        a user or source key in the body is ignored.
        """
        response = authenticated_client.post(
            "/api/v1/events/",
            {
                "title": "  Team Meeting  ",
                "start_at": "2026-11-02T10:00:00Z",
                "end_at": "2026-11-02T11:00:00Z",
                "user": 9999,
                "source": "moodle",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED, response.data
        assert response.data["title"] == "Team Meeting"  # stripped
        assert response.data["kind"] == "event"
        assert response.data["source"] == "manual"  # 'moodle' in payload was ignored
        assert "user" not in response.data

        event = Event.objects.get(id=response.data["id"])
        assert event.user == user
        assert event.source == Event.Source.MANUAL

    def test_event_duration_validation(self, authenticated_client):
        """end_at < start_at -> 400; end_at == start_at -> 201."""
        # end_at < start_at -> 400
        res_invalid = authenticated_client.post(
            "/api/v1/events/",
            {
                "title": "Invalid Event",
                "start_at": "2026-11-02T11:00:00Z",
                "end_at": "2026-11-02T10:00:00Z",
            },
        )
        assert res_invalid.status_code == status.HTTP_400_BAD_REQUEST
        assert "end_at" in res_invalid.data

        # end_at == start_at -> 201 (zero length allowed)
        res_zero = authenticated_client.post(
            "/api/v1/events/",
            {
                "title": "Instant Event",
                "start_at": "2026-11-02T10:00:00Z",
                "end_at": "2026-11-02T10:00:00Z",
            },
        )
        assert res_zero.status_code == status.HTTP_201_CREATED

    def test_event_category_and_task_ownership(self, authenticated_client, user):
        """Another user's category or task -> 400; your own -> 201."""
        other_user = User.objects.create_user(
            email="other@example.com", password="TestPass123!", timezone="Asia/Kolkata"
        )
        other_cat = Category.objects.create(user=other_user, name="Other Cat")
        other_task = Task.objects.create(user=other_user, title="Other Task")

        own_cat = Category.objects.create(user=user, name="Own Cat")
        own_task = Task.objects.create(user=user, title="Own Task")

        # Other user's category -> 400
        res_cat = authenticated_client.post(
            "/api/v1/events/",
            {
                "title": "Meeting",
                "start_at": "2026-11-02T10:00:00Z",
                "end_at": "2026-11-02T11:00:00Z",
                "category": other_cat.id,
            },
        )
        assert res_cat.status_code == status.HTTP_400_BAD_REQUEST
        assert "category" in res_cat.data

        # Other user's task -> 400
        res_task = authenticated_client.post(
            "/api/v1/events/",
            {
                "title": "Block",
                "kind": "block",
                "start_at": "2026-11-02T10:00:00Z",
                "end_at": "2026-11-02T11:00:00Z",
                "task": other_task.id,
            },
        )
        assert res_task.status_code == status.HTTP_400_BAD_REQUEST
        assert "task" in res_task.data

        # Own category and own task -> 201
        res_own = authenticated_client.post(
            "/api/v1/events/",
            {
                "title": "Own Block",
                "kind": "block",
                "start_at": "2026-11-02T10:00:00Z",
                "end_at": "2026-11-02T11:00:00Z",
                "category": own_cat.id,
                "task": own_task.id,
            },
        )
        assert res_own.status_code == status.HTTP_201_CREATED

    def test_event_isolation(self, api_client):
        """List isolation between two users; another user's event returns 404 on GET, PATCH, DELETE."""
        user1 = User.objects.create_user(
            email="user1@example.com", password="TestPass123!", timezone="Asia/Kolkata"
        )
        user2 = User.objects.create_user(
            email="user2@example.com", password="TestPass123!", timezone="Asia/Kolkata"
        )
        event1 = Event.objects.create(
            user=user1,
            title="User 1 Event",
            start_at="2026-11-02T10:00:00Z",
            end_at="2026-11-02T11:00:00Z",
        )

        token2 = api_client.post(
            "/api/v1/auth/login/",
            {"email": "user2@example.com", "password": "TestPass123!"},
        ).data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token2}")

        # List should not contain user1's event
        res_list = api_client.get("/api/v1/events/")
        assert res_list.status_code == status.HTTP_200_OK
        assert len(res_list.data["results"]) == 0

        # Detail GET -> 404
        assert api_client.get(f"/api/v1/events/{event1.id}/").status_code == status.HTTP_404_NOT_FOUND
        # PATCH -> 404
        assert (
            api_client.patch(
                f"/api/v1/events/{event1.id}/", {"title": "Hacked"}
            ).status_code
            == status.HTTP_404_NOT_FOUND
        )
        # DELETE -> 404
        assert (
            api_client.delete(f"/api/v1/events/{event1.id}/").status_code
            == status.HTTP_404_NOT_FOUND
        )

    def test_event_filter_date_range_and_attributes(self, authenticated_client, user):
        """
        start_date/end_date filter returns events that overlap the window, including one
        that starts the previous evening and ends inside it, and excludes one that ends exactly
        at the window start; invalid date -> 400. kind, category, source filters work.
        """
        # Asia/Kolkata local day 2026-11-02 window in UTC:
        # 2026-11-01 18:30:00 UTC to 2026-11-02 18:30:00 UTC
        cat = Category.objects.create(user=user, name="Lab")

        # 1. Event ends exactly at window start: 17:30 to 18:30 UTC Nov 1 (excluded, since end_at is not > 18:30)
        Event.objects.create(
            user=user,
            title="Ends Exactly At Start",
            start_at="2026-11-01T17:30:00Z",
            end_at="2026-11-01T18:30:00Z",
        )
        # 2. Event starts previous evening and ends inside: 18:00 to 19:30 UTC Nov 1 (included)
        Event.objects.create(
            user=user,
            title="Overlaps Start Boundary",
            start_at="2026-11-01T18:00:00Z",
            end_at="2026-11-01T19:30:00Z",
            kind="event",
            category=cat,
            source="manual",
        )
        # 3. Inside event: block kind
        Event.objects.create(
            user=user,
            title="Inside Block",
            start_at="2026-11-02T10:00:00Z",
            end_at="2026-11-02T11:00:00Z",
            kind="block",
            source="moodle",
        )

        # Query for 2026-11-02
        res = authenticated_client.get(
            "/api/v1/events/?start_date=2026-11-02&end_date=2026-11-02"
        )
        assert res.status_code == status.HTTP_200_OK
        titles = [e["title"] for e in res.data["results"]]
        assert "Overlaps Start Boundary" in titles
        assert "Inside Block" in titles
        assert "Ends Exactly At Start" not in titles

        # Invalid date -> 400
        res_bad = authenticated_client.get("/api/v1/events/?start_date=not-a-date")
        assert res_bad.status_code == status.HTTP_400_BAD_REQUEST

        # Kind filter
        res_kind = authenticated_client.get("/api/v1/events/?kind=block")
        assert res_kind.status_code == status.HTTP_200_OK
        assert len(res_kind.data["results"]) == 1
        assert res_kind.data["results"][0]["title"] == "Inside Block"

        # Category filter
        res_cat = authenticated_client.get(f"/api/v1/events/?category={cat.id}")
        assert res_cat.status_code == status.HTTP_200_OK
        assert len(res_cat.data["results"]) == 1
        assert res_cat.data["results"][0]["title"] == "Overlaps Start Boundary"

        # Source filter
        res_source = authenticated_client.get("/api/v1/events/?source=moodle")
        assert res_source.status_code == status.HTTP_200_OK
        assert len(res_source.data["results"]) == 1
        assert res_source.data["results"][0]["title"] == "Inside Block"

    def test_delete_task_or_category_sets_null(self, user):
        """Deleting a task or a category sets the event's reference to null and the event survives."""
        cat = Category.objects.create(user=user, name="Temp")
        task = Task.objects.create(user=user, title="Temp Task")
        event = Event.objects.create(
            user=user,
            title="Surviving Event",
            category=cat,
            task=task,
            start_at="2026-11-02T10:00:00Z",
            end_at="2026-11-02T11:00:00Z",
        )

        cat.delete()
        task.delete()

        event.refresh_from_db()
        assert event.category is None
        assert event.task is None
        assert event.title == "Surviving Event"

    def test_event_unique_external_id_constraint(self, user):
        """
        Two events with the same (user, source, external_id) fail at the DB level;
        two manual events with empty external_id are fine.
        """
        # Duplicate with non-empty external_id -> IntegrityError
        Event.objects.create(
            user=user,
            title="Moodle Event 1",
            source=Event.Source.MOODLE,
            external_id="moodle-123",
            start_at="2026-11-02T10:00:00Z",
            end_at="2026-11-02T11:00:00Z",
        )
        from django.db import transaction
        with transaction.atomic(), pytest.raises(IntegrityError):
            Event.objects.create(
                user=user,
                title="Moodle Event 2",
                source=Event.Source.MOODLE,
                external_id="moodle-123",
                start_at="2026-11-02T10:00:00Z",
                end_at="2026-11-02T11:00:00Z",
            )

        # Two manual events with empty external_id are fine
        e1 = Event.objects.create(
            user=user,
            title="Manual 1",
            source=Event.Source.MANUAL,
            external_id="",
            start_at="2026-11-02T10:00:00Z",
            end_at="2026-11-02T11:00:00Z",
        )
        e2 = Event.objects.create(
            user=user,
            title="Manual 2",
            source=Event.Source.MANUAL,
            external_id="",
            start_at="2026-11-02T10:00:00Z",
            end_at="2026-11-02T11:00:00Z",
        )
        assert e1.id != e2.id


# ---------------------------------------------------------------------------
# 3. Routines and check-ins tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRoutines:
    def test_create_routine_defaults_and_validation(self, authenticated_client, user):
        """
        Create a routine; start_date defaults to the user's local today;
        invalid weekdays (empty, duplicates, 7, strings), end_time <= start_time,
        and end_date < start_date -> 400.
        """
        # Successful create without start_date -> defaults to local today
        res_ok = authenticated_client.post(
            "/api/v1/routines/",
            {
                "title": "Morning Run",
                "weekdays": [0, 2, 4],
                "start_time": "06:00:00",
                "end_time": "07:00:00",
            },
            format="json",
        )
        assert res_ok.status_code == status.HTTP_201_CREATED, res_ok.data
        expected_today = local_today(user.timezone).isoformat()
        assert res_ok.data["start_date"] == expected_today

        # Empty weekdays -> 400
        res_empty = authenticated_client.post(
            "/api/v1/routines/",
            {
                "title": "Gym",
                "weekdays": [],
                "start_time": "06:00:00",
                "end_time": "07:00:00",
            },
            format="json",
        )
        assert res_empty.status_code == status.HTTP_400_BAD_REQUEST

        # Duplicate weekdays -> 400
        res_dup = authenticated_client.post(
            "/api/v1/routines/",
            {
                "title": "Gym",
                "weekdays": [1, 1],
                "start_time": "06:00:00",
                "end_time": "07:00:00",
            },
            format="json",
        )
        assert res_dup.status_code == status.HTTP_400_BAD_REQUEST

        # Weekday 7 out of range -> 400
        res_7 = authenticated_client.post(
            "/api/v1/routines/",
            {
                "title": "Gym",
                "weekdays": [7],
                "start_time": "06:00:00",
                "end_time": "07:00:00",
            },
            format="json",
        )
        assert res_7.status_code == status.HTTP_400_BAD_REQUEST

        # Weekdays strings -> 400
        res_str = authenticated_client.post(
            "/api/v1/routines/",
            {
                "title": "Gym",
                "weekdays": ["Monday"],
                "start_time": "06:00:00",
                "end_time": "07:00:00",
            },
            format="json",
        )
        assert res_str.status_code == status.HTTP_400_BAD_REQUEST

        # end_time <= start_time -> 400
        res_time = authenticated_client.post(
            "/api/v1/routines/",
            {
                "title": "Gym",
                "weekdays": [0],
                "start_time": "07:00:00",
                "end_time": "06:00:00",
            },
            format="json",
        )
        assert res_time.status_code == status.HTTP_400_BAD_REQUEST

        # end_date < start_date -> 400
        res_date = authenticated_client.post(
            "/api/v1/routines/",
            {
                "title": "Gym",
                "weekdays": [0],
                "start_time": "06:00:00",
                "end_time": "07:00:00",
                "start_date": "2026-11-10",
                "end_date": "2026-11-05",
            },
            format="json",
        )
        assert res_date.status_code == status.HTTP_400_BAD_REQUEST

    def test_routine_occurs_on(self, user):
        """routine_occurs_on: weekday match, before start_date, after end_date, inactive."""
        routine = Routine.objects.create(
            user=user,
            title="Study",
            weekdays=[0, 2],  # Mon, Wed
            start_time=time(18, 0),
            end_time=time(19, 0),
            start_date=date(2026, 11, 2),  # Monday
            end_date=date(2026, 11, 16),
            is_active=True,
        )

        # 1. Matching Monday within range -> True
        assert routine_occurs_on(routine, date(2026, 11, 2)) is True
        # 2. Weekday mismatch (Tuesday 2026-11-03) -> False
        assert routine_occurs_on(routine, date(2026, 11, 3)) is False
        # 3. Before start_date (Monday 2026-10-26) -> False
        assert routine_occurs_on(routine, date(2026, 10, 26)) is False
        # 4. After end_date (Monday 2026-11-23) -> False
        assert routine_occurs_on(routine, date(2026, 11, 23)) is False
        # 5. Inactive routine -> False
        routine.is_active = False
        routine.save()
        assert routine_occurs_on(routine, date(2026, 11, 2)) is False

    def test_routine_occurrences_utc_conversion_and_fixed_queries(
        self, user, django_assert_num_queries
    ):
        """
        routine_occurrences converts local wall-clock times to the correct UTC instants
        (e.g. 18:00 IST is 12:30 UTC) and reports the right status per day.
        Assert a small, fixed number of DB queries regardless of how many routines exist.
        """
        # Create 5 routines
        for i in range(5):
            Routine.objects.create(
                user=user,
                title=f"Routine {i}",
                weekdays=[0],  # Monday
                start_time=time(18, 0),
                end_time=time(19, 0),
                start_date=date(2026, 11, 2),
            )

        # 2 queries: 1 for routines, 1 for prefetched checkins
        with django_assert_num_queries(2):
            occs = routine_occurrences(user, date(2026, 11, 2), date(2026, 11, 2))

        assert len(occs) == 5
        # 18:00 IST is 12:30 UTC
        utc_zone = ZoneInfo("UTC")
        assert occs[0]["start_at"] == datetime(2026, 11, 2, 12, 30, tzinfo=utc_zone)
        assert occs[0]["end_at"] == datetime(2026, 11, 2, 13, 30, tzinfo=utc_zone)
        assert occs[0]["status"] == "pending"

    def test_routine_checkin_lifecycle(self, authenticated_client, user, api_client):
        """
        Check-in: POST creates (201), POST again updates (200) without a duplicate row;
        a date that is not a scheduled day -> 400; done=false makes the status skipped;
        DELETE returns the status to pending and is idempotent; another user's routine returns 404.
        """
        routine = Routine.objects.create(
            user=user,
            title="Gym",
            weekdays=[0],  # Monday only
            start_time=time(18, 0),
            end_time=time(19, 0),
            start_date=date(2026, 11, 2),
        )

        # 1. POST creates (201)
        res_create = authenticated_client.post(
            f"/api/v1/routines/{routine.id}/checkin/",
            {"date": "2026-11-02", "done": True},
            format="json",
        )
        assert res_create.status_code == status.HTTP_201_CREATED
        assert res_create.data["done"] is True
        assert RoutineCheckin.objects.filter(routine=routine).count() == 1

        # 2. POST again updates (200) with done=False -> status skipped
        res_update = authenticated_client.post(
            f"/api/v1/routines/{routine.id}/checkin/",
            {"date": "2026-11-02", "done": False},
            format="json",
        )
        assert res_update.status_code == status.HTTP_200_OK
        assert res_update.data["done"] is False
        assert RoutineCheckin.objects.filter(routine=routine).count() == 1

        occs_skipped = routine_occurrences(user, date(2026, 11, 2), date(2026, 11, 2))
        assert occs_skipped[0]["status"] == "skipped"

        # 3. Not a scheduled day -> 400
        res_bad_day = authenticated_client.post(
            f"/api/v1/routines/{routine.id}/checkin/",
            {"date": "2026-11-03", "done": True},  # Tuesday
            format="json",
        )
        assert res_bad_day.status_code == status.HTTP_400_BAD_REQUEST

        # 4. DELETE returns status to pending and is idempotent
        res_del = authenticated_client.delete(
            f"/api/v1/routines/{routine.id}/checkin/?date=2026-11-02"
        )
        assert res_del.status_code == status.HTTP_204_NO_CONTENT
        occs_pending = routine_occurrences(user, date(2026, 11, 2), date(2026, 11, 2))
        assert occs_pending[0]["status"] == "pending"

        # Idempotent DELETE when row does not exist -> 204
        res_del_again = authenticated_client.delete(
            f"/api/v1/routines/{routine.id}/checkin/?date=2026-11-02"
        )
        assert res_del_again.status_code == status.HTTP_204_NO_CONTENT

        # 5. Another user's routine returns 404
        user2 = User.objects.create_user(
            email="user2@example.com", password="TestPass123!", timezone="Asia/Kolkata"
        )
        token2 = api_client.post(
            "/api/v1/auth/login/",
            {"email": "user2@example.com", "password": "TestPass123!"},
        ).data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token2}")

        res_other = api_client.post(
            f"/api/v1/routines/{routine.id}/checkin/",
            {"date": "2026-11-02", "done": True},
            format="json",
        )
        assert res_other.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_routine_deletes_checkins(self, user):
        """Deleting a routine cascades to its check-ins."""
        routine = Routine.objects.create(
            user=user,
            title="Habit",
            weekdays=[0],
            start_time=time(7, 0),
            end_time=time(8, 0),
            start_date=date(2026, 11, 2),
        )
        RoutineCheckin.objects.create(
            user=user, routine=routine, date=date(2026, 11, 2), done=True
        )

        routine_id = routine.id
        routine.delete()
        assert not RoutineCheckin.objects.filter(routine_id=routine_id).exists()


# ---------------------------------------------------------------------------
# 4. Agenda tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAgenda:
    def test_agenda_query_validation(self, authenticated_client):
        """Missing start_date or end_date, end_date < start_date, and span over 62 days -> 400."""
        # Missing params -> 400
        assert (
            authenticated_client.get("/api/v1/calendar/agenda/").status_code
            == status.HTTP_400_BAD_REQUEST
        )

        # end_date < start_date -> 400
        assert (
            authenticated_client.get(
                "/api/v1/calendar/agenda/?start_date=2026-11-05&end_date=2026-11-02"
            ).status_code
            == status.HTTP_400_BAD_REQUEST
        )

        # Span > 62 days -> 400 (70 days)
        assert (
            authenticated_client.get(
                "/api/v1/calendar/agenda/?start_date=2026-11-01&end_date=2027-01-10"
            ).status_code
            == status.HTTP_400_BAD_REQUEST
        )

    def test_agenda_merges_all_types_and_isolates(self, authenticated_client, user):
        """
        Contains all three item types, sorted correctly; a task due in the window appears
        with its status; items outside the window and other users' items are absent.
        """
        other_user = User.objects.create_user(
            email="other@example.com", password="TestPass123!", timezone="Asia/Kolkata"
        )
        # Other user's event
        Event.objects.create(
            user=other_user,
            title="Other Event",
            start_at="2026-11-02T10:00:00Z",
            end_at="2026-11-02T11:00:00Z",
        )

        # Event outside window
        Event.objects.create(
            user=user,
            title="Future Event",
            start_at="2026-11-10T10:00:00Z",
            end_at="2026-11-10T11:00:00Z",
        )

        # Target items inside 2026-11-02
        Event.objects.create(
            user=user,
            title="Lab Event",
            start_at="2026-11-02T10:00:00Z",
            end_at="2026-11-02T11:00:00Z",
        )
        routine = Routine.objects.create(
            user=user,
            title="Gym",
            weekdays=[0],  # Monday
            start_time=time(18, 0),
            end_time=time(19, 0),
            start_date=date(2026, 11, 2),
        )
        # Checkin for routine
        RoutineCheckin.objects.create(
            user=user, routine=routine, date=date(2026, 11, 2), done=True
        )

        task = Task.objects.create(
            user=user,
            title="Submit Report",
            due_at="2026-11-02T10:00:00Z",
            status=Task.Status.DONE,
        )

        response = authenticated_client.get(
            "/api/v1/calendar/agenda/?start_date=2026-11-02&end_date=2026-11-02"
        )
        assert response.status_code == status.HTTP_200_OK
        items = response.data["items"]
        assert len(items) == 3

        types = [item["type"] for item in items]
        assert "event" in types
        assert "routine" in types
        assert "task" in types

        # Check routine status was resolved to done
        routine_item = next(i for i in items if i["type"] == "routine")
        assert routine_item["status"] == "done"

        # Check task appears with its status
        task_item = next(i for i in items if i["type"] == "task")
        assert task_item["status"] == Task.Status.DONE
        assert task_item["id"] == task.id

        # Other user's item and outside event absent
        titles = [i["title"] for i in items]
        assert "Other Event" not in titles
        assert "Future Event" not in titles

    def test_routine_near_midnight_lands_on_correct_local_day(self, user):
        """A routine occurrence near midnight lands on the right local day."""
        # 23:30 local time in Asia/Kolkata
        Routine.objects.create(
            user=user,
            title="Late Night Journal",
            weekdays=[0],  # Monday Nov 2
            start_time=time(23, 30),
            end_time=time(23, 55),
            start_date=date(2026, 11, 2),
        )

        result = agenda(user, date(2026, 11, 2), date(2026, 11, 2))
        assert len(result["items"]) == 1
        item = result["items"][0]
        assert item["details"]["date"] == "2026-11-02"
        # 23:30 IST is 18:00 UTC on the same day (Nov 2)
        assert item["start_at"] == "2026-11-02T18:00:00+00:00"


# ---------------------------------------------------------------------------
# 5. Free slots and task suggestions tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestFreeSlots:
    def test_merge_intervals(self):
        """merge_intervals: overlapping, touching, nested and empty inputs."""
        # Empty
        assert merge_intervals([]) == []

        # Overlapping & touching & nested
        t1 = datetime(2026, 11, 2, 10, 0)
        t2 = datetime(2026, 11, 2, 11, 0)
        t3 = datetime(2026, 11, 2, 11, 0)  # touching
        t4 = datetime(2026, 11, 2, 12, 0)
        t5 = datetime(2026, 11, 2, 11, 15) # nested inside (t3, t4)
        t6 = datetime(2026, 11, 2, 11, 45)
        t7 = datetime(2026, 11, 2, 13, 0)
        t8 = datetime(2026, 11, 2, 14, 0)

        merged = merge_intervals([(t1, t2), (t3, t4), (t5, t6), (t7, t8)])
        assert len(merged) == 2
        assert merged[0] == (t1, t4)  # 10:00 to 12:00
        assert merged[1] == (t7, t8)  # 13:00 to 14:00

    def test_free_slots_intervals_and_routines(self, user):
        """
        No events: the whole work window is one slot.
        With an event in the middle: two slots.
        A skipped routine frees its time, a pending one blocks it.
        """
        day = date(2026, 11, 2)
        # Fixed now before work_start (09:00 IST = 03:30 UTC)
        fixed_now = local_to_utc(user.timezone, day, time(8, 0))

        # 1. No events: full work window (9 hours = 540 min)
        slots_empty = free_slots(user, day, 15, now=fixed_now)
        assert len(slots_empty) == 1
        assert slots_empty[0]["minutes"] == 540

        # 2. Event in middle (12:00-13:00 IST = 06:30-07:30 UTC): two slots
        event = Event.objects.create(
            user=user,
            title="Lunch Meeting",
            start_at="2026-11-02T06:30:00Z",
            end_at="2026-11-02T07:30:00Z",
        )
        slots_event = free_slots(user, day, 15, now=fixed_now)
        assert len(slots_event) == 2
        event.delete()

        # 3. Routine pending blocks time -> splits window
        routine = Routine.objects.create(
            user=user,
            title="Gym",
            weekdays=[0],
            start_time=time(12, 0),
            end_time=time(13, 0),
            start_date=day,
        )
        slots_pending = free_slots(user, day, 15, now=fixed_now)
        assert len(slots_pending) == 2

        # 4. Routine skipped (done=False) frees the time -> 1 full slot
        RoutineCheckin.objects.create(user=user, routine=routine, date=day, done=False)
        slots_skipped = free_slots(user, day, 15, now=fixed_now)
        assert len(slots_skipped) == 1
        assert slots_skipped[0]["minutes"] == 540

    def test_free_slots_today_starts_at_now(self, user):
        """On today's date the first slot starts at now when now is inside the work window."""
        today = local_today(user.timezone)
        # 10:00 IST is 1 hour into the 09:00-18:00 window
        now_inside = local_to_utc(user.timezone, today, time(10, 0))

        slots = free_slots(user, today, 15, now=now_inside)
        assert len(slots) == 1
        assert slots[0]["start_at"] == now_inside.isoformat()
        assert slots[0]["minutes"] == 8 * 60  # 10:00 to 18:00 = 480 min

    def test_free_slots_min_minutes_filter_and_validation(
        self, authenticated_client, user
    ):
        """min_minutes filters out short gaps; invalid min_minutes (4, 481) -> 400."""
        day = date(2026, 11, 2)
        fixed_now = local_to_utc(user.timezone, day, time(8, 0))

        # Event leaving a 20-minute gap at start (09:00 to 09:20 IST free, 09:20 to 18:00 busy)
        # 09:20 IST = 03:50 UTC
        Event.objects.create(
            user=user,
            title="Big Event",
            start_at="2026-11-02T03:50:00Z",
            end_at="2026-11-02T12:30:00Z",
        )

        # min_minutes=30 excludes the 20-min gap
        slots_30 = free_slots(user, day, 30, now=fixed_now)
        assert len(slots_30) == 0

        # min_minutes=15 includes the 20-min gap
        slots_15 = free_slots(user, day, 15, now=fixed_now)
        assert len(slots_15) == 1
        assert slots_15[0]["minutes"] == 20

        # API query validation: 4 and 481 -> 400
        assert (
            authenticated_client.get("/api/v1/free-slots/?min_minutes=4").status_code
            == status.HTTP_400_BAD_REQUEST
        )
        assert (
            authenticated_client.get("/api/v1/free-slots/?min_minutes=481").status_code
            == status.HTTP_400_BAD_REQUEST
        )

    def test_suggest_tasks_rules(self, user):
        """
        Suggestions:
        - A task that fits is suggested;
        - A task bigger than the slot is not;
        - Each task appears at most once across slots;
        - Tasks without estimate_min and done tasks are never suggested;
        - The order follows priority_rank.
        """
        day = date(2026, 11, 2)
        utc = ZoneInfo("UTC")

        # Two slots: slot 1 (60 mins), slot 2 (120 mins)
        slots = [
            {"start_at": "2026-11-02T03:30:00+00:00", "end_at": "2026-11-02T04:30:00+00:00", "minutes": 60},
            {"start_at": "2026-11-02T05:00:00+00:00", "end_at": "2026-11-02T07:00:00+00:00", "minutes": 120},
        ]

        # 1. Done task -> should NOT be suggested
        Task.objects.create(
            user=user,
            title="Done Task",
            estimate_min=30,
            status=Task.Status.DONE,
            due_at=datetime(2026, 11, 2, 10, 0, tzinfo=utc),
        )

        # 2. Task without estimate_min -> should NOT be suggested
        Task.objects.create(
            user=user,
            title="No Estimate Task",
            estimate_min=None,
            due_at=datetime(2026, 11, 2, 10, 0, tzinfo=utc),
        )

        # 3. Overdue task (rank 0, highest priority), 45 min -> fits in slot 1
        task_overdue = Task.objects.create(
            user=user,
            title="Overdue Task",
            estimate_min=45,
            due_at=datetime(2026, 11, 1, 10, 0, tzinfo=utc),
        )

        # 4. Urgent & important task (rank 1), 75 min -> does NOT fit slot 1 (60-45=15 remaining), fits slot 2
        task_rank1 = Task.objects.create(
            user=user,
            title="Urgent & Important",
            estimate_min=75,
            is_important=True,
            due_at=datetime(2026, 11, 3, 10, 0, tzinfo=utc),
        )

        # 5. Normal task (rank 4), 30 min -> fits remaining 45 min in slot 2
        task_rank4 = Task.objects.create(
            user=user,
            title="Normal Task",
            estimate_min=30,
            due_at=datetime(2026, 11, 10, 10, 0, tzinfo=utc),
        )

        # 6. Task bigger than all remaining capacities (200 min) -> not suggested
        Task.objects.create(
            user=user,
            title="Giant Task",
            estimate_min=200,
            due_at=datetime(2026, 11, 2, 10, 0, tzinfo=utc),
        )

        fixed_now = datetime(2026, 11, 2, 8, 0, tzinfo=utc)
        result_slots = suggest_tasks(user, slots, now=fixed_now)

        slot1_sug = [s["id"] for s in result_slots[0]["suggestions"]]
        slot2_sug = [s["id"] for s in result_slots[1]["suggestions"]]

        assert slot1_sug == [task_overdue.id]
        assert slot2_sug == [task_rank1.id, task_rank4.id]

        # No task suggested more than once
        all_sug = slot1_sug + slot2_sug
        assert len(all_sug) == len(set(all_sug))
