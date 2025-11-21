"""CLI command to import messages from Telegram."""

import argparse
import logging
from typing import Optional

from exocortex.core.db import get_session
from exocortex.core.models import TelegramMessage, TimelineItem
from exocortex.integrations.telegram_client import fetch_recent_messages

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def import_telegram_messages(limit: int = 50) -> tuple[int, int]:
    """
    Import Telegram messages and create corresponding timeline items.

    Args:
        limit: Maximum number of messages to fetch

    Returns:
        Tuple of (telegram_messages_created, timeline_items_created)
    """
    # Fetch messages from Telegram
    try:
        messages = fetch_recent_messages(limit=limit)
    except Exception as e:
        error_msg = str(e)
        if "Flood control" in error_msg or "429" in error_msg:
            logger.error(f"Telegram rate limit exceeded: {e}")
            logger.info("Please wait a few minutes before trying again.")
        else:
            logger.error(f"Failed to fetch messages from Telegram: {e}")
        raise

    if not messages:
        logger.info("No messages to import")
        return (0, 0)

    telegram_count = 0
    timeline_count = 0

    with get_session() as session:
        for msg_payload in messages:
            # Check if message already exists (by chat_id + message_id)
            existing = (
                session.query(TelegramMessage)
                .filter(
                    TelegramMessage.chat_id == msg_payload.chat_id,
                    TelegramMessage.message_id == msg_payload.message_id,
                )
                .first()
            )

            if existing:
                logger.debug(f"Message {msg_payload.message_id} already exists, skipping")
                continue

            # Create TelegramMessage
            telegram_msg = TelegramMessage(
                chat_id=msg_payload.chat_id,
                message_id=msg_payload.message_id,
                sender=msg_payload.sender,
                text=msg_payload.text,
                timestamp=msg_payload.timestamp,
                raw_json=msg_payload.raw_json,
            )
            session.add(telegram_msg)
            session.flush()  # Get the ID

            telegram_count += 1

            # Create corresponding TimelineItem
            content = msg_payload.text or "[No text content]"
            title = None
            if msg_payload.text:
                # Use first line or first 100 chars as title
                first_line = msg_payload.text.split("\n")[0]
                title = first_line[:100] if len(first_line) > 100 else first_line

            timeline_item = TimelineItem(
                source_type="telegram",
                source_id=telegram_msg.id,
                telegram_message_id=telegram_msg.id,
                timestamp=msg_payload.timestamp,
                title=title,
                content=content,
                meta=msg_payload.raw_json,
            )
            session.add(timeline_item)
            timeline_count += 1

    logger.info(f"Imported {telegram_count} Telegram messages and {timeline_count} timeline items")
    return (telegram_count, timeline_count)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Import messages from Telegram")
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of messages to fetch (default: 50)",
    )

    args = parser.parse_args()

    try:
        telegram_count, timeline_count = import_telegram_messages(limit=args.limit)
        print(f"✓ Imported {telegram_count} Telegram messages")
        print(f"✓ Created {timeline_count} timeline items")
    except Exception as e:
        print(f"Error: {e}")
        exit(1)


if __name__ == "__main__":
    main()

