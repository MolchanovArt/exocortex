PROJECT: Exocortex / FreeMinder MVP (local prototype)

ROLE
You are an expert Python backend engineer helping build the first minimal prototype of "Exocortex", starting from a FreeMinder-like module.
The goal is to build a SMALL, CLEAN codebase that can run locally, integrate with Telegram and Google services, and use OpenAI as the reasoning core.
Keep code size minimal, focus on testability and clear separation of concerns.

HIGH-LEVEL GOALS (MVP)
1. Local Python app (no cloud, no Docker at first).
2. Integrations:
   - Telegram: import messages from specific chats or exported JSON.
   - Google Calendar: read events.
   - Google Drive/Files: list and fetch basic metadata for files (later content).
3. Internal memory:
   - A persistent store (SQLite) for:
     - Raw items: telegram messages, calendar events, files.
     - Normalized "TimelineItems" and "Notes/Tasks".
   - A "UserProfile" / "BaseMemory" loaded from a local JSON file.
4. OpenAI integration:
   - Use OpenAI API for:
     - Summarizing imported data.
     - Classifying messages into categories (idea / task / reference / noise).
5. CLI entry points / small scripts for:
   - Import from Telegram.
   - Import from Google Calendar.
   - Run a simple "freeminder" pass that:
     - Reads new raw items.
     - Uses OpenAI to classify / summarize.
     - Writes structured records into DB.
   - Simple query CLI: e.g. "show today tasks" / "list last 10 captured thoughts".

TECH STACK / CONVENTIONS
- Language: Python 3.11+.
- Package management: keep it simple (requirements.txt + venv). No Poetry unless explicitly added later.
- Project layout (src layout):

  exocortex/
    README.md
    .env.example
    requirements.txt
    src/exocortex/__init__.py
    src/exocortex/config.py
    src/exocortex/db.py
    src/exocortex/models.py          # Pydantic models + ORM models
    src/exocortex/openai_client.py
    src/exocortex/memory/base_memory.py
    src/exocortex/integrations/telegram_client.py
    src/exocortex/integrations/google_calendar.py
    src/exocortex/integrations/google_drive.py
    src/exocortex/freeminder/pipeline.py
    src/exocortex/cli/import_telegram.py
    src/exocortex/cli/import_calendar.py
    src/exocortex/cli/run_freeminder.py
    src/exocortex/cli/query_cli.py
    tests/...

- Dependencies (initial suggestion):
  - openai (official Python client)
  - python-dotenv
  - SQLAlchemy or SQLModel (SQLite)
  - pydantic
  - python-telegram-bot OR aiogram (choose one, prefer simple usage)
  - google-api-python-client, google-auth-httplib2, google-auth-oauthlib
  - pytest

- Configuration:
  - Use `.env` with environment variables.
  - Load config via a central Config object (`src/exocortex/config.py`) using pydantic BaseSettings if convenient.
  - NO hardcoded secrets. Use env vars.

- Storage:
  - Use SQLite (`exocortex.db` in project root).
  - Provide simple migrations via SQLAlchemy metadata create_all for now (no Alembic at first).

CORE DATA STRUCTURES (first iteration)
Implement minimal models to start, keeping them extendable:

1) UserProfile / BaseMemory (Pydantic model)
   - id (str) – fixed "artem" for now
   - name (str)
   - roles (list[str])
   - current_projects (list[str])
   - preferences (dict[str, Any]) – simple, high-level preferences
   - narrative (str) – short summary about the user

   Load from a JSON file: `data/user_profile.json` at startup.

2) Raw items:
   - TelegramMessage:
       id, chat_id, sender, text, timestamp, raw_json
   - CalendarEvent:
       id, calendar_id, title, description, start_time, end_time, raw_json
   - DriveFile:
       id, name, mime_type, modified_time, parents, raw_json

3) Normalized:
   - TimelineItem:
       id, source_type ("telegram", "calendar", "drive"),
       source_id, timestamp,
       title (optional), content,
       meta (JSON)
   - Thought / FreeMinderItem:
       id, timeline_item_id,
       type ("task", "idea", "note", "noise"),
       summary,
       status ("new", "planned", "done"),
       planned_for (datetime | null)

ARCHITECTURE / RESPONSIBILITIES

