"""Telegram integration client."""

import asyncio
import json
import logging
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from telegram import Bot
from telegram.error import TelegramError, TimedOut, NetworkError

from exocortex.core.config import config

logger = logging.getLogger(__name__)


class TelegramMessagePayload(BaseModel):
    """Pydantic model for raw Telegram message data."""

    message_id: int = Field(..., description="Telegram message ID")
    chat_id: str = Field(..., description="Chat ID as string")
    sender: Optional[str] = Field(None, description="Sender username or name")
    text: Optional[str] = Field(None, description="Message text content")
    timestamp: datetime = Field(..., description="Message timestamp")
    raw_json: str = Field(..., description="Raw message data as JSON string")


async def _fetch_recent_messages_async(limit: int = 50) -> List[TelegramMessagePayload]:
    """
    Async implementation of fetch_recent_messages.

    Args:
        limit: Maximum number of messages to fetch

    Returns:
        List of TelegramMessagePayload objects

    Raises:
        ValueError: If Telegram credentials are not configured
        TelegramError: If there's an error communicating with Telegram API
    """
    if not config.telegram_bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set in configuration")

    if not config.telegram_target_chat_id:
        raise ValueError("TELEGRAM_TARGET_CHAT_ID is not set in configuration")

    bot = Bot(token=config.telegram_bot_token)
    target_chat_id = config.telegram_target_chat_id

    messages: List[TelegramMessagePayload] = []

    try:
        # Get updates (messages) from the bot
        # Note: This only gets messages sent to the bot or in chats where the bot is a member
        # python-telegram-bot v20 is async-first
        updates = await bot.get_updates(limit=limit * 2, timeout=10)  # Get more to filter by chat_id

        for update in updates:
            if not update.message:
                continue

            message = update.message
            chat_id_str = str(message.chat.id)

            # Filter by target chat ID
            if chat_id_str != target_chat_id:
                continue

            # Extract sender information
            sender = None
            if message.from_user:
                sender = message.from_user.username or message.from_user.first_name
                if message.from_user.last_name:
                    sender = f"{sender} {message.from_user.last_name}"

            # Convert message to JSON for raw storage
            try:
                # Use model_dump for Pydantic v2 or to_dict for older versions
                if hasattr(message, "model_dump"):
                    msg_dict = message.model_dump(mode="json")
                else:
                    msg_dict = message.to_dict()
                raw_json = json.dumps(msg_dict, default=str, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"Failed to serialize message {message.message_id} to JSON: {e}")
                raw_json = "{}"

            payload = TelegramMessagePayload(
                message_id=message.message_id,
                chat_id=chat_id_str,
                sender=sender,
                text=message.text,
                timestamp=message.date,
                raw_json=raw_json,
            )

            messages.append(payload)

            # Stop if we've collected enough messages
            if len(messages) >= limit:
                break

    except TelegramError as e:
        logger.error(f"Telegram API error: {e}")
        # Try to close bot, but don't fail if it errors (e.g., rate limit)
        try:
            await bot.close()
        except Exception as close_error:
            # Silently ignore close errors, especially rate limits
            logger.debug(f"Error closing bot (non-critical): {close_error}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching Telegram messages: {e}")
        # Try to close bot, but don't fail if it errors
        try:
            await bot.close()
        except Exception as close_error:
            # Silently ignore close errors
            logger.debug(f"Error closing bot (non-critical): {close_error}")
        raise

    # Close the bot session normally
    # Note: We don't strictly need to close the bot, but it's good practice
    # However, if there's a rate limit or other error, we can safely ignore it
    # since the messages have already been fetched successfully
    try:
        await bot.close()
    except (TelegramError, TimedOut, NetworkError) as e:
        # Ignore rate limits and network errors on close - they're non-critical
        # The messages have already been fetched, so closing is just cleanup
        error_msg = str(e)
        if "429" in error_msg or "Too Many Requests" in error_msg or "rate limit" in error_msg.lower():
            logger.debug(f"Rate limit on bot.close() - safely ignored (messages already fetched)")
        else:
            logger.debug(f"Error closing bot (non-critical): {e}")
    except Exception as e:
        # Catch any other exceptions and ignore them
        logger.debug(f"Error closing bot (non-critical): {e}")

    logger.info(f"Fetched {len(messages)} messages from chat {target_chat_id}")
    return messages


def fetch_recent_messages(limit: int = 50) -> List[TelegramMessagePayload]:
    """
    Fetch recent messages from the configured Telegram chat (synchronous wrapper).

    Args:
        limit: Maximum number of messages to fetch

    Returns:
        List of TelegramMessagePayload objects

    Raises:
        ValueError: If Telegram credentials are not configured
        TelegramError: If there's an error communicating with Telegram API
    """
    return asyncio.run(_fetch_recent_messages_async(limit=limit))

