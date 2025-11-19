"""CLI for querying Exocortex data."""

import argparse
import json
from typing import Any

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


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Query Exocortex data")
    parser.add_argument(
        "--show-profile",
        action="store_true",
        help="Show the loaded user profile",
    )

    args = parser.parse_args()

    if args.show_profile:
        show_profile()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

