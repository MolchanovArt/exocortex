# Exocortex Workflow: Telegram Message → Planned Task

Complete workflow from importing Telegram messages to planning tasks with auto-suggestions.

## Quick Start

```bash
# 1. Import Telegram messages
PYTHONPATH=src python -m exocortex.cli.import_telegram --limit 50

# 2. Process messages through FreeMinder (classify & summarize)
PYTHONPATH=src python -m exocortex.cli.run_freeminder --limit 50

# 3. Plan tasks (with auto-suggestions!)
PYTHONPATH=src python -m exocortex.cli.plan_tasks --limit 20

# 4. Review overdue tasks
PYTHONPATH=src python -m exocortex.cli.review_tasks --all
```

---

## Step-by-Step Guide

### Step 1: Import Telegram Messages

Import messages from your Telegram chat:

```bash
PYTHONPATH=src python -m exocortex.cli.import_telegram --limit 50
```

**What happens:**
- Fetches recent messages from Telegram (up to `--limit`)
- Creates `TelegramMessage` records in database
- Creates corresponding `TimelineItem` records
- Skips duplicates automatically

**Expected output:**
```
✓ Imported 5 Telegram messages
✓ Created 5 timeline items
```

---

### Step 2: Process Through FreeMinder

Classify and summarize timeline items:

```bash
PYTHONPATH=src python -m exocortex.cli.run_freeminder --limit 50
```

**What happens:**
- Reads unprocessed `TimelineItem` records
- Uses OpenAI to classify as: `task`, `idea`, `note`, or `noise`
- Generates summaries
- Creates `MindItem` records

**Expected output:**
```
Processed 5 timeline items:
  - tasks: 3
  - ideas: 1
  - notes: 1
  - noise: 0
```

---

### Step 3: Plan Tasks (with Auto-Suggestions!)

Plan tasks interactively with automatic slot suggestions:

```bash
PYTHONPATH=src python -m exocortex.cli.plan_tasks --limit 20
```

**Interactive options:**
- `[s]kip` - Skip this task
- `[t]oday` - Plan for today at 10:00
- `[m]tomorrow` - Plan for tomorrow at 10:00
- `[d]ate` - Enter custom date/datetime
- `[a]uto` - **NEW!** Get automatic slot suggestions based on:
  - Your work hours and work days
  - Existing calendar events
  - Already planned tasks
  - Energy profile (high/medium/low energy times)
  - Sleep blocks and meal times
- `[q]uit` - Exit planning

**Example with auto-suggestions:**

```
Task #4: нужно купить молоко
  Source: telegram
  Created: 2025-11-26 00:35

[s]kip / [t]oday / [m]tomorrow / [d]ate / [a]uto / [q]uit: a

Available slots:
  1) 2025-11-27 11:00–12:00 (high energy)
  2) 2025-11-27 16:00–17:00 (medium energy)
  3) 2025-11-28 10:00–11:00 (high energy)
Choose a slot number or [s]kip: 1
✓ Planned for 2025-11-27 11:00 - 12:00
```