- src/exocortex/config.py
  - Central config: load env vars such as:
    OPENAI_API_KEY
    TELEGRAM_BOT_TOKEN
    TELEGRAM_TARGET_CHAT_ID (or a list)
    GOOGLE_CREDENTIALS_FILE (path)
    GOOGLE_TOKEN_FILE (path)
    GOOGLE_CALENDAR_ID
    GOOGLE_DRIVE_ROOT_FOLDER_ID (optional)
    EXOCORTEX_DB_PATH
    USER_PROFILE_PATH

- src/exocortex/db.py
  - Initialize SQLite engine and session factory.
  - Define Base = declarative_base() (or use SQLModel).
  - Expose `get_session()` context manager for use in scripts.

- src/exocortex/openai_client.py
  - Thin wrapper over OpenAI client.
  - Provide functions:
    - classify_message(text: str) -> Literal["task","idea","note","noise"]
    - summarize_text(text: str, context: Optional[UserProfile]) -> str
  - Keep prompts as constants, easy to tweak.

- src/exocortex/memory/base_memory.py
  - Load user profile JSON on startup.
  - Expose a singleton-like helper: `get_user_profile()`.

- src/exocortex/integrations/telegram_client.py
  - Encapsulate Telegram API usage.
  - Provide:
    - fetch_recent_messages(limit: int) -> list[TelegramMessageModel]
    - (Later) import from exported JSON.

- src/exocortex/integrations/google_calendar.py
  - Handle OAuth and token storage locally (credentials.json + token.json).
  - Provide:
    - fetch_events(time_min, time_max) -> list[CalendarEventModel]

- src/exocortex/integrations/google_drive.py
  - Provide:
    - fetch_recent_files(limit: int) -> list[DriveFileModel]

- src/exocortex/freeminder/pipeline.py
  - Functions to:
    - ingest_raw_items_from_integrations()
    - normalize_to_timeline()
    - run_classification_and_summarization()
  - For now, pipeline can be simple sequential functions.

- src/exocortex/cli/*.py
  - Small Click/argparse scripts to run steps:
    - `python -m exocortex.cli.import_telegram`
    - `python -m exocortex.cli.import_calendar`
    - `python -m exocortex.cli.run_freeminder`
    - `python -m exocortex.cli.query_cli`

TESTING
- Use pytest.
- For each integration, create mockable layers:
  - For Telegram/Google, separate "API client" from "importer" logic so importer can be tested with fake data.
- Add at least:
  - tests for classification & summarization helper functions (using stubbed OpenAI responses).
  - tests for DB models and Timeline normalization (in-memory SQLite).

DEVELOPMENT STRATEGY (MILESTONES)

M0 – SCAFFOLD
- Create project structure and empty files.
- Implement config loading (.env, BaseSettings).
- Add db.py with SQLite connection and a single test table.
- Implement user_profile loading from data/user_profile.json.
- Add one trivial CLI command: print user_profile summary.

M1 – TELEGRAM IMPORT
- Add Telegram integration.
- Implement models and DB tables for TelegramMessage and TimelineItem.
- CLI: `import_telegram` – fetch last N messages from a specific chat and store in DB as raw messages + timeline items (source_type="telegram").

M2 – GOOGLE CALENDAR IMPORT
- Google OAuth + Calendar integration.
- DB models for CalendarEvent and TimelineItem from calendar.
- CLI: `import_calendar` – fetch events in a date range, store.

M3 – FREEMINDER PIPELINE
- Implement OpenAI wrapper.
- Implement FreeMinder pipeline to:
  - read new TimelineItems,
  - classify type,
  - create FreeMinderItem entries (task/idea/note/noise),
  - set basic planned_for suggestion for tasks (for now just "today or tomorrow").

M4 – QUERY INTERFACE
- CLI `query_cli`:
  - list tasks for today / tomorrow.
  - list last N ideas with source links.
- Keep it text-only first.

STYLE / QUALITY
- Keep functions small and composable.
- Prefer type hints everywhere.
- Add docstrings to public functions.
- Keep prompts in separate constants for easier iteration.
- Do NOT prematurely optimize. Simplicity > cleverness.
- If a choice arises between more features and less code, prefer less code.

WHEN IMPLEMENTING NEW FEATURES
- Start from the existing architecture and extend in small, incremental steps.
- Keep commits and changesets small: add or modify a few files at a time.
- If something feels too big, propose splitting into smaller milestones.