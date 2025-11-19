"""CLI for querying Exocortex data."""

import argparse
import json
from pathlib import Path
from typing import Any

from exocortex.core.config import config
from exocortex.core.db import init_db
from exocortex.memory.base_memory import get_user_profile


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

    args = parser.parse_args()

    if args.init_db:
        init_database()
    elif args.check_db:
        check_database()
    elif args.show_profile:
        show_profile()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