**Auto-suggestions consider:**
- Work hours from `user_profile.json` → `preferences.planning_preferences.work_hours`
- Work days (Mon-Fri by default)
- Existing calendar events (avoids conflicts)
- Already planned tasks (avoids double-booking)
- Energy profile (prioritizes high-energy windows)
- Sleep blocks and meal times (avoids those times)
- `avoid_after` time (won't suggest slots after this time)

---

### Step 4: Review Tasks

Review and mark tasks as done:

```bash
# Review only overdue tasks
PYTHONPATH=src python -m exocortex.cli.review_tasks --limit 50

# Review ALL tasks (including future ones)
PYTHONPATH=src python -m exocortex.cli.review_tasks --all --limit 50
```

**Interactive options:**
- `[y]es` - Mark as done (no comment)
- `[c]omment` - Mark as done with completion comment
- `[n]o` - Leave as is
- `[s]kip` - Skip this task
- `[q]uit` - Exit review

---

## Testing Auto Planning Feature

### Prerequisites

1. **Configure planning preferences** in `data/user_profile.json`:
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

2. **Have some unplanned tasks** in the database (from Step 1 & 2)

3. **Optional: Have calendar events** to test conflict avoidance:
   ```bash
   PYTHONPATH=src python -m exocortex.cli.import_calendar --days 7
   ```

### Test Steps

1. **Import Telegram messages:**
   ```bash
   PYTHONPATH=src python -m exocortex.cli.import_telegram --limit 10
   ```

2. **Process through FreeMinder:**
   ```bash
   PYTHONPATH=src python -m exocortex.cli.run_freeminder --limit 10
   ```

3. **Plan tasks with auto-suggestions:**
   ```bash
   PYTHONPATH=src python -m exocortex.cli.plan_tasks --limit 5
   ```
   
   **Test the `[a]uto` option:**
   - Select `a` when prompted
   - Verify slots are suggested
   - Check that slots:
     - Don't conflict with calendar events
     - Don't conflict with already planned tasks
     - Fall within work hours
     - Respect `avoid_after` time
     - Show energy levels (high/medium/low)
   - Select a slot number to plan the task

4. **Verify planned tasks:**
   ```bash
   PYTHONPATH=src python -m exocortex.cli.query_cli --tasks-today
   PYTHONPATH=src python -m exocortex.cli.query_cli --tasks-tomorrow
   ```

5. **Test conflict avoidance:**
   - Plan a task manually for a specific time
   - Try to plan another task with `[a]uto`
   - Verify the auto-suggestions don't overlap with the manually planned task

---

## Query Commands

### View Tasks
```bash
# Tasks for today
PYTHONPATH=src python -m exocortex.cli.query_cli --tasks-today

# Tasks for tomorrow
PYTHONPATH=src python -m exocortex.cli.query_cli --tasks-tomorrow

# Filter out past calendar events
PYTHONPATH=src python -m exocortex.cli.query_cli --tasks-today --future-only
```

### View Ideas & Notes
```bash
# Last 5 ideas
PYTHONPATH=src python -m exocortex.cli.query_cli --last-ideas 5

# Last 10 notes
PYTHONPATH=src python -m exocortex.cli.query_cli --last-notes 10
```

### View Timeline
```bash
# Last 20 timeline items
PYTHONPATH=src python -m exocortex.cli.query_cli --timeline 20

# Only future events
PYTHONPATH=src python -m exocortex.cli.query_cli --timeline 20 --future-only
```

---

## Troubleshooting

### No messages imported
- Check `TELEGRAM_BOT_TOKEN` and `TELEGRAM_TARGET_CHAT_ID` in `.env`
- Verify bot has access to the chat
- Note: `get_updates()` only returns NEW messages (not historical)

### No slots suggested
- Check `planning_preferences` in `user_profile.json`
- Verify work hours and work days are set correctly
- Check if all time slots are already booked
- Try increasing `days_ahead` in the code (default: 7 days)

### Rate limit errors
- Wait a few minutes between imports
- The 429 error on `bot.close()` is non-critical and handled silently

---

## Complete Example Session

```bash
# 1. Import messages
$ PYTHONPATH=src python -m exocortex.cli.import_telegram --limit 10
✓ Imported 3 Telegram messages
✓ Created 3 timeline items

# 2. Process through FreeMinder
$ PYTHONPATH=src python -m exocortex.cli.run_freeminder --limit 10
Processed 3 timeline items:
  - tasks: 2
  - ideas: 1

# 3. Plan tasks with auto-suggestions
$ PYTHONPATH=src python -m exocortex.cli.plan_tasks --limit 5
Found 2 unplanned task(s).

Task #4: нужно купить молоко
[s]kip / [t]oday / [m]tomorrow / [d]ate / [a]uto / [q]uit: a

Available slots:
  1) 2025-11-27 11:00–12:00 (high energy)
  2) 2025-11-27 16:00–17:00 (medium energy)
Choose a slot number or [s]kip: 1
✓ Planned for 2025-11-27 11:00 - 12:00

Task #5: надо бы определиться где буду жить
[s]kip / [t]oday / [m]tomorrow / [d]ate / [a]uto / [q]uit: t
✓ Planned for 2025-11-26 10:00 - 11:00

✓ Planned 2 task(s).

# 4. View planned tasks
$ PYTHONPATH=src python -m exocortex.cli.query_cli --tasks-today
Tasks for 2025-11-26:
  - надо бы определиться где буду жить (10:00-11:00)

# 5. Review tasks later
$ PYTHONPATH=src python -m exocortex.cli.review_tasks --all
Found 2 task(s).
...
```

