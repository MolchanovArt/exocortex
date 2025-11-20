"""Data models using Pydantic and SQLAlchemy ORM."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from exocortex.core.db import Base


# Pydantic models
class UserProfile(BaseModel):
    """User profile model loaded from JSON."""

    id: str = Field(..., description="User identifier")
    name: str = Field(..., description="User name")
    roles: List[str] = Field(default_factory=list, description="User roles")
    current_projects: List[str] = Field(default_factory=list, description="Current projects")
    preferences: Dict[str, Any] = Field(default_factory=dict, description="User preferences")
    narrative: str = Field("", description="User narrative/summary")

    class Config:
        """Pydantic config."""

        extra = "allow"  # Allow extra fields in JSON


# SQLAlchemy ORM models
class TelegramMessage(Base):
    """ORM model for Telegram messages."""

    __tablename__ = "telegram_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String, nullable=False, index=True)
    message_id = Column(Integer, nullable=False, index=True)
    sender = Column(String, nullable=True)
    text = Column(Text, nullable=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    raw_json = Column(Text, nullable=True)  # Store as JSON string

    # Relationship to timeline items
    timeline_items = relationship("TimelineItem", back_populates="telegram_message", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<TelegramMessage(id={self.id}, chat_id={self.chat_id}, message_id={self.message_id})>"


class TimelineItem(Base):
    """ORM model for normalized timeline items from various sources."""

    __tablename__ = "timeline_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_type = Column(String, nullable=False, index=True)  # e.g., "telegram", "calendar", "drive"
    source_id = Column(Integer, ForeignKey("telegram_messages.id"), nullable=True)  # FK to source table
    timestamp = Column(DateTime, nullable=False, index=True)
    title = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    meta = Column(Text, nullable=True)  # Store as JSON string

    # Relationships
    telegram_message = relationship("TelegramMessage", back_populates="timeline_items")

    def __repr__(self) -> str:
        return f"<TimelineItem(id={self.id}, source_type={self.source_type}, timestamp={self.timestamp})>"

