"""FreeMinder pipeline: classify and process timeline items."""

import logging
from datetime import datetime
from typing import Dict, List

from sqlalchemy.orm import Session

from exocortex.core.models import MindItem, TimelineItem
from exocortex.core.openai_client import classify_timeline_item, summarize_timeline_item
from exocortex.memory.base_memory import get_user_profile

logger = logging.getLogger(__name__)


def get_unprocessed_timeline_items(session: Session, limit: int = 50) -> List[TimelineItem]:
    """
    Get timeline items that have not been processed yet (no linked MindItem).

    Args:
        session: Database session
        limit: Maximum number of items to return

    Returns:
        List of TimelineItem objects that don't have a MindItem yet
    """
    # Find TimelineItems that don't have a corresponding MindItem
    processed_ids = session.query(MindItem.timeline_item_id).subquery()

    unprocessed = (
        session.query(TimelineItem)
        .filter(~TimelineItem.id.in_(session.query(processed_ids)))
        .order_by(TimelineItem.timestamp.desc())
        .limit(limit)
        .all()
    )

    return unprocessed


def process_timeline_items(session: Session, limit: int = 50) -> Dict[str, int]:
    """
    Process unprocessed timeline items: classify and summarize using OpenAI.

    Args:
        session: Database session
        limit: Maximum number of items to process

    Returns:
        Dictionary with stats: {
            "total": total processed,
            "task": count of tasks,
            "idea": count of ideas,
            "note": count of notes,
            "noise": count of noise
        }
    """
    # Load user profile for context
    try:
        user_profile = get_user_profile()
    except Exception as e:
        logger.warning(f"Failed to load user profile: {e}. Continuing without profile context.")
        user_profile = None

    # Get unprocessed items
    items = get_unprocessed_timeline_items(session, limit=limit)

    if not items:
        logger.info("No unprocessed timeline items found")
        return {"total": 0, "task": 0, "idea": 0, "note": 0, "noise": 0}

    stats = {"total": 0, "task": 0, "idea": 0, "note": 0, "noise": 0}

    for item in items:
        try:
            # Build text input from TimelineItem
            text_parts = []
            if item.title:
                text_parts.append(f"Title: {item.title}")
            text_parts.append(item.content)
            if item.source_type:
                text_parts.append(f"[Source: {item.source_type}]")

            text = "\n".join(text_parts)

            # Classify and summarize
            item_type = classify_timeline_item(text, user_profile)
            summary = summarize_timeline_item(text, user_profile)

            # Determine planned_for (simple heuristic)
            planned_for = None
            if item_type == "task" and item.source_type == "calendar":
                # For calendar tasks, use the event start time
                if hasattr(item, "calendar_event") and item.calendar_event:
                    planned_for = item.calendar_event.start_time

            # Create MindItem
            mind_item = MindItem(
                timeline_item_id=item.id,
                item_type=item_type,
                summary=summary,
                status="new",
                planned_for=planned_for,
                created_at=datetime.utcnow(),
            )

            session.add(mind_item)
            stats["total"] += 1
            stats[item_type] += 1

            logger.debug(f"Processed timeline item {item.id} as {item_type}")

        except Exception as e:
            logger.error(f"Error processing timeline item {item.id}: {e}")
            # Continue with next item instead of failing completely
            continue

    return stats

