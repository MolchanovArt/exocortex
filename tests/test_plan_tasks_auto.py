"""Tests for plan_tasks auto mode."""

from datetime import date, datetime, timedelta, time
from unittest.mock import patch

import pytest

from exocortex.core.db import Base, get_session, init_db
from exocortex.core.models import CalendarEvent, MindItem, TimelineItem
from exocortex.planning.slots import SuggestedSlot


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


def test_plan_task_with_auto_slot(db_session):
    """Test that a task can be planned using auto-suggested slot."""
    from exocortex.cli.plan_tasks import plan_task_interactive

    # Create a timeline item
    timeline_item = TimelineItem(
        source_type="telegram",
        timestamp=datetime.now(),
        title="Test Task",
        content="Test task content",
        meta="{}",
    )
    db_session.add(timeline_item)
    db_session.flush()

    # Create an unplanned task
    task = MindItem(
        timeline_item_id=timeline_item.id,
        item_type="task",
        summary="Test Task",
        status="new",
        planned_start=None,
        created_at=datetime.now(),
    )
    db_session.add(task)
    db_session.flush()

    # Mock suggest_slots to return a deterministic slot
    tomorrow = date.today() + timedelta(days=1)
    mock_slot = SuggestedSlot(
        start=datetime.combine(tomorrow, time(11, 0)),
        end=datetime.combine(tomorrow, time(12, 0)),
        reason="free slot",
        energy_level="high",
    )

    with patch("exocortex.cli.plan_tasks.suggest_slots", return_value=[mock_slot]):
        # Mock input to select auto mode and choose slot 1
        with patch("builtins.input", side_effect=["a", "1"]):
            result = plan_task_interactive(task, db_session)

            # Task should be planned
            assert result is True
            assert task.status == "planned"
            assert task.planned_start == mock_slot.start
            assert task.planned_end == mock_slot.end


def test_plan_task_auto_no_slots(db_session):
    """Test auto mode when no slots are available."""
    from exocortex.cli.plan_tasks import plan_task_interactive

    # Create a timeline item
    timeline_item = TimelineItem(
        source_type="telegram",
        timestamp=datetime.now(),
        title="Test Task",
        content="Test task content",
        meta="{}",
    )
    db_session.add(timeline_item)
    db_session.flush()

    # Create an unplanned task
    task = MindItem(
        timeline_item_id=timeline_item.id,
        item_type="task",
        summary="Test Task",
        status="new",
        planned_start=None,
        created_at=datetime.now(),
    )
    db_session.add(task)
    db_session.flush()

    # Mock suggest_slots to return empty list
    with patch("exocortex.cli.plan_tasks.suggest_slots", return_value=[]):
        # Mock input: auto mode, then skip when no slots
        with patch("builtins.input", side_effect=["a", "s"]):
            result = plan_task_interactive(task, db_session)

            # Task should be skipped (not planned)
            assert result is True
            assert task.status != "planned"
            assert task.planned_start is None

