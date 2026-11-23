from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
import requests
from datetime import datetime, timedelta, timezone as dt_timezone
import hashlib

from apps.planner.models import ExternalEvent


class Command(BaseCommand):
    help = "Sync CSE department talks from IITB CSE feed"

    def handle(self, *args, **options):
        url = "https://www.cse.iitb.ac.in/~internal-live/webcal/export/"
        timeout = 30
        cutoff_days = 90

        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            ics_content = response.text
        except requests.RequestException as e:
            raise CommandError(f"Failed to fetch CSE feed: {e}")

        events = self.parse_ics(ics_content)

        cutoff_date = timezone.now() - timedelta(days=cutoff_days)
        events = [e for e in events if e["start_at"] >= cutoff_date]

        created = 0
        updated = 0
        removed = 0

        seen_ids = set()

        for event_data in events:
            external_id = event_data["external_id"]
            seen_ids.add(external_id)

            end_at = event_data["start_at"] + timedelta(hours=1)

            event, event_created = ExternalEvent.objects.update_or_create(
                source=ExternalEvent.Source.CSE,
                external_id=external_id,
                defaults={
                    "title": event_data["title"],
                    "description": event_data.get("description", ""),
                    "location": "",
                    "start_at": event_data["start_at"],
                    "end_at": end_at,
                    "url": "",
                    "removed_at": None,
                }
            )

            if event_created:
                created += 1
            else:
                updated += 1

        removed_events = ExternalEvent.objects.filter(
            source=ExternalEvent.Source.CSE,
            removed_at__isnull=True
        ).exclude(external_id__in=seen_ids)

        removed = removed_events.update(removed_at=timezone.now())

        self.stdout.write(
            self.style.SUCCESS(
                f"CSE feed sync: {created} created, {updated} updated, {removed} removed"
            )
        )

    def parse_ics(self, ics_content):
        events = []
        current_event = {}

        lines = []
        for line in ics_content.splitlines():
            if line.startswith(" ") or line.startswith("\t"):
                if lines:
                    lines[-1] += line[1:]
            else:
                lines.append(line)

        for line in lines:
            if line.startswith("BEGIN:VEVENT"):
                current_event = {}
            elif line.startswith("END:VEVENT"):
                if current_event and "title" in current_event and "start_at" in current_event:
                    external_id = hashlib.md5(
                        f"{current_event['title']}_{current_event['start_at'].isoformat()}".encode()
                    ).hexdigest()
                    current_event["external_id"] = external_id
                    events.append(current_event)
                current_event = {}
            elif ":" in line:
                key, value = line.split(":", 1)
                key = key.split(";")[0].strip()
                value = value.strip()

                value = value.replace(r"\,", ",").replace(r"\n", "\n").replace(r"\;", ";")

                if key == "SUMMARY":
                    current_event["title"] = value
                elif key == "ABSTRACT" or key == "DESCRIPTION":
                    current_event["description"] = value
                elif key == "DTSTART":
                    start_at = self.parse_ics_datetime(value)
                    if start_at is not None:
                        current_event["start_at"] = start_at

        return events

    def parse_ics_datetime(self, dt_str):
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1]
            dt = datetime.strptime(dt_str, "%Y%m%dT%H%M%S")
            return dt.replace(tzinfo=dt_timezone.utc)
        return None