"""Tests for query CLI functionality."""

from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest

from exocortex.core.db import Base, get_session, init_db
from exocortex.core.models import CalendarEvent, MindItem, TelegramMessage, TimelineItem
from exocortex.cli.query_helpers import (
    get_recent_items_by_type,
    get_recent_timeline_items,
    get_tasks_for_day,
)


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


def test_get_tasks_for_day(db_session):
    """Test getting tasks for a specific day."""
    today = date.today()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    # Create timeline items
    timeline_items = [
        TimelineItem(
            source_type="telegram",
            timestamp=datetime.now(),
            title="Task 1",
            content="Do something today",
            meta="{}",
        ),
        TimelineItem(
            source_type="telegram",
            timestamp=datetime.now(),
            title="Task 2",
            content="Do something tomorrow",
            meta="{}",
        ),
        TimelineItem(
            source_type="telegram",
            timestamp=datetime.now(),
            title="Task 3",
            content="Do something yesterday",
            meta="{}",
        ),
    ]
    for item in timeline_items:
        db_session.add(item)
    db_session.flush()

    # Create mind items (tasks)
    # Task 1: planned for today
    task1 = MindItem(
        timeline_item_id=timeline_items[0].id,
        item_type="task",
        summary="Task 1 summary",
        status="new",
        planned_for=datetime.combine(today, datetime.min.time()),
        created_at=datetime.now(),
    )

    # Task 2: planned for tomorrow
    task2 = MindItem(
        timeline_item_id=timeline_items[1].id,
        item_type="task",
        summary="Task 2 summary",
        status="planned",
        planned_for=datetime.combine(tomorrow, datetime.min.time()),
        created_at=datetime.now(),
    )

    # Task 3: planned for yesterday (should not appear)
    task3 = MindItem(
        timeline_item_id=timeline_items[2].id,
        item_type="task",
        summary="Task 3 summary",
        status="new",
        planned_for=datetime.combine(yesterday, datetime.min.time()),
        created_at=datetime.now(),
    )

    # Task 4: no planned_for, but created today (should appear)
    timeline_item4 = TimelineItem(
        source_type="telegram",
        timestamp=datetime.now(),
        title="Task 4",
        content="Task without planned date",
        meta="{}",
    )
    db_session.add(timeline_item4)
    db_session.flush()

    task4 = MindItem(
        timeline_item_id=timeline_item4.id,
        item_type="task",
        summary="Task 4 summary",
        status="new",
        planned_for=None,
        created_at=datetime.combine(today, datetime.min.time()),
    )

    # Task 5: done status (should not appear)
    timeline_item5 = TimelineItem(
        source_type="telegram",
        timestamp=datetime.now(),
        title="Task 5",
        content="Done task",
        meta="{}",
    )
    db_session.add(timeline_item5)
    db_session.flush()

    task5 = MindItem(
        timeline_item_id=timeline_item5.id,
        item_type="task",
        summary="Task 5 summary",
        status="done",
        planned_for=datetime.combine(today, datetime.min.time()),
        created_at=datetime.now(),
    )

    db_session.add_all([task1, task2, task3, task4, task5])
    db_session.flush()

    # Get tasks for today
    tasks = get_tasks_for_day(db_session, today)

    # Should return task1 and task4 (not task3, task5, or task2)
    assert len(tasks) == 2
    assert tasks[0].id in [task1.id, task4.id]
    assert tasks[1].id in [task1.id, task4.id]


