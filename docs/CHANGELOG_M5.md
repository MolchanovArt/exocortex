# Changelog: Milestones M5-A and M5-B

## Summary

This document summarizes all changes made during the implementation of:
- **M5-A**: Close the Action Cycle v1 (plan → do → review)
- **M5-B**: Planning preferences + automatic slot suggestions

---

## Milestone M5-A: Close the Action Cycle v1

### Goal
Implement basic planning and review functionalities to close the action cycle: plan tasks, mark them as done, and review overdue tasks.

### Changes Made

#### 1. Extended MindItem Model (`src/exocortex/core/models.py`)
- **Added fields:**
  - `planned_start` (nullable datetime) - When the task should start
  - `planned_end` (nullable datetime) - When the task should end
  - `done_at` (nullable datetime) - When the task was completed
  - `completion_comment` (nullable text) - Optional completion note
- **Updated status values:** `"new"`, `"planned"`, `"in_progress"`, `"done"`
- **Kept `planned_for`** for backward compatibility

#### 2. Planning CLI (`src/exocortex/cli/plan_tasks.py`) - NEW FILE
- `get_unplanned_tasks()` - Finds tasks that need planning
- `plan_task_interactive()` - Interactive planning for each task
- **Options:**
  - `[s]kip` - Skip this task
  - `[t]oday` - Plan for today at 10:00
  - `[m]tomorrow` - Plan for tomorrow at 10:00
  - `[d]ate` - Enter custom date/datetime
  - `[q]uit` - Exit planning
- Sets `planned_start`, `planned_end`, and `status="planned"`

#### 3. Review CLI (`src/exocortex/cli/review_tasks.py`) - NEW FILE
- `get_tasks_for_review()` - Finds tasks for review (overdue by default)
- `review_task_interactive()` - Interactive review for each task
- **Options:**
  - `[y]es` - Mark as done (no comment)
  - `[c]omment` - Mark as done with completion comment
  - `[n]o` - Leave as is
  - `[s]kip` - Skip this task
  - `[q]uit` - Exit review
- **CLI arguments:**
  - `--limit N` - Maximum number of tasks to show (default: 50)
  - `--all` - Show all tasks, not just overdue ones
- Sets `status="done"`, `done_at=now()`, and optional `completion_comment`

#### 4. Tests (`tests/test_action_cycle.py`) - NEW FILE
- `test_get_unplanned_tasks()` - Verifies unplanned task selection
- `test_get_tasks_for_review()` - Verifies overdue task selection
- `test_get_tasks_for_review_with_calendar_events()` - Verifies calendar event integration

#### 5. Updated Query CLI Help (`src/exocortex/cli/query_cli.py`)
- Added epilog mentioning `plan_tasks` and `review_tasks` commands

#### 6. Database Migration
- Added new columns to `mind_items` table:
  - `planned_start DATETIME`
  - `planned_end DATETIME`
  - `done_at DATETIME`
  - `completion_comment TEXT`

---

## Milestone M5-B: Planning Preferences + Automatic Slot Suggestions

### Goal
Use user planning preferences (work hours, sleep, lunch, energy profile) and existing Calendar events + planned tasks to suggest free time slots for task planning.

### Changes Made

#### 1. Extended User Profile Models (`src/exocortex/core/models.py`)
- **Added Pydantic models:**
  - `PlanningPreferences`: timezone, work_days, work_hours, sleep_blocks, soft_blocks, max_focus_blocks_per_day, default_task_duration_minutes, avoid_after
  - `WorkHours`: start, end (HH:MM strings)
  - `TimeBlock`: start, end (for sleep blocks)
  - `SoftBlock`: label, start, end (for meal/break times)
  - `EnergyProfileEntry`: label, start, end, level ("high"/"medium"/"low")

#### 2. Extended Base Memory (`src/exocortex/memory/base_memory.py`)
- `get_planning_preferences()` - Returns PlanningPreferences with defaults
- `get_energy_profile()` - Returns list of EnergyProfileEntry objects

#### 3. Planning Preferences Module (`src/exocortex/planning/preferences.py`) - NEW FILE
- `get_planning_preferences()` - Wrapper with defaults
- `get_timezone()` - Returns timezone string (defaults to "Europe/Riga")
- `get_timezone_obj()` - Returns pytz timezone object
- `parse_time(time_str)` - Parses "HH:MM" to time object
- `work_days_as_weekday_indices(work_days)` - Converts day names to weekday indices (Mon=0, Sun=6)

#### 4. Planning Slots Module (`src/exocortex/planning/slots.py`) - NEW FILE
- `SuggestedSlot` dataclass: start, end, reason, energy_level
- `suggest_slots(session, *, days_ahead=7, block_minutes=None, max_suggestions=3)` - Main function
  - Builds daily work ranges from preferences
  - Fetches busy intervals from CalendarEvent and planned MindItem tasks
  - Subtracts busy intervals, sleep blocks, and soft blocks
  - Generates slots respecting avoid_after and energy profile
  - Sorts by time and energy level (high > medium > low)
  - Respects max_focus_blocks_per_day

#### 5. Updated Plan Tasks CLI (`src/exocortex/cli/plan_tasks.py`)
- **Added `[a]uto` option** to interactive menu
- When user selects 'a':
  - Calls `suggest_slots()` to get available slots
  - Displays slots with energy levels
  - User can select a slot number or skip
  - Selected slot is applied to task (planned_start, planned_end, status="planned")

