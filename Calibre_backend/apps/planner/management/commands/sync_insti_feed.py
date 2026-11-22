from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
import requests
from datetime import datetime, timedelta
import time

from apps.planner.models import ExternalEvent


class Command(BaseCommand):
    help = "Sync Institute events from IITB Gymkhana API"

    def add_arguments(self, parser):
        parser.add_argument(
            '--full',
            action='store_true',
            help='Fetch full events-all list (slower, ~10MB, for initial import and daily sync)',
        )
        parser.add_argument(
            '--cutoff-days',
            type=int,
            default=30,
            help='Import events from this many days ago (default: 30)',
        )

    def handle(self, *args, **options):
        use_full = options.get('full', False)
        cutoff_days = options.get('cutoff_days', 30)
        
        if use_full:
            # Full sync with events-all endpoint
            url = "https://gymkhana.iitb.ac.in/instiapp/api/events-all"
            timeout = 120  # Longer timeout for large response
            max_retries = 3
            retry_delay = 5
        else:
            # Light sync with events endpoint
            url = "https://gymkhana.iitb.ac.in/instiapp/api/events"
            timeout = 30
            max_retries = 1
            retry_delay = 0
        
        # Fetch with retries
        data = None
        for attempt in range(max_retries):
            try:
                response = requests.get(url, timeout=timeout)
                response.raise_for_status()
                data = response.json()
                break
            except requests.RequestException as e:
                if attempt < max_retries - 1:
                    self.stdout.write(
                        self.style.WARNING(f"Attempt {attempt + 1} failed: {e}. Retrying in {retry_delay}s...")
                    )
                    time.sleep(retry_delay)
                else:
                    raise CommandError(f"Failed to fetch Institute feed after {max_retries} attempts: {e}")
            except ValueError as e:
                raise CommandError(f"Invalid JSON response: {e}")
        
        if not data:
            raise CommandError("No data received from Institute feed")
        
        # Parse events from API response
        events = self.parse_api_response(data, cutoff_days)
        
        # Upsert events
        created = 0
        updated = 0
        removed = 0
        
        seen_ids = set()
        
        for event_data in events:
            external_id = event_data["external_id"]
            seen_ids.add(external_id)
            
            event, event_created = ExternalEvent.objects.update_or_create(
                source=ExternalEvent.Source.INSTI,
                external_id=external_id,
                defaults={
                    "title": event_data["title"],
                    "description": event_data["description"],
                    "location": event_data["location"],
                    "start_at": event_data["start_at"],
                    "end_at": event_data["end_at"],
                    "url": event_data["url"],
                    "removed_at": None,
                }
            )
            
            if event_created:
                created += 1
            else:
                updated += 1
        
        # Mark removed events (only on full sync)
        if use_full:
            removed_events = ExternalEvent.objects.filter(
                source=ExternalEvent.Source.INSTI,
                removed_at__isnull=True
            ).exclude(external_id__in=seen_ids)
            
            removed_count = removed_events.update(removed_at=timezone.now())
            removed = removed_count
        
        mode = "full" if use_full else "light"
        self.stdout.write(
            self.style.SUCCESS(
                f"Institute feed sync ({mode}): {created} created, {updated} updated, {removed} removed"
            )
        )
    
    def parse_api_response(self, data, cutoff_days=30):
        """Parse Institute API response and extract events."""
        events = []
        
        # API returns {count, data: [...]}
        items = data.get("data", [])
        
        # Calculate cutoff date
        cutoff_date = timezone.now() - timedelta(days=cutoff_days)
        
        for item in items:
            # Only import approved events
            verification_status = item.get("verification_status", "").lower()
            if verification_status != "approved":
                continue
            
            # Parse start time
            start_at = self.parse_datetime(item.get("start_time"))
            if not start_at:
                continue
            
            # Skip bad dates (e.g., 1970-01-01)
            if start_at < cutoff_date:
                continue
            
            # Handle all_day events
            all_day = item.get("all_day", False)
            if all_day:
                # Use the whole local day
                start_date = start_at.date()
                # Set start to midnight UTC of that day in user's timezone
                # For simplicity, use the start_at as is and set end to end of day
                end_at = self.parse_datetime(item.get("end_time"))
                if not end_at:
                    # If no end_time, set to end of day
                    from zoneinfo import ZoneInfo
                    tz = ZoneInfo("Asia/Kolkata")  # Institute timezone
                    end_at = datetime.combine(start_date, datetime.max.time()).replace(tzinfo=tz)
                    end_at = end_at.astimezone(timezone.utc)
            else:
                end_at = self.parse_datetime(item.get("end_time"))
                if not end_at:
                    continue
            
            # Build location from venues and venue_room
            location_parts = []
            venues = item.get("venues", [])
            if venues:
                for venue in venues:
                    venue_name = venue.get("name", "")
                    if venue_name:
                        location_parts.append(venue_name)
            venue_room = item.get("venue_room", "")
            if venue_room:
                location_parts.append(venue_room)
            location = ", ".join(location_parts) if location_parts else ""
            
            # Use description, fallback to longdescription
            description = item.get("description", "") or item.get("longdescription", "")
            
            event = {
                "external_id": str(item.get("id", "")),
                "title": item.get("name", ""),
                "description": description,
                "location": location,
                "start_at": start_at,
                "end_at": end_at,
                "url": item.get("website_url", ""),
            }
            
            if event["external_id"] and event["title"]:
                events.append(event)
        
        return events
    
    def parse_datetime(self, dt_str):
        """Parse datetime string from API response (ISO 8601 with +05:30 offset)."""
        if not dt_str:
            return None
        
        # Try common datetime formats (ISO 8601 with timezone)
        formats = [
            "%Y-%m-%dT%H:%M:%S%z",  # 2026-11-21T14:00:00+05:30
            "%Y-%m-%dT%H:%M:%S.%f%z",  # 2026-11-21T14:00:00.260000+05:30
            "%Y-%m-%dT%H:%M:%SZ",  # 2026-11-21T14:00:00Z
            "%Y-%m-%d %H:%M:%S",  # 2026-11-21 14:00:00
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(dt_str, fmt)
                if dt.tzinfo is None:
                    dt = timezone.make_aware(dt, timezone.utc)
                else:
                    # Convert to UTC
                    dt = dt.astimezone(timezone.utc)
                return dt
            except ValueError:
                continue
        
        return None
