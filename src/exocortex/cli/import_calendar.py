"""CLI command to import events from Google Calendar."""

import argparse
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

from exocortex.core.db import get_session
from exocortex.core.models import CalendarEvent, TimelineItem
from exocortex.integrations.google_calendar import fetch_events

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def import_calendar_events(
    time_min: datetime,
    time_max: datetime,
    calendar_id: Optional[str] = None,
    max_results: int = 100,
) -> Tuple[int, int]:
    """
    Import Google Calendar events and create corresponding timeline items.

    Args:
        time_min: Start of time range (inclusive)
        time_max: End of time range (exclusive)
        calendar_id: Calendar ID to fetch from (defaults to config value)
        max_results: Maximum number of events to fetch

    Returns:
        Tuple of (calendar_events_created, timeline_items_created)
    """
    # Fetch events from Google Calendar
    try:
        events = fetch_events(
            time_min=time_min,
            time_max=time_max,
            max_results=max_results,
            calendar_id=calendar_id,
        )
    except Exception as e:
        logger.error(f"Failed to fetch events from Google Calendar: {e}")
        raise

    if not events:
        logger.info("No events to import")
        return (0, 0)

    calendar_count = 0
    timeline_count = 0

    with get_session() as session:
        for event_payload in events:
            # Check if event already exists (by calendar_id + event_id)
            existing = (
                session.query(CalendarEvent)
                .filter(
                    CalendarEvent.calendar_id == event_payload.calendar_id,
                    CalendarEvent.event_id == event_payload.event_id,
                )
                .first()
            )

            if existing:
                # Update existing event
                existing.title = event_payload.title
                existing.description = event_payload.description
                existing.start_time = event_payload.start_time
                existing.end_time = event_payload.end_time
                existing.raw_json = event_payload.raw_json
                calendar_event = existing
                logger.debug(f"Updated existing event {event_payload.event_id}")
            else:
                # Create new CalendarEvent
                calendar_event = CalendarEvent(
                    calendar_id=event_payload.calendar_id,
                    event_id=event_payload.event_id,
                    title=event_payload.title,
                    description=event_payload.description,
                    start_time=event_payload.start_time,
                    end_time=event_payload.end_time,
                    raw_json=event_payload.raw_json,
                )
                session.add(calendar_event)
                session.flush()  # Get the ID
                calendar_count += 1

            # Check if timeline item already exists for this event
            existing_timeline = (
                session.query(TimelineItem)
                .filter(
                    TimelineItem.source_type == "calendar",
                    TimelineItem.calendar_event_id == calendar_event.id,
                )
                .first()
            )

            if existing_timeline:
                # Update existing timeline item
                existing_timeline.timestamp = event_payload.start_time
                existing_timeline.title = event_payload.title
                existing_timeline.content = event_payload.description or f"Event: {event_payload.title}"
                existing_timeline.meta = json.dumps({"event_id": event_payload.event_id}, ensure_ascii=False)
                logger.debug(f"Updated existing timeline item for event {event_payload.event_id}")
            else:
                # Create corresponding TimelineItem
                content = event_payload.description or f"Event: {event_payload.title}"
                if event_payload.end_time:
                    duration = event_payload.end_time - event_payload.start_time
                    content = f"{content}\nDuration: {duration}"

                meta = json.dumps({"event_id": event_payload.event_id}, ensure_ascii=False)

                timeline_item = TimelineItem(
                    source_type="calendar",
                    source_id=calendar_event.id,
                    calendar_event_id=calendar_event.id,
                    timestamp=event_payload.start_time,
                    title=event_payload.title,
                    content=content,
                    meta=meta,
                )
                session.add(timeline_item)
                timeline_count += 1

    logger.info(f"Imported {calendar_count} calendar events and {timeline_count} timeline items")
    return (calendar_count, timeline_count)


def parse_date(date_str: str) -> datetime:
    """Parse date string in YYYY-MM-DD format to datetime."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Expected YYYY-MM-DD")


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Import events from Google Calendar")
    parser.add_argument(
        "--days",
        type=int,
        help="Number of days to import (from today, going forward)",
    )
    parser.add_argument(
        "--from",
        dest="from_date",
        type=str,
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--to",
        dest="to_date",
        type=str,
        help="End date (YYYY-MM-DD, exclusive)",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=100,
        help="Maximum number of events to fetch (default: 100)",
    )

    args = parser.parse_args()

    # Determine time range
    now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    if args.days:
        time_min = now
        time_max = now + timedelta(days=args.days)
    elif args.from_date and args.to_date:
        time_min = parse_date(args.from_date)
        time_max = parse_date(args.to_date)
    elif args.from_date:
        time_min = parse_date(args.from_date)
        time_max = time_min + timedelta(days=7)  # Default to 7 days
    else:
        # Default: import next 7 days
        time_min = now
        time_max = now + timedelta(days=7)

    try:
        calendar_count, timeline_count = import_calendar_events(
            time_min=time_min,
            time_max=time_max,
            max_results=args.max_results,
        )
        print(f"✓ Imported {calendar_count} calendar events")
        print(f"✓ Created {timeline_count} timeline items")
    except Exception as e:
        print(f"Error: {e}")
        exit(1)


if __name__ == "__main__":
    main()

