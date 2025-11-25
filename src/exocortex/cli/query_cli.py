"""CLI for querying Exocortex data."""

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from exocortex.core.config import config
from exocortex.core.db import get_session, init_db
from exocortex.core.models import MindItem, TimelineItem
from exocortex.memory.base_memory import get_user_profile
from exocortex.cli.query_helpers import (
    get_recent_items_by_type,
    get_recent_timeline_items,
    get_tasks_for_day,
)


def show_profile() -> None:
    """Print the loaded user profile."""
    try:
        profile = get_user_profile()
        print("User Profile:")
        print("=" * 50)
        print(f"ID: {profile.id}")
        print(f"Name: {profile.name}")
        print(f"Roles: {', '.join(profile.roles)}")
        print(f"\nCurrent Projects:")
        for project in profile.current_projects:
            print(f"  - {project}")
        print(f"\nPreferences:")
        print(json.dumps(profile.preferences, indent=2))
        print(f"\nNarrative:")
        print(profile.narrative)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        exit(1)
    except Exception as e:
        print(f"Error loading profile: {e}")
        exit(1)


def init_database() -> None:
    """Initialize the database and create all tables."""
    try:
        init_db()
        db_path = config.get_db_path()
        print(f"Database initialized successfully at: {db_path.absolute()}")
        
        # Check what tables were created
        from exocortex.core.db import engine
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if tables:
            print(f"\nTables created ({len(tables)}):")
            for table in tables:
                print(f"  - {table}")
        else:
            print("\nNo tables created yet (no ORM models defined).")
            print("Tables will be created when you add models (e.g., in M1).")
        
        print(f"\nDatabase file size: {db_path.stat().st_size} bytes")
    except Exception as e:
        print(f"Error initializing database: {e}")
        exit(1)


def check_database() -> None:
    """Check database status and show existing tables."""
    try:
        db_path = config.get_db_path()
        
        if not db_path.exists():
            print(f"Database file does not exist at: {db_path.absolute()}")
            print("Run --init-db to create it.")
            return
        
        print(f"Database location: {db_path.absolute()}")
        print(f"File size: {db_path.stat().st_size} bytes")
        print(f"File exists: ✓")
        
        # Check tables
        from exocortex.core.db import engine
        from sqlalchemy import inspect
        
        try:
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            print(f"\nTables in database ({len(tables)}):")
            if tables:
                for table in tables:
                    columns = inspector.get_columns(table)
                    print(f"  - {table} ({len(columns)} columns)")
                    for col in columns:
                        print(f"      • {col['name']}: {col['type']}")
            else:
                print("  (no tables yet)")
                print("\nThis is normal - tables will be created when you:")
                print("  1. Define ORM models (e.g., in M1)")
                print("  2. Run --init-db again")
        except Exception as e:
            print(f"\nError inspecting database: {e}")
            
    except Exception as e:
        print(f"Error checking database: {e}")
        exit(1)


def show_tasks_for_day(target_date: date, future_only: bool = False) -> None:
    """Print tasks for a specific day."""
    try:
        with get_session() as session:
            tasks = get_tasks_for_day(session, target_date, future_only=future_only)

            if not tasks:
                print(f"No tasks found for {target_date.strftime('%Y-%m-%d')}")
                return

            print(f"Tasks for {target_date.strftime('%Y-%m-%d')}:")
            print("=" * 70)

            for idx, task in enumerate(tasks, 1):
                # Get timeline item for source info
                timeline_item = task.timeline_item

                # Format time
                time_str = ""
                if task.planned_for:
                    time_str = task.planned_for.strftime("%H:%M")
                elif task.created_at:
                    time_str = task.created_at.strftime("%H:%M")

                # Format source
                source = timeline_item.source_type if timeline_item else "unknown"

                print(f"{idx}. {task.summary}")
                print(f"   [{time_str}] [{source}] Status: {task.status}")
                if task.planned_for:
                    print(f"   Planned for: {task.planned_for.strftime('%Y-%m-%d %H:%M')}")
                print()

    except Exception as e:
        print(f"Error: {e}")
        exit(1)


