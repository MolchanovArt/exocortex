"""Tests for Telegram import functionality."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from exocortex.core.db import Base, get_session, init_db
from exocortex.core.models import TelegramMessage, TimelineItem
from exocortex.integrations.telegram_client import TelegramMessagePayload, fetch_recent_messages


@pytest.fixture
def db_session(tmp_path, monkeypatch):
    """Create a temporary database for testing."""
    import exocortex.core.config as config_module
    import exocortex.core.db as db_module

    # Create a temporary database file
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(config_module.config, "exocortex_db_path", str(test_db))

    # Reinitialize the engine with the new path
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{test_db}", connect_args={"check_same_thread": False})
    db_module.engine = engine
    db_module.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db_module.Base = Base

    # Create tables
    Base.metadata.create_all(bind=engine)

    # Create a session
    session = db_module.SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def test_telegram_message_payload():
    """Test TelegramMessagePayload Pydantic model."""
    payload = TelegramMessagePayload(
        message_id=123,
        chat_id="-1001234567890",
        sender="test_user",
        text="Hello, world!",
        timestamp=datetime.now(),
        raw_json='{"test": "data"}',
    )

    assert payload.message_id == 123
    assert payload.chat_id == "-1001234567890"
    assert payload.sender == "test_user"
    assert payload.text == "Hello, world!"


@patch("exocortex.integrations.telegram_client.Bot")
def test_fetch_recent_messages_mock(mock_bot_class):
    """Test fetch_recent_messages with mocked Telegram API."""
    # Mock bot instance
    mock_bot = MagicMock()
    mock_bot_class.return_value = mock_bot

    # Mock message objects
    mock_message1 = MagicMock()
    mock_message1.message_id = 1
    mock_message1.chat.id = -1001234567890
    mock_message1.from_user.username = "user1"
    mock_message1.from_user.first_name = "User"
    mock_message1.from_user.last_name = None
    mock_message1.text = "Test message 1"
    mock_message1.date = datetime(2024, 1, 1, 12, 0, 0)
    # Try both to_dict and model_dump for compatibility
    if hasattr(mock_message1, "to_dict"):
        mock_message1.to_dict.return_value = {"message_id": 1, "text": "Test message 1"}
    if hasattr(mock_message1, "model_dump"):
        mock_message1.model_dump.return_value = {"message_id": 1, "text": "Test message 1"}

    mock_message2 = MagicMock()
    mock_message2.message_id = 2
    mock_message2.chat.id = -1001234567890
    mock_message2.from_user.username = None
    mock_message2.from_user.first_name = "User"
    mock_message2.from_user.last_name = "Two"
    mock_message2.text = "Test message 2"
    mock_message2.date = datetime(2024, 1, 1, 12, 1, 0)
    if hasattr(mock_message2, "to_dict"):
        mock_message2.to_dict.return_value = {"message_id": 2, "text": "Test message 2"}
    if hasattr(mock_message2, "model_dump"):
        mock_message2.model_dump.return_value = {"message_id": 2, "text": "Test message 2"}

    mock_update1 = MagicMock()
    mock_update1.message = mock_message1
    mock_update2 = MagicMock()
    mock_update2.message = mock_message2

    mock_bot.get_updates.return_value = [mock_update1, mock_update2]

    # Mock config
    with patch("exocortex.integrations.telegram_client.config") as mock_config:
        mock_config.telegram_bot_token = "test_token"
        mock_config.telegram_target_chat_id = "-1001234567890"

        messages = fetch_recent_messages(limit=10)

        assert len(messages) == 2
        assert messages[0].message_id == 1
        assert messages[0].text == "Test message 1"
        assert messages[1].message_id == 2
        assert messages[1].text == "Test message 2"


def test_import_telegram_messages(db_session):
    """Test importing Telegram messages and creating timeline items."""
    from exocortex.cli.import_telegram import import_telegram_messages

    # Create mock message payloads
    mock_messages = [
        TelegramMessagePayload(
            message_id=1,
            chat_id="-1001234567890",
            sender="user1",
            text="First message",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            raw_json='{"message_id": 1}',
        ),
        TelegramMessagePayload(
            message_id=2,
            chat_id="-1001234567890",
            sender="user2",
            text="Second message\nWith multiple lines",
            timestamp=datetime(2024, 1, 1, 12, 1, 0),
            raw_json='{"message_id": 2}',
        ),
    ]

    # Mock fetch_recent_messages
    with patch("exocortex.cli.import_telegram.fetch_recent_messages", return_value=mock_messages):
        # Mock get_session to use our test session
        with patch("exocortex.cli.import_telegram.get_session") as mock_get_session:
            # Create a context manager that yields our test session
            from contextlib import contextmanager

            @contextmanager
            def session_context():
                yield db_session

            mock_get_session.return_value = session_context()

            telegram_count, timeline_count = import_telegram_messages(limit=10)

            assert telegram_count == 2
            assert timeline_count == 2

            # Verify TelegramMessage records
            telegram_messages = db_session.query(TelegramMessage).all()
            assert len(telegram_messages) == 2
            assert telegram_messages[0].message_id == 1
            assert telegram_messages[0].text == "First message"
            assert telegram_messages[1].message_id == 2

            # Verify TimelineItem records
            timeline_items = db_session.query(TimelineItem).all()
            assert len(timeline_items) == 2
            assert timeline_items[0].source_type == "telegram"
            assert timeline_items[0].content == "First message"
            assert timeline_items[1].content == "Second message\nWith multiple lines"
            assert timeline_items[1].title == "Second message"

            # Verify relationships
            assert timeline_items[0].source_id == telegram_messages[0].id
            assert timeline_items[1].source_id == telegram_messages[1].id


def test_import_telegram_deduplication(db_session):
    """Test that duplicate messages are not imported twice."""
    from exocortex.cli.import_telegram import import_telegram_messages

    mock_messages = [
        TelegramMessagePayload(
            message_id=1,
            chat_id="-1001234567890",
            sender="user1",
            text="Duplicate test",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            raw_json='{"message_id": 1}',
        ),
    ]

    with patch("exocortex.cli.import_telegram.fetch_recent_messages", return_value=mock_messages):
        with patch("exocortex.cli.import_telegram.get_session") as mock_get_session:
            from contextlib import contextmanager

            @contextmanager
            def session_context():
                yield db_session

            mock_get_session.return_value = session_context()

            # First import
            telegram_count1, timeline_count1 = import_telegram_messages(limit=10)
            assert telegram_count1 == 1
            assert timeline_count1 == 1

            # Second import (should skip duplicates)
            telegram_count2, timeline_count2 = import_telegram_messages(limit=10)
            assert telegram_count2 == 0
            assert timeline_count2 == 0

            # Verify only one record exists
            telegram_messages = db_session.query(TelegramMessage).all()
            assert len(telegram_messages) == 1

