"""CLI command to plan tasks interactively."""

import argparse
import sys
from datetime import date, datetime, time, timedelta
from typing import List, Optional

from exocortex.core.db import get_session
from exocortex.core.models import MindItem, TimelineItem
from exocortex.planning.slots import suggest_slots


def get_unplanned_tasks(session, limit: int = 20) -> List[MindItem]:
    """
    Get tasks that need planning.

    Selects tasks where:
    - item_type = "task"
    - status is null or status = "new"
    - planned_start is null

    Args:
        session: Database session
        limit: Maximum number of tasks to return

    Returns:
        List of MindItem objects
    """
    from sqlalchemy import or_

    tasks = (
        session.query(MindItem)
        .join(TimelineItem, MindItem.timeline_item_id == TimelineItem.id)
        .filter(
            MindItem.item_type == "task",
            or_(MindItem.status.is_(None), MindItem.status == "new"),
            MindItem.planned_start.is_(None),
        )
        .order_by(MindItem.created_at.asc())
        .limit(limit)
        .all()
    )

    return tasks


def parse_datetime_input(date_str: str, default_time: time = time(10, 0)) -> datetime:
    """
    Parse datetime input from user.

    Supports:
    - "YYYY-MM-DD" -> date with default_time
    - "YYYY-MM-DD HH:MM" -> full datetime

    Args:
        date_str: Date/datetime string from user
        default_time: Default time to use if only date provided

    Returns:
        datetime object

    Raises:
        ValueError: If input cannot be parsed
    """
    date_str = date_str.strip()

    # Try parsing as full datetime first
    try:
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M")
    except ValueError:
        pass

    # Try parsing as date only
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        return datetime.combine(date_obj, default_time)
    except ValueError:
        pass

    raise ValueError(f"Invalid date format: {date_str}. Expected YYYY-MM-DD or YYYY-MM-DD HH:MM")


def plan_task_interactive(task: MindItem, session) -> bool:
    """
    Interactively plan a single task.

    Args:
        task: MindItem to plan
        session: Database session

    Returns:
        True if task was planned, False if skipped or quit
    """
    timeline_item = task.timeline_item

    # Print task info
    print(f"\nTask #{task.id}: {task.summary}")
    if timeline_item:
        print(f"  Source: {timeline_item.source_type}")
        if timeline_item.timestamp:
            print(f"  Created: {timeline_item.timestamp.strftime('%Y-%m-%d %H:%M')}")
    if task.created_at:
        print(f"  Added: {task.created_at.strftime('%Y-%m-%d %H:%M')}")

    # Prompt user
    while True:
        response = input("\n[s]kip / [t]oday / [m]tomorrow / [d]ate / [a]uto / [q]uit: ").strip().lower()

        if response == "q":
            return False  # Signal to quit

        if response == "s":
            return True  # Skip, but continue with next task

        if response == "a":
            # Auto-suggest slots
            slots = suggest_slots(session, days_ahead=7, max_suggestions=3)
            if not slots:
                print("No free slots found in the next 7 days. Try [d]ate or adjust preferences.")
                continue

            # Display available slots
            print("\nAvailable slots:")
            for i, slot in enumerate(slots, 1):
                energy_label = f" ({slot.energy_level} energy)" if slot.energy_level else ""
                print(f"  {i}) {slot.start.strftime('%Y-%m-%d %H:%M')}–{slot.end.strftime('%H:%M')}{energy_label}")

            # Prompt for slot selection
            while True:
                slot_input = input("Choose a slot number or [s]kip: ").strip().lower()
                if slot_input == "s":
                    return True  # Skip this task

                try:
                    slot_num = int(slot_input)
                    if 1 <= slot_num <= len(slots):
                        selected_slot = slots[slot_num - 1]
                        planned_start = selected_slot.start
                        planned_end = selected_slot.end
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(slots)}.")
                except ValueError:
                    print("Invalid input. Please enter a number or 's' to skip.")

            # Break out of outer loop
            break

        if response == "t":
            # Plan for today at 10:00
            today = date.today()
            planned_start = datetime.combine(today, time(10, 0))
            planned_end = planned_start + timedelta(hours=1)
            break

        if response == "m":
            # Plan for tomorrow at 10:00
            tomorrow = date.today() + timedelta(days=1)
            planned_start = datetime.combine(tomorrow, time(10, 0))
            planned_end = planned_start + timedelta(hours=1)
            break

        if response == "d":
            # Ask for date
            date_input = input("Enter date (YYYY-MM-DD) or datetime (YYYY-MM-DD HH:MM): ").strip()
            try:
                planned_start = parse_datetime_input(date_input)
                planned_end = planned_start + timedelta(hours=1)
                break
            except ValueError as e:
                print(f"Error: {e}")
                continue

        print("Invalid option. Please choose s, t, m, d, a, or q.")

    # Update task
    task.planned_start = planned_start
    task.planned_end = planned_end
    task.status = "planned"
    session.add(task)
    session.flush()

    print(f"✓ Planned for {planned_start.strftime('%Y-%m-%d %H:%M')} - {planned_end.strftime('%H:%M')}")
    return True


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Interactively plan tasks")
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of tasks to show (default: 20)",
    )

    args = parser.parse_args()

    try:
        with get_session() as session:
            tasks = get_unplanned_tasks(session, limit=args.limit)

            if not tasks:
                print("No unplanned tasks found.")
                return

            print(f"Found {len(tasks)} unplanned task(s).")
            print("Planning tasks... (press 'q' at any time to quit)\n")

            planned_count = 0
            for task in tasks:
                result = plan_task_interactive(task, session)
                if result is False:  # User quit
                    print("\nPlanning interrupted by user.")
                    break
                if task.status == "planned":
                    planned_count += 1

            session.commit()

            print(f"\n✓ Planned {planned_count} task(s).")

    except KeyboardInterrupt:
        print("\n\nPlanning interrupted.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