def show_recent_items(item_type: str, limit: int, future_only: bool = False) -> None:
    """Print recent items by type (ideas or notes)."""
    try:
        with get_session() as session:
            items = get_recent_items_by_type(
                session, item_type, limit=limit, future_only=future_only
            )

            if not items:
                print(f"No {item_type}s found")
                return

            print(f"Recent {item_type}s (last {len(items)}):")
            print("=" * 70)

            for idx, item in enumerate(items, 1):
                created_str = item.created_at.strftime("%Y-%m-%d %H:%M")
                print(f"{idx}. {item.summary}")
                print(f"   Created: {created_str}")
                print()

    except Exception as e:
        print(f"Error: {e}")
        exit(1)


def show_timeline(limit: int, future_only: bool = False) -> None:
    """Print recent timeline items."""
    try:
        with get_session() as session:
            items = get_recent_timeline_items(session, limit=limit, future_only=future_only)

            if not items:
                print("No timeline items found")
                return

            print(f"Recent timeline items (last {len(items)}):")
            print("=" * 70)

            for idx, item in enumerate(items, 1):
                timestamp_str = item.timestamp.strftime("%Y-%m-%d %H:%M")
                content_preview = item.content[:80] + "..." if len(item.content) > 80 else item.content
                title_str = f" - {item.title}" if item.title else ""

                print(f"{idx}. [{timestamp_str}] [{item.source_type}]{title_str}")
                print(f"   {content_preview}")
                print()

    except Exception as e:
        print(f"Error: {e}")
        exit(1)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Query Exocortex data")
    parser.add_argument(
        "--show-profile",
        action="store_true",
        help="Show the loaded user profile",
    )
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Initialize the database and create all tables",
    )
    parser.add_argument(
        "--check-db",
        action="store_true",
        help="Check database status and show existing tables",
    )
    parser.add_argument(
        "--tasks-today",
        action="store_true",
        help="Show tasks for today",
    )
    parser.add_argument(
        "--tasks-tomorrow",
        action="store_true",
        help="Show tasks for tomorrow",
    )
    parser.add_argument(
        "--last-ideas",
        type=int,
        metavar="N",
        help="Show last N ideas",
    )
    parser.add_argument(
        "--last-notes",
        type=int,
        metavar="N",
        help="Show last N notes",
    )
    parser.add_argument(
        "--timeline",
        type=int,
        metavar="N",
        help="Show last N timeline items",
    )
    parser.add_argument(
        "--future-only",
        action="store_true",
        help="Show only future events/items (exclude past calendar events)",
    )

    args = parser.parse_args()

    # Count how many query options are set
    query_options = [
        args.show_profile,
        args.init_db,
        args.check_db,
        args.tasks_today,
        args.tasks_tomorrow,
        args.last_ideas is not None,
        args.last_notes is not None,
        args.timeline is not None,
    ]
    active_options = sum(query_options)

    if active_options == 0:
        parser.print_help()
        return

    if active_options > 1:
        print("Error: Only one query option can be used at a time")
        parser.print_help()
        exit(1)

    # Execute the selected option
    if args.init_db:
        init_database()
    elif args.check_db:
        check_database()
    elif args.show_profile:
        show_profile()
    elif args.tasks_today:
        today = date.today()
        show_tasks_for_day(today, future_only=args.future_only)
    elif args.tasks_tomorrow:
        tomorrow = date.today() + timedelta(days=1)
        show_tasks_for_day(tomorrow, future_only=args.future_only)
    elif args.last_ideas is not None:
        show_recent_items("idea", args.last_ideas, future_only=args.future_only)
    elif args.last_notes is not None:
        show_recent_items("note", args.last_notes, future_only=args.future_only)
    elif args.timeline is not None:
        show_timeline(args.timeline, future_only=args.future_only)


if __name__ == "__main__":
    main()

