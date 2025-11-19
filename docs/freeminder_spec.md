# FreeMinder MVP Spec

Goal: turn raw stream of messages/events into a minimal, actionable memory.

## Inputs

- Telegram messages from selected chats.
- Google Calendar events (past and near future).
- (Later) Google Drive files.

## Processing

1. Normalize all inputs into `TimelineItem`s.
2. For each new TimelineItem, use OpenAI to:
   - Classify type: task / idea / note / noise.
   - Generate a short summary.
3. Persist results as `FreeMinderItem`s.

## Outputs

- CLI queries:
  - List tasks for today / tomorrow.
  - List last N ideas (with source).
  - Show summary of last N days.

## Non-goals (for now)

- UI / web frontend.
- Calendar write-backs.
- Complex scheduling.