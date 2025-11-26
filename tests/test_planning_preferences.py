"""Tests for planning preferences."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from exocortex.core.models import PlanningPreferences
from exocortex.memory.base_memory import get_energy_profile, get_planning_preferences, reload_user_profile
from exocortex.planning.preferences import get_timezone, get_timezone_obj, parse_time, work_days_as_weekday_indices


def test_parse_time():
    """Test parsing time strings."""
    from datetime import time

    assert parse_time("10:00") == time(10, 0)
    assert parse_time("23:59") == time(23, 59)
    assert parse_time("09:30") == time(9, 30)

    with pytest.raises(ValueError):
        parse_time("invalid")
    with pytest.raises(ValueError):
        parse_time("25:00")


def test_work_days_as_weekday_indices():
    """Test converting work day names to indices."""
    assert work_days_as_weekday_indices(["Mon", "Tue", "Wed"]) == {0, 1, 2}
    assert work_days_as_weekday_indices(["Monday", "Friday"]) == {0, 4}
    assert work_days_as_weekday_indices(["sat", "sun"]) == {5, 6}
    assert work_days_as_weekday_indices([]) == set()


def test_get_planning_preferences_with_defaults(tmp_path, monkeypatch):
    """Test that get_planning_preferences applies defaults."""
    # Create a minimal profile without planning_preferences
    profile_data = {
        "id": "test",
        "name": "Test User",
        "preferences": {},
    }

    profile_file = tmp_path / "user_profile.json"
    with open(profile_file, "w") as f:
        json.dump(profile_data, f)

    # Mock the config to use our test profile
    import exocortex.core.config as config_module

    monkeypatch.setattr(config_module.config, "user_profile_path", str(profile_file))

    # Reload profile
    reload_user_profile()

    # Get preferences - should return defaults
    prefs = get_planning_preferences()
    assert isinstance(prefs, PlanningPreferences)
    assert prefs.timezone == "Europe/Riga"
    assert prefs.work_days == ["Mon", "Tue", "Wed", "Thu", "Fri"]
    assert prefs.work_hours.start == "10:00"
    assert prefs.work_hours.end == "19:00"
    assert prefs.default_task_duration_minutes == 60


def test_get_planning_preferences_from_profile(tmp_path, monkeypatch):
    """Test that get_planning_preferences loads from profile."""
    profile_data = {
        "id": "test",
        "name": "Test User",
        "preferences": {
            "planning_preferences": {
                "timezone": "America/New_York",
                "work_days": ["Mon", "Wed", "Fri"],
                "work_hours": {"start": "09:00", "end": "17:00"},
                "default_task_duration_minutes": 30,
            }
        },
    }

    profile_file = tmp_path / "user_profile.json"
    with open(profile_file, "w") as f:
        json.dump(profile_data, f)

    import exocortex.core.config as config_module

    monkeypatch.setattr(config_module.config, "user_profile_path", str(profile_file))
    reload_user_profile()

    prefs = get_planning_preferences()
    assert prefs.timezone == "America/New_York"
    assert prefs.work_days == ["Mon", "Wed", "Fri"]
    assert prefs.work_hours.start == "09:00"
    assert prefs.work_hours.end == "17:00"
    assert prefs.default_task_duration_minutes == 30


def test_get_energy_profile(tmp_path, monkeypatch):
    """Test getting energy profile."""
    profile_data = {
        "id": "test",
        "name": "Test User",
        "preferences": {
            "energy_profile": [
                {"label": "morning", "start": "07:00", "end": "12:00", "level": "high"},
                {"label": "afternoon", "start": "12:00", "end": "17:00", "level": "medium"},
            ]
        },
    }

    profile_file = tmp_path / "user_profile.json"
    with open(profile_file, "w") as f:
        json.dump(profile_data, f)

    import exocortex.core.config as config_module

    monkeypatch.setattr(config_module.config, "user_profile_path", str(profile_file))
    reload_user_profile()

    energy_profile = get_energy_profile()
    assert len(energy_profile) == 2
    assert energy_profile[0].label == "morning"
    assert energy_profile[0].level == "high"
    assert energy_profile[1].label == "afternoon"
    assert energy_profile[1].level == "medium"


def test_get_timezone():
    """Test getting timezone string."""
    # This will use the actual profile or defaults
    tz = get_timezone()
    assert isinstance(tz, str)
    assert len(tz) > 0


def test_get_timezone_obj():
    """Test getting timezone object."""
    tz_obj = get_timezone_obj()
    assert tz_obj is not None

