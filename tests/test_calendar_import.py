"""Tests for Google Calendar import functionality."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from exocortex.core.db import Base, get_session, init_db
from exocortex.core.models import CalendarEvent, TimelineItem
from exocortex.integrations.google_calendar import CalendarEventPayload, fetch_events


@pytest.fixture
def db_session(tmp_path, monkeypatch):
    """Create a temporary database for testing."""
    import exocortex.core.config as config_module
    import exocortex.core.db as db_module

    # Create a temporary database file
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(config_module.config, "exocortex_db_path", str(test_db))

    # Reinitialize the engine with the new path
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{test_db}", connect_args={"check_same_thread": False})
    db_module.engine = engine
    db_module.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db_module.Base = Base

    # Create tables
    Base.metadata.create_all(bind=engine)

    # Create a session
    session = db_module.SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def test_calendar_event_payload():
    """Test CalendarEventPayload Pydantic model."""
    payload = CalendarEventPayload(
        event_id="test_event_123",
        calendar_id="primary",
        title="Test Event",
        description="Test description",
        start_time=datetime(2024, 1, 1, 12, 0, 0),
        end_time=datetime(2024, 1, 1, 13, 0, 0),
        raw_json='{"id": "test_event_123"}',
    )

    assert payload.event_id == "test_event_123"
    assert payload.calendar_id == "primary"
    assert payload.title == "Test Event"
    assert payload.description == "Test description"


@patch("exocortex.integrations.google_calendar.get_calendar_service")
def test_fetch_events_mock(mock_get_service):
    """Test fetch_events with mocked Google Calendar API."""
    # Mock calendar service
    mock_service = MagicMock()
    mock_get_service.return_value = mock_service

    # Mock events list response
    mock_events_list = MagicMock()
    mock_service.events.return_value.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "event1",
                "summary": "Test Event 1",
                "description": "Description 1",
                "status": "confirmed",
                "start": {"dateTime": "2024-01-01T12:00:00Z"},
                "end": {"dateTime": "2024-01-01T13:00:00Z"},
            },
            {
                "id": "event2",
                "summary": "Test Event 2",
                "status": "confirmed",
                "start": {"date": "2024-01-02"},
                "end": {"date": "2024-01-02"},
            },
            {
                "id": "cancelled_event",
                "summary": "Cancelled Event",
                "status": "cancelled",
                "start": {"dateTime": "2024-01-01T14:00:00Z"},
            },
        ]
    }

    # Mock config
    with patch("exocortex.integrations.google_calendar.config") as mock_config:
        mock_config.google_calendar_id = "primary"

        time_min = datetime(2024, 1, 1)
        time_max = datetime(2024, 1, 3)

        events = fetch_events(time_min=time_min, time_max=time_max, calendar_id="primary")

        # Should return 2 events (cancelled one is skipped)
        assert len(events) == 2
        assert events[0].event_id == "event1"
        assert events[0].title == "Test Event 1"
        assert events[1].event_id == "event2"
        assert events[1].title == "Test Event 2"


def test_import_calendar_events(db_session):
    """Test importing calendar events and creating timeline items."""
    from exocortex.cli.import_calendar import import_calendar_events

    # Create mock event payloads
    mock_events = [
        CalendarEventPayload(
            event_id="event1",
            calendar_id="primary",
            title="Meeting",
            description="Team meeting",
            start_time=datetime(2024, 1, 1, 12, 0, 0),
            end_time=datetime(2024, 1, 1, 13, 0, 0),
            raw_json='{"id": "event1"}',
        ),
        CalendarEventPayload(
            event_id="event2",
            calendar_id="primary",
            title="Lunch",
            description=None,
            start_time=datetime(2024, 1, 1, 13, 0, 0),
            end_time=None,
            raw_json='{"id": "event2"}',
        ),
    ]

    # Mock fetch_events
    with patch("exocortex.cli.import_calendar.fetch_events", return_value=mock_events):
        # Mock get_session to use our test session
        with patch("exocortex.cli.import_calendar.get_session") as mock_get_session:
            from contextlib import contextmanager

            @contextmanager
            def session_context():
                yield db_session

            mock_get_session.return_value = session_context()

            time_min = datetime(2024, 1, 1)
            time_max = datetime(2024, 1, 2)

            calendar_count, timeline_count = import_calendar_events(
                time_min=time_min, time_max=time_max
            )

            assert calendar_count == 2
            assert timeline_count == 2

            # Verify CalendarEvent records
            calendar_events = db_session.query(CalendarEvent).all()
            assert len(calendar_events) == 2
            assert calendar_events[0].event_id == "event1"
            assert calendar_events[0].title == "Meeting"
            assert calendar_events[1].event_id == "event2"

            # Verify TimelineItem records
            timeline_items = db_session.query(TimelineItem).all()
            assert len(timeline_items) == 2
            assert timeline_items[0].source_type == "calendar"
            assert timeline_items[0].title == "Meeting"
            assert timeline_items[1].title == "Lunch"

            # Verify relationships
            assert timeline_items[0].calendar_event_id == calendar_events[0].id
            assert timeline_items[1].calendar_event_id == calendar_events[1].id


def test_import_calendar_deduplication(db_session):
    """Test that duplicate events are not imported twice."""
    from exocortex.cli.import_calendar import import_calendar_events

    mock_events = [
        CalendarEventPayload(
            event_id="event1",
            calendar_id="primary",
            title="Meeting",
            description="Team meeting",
            start_time=datetime(2024, 1, 1, 12, 0, 0),
            end_time=datetime(2024, 1, 1, 13, 0, 0),
            raw_json='{"id": "event1"}',
        ),
    ]

    with patch("exocortex.cli.import_calendar.fetch_events", return_value=mock_events):
        with patch("exocortex.cli.import_calendar.get_session") as mock_get_session:
            from contextlib import contextmanager

            @contextmanager
            def session_context():
                yield db_session

            mock_get_session.return_value = session_context()

            time_min = datetime(2024, 1, 1)
            time_max = datetime(2024, 1, 2)

            # First import
            calendar_count1, timeline_count1 = import_calendar_events(
                time_min=time_min, time_max=time_max
            )
            assert calendar_count1 == 1
            assert timeline_count1 == 1

            # Second import (should update, not duplicate)
            calendar_count2, timeline_count2 = import_calendar_events(
                time_min=time_min, time_max=time_max
            )
            assert calendar_count2 == 0  # No new events created
            assert timeline_count2 == 0  # No new timeline items created

            # Verify only one record exists
            calendar_events = db_session.query(CalendarEvent).all()
            assert len(calendar_events) == 1

            timeline_items = db_session.query(TimelineItem).all()
            assert len(timeline_items) == 1

