"""Helper functions for querying Exocortex data."""

from datetime import date, datetime, timedelta
from typing import List

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from exocortex.core.models import CalendarEvent, MindItem, TimelineItem


def get_tasks_for_day(
    session: Session, target_date: date, future_only: bool = False
) -> List[MindItem]:
    """
    Get tasks for a specific day.

    Tasks are selected where:
    - item_type = "task"
    - status in ("new", "planned")
    - planned_for is on target_date OR (if planned_for is null) created_at is on target_date
    - If future_only=True: exclude past calendar events (start_time < now)

    Args:
        session: Database session
        target_date: Target date (local time)
        future_only: If True, exclude past calendar events

    Returns:
        List of MindItem objects
    """
    # Convert date to datetime range (start and end of day)
    start_of_day = datetime.combine(target_date, datetime.min.time())
    end_of_day = datetime.combine(target_date, datetime.max.time())
    now = datetime.now()

    # Base query
    query = session.query(MindItem).filter(
        MindItem.item_type == "task",
        MindItem.status.in_(["new", "planned"]),
        or_(
            and_(
                MindItem.planned_for >= start_of_day,
                MindItem.planned_for <= end_of_day,
            ),
            and_(
                MindItem.planned_for.is_(None),
                MindItem.created_at >= start_of_day,
                MindItem.created_at <= end_of_day,
            ),
        ),
    )

    # Apply future_only filter if requested
    if future_only:
        query = (
            query.join(TimelineItem, MindItem.timeline_item_id == TimelineItem.id)
            .outerjoin(CalendarEvent, TimelineItem.calendar_event_id == CalendarEvent.id)
            .filter(
                # Include all non-calendar items, or calendar events that haven't started yet
                or_(
                    CalendarEvent.id.is_(None),  # Not a calendar event
                    CalendarEvent.start_time >= now,  # Calendar event hasn't started yet
                )
            )
        )

    tasks = query.order_by(
        MindItem.planned_for.asc().nullslast(), MindItem.created_at.asc()
    ).all()

    return tasks


def get_recent_items_by_type(
    session: Session, item_type: str, limit: int = 20, future_only: bool = False
) -> List[MindItem]:
    """
    Get recent MindItems by type.

    Args:
        session: Database session
        item_type: Type of item ("idea", "note", etc.)
        limit: Maximum number of items to return
        future_only: If True, exclude past calendar events (start_time < now)

    Returns:
        List of MindItem objects ordered by created_at desc
    """
    now = datetime.now()

    # Base query
    query = session.query(MindItem).filter(MindItem.item_type == item_type)

    # Apply future_only filter if requested
    if future_only:
        query = (
            query.join(TimelineItem, MindItem.timeline_item_id == TimelineItem.id)
            .outerjoin(CalendarEvent, TimelineItem.calendar_event_id == CalendarEvent.id)
            .filter(
                # Include all non-calendar items, or calendar events that haven't started yet
                or_(
                    CalendarEvent.id.is_(None),  # Not a calendar event
                    CalendarEvent.start_time >= now,  # Calendar event hasn't started yet
                )
            )
        )

    items = query.order_by(MindItem.created_at.desc()).limit(limit).all()

    return items


def get_recent_timeline_items(
    session: Session, limit: int = 30, future_only: bool = False
) -> List[TimelineItem]:
    """
    Get recent TimelineItems.

    Args:
        session: Database session
        limit: Maximum number of items to return
        future_only: If True, exclude past calendar events (start_time < now)

    Returns:
        List of TimelineItem objects ordered by timestamp desc
    """
    # Base query
    query = session.query(TimelineItem)

    # Apply future_only filter if requested
    if future_only:
        now = datetime.now()
        query = (
            query.outerjoin(CalendarEvent, TimelineItem.calendar_event_id == CalendarEvent.id)
            .filter(
                # Include all non-calendar items, or calendar events that haven't started yet
                or_(
                    CalendarEvent.id.is_(None),  # Not a calendar event
                    CalendarEvent.start_time >= now,  # Calendar event hasn't started yet
                )
            )
        )

    items = query.order_by(TimelineItem.timestamp.desc()).limit(limit).all()

    return items

