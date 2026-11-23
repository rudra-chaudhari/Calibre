import json
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.planner.models import TimetableEntry

DAY_NAME_TO_WEEKDAY = {
    "mon": 0, "monday": 0,
    "tue": 1, "tuesday": 1,
    "wed": 2, "wednesday": 2,
    "thu": 3, "thursday": 3,
    "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
}


class Command(BaseCommand):
    help = "Import the department timetable from a JSON file into TimetableEntry"

    def add_arguments(self, parser):
        parser.add_argument(
            "file",
            type=str,
            help="Path to the timetable JSON file (e.g. Utils/combined_timetable.json)",
        )

    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.exists():
            self.stdout.write(self.style.ERROR(f"File not found: {path}"))
            return

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        rows = data.get("timetable", data) if isinstance(data, dict) else data
        if not isinstance(rows, list):
            self.stdout.write(self.style.ERROR("JSON must contain a 'timetable' list or be a list."))
            return

        entries = []
        errors = []
        for idx, row in enumerate(rows):
            weekday = self._weekday_for(row)
            start_time = self._parse_time(row.get("start_time"))
            end_time = self._parse_time(row.get("end_time"))

            if weekday is None or start_time is None or end_time is None:
                errors.append(idx)
                continue
            if end_time <= start_time:
                errors.append(idx)
                continue

            entries.append(
                TimetableEntry(
                    department=(row.get("department") or "").strip().upper(),
                    course_code=(row.get("course_code") or "").strip(),
                    section=(row.get("section") or "").strip(),
                    weekday=weekday,
                    start_time=start_time,
                    end_time=end_time,
                    room=(row.get("room") or "").strip(),
                    instructor=(row.get("instructor") or "").strip(),
                    marker=(row.get("marker") or "").strip(),
                )
            )

        with transaction.atomic():
            TimetableEntry.objects.all().delete()
            TimetableEntry.objects.bulk_create(entries, ignore_conflicts=True)

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {len(entries)} timetable entries "
                f"({len(errors)} skipped) from {path}"
            )
        )

    @staticmethod
    def _weekday_for(row):
        day_no = row.get("day_no")
        if day_no:
            return day_no - 1
        for key in ("day", "day_name"):
            value = (row.get(key) or "").strip().lower()
            if value in DAY_NAME_TO_WEEKDAY:
                return DAY_NAME_TO_WEEKDAY[value]
        return None

    @staticmethod
    def _parse_time(value):
        if not value:
            return None
        try:
            return datetime.strptime(value.strip(), "%H:%M").time()
        except (ValueError, AttributeError):
            return None
