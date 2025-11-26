"""Planning preferences utilities."""

from datetime import time
from typing import Set

import pytz

from exocortex.memory.base_memory import get_energy_profile as _get_energy_profile, get_planning_preferences as _get_planning_preferences
from exocortex.core.models import EnergyProfileEntry, PlanningPreferences


def get_planning_preferences() -> PlanningPreferences:
    """
    Get planning preferences with defaults applied.

    Returns:
        PlanningPreferences instance (never None).
    """
    return _get_planning_preferences()


def get_timezone() -> str:
    """
    Get timezone string from planning preferences.

    Returns:
        Timezone string, defaults to "Europe/Riga" if not set.
    """
    prefs = get_planning_preferences()
    return prefs.timezone or "Europe/Riga"


def get_timezone_obj():
    """
    Get timezone object from planning preferences.

    Returns:
        pytz timezone object, defaults to Europe/Riga.
    """
    tz_str = get_timezone()
    try:
        return pytz.timezone(tz_str)
    except Exception:
        return pytz.timezone("Europe/Riga")


def parse_time(time_str: str) -> time:
    """
    Parse time string in HH:MM format.

    Args:
        time_str: Time string in HH:MM format

    Returns:
        time object

    Raises:
        ValueError: If time_str cannot be parsed
    """
    try:
        hour, minute = map(int, time_str.split(":"))
        return time(hour, minute)
    except (ValueError, AttributeError) as e:
        raise ValueError(f"Invalid time format: {time_str}. Expected HH:MM") from e


def work_days_as_weekday_indices(work_days: list[str]) -> Set[int]:
    """
    Convert work day names to weekday indices.

    Args:
        work_days: List of day names (e.g., ["Mon", "Tue", "Wed"])

    Returns:
        Set of weekday indices where Monday=0, Sunday=6
    """
    day_map = {
        "mon": 0,
        "tue": 1,
        "wed": 2,
        "thu": 3,
        "fri": 4,
        "sat": 5,
        "sun": 6,
    }
    indices = set()
    for day in work_days:
        day_lower = day.lower()[:3]  # Take first 3 chars
        if day_lower in day_map:
            indices.add(day_map[day_lower])
    return indices

