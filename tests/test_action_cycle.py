"""Tests for action cycle (planning and review) functionality."""

from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest

from exocortex.core.db import Base, get_session, init_db
from exocortex.core.models import CalendarEvent, MindItem, TimelineItem
from exocortex.cli.plan_tasks import get_unplanned_tasks
from exocortex.cli.review_tasks import get_tasks_for_review


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


def test_get_unplanned_tasks(db_session):
    """Test getting unplanned tasks."""
    # Create timeline items
    timeline_items = [
        TimelineItem(
            source_type="telegram",
            timestamp=datetime.now(),
            title="Task 1",
            content="Unplanned task",
            meta="{}",
        ),
        TimelineItem(
            source_type="telegram",
            timestamp=datetime.now(),
            title="Task 2",
            content="Already planned task",
            meta="{}",
        ),
        TimelineItem(
            source_type="telegram",
            timestamp=datetime.now(),
            title="Task 3",
            content="Task with status planned",
            meta="{}",
        ),
    ]
    for item in timeline_items:
        db_session.add(item)
    db_session.flush()

    # Create mind items
    # Task 1: unplanned (status=new, planned_start=None)
    task1 = MindItem(
        timeline_item_id=timeline_items[0].id,
        item_type="task",
        summary="Unplanned task",
        status="new",
        planned_start=None,
        created_at=datetime.now(),
    )

    # Task 2: already planned (has planned_start)
    task2 = MindItem(
        timeline_item_id=timeline_items[1].id,
        item_type="task",
        summary="Already planned task",
        status="new",
        planned_start=datetime.now() + timedelta(days=1),
        planned_end=datetime.now() + timedelta(days=1, hours=1),
        created_at=datetime.now(),
    )

    # Task 3: status is "planned" (should not appear)
    task3 = MindItem(
        timeline_item_id=timeline_items[2].id,
        item_type="task",
        summary="Task with status planned",
        status="planned",
        planned_start=None,
        created_at=datetime.now(),
    )

    db_session.add_all([task1, task2, task3])
    db_session.flush()

    # Get unplanned tasks
    unplanned = get_unplanned_tasks(db_session, limit=10)

    # Should only return task1
    assert len(unplanned) == 1
    assert unplanned[0].id == task1.id
    assert unplanned[0].summary == "Unplanned task"


def test_get_tasks_for_review(db_session):
    """Test getting tasks for review (overdue tasks)."""
    now = datetime.now()
    past_time = now - timedelta(hours=2)
    future_time = now + timedelta(hours=2)

    # Create timeline items
    timeline_items = [
        TimelineItem(
            source_type="telegram",
            timestamp=datetime.now(),
            title="Overdue task 1",
            content="Task with past planned_end",
            meta="{}",
        ),
        TimelineItem(
            source_type="telegram",
            timestamp=datetime.now(),
            title="Overdue task 2",
            content="Task with past planned_start (no end)",
            meta="{}",
        ),
        TimelineItem(
            source_type="telegram",
            timestamp=datetime.now(),
            title="Future task",
            content="Task in the future",
            meta="{}",
        ),
        TimelineItem(
            source_type="telegram",
            timestamp=datetime.now(),
            title="Done task",
            content="Already done task",
            meta="{}",
        ),
    ]
    for item in timeline_items:
        db_session.add(item)
    db_session.flush()

    # Create mind items
    # Task 1: overdue (planned_end < now)
    task1 = MindItem(
        timeline_item_id=timeline_items[0].id,
        item_type="task",
        summary="Overdue task 1",
        status="planned",
        planned_start=past_time - timedelta(hours=1),
        planned_end=past_time,
        created_at=datetime.now(),
    )

    # Task 2: overdue (planned_start < now, no planned_end)
    task2 = MindItem(
        timeline_item_id=timeline_items[1].id,
        item_type="task",
        summary="Overdue task 2",
        status="planned",
        planned_start=past_time,
        planned_end=None,
        created_at=datetime.now(),
    )

    # Task 3: future task (should not appear)
    task3 = MindItem(
        timeline_item_id=timeline_items[2].id,
        item_type="task",
        summary="Future task",
        status="planned",
        planned_start=future_time,
        planned_end=future_time + timedelta(hours=1),
        created_at=datetime.now(),
    )

    # Task 4: done task (should not appear)
    task4 = MindItem(
        timeline_item_id=timeline_items[3].id,
        item_type="task",
        summary="Done task",
        status="done",
        planned_start=past_time,
        planned_end=past_time + timedelta(hours=1),
        done_at=now - timedelta(hours=1),
        created_at=datetime.now(),
    )

    db_session.add_all([task1, task2, task3, task4])
    db_session.flush()

    # Get tasks for review
    review_tasks = get_tasks_for_review(db_session, limit=10)

    # Should return task1 and task2, but not task3 or task4
    assert len(review_tasks) == 2
    task_ids = [t.id for t in review_tasks]
    assert task1.id in task_ids
    assert task2.id in task_ids
    assert task3.id not in task_ids
    assert task4.id not in task_ids


def test_get_tasks_for_review_with_calendar_events(db_session):
    """Test that tasks with past calendar events are included in review."""
    now = datetime.now()
    past_time = now - timedelta(hours=2)

    # Create a past calendar event
    calendar_event = CalendarEvent(
        calendar_id="primary",
        event_id="past_event",
        title="Past Event",
        description="This event already happened",
        start_time=past_time,
        end_time=past_time + timedelta(hours=1),
        raw_json="{}",
    )
    db_session.add(calendar_event)
    db_session.flush()

    timeline_item = TimelineItem(
        source_type="calendar",
        timestamp=past_time,
        title="Past Event",
        content="This event already happened",
        meta="{}",
        calendar_event_id=calendar_event.id,
    )
    db_session.add(timeline_item)
    db_session.flush()

    # Create a task linked to the past calendar event
    task = MindItem(
        timeline_item_id=timeline_item.id,
        item_type="task",
        summary="Task from past calendar event",
        status="planned",
        planned_start=None,  # No planned time set
        planned_end=None,
        created_at=datetime.now(),
    )
    db_session.add(task)
    db_session.flush()

    # Get tasks for review
    review_tasks = get_tasks_for_review(db_session, limit=10)

    # Should include the task because its calendar event is in the past
    assert len(review_tasks) == 1
    assert review_tasks[0].id == task.id

