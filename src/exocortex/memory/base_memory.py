"""Base memory: user profile loading and management."""

import json
from pathlib import Path
from typing import Optional

from exocortex.core.config import config
from exocortex.core.models import UserProfile


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

