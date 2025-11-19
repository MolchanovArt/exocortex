# Exocortex / FreeMinder MVP

Local prototype of a personal "Exocortex" — starting from a FreeMinder-like module
that captures raw inputs (Telegram messages, Google Calendar events, files) and
turns them into a structured memory of tasks, ideas and notes.

## Current scope

- Local Python app (no cloud).
- Integrations:
  - Telegram: import messages from specific chats or exported JSON.
  - Google Calendar: read events.
  - Google Drive: list recent files.
- Internal memory:
  - SQLite DB for raw items, timeline items, and FreeMinder items.
  - `data/user_profile.json` for base user profile.

## Quick start

1. Create and activate a virtual environment.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt