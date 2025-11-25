"""CLI command to review overdue tasks."""

import argparse
import sys
from datetime import datetime
from typing import List

from exocortex.core.db import get_session
from exocortex.core.models import CalendarEvent, MindItem, TimelineItem


def get_tasks_for_review(session, limit: int = 50, all_tasks: bool = False) -> List[MindItem]:
    """
    Get tasks that should be reviewed.

    Selects tasks where:
    - item_type = "task"
    - status in ("new", "planned", "in_progress")
    - If all_tasks=False (default): only overdue tasks
      - (planned_end < now OR (planned_end is null AND planned_start < now))
      - OR tasks whose linked calendar event is in the past
    - If all_tasks=True: all tasks regardless of due date

    Args:
        session: Database session
        limit: Maximum number of tasks to return
        all_tasks: If True, return all tasks; if False, only overdue tasks

    Returns:
        List of MindItem objects
    """
    from sqlalchemy import and_, or_

    # Base query
    query = (
        session.query(MindItem)
        .join(TimelineItem, MindItem.timeline_item_id == TimelineItem.id)
        .outerjoin(CalendarEvent, TimelineItem.calendar_event_id == CalendarEvent.id)
        .filter(
            MindItem.item_type == "task",
            MindItem.status.in_(["new", "planned", "in_progress"]),
        )
    )

    # Apply overdue filter only if not showing all tasks
    if not all_tasks:
        now = datetime.now()
        query = query.filter(
            # Overdue: planned_end < now OR (planned_end is null AND planned_start < now)
            # OR calendar event is in the past
            or_(
                # Task with planned_end in the past
                and_(
                    MindItem.planned_end.isnot(None),
                    MindItem.planned_end < now,
                ),
                # Task with planned_start in the past but no planned_end
                and_(
                    MindItem.planned_end.is_(None),
                    MindItem.planned_start.isnot(None),
                    MindItem.planned_start < now,
                ),
                # Calendar event is in the past
                and_(
                    CalendarEvent.id.isnot(None),
                    CalendarEvent.start_time < now,
                ),
            ),
        )

    tasks = (
        query.order_by(
            MindItem.planned_end.asc().nullslast(), MindItem.planned_start.asc().nullslast()
        )
        .limit(limit)
        .all()
    )

    return tasks


def review_task_interactive(task: MindItem, session) -> bool:
    """
    Interactively review a single task.

    Args:
        task: MindItem to review
        session: Database session

    Returns:
        True if should continue, False if quit
    """
    timeline_item = task.timeline_item

    # Print task info
    print(f"\nTask #{task.id}: {task.summary}")
    print(f"  Status: {task.status}")
    if task.planned_start:
        print(f"  Planned: {task.planned_start.strftime('%Y-%m-%d %H:%M')}", end="")
        if task.planned_end:
            print(f" - {task.planned_end.strftime('%H:%M')}")
        else:
            print()
    if timeline_item:
        print(f"  Source: {timeline_item.source_type}")
        if hasattr(timeline_item, "calendar_event") and timeline_item.calendar_event:
            event = timeline_item.calendar_event
            print(f"  Calendar event: {event.title} ({event.start_time.strftime('%Y-%m-%d %H:%M')})")

    # Prompt user
    while True:
        response = input("\nMark as done? [y]es / [n]o / [c]omment / [s]kip / [q]uit: ").strip().lower()

        if response == "q":
            return False  # Signal to quit

        if response == "s":
            return True  # Skip, but continue with next task

        if response == "n":
            return True  # Leave as is, continue

        if response == "y":
            # Mark as done
            task.status = "done"
            task.done_at = datetime.now()
            task.completion_comment = None
            session.add(task)
            session.flush()
            print("✓ Marked as done.")
            return True

        if response == "c":
            # Ask for comment
            comment = input("Enter completion comment: ").strip()
            task.status = "done"
            task.done_at = datetime.now()
            task.completion_comment = comment
            session.add(task)
            session.flush()
            print("✓ Marked as done with comment.")
            return True

        print("Invalid option. Please choose y, n, c, s, or q.")

    return True


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Review overdue tasks")
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of tasks to show (default: 50)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Show all tasks (not just overdue ones)",
    )

    args = parser.parse_args()

    try:
        with get_session() as session:
            tasks = get_tasks_for_review(session, limit=args.limit, all_tasks=args.all)

            if not tasks:
                if args.all:
                    print("No tasks found.")
                else:
                    print("No tasks need review.")
                return

            if args.all:
                print(f"Found {len(tasks)} task(s).")
            else:
                print(f"Found {len(tasks)} task(s) that need review.")
            print("Reviewing tasks... (press 'q' at any time to quit)\n")

            done_count = 0
            for task in tasks:
                result = review_task_interactive(task, session)
                if result is False:  # User quit
                    print("\nReview interrupted by user.")
                    break
                if task.status == "done":
                    done_count += 1

            session.commit()

            print(f"\n✓ Marked {done_count} task(s) as done.")

    except KeyboardInterrupt:
        print("\n\nReview interrupted.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

