## Why

Jatayu currently surfaces information only when asked or via the morning briefing. There are several high-value moments each day — midday email accumulation, evening planning, and imminent calendar appointments — where a timely, unprompted nudge would be genuinely useful rather than reactive.

## What Changes

- **New**: Evening wind-down brief (8pm daily) — tomorrow's calendar, tomorrow morning weather/commute, any actionable emails that arrived since the morning triage
- **New**: Midday email triage (12:30pm weekdays) — scan inbox since morning briefing and surface only actionable/time-sensitive items; silent if nothing warrants attention
- **New**: Leave-now alerts — each morning, read today's calendar and pre-schedule one-shot tasks for external appointments, firing at (event start − drive time − 15 min buffer) to prompt the Owner to leave

## Capabilities

### New Capabilities

- `evening-briefing`: Daily 8pm summary covering tomorrow's calendar, weather/commute forecast, and any outstanding actionable emails
- `email-triage`: Weekday 12:30pm inbox scan; fires an alert only when actionable email is present, otherwise silent
- `leave-now-alerts`: Morning pre-scheduler that reads today's calendar, identifies external appointments with locations, computes drive times, and creates one-shot heartbeat tasks timed to fire when the Owner needs to leave

### Modified Capabilities

- `morning-briefing`: Add a pre-scheduler step that generates leave-now one-shot tasks for today's external appointments

## Impact

- `tasks/pending.json` — three new recurring task entries (evening brief, email triage, updated morning brief with pre-scheduler step)
- `.claude/skills/tasks/` — skills may need updating to document the pre-scheduler pattern and leave-now task format
- `scripts/tasks_store.py` — used (read/write) by the pre-scheduler prompt at runtime; no code changes needed
- `plugins/directions/` — used by the pre-scheduler to compute drive times; no code changes needed
- No new dependencies, no breaking changes