def test_get_recent_timeline_items_filters_past_calendar_events(db_session):
    """Test that past calendar events are filtered out from timeline."""
    now = datetime.now()
    past_time = now - timedelta(hours=2)  # 2 hours ago
    future_time = now + timedelta(hours=2)  # 2 hours from now

    # Create a past calendar event
    past_calendar_event = CalendarEvent(
        calendar_id="primary",
        event_id="past_event",
        title="Past Event",
        description="This event already happened",
        start_time=past_time,
        end_time=past_time + timedelta(hours=1),
        raw_json="{}",
    )
    db_session.add(past_calendar_event)
    db_session.flush()

    past_timeline_item = TimelineItem(
        source_type="calendar",
        timestamp=past_time,
        title="Past Event",
        content="This event already happened",
        meta="{}",
        calendar_event_id=past_calendar_event.id,
    )

    # Create a future calendar event
    future_calendar_event = CalendarEvent(
        calendar_id="primary",
        event_id="future_event",
        title="Future Event",
        description="This event is in the future",
        start_time=future_time,
        end_time=future_time + timedelta(hours=1),
        raw_json="{}",
    )
    db_session.add(future_calendar_event)
    db_session.flush()

    future_timeline_item = TimelineItem(
        source_type="calendar",
        timestamp=future_time,
        title="Future Event",
        content="This event is in the future",
        meta="{}",
        calendar_event_id=future_calendar_event.id,
    )

    # Create a non-calendar timeline item (should always be included)
    telegram_timeline_item = TimelineItem(
        source_type="telegram",
        timestamp=now - timedelta(hours=1),
        title="Telegram message",
        content="Some message",
        meta="{}",
    )

    db_session.add_all([past_timeline_item, future_timeline_item, telegram_timeline_item])
    db_session.flush()

    # Get recent timeline items without filter (should return all)
    items_all = get_recent_timeline_items(db_session, limit=10, future_only=False)
    assert len(items_all) == 3  # All items

    # Get recent timeline items with future_only filter
    items = get_recent_timeline_items(db_session, limit=10, future_only=True)

    # Should return future calendar event and telegram item, but not past calendar event
    assert len(items) == 2
    item_ids = [item.id for item in items]
    assert future_timeline_item.id in item_ids
    assert telegram_timeline_item.id in item_ids
    assert past_timeline_item.id not in item_ids


def test_get_recent_items_by_type(db_session):
    """Test getting recent items by type."""
    # Create timeline items
    timeline_items = [
        TimelineItem(
            source_type="telegram",
            timestamp=datetime.now() - timedelta(hours=i),
            title=f"Item {i}",
            content=f"Content {i}",
            meta="{}",
        )
        for i in range(5)
    ]
    for item in timeline_items:
        db_session.add(item)
    db_session.flush()

    # Create mind items (mix of ideas and notes)
    mind_items = []
    for i, timeline_item in enumerate(timeline_items):
        item_type = "idea" if i % 2 == 0 else "note"
        mind_item = MindItem(
            timeline_item_id=timeline_item.id,
            item_type=item_type,
            summary=f"Summary {i}",
            status="new",
            created_at=datetime.now() - timedelta(hours=i),
        )
        mind_items.append(mind_item)
        db_session.add(mind_item)

    db_session.flush()

    # Get recent ideas
    ideas = get_recent_items_by_type(db_session, "idea", limit=10)
    assert len(ideas) == 3  # Items 0, 2, 4
    assert all(item.item_type == "idea" for item in ideas)
    # Should be ordered by created_at desc
    assert ideas[0].created_at >= ideas[1].created_at

    # Get recent notes
    notes = get_recent_items_by_type(db_session, "note", limit=10)
    assert len(notes) == 2  # Items 1, 3
    assert all(item.item_type == "note" for item in notes)


def test_get_recent_timeline_items(db_session):
    """Test getting recent timeline items."""
    # Create timeline items with different timestamps
    timeline_items = [
        TimelineItem(
            source_type="telegram" if i % 2 == 0 else "calendar",
            timestamp=datetime.now() - timedelta(hours=i),
            title=f"Item {i}",
            content=f"Content {i}",
            meta="{}",
        )
        for i in range(10)
    ]
    for item in timeline_items:
        db_session.add(item)

    db_session.flush()

    # Get recent items
    items = get_recent_timeline_items(db_session, limit=5)

    assert len(items) == 5
    # Should be ordered by timestamp desc
    assert items[0].timestamp >= items[1].timestamp
    assert items[1].timestamp >= items[2].timestamp

