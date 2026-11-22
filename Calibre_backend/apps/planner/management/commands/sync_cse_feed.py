from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
import requests
from datetime import datetime, timedelta
import hashlib
import re

from apps.planner.models import ExternalEvent


class Command(BaseCommand):
    help = "Sync CSE department talks from IITB CSE feed"

    def handle(self, *args, **options):
        url = "https://www.cse.iitb.ac.in/~internal-live/webcal/export/"
        timeout = 30
        cutoff_days = 30  # Keep events from 30 days ago or later
        
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            ics_content = response.text
        except requests.RequestException as e:
            raise CommandError(f"Failed to fetch CSE feed: {e}")
        
        # Parse ICS format
        events = self.parse_ics(ics_content)
        
        # Filter by date
        cutoff_date = timezone.now() - timedelta(days=cutoff_days)
        events = [e for e in events if e["start_at"] >= cutoff_date]
        
        # Upsert events
        created = 0
        updated = 0
        removed = 0
        
        seen_ids = set()
        
        for event_data in events:
            external_id = event_data["external_id"]
            seen_ids.add(external_id)
            
            # Calculate end_at (1 hour after start)
            end_at = event_data["start_at"] + timedelta(hours=1)
            
            event, event_created = ExternalEvent.objects.update_or_create(
                source=ExternalEvent.Source.CSE,
                external_id=external_id,
                defaults={
                    "title": event_data["title"],
                    "description": event_data["description"],
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
        
        # Mark removed events
        removed_events = ExternalEvent.objects.filter(
            source=ExternalEvent.Source.CSE,
            removed_at__isnull=True
        ).exclude(external_id__in=seen_ids)
        
        removed_count = removed_events.update(removed_at=timezone.now())
        removed = removed_count
        
        self.stdout.write(
            self.style.SUCCESS(
                f"CSE feed sync: {created} created, {updated} updated, {removed} removed"
            )
        )
    
    def parse_ics(self, ics_content):
        """Parse ICS format and extract events."""
        events = []
        current_event = {}
        
        # Unfold continuation lines (lines starting with space)
        lines = []
        for line in ics_content.splitlines():
            if line.startswith(" ") or line.startswith("\t"):
                if lines:
                    lines[-1] += line[1:]  # Remove leading space and append
            else:
                lines.append(line)
        
        for line in lines:
            if line.startswith("BEGIN:VEVENT"):
                current_event = {}
            elif line.startswith("END:VEVENT"):
                if current_event and "title" in current_event and "start_at" in current_event:
                    # Build external_id as hash of title + start_at
                    external_id = hashlib.md5(
                        f"{current_event['title']}_{current_event['start_at'].isoformat()}".encode()
                    ).hexdigest()
                    current_event["external_id"] = external_id
                    events.append(current_event)
                current_event = {}
            elif ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                
                # Unescape ICS characters
                value = value.replace(r"\,", ",").replace(r"\n", "\n").replace(r"\;", ";")
                
                if key == "SUMMARY":
                    current_event["title"] = value
                elif key == "DESCRIPTION":
                    current_event["description"] = value
                elif key == "DTSTART":
                    current_event["start_at"] = self.parse_ics_datetime(value)
        
        return events
    
    def parse_ics_datetime(self, dt_str):
        """Parse ICS datetime format (UTC with Z suffix)."""
        # Format: 20261029T143000Z
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1]  # Remove Z
            dt = datetime.strptime(dt_str, "%Y%m%dT%H%M%S")
            return timezone.make_aware(dt, timezone.utc)
        return None
