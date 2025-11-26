"""Data models using Pydantic and SQLAlchemy ORM."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from exocortex.core.db import Base


# Pydantic models for planning preferences
class WorkHours(BaseModel):
    """Work hours configuration."""

    start: str = Field(..., description="Start time in HH:MM format")
    end: str = Field(..., description="End time in HH:MM format")


class TimeBlock(BaseModel):
    """A time block (e.g., sleep block)."""

    start: str = Field(..., description="Start time in HH:MM format")
    end: str = Field(..., description="End time in HH:MM format")


class SoftBlock(BaseModel):
    """A soft block (e.g., meal times, breaks)."""

    label: str = Field(..., description="Label for the block (e.g., 'lunch')")
    start: str = Field(..., description="Start time in HH:MM format")
    end: str = Field(..., description="End time in HH:MM format")


class EnergyProfileEntry(BaseModel):
    """An energy profile entry for a time period."""

    label: str = Field(..., description="Label for the period (e.g., 'morning')")
    start: str = Field(..., description="Start time in HH:MM format")
    end: str = Field(..., description="End time in HH:MM format")
    level: str = Field(..., description="Energy level: 'high', 'medium', or 'low'")


class PlanningPreferences(BaseModel):
    """Planning preferences configuration."""

    timezone: str = Field(default="Europe/Riga", description="Timezone string (e.g., 'Europe/Riga')")
    work_days: List[str] = Field(default_factory=lambda: ["Mon", "Tue", "Wed", "Thu", "Fri"], description="Work days")
    work_hours: WorkHours = Field(
        default_factory=lambda: WorkHours(start="10:00", end="19:00"), description="Work hours"
    )
    sleep_blocks: List[TimeBlock] = Field(default_factory=list, description="Sleep blocks")
    soft_blocks: List[SoftBlock] = Field(default_factory=list, description="Soft blocks (meals, breaks)")
    max_focus_blocks_per_day: int = Field(default=3, description="Maximum focus blocks per day")
    default_task_duration_minutes: int = Field(default=60, description="Default task duration in minutes")
    avoid_after: Optional[str] = Field(default=None, description="Avoid scheduling after this time (HH:MM)")


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


class CalendarEvent(Base):
    """ORM model for Google Calendar events."""

    __tablename__ = "calendar_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    calendar_id = Column(String, nullable=False, index=True)
    event_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=True)
    raw_json = Column(Text, nullable=True)  # Store as JSON string

    # Relationship to timeline items
    timeline_items = relationship("TimelineItem", back_populates="calendar_event", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<CalendarEvent(id={self.id}, calendar_id={self.calendar_id}, event_id={self.event_id})>"


class TimelineItem(Base):
    """ORM model for normalized timeline items from various sources."""

    __tablename__ = "timeline_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_type = Column(String, nullable=False, index=True)  # e.g., "telegram", "calendar", "drive"
    source_id = Column(Integer, nullable=True)  # Generic reference to source table (FK handled per source_type)
    timestamp = Column(DateTime, nullable=False, index=True)
    title = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    meta = Column(Text, nullable=True)  # Store as JSON string

    # Foreign keys for specific source types (using composite approach)
    telegram_message_id = Column(Integer, ForeignKey("telegram_messages.id"), nullable=True)
    calendar_event_id = Column(Integer, ForeignKey("calendar_events.id"), nullable=True)

    # Relationships
    telegram_message = relationship("TelegramMessage", back_populates="timeline_items")
    calendar_event = relationship("CalendarEvent", back_populates="timeline_items")

    # Relationship to mind items
    mind_items = relationship("MindItem", back_populates="timeline_item", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<TimelineItem(id={self.id}, source_type={self.source_type}, timestamp={self.timestamp})>"


class MindItem(Base):
    """ORM model for FreeMinder items (classified timeline items)."""

    __tablename__ = "mind_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timeline_item_id = Column(Integer, ForeignKey("timeline_items.id"), nullable=False, index=True, unique=True)
    item_type = Column(String, nullable=False, index=True)  # "task", "idea", "note", "noise"
    summary = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="new", index=True)  # "new", "planned", "in_progress", "done"
    planned_for = Column(DateTime, nullable=True, index=True)  # Legacy field, kept for backward compatibility
    planned_start = Column(DateTime, nullable=True, index=True)
    planned_end = Column(DateTime, nullable=True, index=True)
    done_at = Column(DateTime, nullable=True, index=True)
    completion_comment = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())

    # Relationship
    timeline_item = relationship("TimelineItem", back_populates="mind_items")

    def __repr__(self) -> str:
        return f"<MindItem(id={self.id}, timeline_item_id={self.timeline_item_id}, item_type={self.item_type})>"

