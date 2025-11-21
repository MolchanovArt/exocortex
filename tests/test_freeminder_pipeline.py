"""Tests for FreeMinder pipeline functionality."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from exocortex.core.db import Base, get_session, init_db
from exocortex.core.models import CalendarEvent, MindItem, TelegramMessage, TimelineItem
from exocortex.modules.freeminder.pipeline import (
    get_unprocessed_timeline_items,
    process_timeline_items,
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


def test_get_unprocessed_timeline_items(db_session):
    """Test getting unprocessed timeline items."""
    # Create some timeline items
    item1 = TimelineItem(
        source_type="telegram",
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        title="Test 1",
        content="Content 1",
        meta="{}",
    )
    item2 = TimelineItem(
        source_type="telegram",
        timestamp=datetime(2024, 1, 1, 13, 0, 0),
        title="Test 2",
        content="Content 2",
        meta="{}",
    )
    db_session.add(item1)
    db_session.add(item2)
    db_session.flush()

    # Create a MindItem for item1 (so it should be excluded)
    mind_item = MindItem(
        timeline_item_id=item1.id,
        item_type="note",
        summary="Summary",
        status="new",
    )
    db_session.add(mind_item)
    db_session.flush()

    # Get unprocessed items
    unprocessed = get_unprocessed_timeline_items(db_session, limit=10)

    # Should only return item2
    assert len(unprocessed) == 1
    assert unprocessed[0].id == item2.id


@patch("exocortex.modules.freeminder.pipeline.classify_timeline_item")
@patch("exocortex.modules.freeminder.pipeline.summarize_timeline_item")
def test_process_timeline_items(mock_summarize, mock_classify, db_session):
    """Test processing timeline items."""
    # Mock OpenAI functions
    mock_classify.side_effect = ["task", "idea", "note"]
    mock_summarize.side_effect = ["Summary 1", "Summary 2", "Summary 3"]

    # Create timeline items
    items = [
        TimelineItem(
            source_type="telegram",
            timestamp=datetime(2024, 1, 1, 12, i, 0),
            title=f"Test {i+1}",
            content=f"Content {i+1}",
            meta="{}",
        )
        for i in range(3)
    ]
    for item in items:
        db_session.add(item)
    db_session.flush()

    # Process items
    stats = process_timeline_items(db_session, limit=10)

    # Verify stats
    assert stats["total"] == 3
    assert stats["task"] == 1
    assert stats["idea"] == 1
    assert stats["note"] == 1
    assert stats["noise"] == 0

    # Verify MindItems were created
    mind_items = db_session.query(MindItem).all()
    assert len(mind_items) == 3

    # Verify each MindItem
    assert mind_items[0].item_type == "task"
    assert mind_items[0].summary == "Summary 1"
    assert mind_items[0].status == "new"
    assert mind_items[1].item_type == "idea"
    assert mind_items[2].item_type == "note"

    # Verify relationships
    assert mind_items[0].timeline_item_id == items[0].id
    assert mind_items[1].timeline_item_id == items[1].id
    assert mind_items[2].timeline_item_id == items[2].id


@patch("exocortex.modules.freeminder.pipeline.classify_timeline_item")
@patch("exocortex.modules.freeminder.pipeline.summarize_timeline_item")
def test_process_timeline_items_no_reprocessing(mock_summarize, mock_classify, db_session):
    """Test that processed items are not reprocessed."""
    # Mock OpenAI functions
    mock_classify.return_value = "task"
    mock_summarize.return_value = "Summary"

    # Create a timeline item
    item = TimelineItem(
        source_type="telegram",
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        title="Test",
        content="Content",
        meta="{}",
    )
    db_session.add(item)
    db_session.flush()

    # Process first time
    stats1 = process_timeline_items(db_session, limit=10)
    assert stats1["total"] == 1

    # Process again (should not reprocess)
    stats2 = process_timeline_items(db_session, limit=10)
    assert stats2["total"] == 0

    # Verify OpenAI was only called once
    assert mock_classify.call_count == 1
    assert mock_summarize.call_count == 1

    # Verify only one MindItem exists
    mind_items = db_session.query(MindItem).all()
    assert len(mind_items) == 1


@patch("exocortex.modules.freeminder.pipeline.classify_timeline_item")
@patch("exocortex.modules.freeminder.pipeline.summarize_timeline_item")
def test_process_calendar_task_planned_for(mock_summarize, mock_classify, db_session):
    """Test that calendar tasks get planned_for set from event start time."""
    # Mock OpenAI functions
    mock_classify.return_value = "task"
    mock_summarize.return_value = "Summary"

    # Create a calendar event
    calendar_event = CalendarEvent(
        calendar_id="primary",
        event_id="event1",
        title="Meeting",
        description="Team meeting",
        start_time=datetime(2024, 1, 2, 14, 0, 0),
        end_time=datetime(2024, 1, 2, 15, 0, 0),
        raw_json="{}",
    )
    db_session.add(calendar_event)
    db_session.flush()

    # Create timeline item linked to calendar event
    timeline_item = TimelineItem(
        source_type="calendar",
        timestamp=datetime(2024, 1, 2, 14, 0, 0),
        title="Meeting",
        content="Team meeting",
        meta="{}",
        calendar_event_id=calendar_event.id,
    )
    db_session.add(timeline_item)
    db_session.flush()

    # Process
    stats = process_timeline_items(db_session, limit=10)
    assert stats["total"] == 1
    assert stats["task"] == 1

    # Verify planned_for is set
    mind_item = db_session.query(MindItem).first()
    assert mind_item is not None
    assert mind_item.planned_for == calendar_event.start_time