#### 6. Tests
- `tests/test_planning_preferences.py` - Tests for preferences parsing, defaults, timezone, utilities
- `tests/test_planning_slots.py` - Tests for slot suggestion logic (no conflicts, respects calendar events, planned tasks, avoid_after, block_minutes, max_suggestions)
- `tests/test_plan_tasks_auto.py` - Tests for auto mode integration

#### 7. Dependencies (`requirements.txt`)
- Added `pytz>=2023.3` for timezone support

---

## Additional Fixes and Improvements

### 1. Telegram Import Rate Limit Handling (`src/exocortex/integrations/telegram_client.py`)
- Improved error handling for 429 (Too Many Requests) errors on `bot.close()`
- Rate limit errors on close are now silently ignored (non-critical)
- Added better logging for rate limit scenarios

### 2. Import Fixes
- Fixed import error: `get_energy_profile` should be imported from `exocortex.memory.base_memory`, not `exocortex.planning.preferences`

### 3. Documentation (`docs/WORKFLOW.md`) - NEW FILE
- Complete workflow guide from Telegram message to planned task
- Step-by-step instructions for all CLI commands
- Testing guide for auto planning feature
- Troubleshooting section

---

## Files Created

### New Files
- `src/exocortex/cli/plan_tasks.py` - Planning CLI
- `src/exocortex/cli/review_tasks.py` - Review CLI
- `src/exocortex/planning/__init__.py` - Planning module init
- `src/exocortex/planning/preferences.py` - Planning preferences utilities
- `src/exocortex/planning/slots.py` - Slot suggestion logic
- `tests/test_action_cycle.py` - Tests for action cycle
- `tests/test_planning_preferences.py` - Tests for preferences
- `tests/test_planning_slots.py` - Tests for slot suggestions
- `tests/test_plan_tasks_auto.py` - Tests for auto mode
- `docs/WORKFLOW.md` - Workflow documentation
- `docs/CHANGELOG_M5.md` - This file

### Modified Files
- `src/exocortex/core/models.py` - Added planning preference models and extended MindItem
- `src/exocortex/memory/base_memory.py` - Added preference getters
- `src/exocortex/cli/plan_tasks.py` - Added [a]uto option (M5-B)
- `src/exocortex/cli/query_cli.py` - Updated help text
- `src/exocortex/integrations/telegram_client.py` - Improved rate limit handling
- `requirements.txt` - Added pytz

---

## Key Features

### M5-A Features
✅ Interactive task planning (today/tomorrow/custom date)  
✅ Task review with completion tracking  
✅ Mark tasks as done with optional comments  
✅ Review all tasks or only overdue ones (`--all` flag)  
✅ Full test coverage

### M5-B Features
✅ Automatic slot suggestions based on:
  - Work hours and work days
  - Existing calendar events (avoids conflicts)
  - Already planned tasks (avoids double-booking)
  - Energy profile (prioritizes high-energy windows)
  - Sleep blocks and meal times
  - `avoid_after` time constraint
✅ Energy-aware scheduling (high > medium > low)
✅ Configurable via `user_profile.json`
✅ Deterministic and testable (no LLM calls)

---

## Usage Examples

### Plan Tasks with Auto-Suggestions
```bash
PYTHONPATH=src python -m exocortex.cli.plan_tasks --limit 20
# Select [a]uto when prompted to get automatic slot suggestions
```

### Review Tasks
```bash
# Review overdue tasks
PYTHONPATH=src python -m exocortex.cli.review_tasks --limit 50

# Review all tasks (including future ones)
PYTHONPATH=src python -m exocortex.cli.review_tasks --all --limit 50
```

### Complete Workflow
```bash
# 1. Import Telegram messages
PYTHONPATH=src python -m exocortex.cli.import_telegram --limit 50

# 2. Process through FreeMinder
PYTHONPATH=src python -m exocortex.cli.run_freeminder --limit 50

# 3. Plan tasks (with auto-suggestions!)
PYTHONPATH=src python -m exocortex.cli.plan_tasks --limit 20

# 4. Review tasks
PYTHONPATH=src python -m exocortex.cli.review_tasks --all
```

---

## Configuration

Planning preferences are configured in `data/user_profile.json`:

```json
{
  "preferences": {
    "planning_preferences": {
      "timezone": "Europe/Tbilisi",
      "work_days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
      "work_hours": {
        "start": "10:00",
        "end": "19:00"
      },
      "sleep_blocks": [
        { "start": "02:00", "end": "11:00" }
      ],
      "soft_blocks": [
        { "label": "lunch", "start": "15:00", "end": "16:00" }
      ],
      "max_focus_blocks_per_day": 3,
      "default_task_duration_minutes": 60,
      "avoid_after": "21:00"
    },
    "energy_profile": [
      { "label": "morning", "start": "10:00", "end": "12:00", "level": "high" },
      { "label": "afternoon", "start": "12:00", "end": "17:00", "level": "medium" },
      { "label": "evening", "start": "17:00", "end": "19:00", "level": "low" }
    ]
  }
}
```

---

## Testing

All features are covered by tests:
- ✅ Action cycle tests (planning and review)
- ✅ Planning preferences tests
- ✅ Slot suggestion tests (conflict avoidance, energy levels, constraints)
- ✅ Auto mode integration tests

Run tests:
```bash
PYTHONPATH=src pytest tests/test_action_cycle.py tests/test_planning_*.py tests/test_plan_tasks_auto.py -v
```

---

## Status

✅ **M5-A**: Complete and tested  
✅ **M5-B**: Complete and tested  
✅ **Documentation**: Complete  
✅ **All tests passing**

The action cycle (plan → do → review) is now fully functional with intelligent automatic slot suggestions!

