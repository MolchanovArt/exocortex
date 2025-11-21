"""CLI command to run the FreeMinder pipeline."""

import argparse
import logging

from exocortex.core.db import get_session
from exocortex.modules.freeminder.pipeline import process_timeline_items

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Run FreeMinder pipeline to classify timeline items")
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of timeline items to process (default: 50)",
    )

    args = parser.parse_args()

    try:
        with get_session() as session:
            stats = process_timeline_items(session, limit=args.limit)

            # Print summary
            total = stats["total"]
            if total == 0:
                print("No timeline items to process.")
            else:
                print(f"Processed {total} items:")
                print(f"  - {stats['task']} tasks")
                print(f"  - {stats['idea']} ideas")
                print(f"  - {stats['note']} notes")
                print(f"  - {stats['noise']} noise")

    except Exception as e:
        logger.error(f"Error running FreeMinder pipeline: {e}")
        print(f"Error: {e}")
        exit(1)


if __name__ == "__main__":
    main()

