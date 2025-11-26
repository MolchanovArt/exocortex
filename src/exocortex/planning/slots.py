"""Slot suggestion logic for task planning."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, time
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from exocortex.core.models import CalendarEvent, MindItem
from exocortex.memory.base_memory import get_energy_profile
from exocortex.planning.preferences import (
    get_planning_preferences,
    get_timezone_obj,
    parse_time,
    work_days_as_weekday_indices,
)


@dataclass
class SuggestedSlot:
    """A suggested time slot for task planning."""

    start: datetime
    end: datetime
    reason: str
    energy_level: str = "medium"  # "high", "medium", "low"


def _get_energy_level_for_time(dt: datetime, energy_profile) -> str:
    """
    Get energy level for a given datetime based on energy profile.

    Args:
        dt: Datetime to check
        energy_profile: List of EnergyProfileEntry objects

    Returns:
        Energy level string: "high", "medium", or "low" (default: "medium")
    """
    time_only = dt.time()
    for entry in energy_profile:
        entry_start = parse_time(entry.start)
        entry_end = parse_time(entry.end)
        # Handle wrap-around (e.g., 22:00-02:00)
        if entry_start <= entry_end:
            if entry_start <= time_only < entry_end:
                return entry.level
        else:  # Wrap-around case
            if time_only >= entry_start or time_only < entry_end:
                return entry.level
    return "medium"  # Default


def _build_daily_work_ranges(
    start_date: date, days_ahead: int, prefs
) -> List[Tuple[date, time, time]]:
    """
    Build list of daily work ranges.

    Args:
        start_date: Starting date
        days_ahead: Number of days ahead to consider
        prefs: PlanningPreferences object

    Returns:
        List of (date, work_start_time, work_end_time) tuples
    """
    work_day_indices = work_days_as_weekday_indices(prefs.work_days)
    work_start = parse_time(prefs.work_hours.start)
    work_end = parse_time(prefs.work_hours.end)

    ranges = []
    for i in range(days_ahead + 1):
        current_date = start_date + timedelta(days=i)
        weekday = current_date.weekday()  # Monday=0, Sunday=6
        if weekday in work_day_indices:
            ranges.append((current_date, work_start, work_end))

    return ranges


def _subtract_time_blocks(
    work_start: datetime, work_end: datetime, blocks_to_subtract: List[Tuple[datetime, datetime]]
) -> List[Tuple[datetime, datetime]]:
    """
    Subtract time blocks from a work range.

    Args:
        work_start: Start of work range
        work_end: End of work range
        blocks_to_subtract: List of (start, end) datetime tuples to subtract

    Returns:
        List of free (start, end) datetime tuples
    """
    # Sort blocks by start time
    sorted_blocks = sorted(blocks_to_subtract, key=lambda x: x[0])

    free_intervals = []
    current_start = work_start

    for block_start, block_end in sorted_blocks:
        # Skip blocks that don't overlap with work range
        if block_end <= work_start or block_start >= work_end:
            continue

        # If there's a gap before this block, add it as free
        if current_start < block_start:
            free_intervals.append((current_start, min(block_start, work_end)))

        # Update current_start to after this block
        current_start = max(current_start, block_end)

    # Add remaining free time after last block
    if current_start < work_end:
        free_intervals.append((current_start, work_end))

    return free_intervals


def _get_busy_intervals(
    session: Session, start_date: date, days_ahead: int
) -> List[Tuple[datetime, datetime]]:
    """
    Get busy intervals from calendar events and planned tasks.

    Args:
        session: Database session
        start_date: Starting date
        days_ahead: Number of days ahead to consider

    Returns:
        List of (start, end) datetime tuples representing busy intervals
    """
    end_date = start_date + timedelta(days=days_ahead + 1)
    start_datetime = datetime.combine(start_date, time.min)
    end_datetime = datetime.combine(end_date, time.max)

    busy_intervals = []

    # Get calendar events
    calendar_events = (
        session.query(CalendarEvent)
        .filter(
            CalendarEvent.start_time >= start_datetime,
            CalendarEvent.start_time < end_datetime,
        )
        .all()
    )

    for event in calendar_events:
        if event.end_time:
            busy_intervals.append((event.start_time, event.end_time))
        else:
            # If no end_time, assume 1 hour duration
            busy_intervals.append((event.start_time, event.start_time + timedelta(hours=1)))

    # Get planned tasks
    planned_tasks = (
        session.query(MindItem)
        .filter(
            MindItem.item_type == "task",
            MindItem.status.in_(["planned", "in_progress"]),
            MindItem.planned_start.isnot(None),
            MindItem.planned_start >= start_datetime,
            MindItem.planned_start < end_datetime,
        )
        .all()
    )

    for task in planned_tasks:
        if task.planned_start and task.planned_end:
            busy_intervals.append((task.planned_start, task.planned_end))
        elif task.planned_start:
            # If no planned_end, assume default duration
            busy_intervals.append(
                (task.planned_start, task.planned_start + timedelta(hours=1))
            )

    return busy_intervals


def _apply_soft_blocks(
    free_intervals: List[Tuple[datetime, datetime]], prefs, date_obj: date
) -> List[Tuple[datetime, datetime]]:
    """
    Apply soft blocks to free intervals.

    Args:
        free_intervals: List of (start, end) datetime tuples
        prefs: PlanningPreferences object
        date_obj: Date for which to apply soft blocks

    Returns:
        List of free intervals with soft blocks subtracted
    """
    if not prefs.soft_blocks:
        return free_intervals

    soft_block_intervals = []
    for soft_block in prefs.soft_blocks:
        soft_start = parse_time(soft_block.start)
        soft_end = parse_time(soft_block.end)
        soft_start_dt = datetime.combine(date_obj, soft_start)
        soft_end_dt = datetime.combine(date_obj, soft_end)
        # Handle wrap-around
        if soft_end_dt <= soft_start_dt:
            soft_end_dt += timedelta(days=1)
        soft_block_intervals.append((soft_start_dt, soft_end_dt))

    # Subtract soft blocks from free intervals
    result = []
    for interval_start, interval_end in free_intervals:
        subtracted = _subtract_time_blocks(interval_start, interval_end, soft_block_intervals)
        result.extend(subtracted)

    return result


def _apply_sleep_blocks(
    free_intervals: List[Tuple[datetime, datetime]], prefs, date_obj: date
) -> List[Tuple[datetime, datetime]]:
    """
    Apply sleep blocks to free intervals.

    Args:
        free_intervals: List of (start, end) datetime tuples
        prefs: PlanningPreferences object
        date_obj: Date for which to apply sleep blocks

    Returns:
        List of free intervals with sleep blocks subtracted
    """
    if not prefs.sleep_blocks:
        return free_intervals

    sleep_block_intervals = []
    for sleep_block in prefs.sleep_blocks:
        sleep_start = parse_time(sleep_block.start)
        sleep_end = parse_time(sleep_block.end)
        sleep_start_dt = datetime.combine(date_obj, sleep_start)
        sleep_end_dt = datetime.combine(date_obj, sleep_end)
        # Handle wrap-around
        if sleep_end_dt <= sleep_start_dt:
            sleep_end_dt += timedelta(days=1)
        sleep_block_intervals.append((sleep_start_dt, sleep_end_dt))

    # Subtract sleep blocks from free intervals
    result = []
    for interval_start, interval_end in free_intervals:
        subtracted = _subtract_time_blocks(interval_start, interval_end, sleep_block_intervals)
        result.extend(subtracted)

    return result


def suggest_slots(
    session: Session,
    *,
    days_ahead: int = 7,
    block_minutes: Optional[int] = None,
    max_suggestions: int = 3,
) -> List[SuggestedSlot]:
    """
    Suggest available time slots for task planning.

    Args:
        session: Database session
        days_ahead: Number of days ahead to look for slots (default: 7)
        block_minutes: Duration of each slot in minutes (default: from preferences)
        max_suggestions: Maximum number of suggestions to return (default: 3)

    Returns:
        List of SuggestedSlot objects, sorted by date/time and energy level
    """
    prefs = get_planning_preferences()
    energy_profile = get_energy_profile()
    tz = get_timezone_obj()

    if block_minutes is None:
        block_minutes = prefs.default_task_duration_minutes

    block_duration = timedelta(minutes=block_minutes)
    start_date = date.today()
    now = datetime.now()

    # Build daily work ranges
    daily_ranges = _build_daily_work_ranges(start_date, days_ahead, prefs)

    # Get busy intervals
    busy_intervals = _get_busy_intervals(session, start_date, days_ahead)

    # Generate candidate slots
    candidate_slots = []

    for date_obj, work_start_time, work_end_time in daily_ranges:
        # Create datetime range for this day
        work_start_dt = datetime.combine(date_obj, work_start_time)
        work_end_dt = datetime.combine(date_obj, work_end_time)

        # Skip if work day is in the past
        if work_end_dt < now:
            continue

        # Get busy intervals for this day
        day_start = datetime.combine(date_obj, time.min)
        day_end = datetime.combine(date_obj, time.max) + timedelta(days=1)
        day_busy = [
            (start, end)
            for start, end in busy_intervals
            if start >= day_start and start < day_end
        ]

        # Subtract busy intervals
        free_intervals = _subtract_time_blocks(work_start_dt, work_end_dt, day_busy)

        # Apply sleep blocks
        free_intervals = _apply_sleep_blocks(free_intervals, prefs, date_obj)

        # Apply soft blocks
        free_intervals = _apply_soft_blocks(free_intervals, prefs, date_obj)

        # Generate slots from free intervals
        for interval_start, interval_end in free_intervals:
            # Skip if interval is in the past
            if interval_end < now:
                continue

            # Apply avoid_after constraint
            if prefs.avoid_after:
                avoid_after_time = parse_time(prefs.avoid_after)
                avoid_after_dt = datetime.combine(date_obj, avoid_after_time)
                if interval_start >= avoid_after_dt:
                    continue

            # Generate slots of block_duration within this interval
            current_start = max(interval_start, now)
            while current_start + block_duration <= interval_end:
                slot_end = current_start + block_duration
                energy_level = _get_energy_level_for_time(current_start, energy_profile)

                # Determine reason
                if day_busy:
                    reason = "free between calendar events"
                else:
                    reason = "no tasks yet this day"

                candidate_slots.append(
                    SuggestedSlot(
                        start=current_start,
                        end=slot_end,
                        reason=reason,
                        energy_level=energy_level,
                    )
                )

                # Move to next slot (with some gap, or just next block)
                current_start += block_duration

    # Sort by date/time first, then by energy level (high > medium > low)
    energy_priority = {"high": 0, "medium": 1, "low": 2}

    candidate_slots.sort(
        key=lambda s: (
            s.start,
            energy_priority.get(s.energy_level, 1),
        )
    )

    # Apply max_focus_blocks_per_day if set
    if prefs.max_focus_blocks_per_day > 0:
        # Group by date and limit per day
        slots_by_date = {}
        for slot in candidate_slots:
            slot_date = slot.start.date()
            if slot_date not in slots_by_date:
                slots_by_date[slot_date] = []
            slots_by_date[slot_date].append(slot)

        # Limit per day, prioritizing high energy slots
        limited_slots = []
        for date_obj in sorted(slots_by_date.keys()):
            day_slots = slots_by_date[date_obj]
            # Sort day slots by energy level (high first), then by time
            day_slots.sort(
                key=lambda s: (
                    energy_priority.get(s.energy_level, 1),
                    s.start,
                )
            )
            limited_slots.extend(day_slots[: prefs.max_focus_blocks_per_day])
            if len(limited_slots) >= max_suggestions:
                break

        # Re-sort final list by time and energy
        limited_slots.sort(
            key=lambda s: (
                s.start,
                energy_priority.get(s.energy_level, 1),
            )
        )
        candidate_slots = limited_slots[:max_suggestions]
    else:
        candidate_slots = candidate_slots[:max_suggestions]

    return candidate_slots

