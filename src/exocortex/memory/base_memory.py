"""Base memory: user profile loading and management."""

import json
from pathlib import Path
from typing import List, Optional

from exocortex.core.config import config
from exocortex.core.models import EnergyProfileEntry, PlanningPreferences, UserProfile


# Global cache for user profile
_user_profile: Optional[UserProfile] = None


def get_user_profile() -> UserProfile:
    """
    Load and return the user profile.

    The profile is loaded from the JSON file specified in config and cached.
    """
    global _user_profile

    if _user_profile is None:
        profile_path = config.get_user_profile_path()
        if not profile_path.exists():
            raise FileNotFoundError(
                f"User profile not found at {profile_path}. "
                f"Please create it or set USER_PROFILE_PATH environment variable."
            )

        with open(profile_path, "r", encoding="utf-8") as f:
            profile_data = json.load(f)

        _user_profile = UserProfile(**profile_data)

    return _user_profile


def reload_user_profile() -> UserProfile:
    """Force reload the user profile from disk."""
    global _user_profile
    _user_profile = None
    return get_user_profile()


def get_planning_preferences() -> PlanningPreferences:
    """
    Get planning preferences from user profile with defaults.

    Returns:
        PlanningPreferences instance with defaults applied for missing fields.
    """
    profile = get_user_profile()
    prefs_data = profile.preferences.get("planning_preferences", {})

    if not prefs_data:
        # Return defaults
        return PlanningPreferences()

    try:
        return PlanningPreferences(**prefs_data)
    except Exception:
        # If parsing fails, return defaults
        return PlanningPreferences()


def get_energy_profile() -> List[EnergyProfileEntry]:
    """
    Get energy profile from user profile.

    Returns:
        List of EnergyProfileEntry objects, empty list if not found.
    """
    profile = get_user_profile()
    energy_data = profile.preferences.get("energy_profile", [])

    if not energy_data:
        return []

    try:
        return [EnergyProfileEntry(**entry) for entry in energy_data]
    except Exception:
        return []

