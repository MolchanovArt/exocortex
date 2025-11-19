"""Tests for memory module."""

import json
import tempfile
from pathlib import Path

import pytest

from exocortex.core.models import UserProfile
from exocortex.memory.base_memory import get_user_profile, reload_user_profile


def test_user_profile_model() -> None:
    """Test UserProfile Pydantic model."""
    profile_data = {
        "id": "test_user",
        "name": "Test User",
        "roles": ["Developer"],
        "current_projects": ["Project A"],
        "preferences": {"key": "value"},
        "narrative": "Test narrative",
    }

    profile = UserProfile(**profile_data)
    assert profile.id == "test_user"
    assert profile.name == "Test User"
    assert len(profile.roles) == 1
    assert profile.roles[0] == "Developer"


def test_load_user_profile(tmp_path: Path) -> None:
    """Test loading user profile from JSON file."""
    # Create a temporary profile file
    profile_data = {
        "id": "test_user",
        "name": "Test User",
        "roles": ["Developer", "Engineer"],
        "current_projects": ["Project A", "Project B"],
        "preferences": {
            "work_style": "agile",
            "tools": ["Python", "TypeScript"],
        },
        "narrative": "A test user profile",
    }

    profile_file = tmp_path / "test_profile.json"
    with open(profile_file, "w", encoding="utf-8") as f:
        json.dump(profile_data, f)

    # Temporarily override the config path (use absolute path)
    import exocortex.memory.base_memory as memory_module
    import exocortex.core.config as config_module

    original_path = config_module.config.user_profile_path
    config_module.config.user_profile_path = str(profile_file.absolute())

    try:
        # Clear cache
        memory_module._user_profile = None

        profile = get_user_profile()
        assert profile.id == "test_user"
        assert profile.name == "Test User"
        assert len(profile.roles) == 2
        assert len(profile.current_projects) == 2
        assert profile.preferences["work_style"] == "agile"
        assert profile.narrative == "A test user profile"

        # Test caching - should return same instance
        profile2 = get_user_profile()
        assert profile is profile2

        # Test reload
        profile3 = reload_user_profile()
        assert profile3.id == "test_user"
        # Should be a new instance after reload
        assert profile3 is not profile
    finally:
        # Restore original path
        config_module.config.user_profile_path = original_path
        memory_module._user_profile = None


def test_load_user_profile_not_found(tmp_path: Path) -> None:
    """Test that FileNotFoundError is raised when profile doesn't exist."""
    import exocortex.memory.base_memory as memory_module
    import exocortex.core.config as config_module

    original_path = config_module.config.user_profile_path
    # Use absolute path to a non-existent file
    nonexistent_file = tmp_path / "nonexistent_profile.json"
    config_module.config.user_profile_path = str(nonexistent_file.absolute())

    try:
        memory_module._user_profile = None
        with pytest.raises(FileNotFoundError):
            get_user_profile()
    finally:
        config_module.config.user_profile_path = original_path
        memory_module._user_profile = None

