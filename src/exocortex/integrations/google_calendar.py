"""Google Calendar integration client."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import BaseModel, Field

from exocortex.core.config import config

logger = logging.getLogger(__name__)

# Scopes required for Calendar API
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


class CalendarEventPayload(BaseModel):
    """Pydantic model for normalized Google Calendar event data."""

    event_id: str = Field(..., description="Google Calendar event ID")
    calendar_id: str = Field(..., description="Calendar ID")
    title: str = Field(..., description="Event title/summary")
    description: Optional[str] = Field(None, description="Event description")
    start_time: datetime = Field(..., description="Event start time")
    end_time: Optional[datetime] = Field(None, description="Event end time")
    raw_json: str = Field(..., description="Raw event data as JSON string")


def get_calendar_service():
    """
    Get an authorized Google Calendar service object.

    Handles OAuth flow using credentials.json and token.json files.

    Returns:
        Google Calendar API service object

    Raises:
        FileNotFoundError: If credentials file is not found
        ValueError: If credentials are invalid
    """
    creds = None
    credentials_path = Path(config.google_credentials_file) if config.google_credentials_file else None
    token_path = Path(config.google_token_file) if config.google_token_file else None

    if not credentials_path or not credentials_path.exists():
        raise FileNotFoundError(
            f"Google credentials file not found at {credentials_path}. "
            f"Please set GOOGLE_CREDENTIALS_FILE in your .env file."
        )

    # Load existing token if available
    if token_path and token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except Exception as e:
            logger.warning(f"Failed to load token from {token_path}: {e}")

    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.warning(f"Failed to refresh token: {e}")
                creds = None

        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        if token_path:
            token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(token_path, "w") as token:
                token.write(creds.to_json())

    try:
        service = build("calendar", "v3", credentials=creds)
        return service
    except Exception as e:
        raise ValueError(f"Failed to build Calendar service: {e}") from e


def parse_rfc3339_datetime(dt_str: str) -> datetime:
    """
    Parse RFC3339 datetime string to datetime object.

    Handles both full datetime and date-only strings.
    """
    try:
        # Try parsing as full datetime
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except ValueError:
        # Try parsing as date only
        try:
            return datetime.fromisoformat(dt_str)
        except ValueError:
            # Fallback: try common formats
            for fmt in ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
                try:
                    return datetime.strptime(dt_str, fmt)
                except ValueError:
                    continue
            raise ValueError(f"Unable to parse datetime: {dt_str}")


def fetch_events(
    time_min: datetime,
    time_max: datetime,
    max_results: int = 100,
    calendar_id: Optional[str] = None,
) -> List[CalendarEventPayload]:
    """
    Fetch events from Google Calendar.

    Args:
        time_min: Start of time range (inclusive)
        time_max: End of time range (exclusive)
        max_results: Maximum number of events to return
        calendar_id: Calendar ID to fetch from (defaults to config value)

    Returns:
        List of CalendarEventPayload objects

    Raises:
        ValueError: If calendar_id is not configured
        HttpError: If there's an error communicating with Google Calendar API
    """
    if not calendar_id:
        calendar_id = config.google_calendar_id

    if not calendar_id:
        raise ValueError("GOOGLE_CALENDAR_ID is not set in configuration")

    try:
        service = get_calendar_service()
    except Exception as e:
        logger.error(f"Failed to get calendar service: {e}")
        raise

    events: List[CalendarEventPayload] = []

    try:
        # Format times as RFC3339
        time_min_str = time_min.isoformat() + "Z" if time_min.tzinfo is None else time_min.isoformat()
        time_max_str = time_max.isoformat() + "Z" if time_max.tzinfo is None else time_max.isoformat()

        # Call the Calendar API
        events_result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min_str,
                timeMax=time_max_str,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        items = events_result.get("items", [])

        for event in items:
            # Skip cancelled events
            if event.get("status") == "cancelled":
                continue

            # Extract event ID
            event_id = event.get("id")
            if not event_id:
                continue

            # Extract start time
            start = event.get("start", {})
            start_time_str = start.get("dateTime") or start.get("date")
            if not start_time_str:
                logger.warning(f"Event {event_id} has no start time, skipping")
                continue

            try:
                start_time = parse_rfc3339_datetime(start_time_str)
            except ValueError as e:
                logger.warning(f"Failed to parse start time for event {event_id}: {e}")
                continue

            # Extract end time (optional)
            end_time = None
            end = event.get("end", {})
            end_time_str = end.get("dateTime") or end.get("date")
            if end_time_str:
                try:
                    end_time = parse_rfc3339_datetime(end_time_str)
                except ValueError as e:
                    logger.warning(f"Failed to parse end time for event {event_id}: {e}")

            # Extract title and description
            title = event.get("summary", "Untitled Event")
            description = event.get("description")

            # Convert to JSON for raw storage
            try:
                raw_json = json.dumps(event, default=str, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"Failed to serialize event {event_id} to JSON: {e}")
                raw_json = "{}"

            payload = CalendarEventPayload(
                event_id=event_id,
                calendar_id=calendar_id,
                title=title,
                description=description,
                start_time=start_time,
                end_time=end_time,
                raw_json=raw_json,
            )

            events.append(payload)

    except HttpError as e:
        logger.error(f"Google Calendar API error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching calendar events: {e}")
        raise

    logger.info(f"Fetched {len(events)} events from calendar {calendar_id}")
    return events

