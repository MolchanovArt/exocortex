# TODO (initial backlog)

## M0 – Scaffold
- [ ] Create project structure under `src/exocortex`.
- [ ] Add `config.py` with env loading.
- [ ] Add `db.py` with SQLite engine and Base.
- [ ] Add simple models for UserProfile (Pydantic-only).
- [ ] Implement `memory/base_memory.py` with `get_user_profile()`.
- [ ] Add CLI `query_cli.py` with `--show-profile`.

## M1 – Telegram Import
- [ ] Add ORM models for `TelegramMessage` and `TimelineItem`.
- [ ] Implement `integrations/telegram_client.py` using bot token.
- [ ] CLI `import_telegram.py` to fetch last N messages and store them.
- [ ] Unit tests for Telegram importer (with fake data).

## M2 – Google Calendar
- [ ] Implement OAuth flow and calendar client.
- [ ] Add `CalendarEvent` ORM model.
- [ ] Extend `TimelineItem` normalization.
- [ ] CLI `import_calendar.py`.
- [ ] Tests with mocked Google client.

## M3 – FreeMinder Pipeline
- [ ] Implement `openai_client.py` (classify + summarize).
- [ ] Add `FreeMinderItem` ORM model.
- [ ] Implement `freeminder/pipeline.py`:
      - select new TimelineItems,
      - classify,
      - create FreeMinderItems.
- [ ] Tests for classification mapping and pipeline logic.

## M4 – Query CLI
- [ ] Extend `query_cli.py`:
      - list tasks for today/tomorrow,
      - list last N ideas.
- [ ] Add snapshot tests for basic commands.

(Backlog will evolve with usage.)