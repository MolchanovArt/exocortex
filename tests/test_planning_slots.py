"""Tests for slot suggestion logic."""

from datetime import date, datetime, timedelta, time

import pytest

from exocortex.core.db import Base, get_session, init_db
from exocortex.core.models import CalendarEvent, MindItem, TimelineItem
from exocortex.planning.slots import suggest_slots


@pytest.fixture
def db_session(tmp_path, monkeypatch):
    """Create a temporary database for testing."""
    import exocortex.core.config as config_module
    import exocortex.core.db as db_module

    test_db = tmp_path / "test.db"
    monkeypatch.setattr(config_module.config, "exocortex_db_path", str(test_db))

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{test_db}", connect_args={"check_same_thread": False})
    db_module.engine = engine
    db_module.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db_module.Base = Base

    Base.metadata.create_all(bind=engine)

    session = db_module.SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture
def mock_preferences(monkeypatch):
    """Mock planning preferences for testing."""
    from exocortex.core.models import PlanningPreferences, WorkHours

    prefs = PlanningPreferences(
        timezone="UTC",
        work_days=["Mon", "Tue", "Wed", "Thu", "Fri"],
        work_hours=WorkHours(start="10:00", end="18:00"),
        default_task_duration_minutes=60,
        max_focus_blocks_per_day=3,
    )

    def _get_prefs():
        return prefs

    from exocortex import planning

    monkeypatch.setattr(planning.preferences, "get_planning_preferences", _get_prefs)
    monkeypatch.setattr(planning.preferences, "get_timezone_obj", lambda: __import__("pytz").timezone("UTC"))
    monkeypatch.setattr(planning.slots, "get_planning_preferences", _get_prefs)
    monkeypatch.setattr(planning.slots, "get_timezone_obj", lambda: __import__("pytz").timezone("UTC"))


@pytest.fixture
def mock_energy_profile(monkeypatch):
    """Mock energy profile for testing."""
    from exocortex.core.models import EnergyProfileEntry

    profile = [
        EnergyProfileEntry(label="morning", start="10:00", end="12:00", level="high"),
        EnergyProfileEntry(label="afternoon", start="12:00", end="17:00", level="medium"),
        EnergyProfileEntry(label="evening", start="17:00", end="18:00", level="low"),
    ]

    def _get_profile():
        return profile

    import exocortex.planning.preferences as prefs_module
    import exocortex.planning.slots as slots_module

    monkeypatch.setattr(prefs_module, "get_energy_profile", _get_profile)
    monkeypatch.setattr(slots_module, "get_energy_profile", _get_profile)


def test_suggest_slots_no_conflicts(db_session, mock_preferences, mock_energy_profile):
    """Test slot suggestion with no calendar events or planned tasks."""
    # Today is a weekday, work hours 10:00-18:00
    today = date.today()
    # Make sure today is a weekday (Mon-Fri)
    while today.weekday() >= 5:  # Saturday=5, Sunday=6
        today += timedelta(days=1)

    slots = suggest_slots(db_session, days_ahead=1, max_suggestions=3)

    assert len(slots) > 0
    # All slots should be within work hours
    for slot in slots:
        assert slot.start.time() >= time(10, 0)
        assert slot.end.time() <= time(18, 0)
        assert (slot.end - slot.start).total_seconds() == 3600  # 1 hour


def test_suggest_slots_respects_calendar_events(db_session, mock_preferences, mock_energy_profile):
    """Test that slots don't overlap with calendar events."""
    today = date.today()
    while today.weekday() >= 5:
        today += timedelta(days=1)

    # Create a calendar event from 12:00-13:00
    event_start = datetime.combine(today, time(12, 0))
    event_end = datetime.combine(today, time(13, 0))

    calendar_event = CalendarEvent(
        calendar_id="primary",
        event_id="test_event",
        title="Test Event",
        description="Test",
        start_time=event_start,
        end_time=event_end,
        raw_json="{}",
    )
    db_session.add(calendar_event)
    db_session.flush()

    # Create timeline item
    timeline_item = TimelineItem(
        source_type="calendar",
        timestamp=event_start,
        title="Test Event",
        content="Test",
        meta="{}",
        calendar_event_id=calendar_event.id,
    )
    db_session.add(timeline_item)
    db_session.flush()

    slots = suggest_slots(db_session, days_ahead=1, max_suggestions=5)

    # Verify no slots overlap with the calendar event
    for slot in slots:
        # Slot should not overlap: slot.end <= event_start OR slot.start >= event_end
        assert slot.end <= event_start or slot.start >= event_end


def test_suggest_slots_respects_planned_tasks(db_session, mock_preferences, mock_energy_profile):
    """Test that slots don't overlap with planned tasks."""
    today = date.today()
    while today.weekday() >= 5:
        today += timedelta(days=1)

    # Create a timeline item
    timeline_item = TimelineItem(
        source_type="telegram",
        timestamp=datetime.now(),
        title="Test Task",
        content="Test",
        meta="{}",
    )
    db_session.add(timeline_item)
    db_session.flush()

    # Create a planned task from 14:00-15:00
    task_start = datetime.combine(today, time(14, 0))
    task_end = datetime.combine(today, time(15, 0))

    mind_item = MindItem(
        timeline_item_id=timeline_item.id,
        item_type="task",
        summary="Test Task",
        status="planned",
        planned_start=task_start,
        planned_end=task_end,
        created_at=datetime.now(),
    )
    db_session.add(mind_item)
    db_session.flush()

    slots = suggest_slots(db_session, days_ahead=1, max_suggestions=5)

    # Verify no slots overlap with the planned task
    for slot in slots:
        assert slot.end <= task_start or slot.start >= task_end


def test_suggest_slots_respects_avoid_after(monkeypatch, db_session, mock_energy_profile):
    """Test that slots respect avoid_after constraint."""
    from exocortex.core.models import PlanningPreferences, WorkHours

    prefs = PlanningPreferences(
        timezone="UTC",
        work_days=["Mon", "Tue", "Wed", "Thu", "Fri"],
        work_hours=WorkHours(start="10:00", end="18:00"),
        default_task_duration_minutes=60,
        avoid_after="16:00",
    )

    def _get_prefs():
        return prefs

    import exocortex.planning.preferences as prefs_module
    import exocortex.planning.slots as slots_module

    monkeypatch.setattr(prefs_module, "get_planning_preferences", _get_prefs)
    monkeypatch.setattr(slots_module, "get_planning_preferences", _get_prefs)

    slots = suggest_slots(db_session, days_ahead=1, max_suggestions=10)

    # All slots should start before 16:00
    for slot in slots:
        assert slot.start.time() < time(16, 0)


def test_suggest_slots_respects_block_minutes(db_session, mock_preferences, mock_energy_profile):
    """Test that slots respect block_minutes parameter."""
    slots = suggest_slots(db_session, days_ahead=1, block_minutes=30, max_suggestions=5)

    for slot in slots:
        duration_minutes = (slot.end - slot.start).total_seconds() / 60
        assert duration_minutes == 30


def test_suggest_slots_max_suggestions(db_session, mock_preferences, mock_energy_profile):
    """Test that max_suggestions limit is respected."""
    slots = suggest_slots(db_session, days_ahead=7, max_suggestions=3)

    assert len(slots) <= 3

