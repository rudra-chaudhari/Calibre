import pytest
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.utils import timezone as tz

from apps.common.timeutils import local_day_window, local_today, local_to_utc

User = get_user_model()


@pytest.mark.django_db
class TestTimeUtils:
    def test_local_today_ist(self):
        now = datetime(2026, 11, 2, 12, 0, 0, tzinfo=ZoneInfo("UTC"))
        today = local_today("Asia/Kolkata", now)
        assert today == date(2026, 11, 2)

    def test_local_today_utc_midnight(self):
        now = datetime(2026, 11, 2, 0, 30, 0, tzinfo=ZoneInfo("UTC"))
        today = local_today("Asia/Kolkata", now)
        # 00:30 UTC is 06:00 IST
        assert today == date(2026, 11, 2)

    def test_local_day_window_ist(self):
        day = date(2026, 11, 2)
        start, end = local_day_window("Asia/Kolkata", day)
        # IST is UTC+5:30, so midnight IST is 18:30 UTC previous day
        assert start.hour == 18
        assert start.day == 1
        assert end.hour == 18
        assert end.day == 2

    def test_local_to_utc(self):
        day = date(2026, 11, 2)
        time_of_day = time(18, 0)
        utc_dt = local_to_utc("Asia/Kolkata", day, time_of_day)
        # 18:00 IST = 12:30 UTC
        assert utc_dt.hour == 12
        assert utc_dt.minute == 30
