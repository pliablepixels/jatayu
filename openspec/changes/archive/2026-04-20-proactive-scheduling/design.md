## Context

Jatayu's heartbeat system fires every 5 minutes, reads `tasks/pending.json`, and triggers any tasks whose `due` time has passed. Tasks are plain JSON objects with an `action` string (the prompt), optional `repeat`, and optional `chat_id`. The morning briefing is a single entry with `repeat: "1d"`.

The directions plugin (`plugins/directions/directions.py`) accepts `--origin`, `--destination`, and optional `--waypoint` args and returns drive time with live traffic.

The tasks skill (`.claude/skills/tasks/`) gives Claude read/write access to `pending.json` via `scripts/tasks_store.py`.

## Goals / Non-Goals

**Goals:**
- Add evening wind-down and email triage as simple recurring entries in `pending.json`
- Add a pre-scheduler step to the morning briefing that generates one-shot leave-now tasks for today's external appointments
- No new code — use existing heartbeat, directions plugin, and tasks_store machinery

**Non-Goals:**
- Location-triggered alerts (geofencing)
- SMS/push fallback if iMessage is unavailable
- Configurable alert lead time per-event
- Multi-day lookahead for leave-now alerts

## Decisions

### 1. Fixed-schedule tasks as pending.json entries (not code)

Evening brief and email triage are added directly to `pending.json` as recurring entries. No new Python scripts, no new launchd agents.

**Alternatives considered**: A separate cron script per feature — rejected because it adds operational complexity (more launchd plists) for zero benefit. The heartbeat already handles all scheduling.

### 2. Pre-scheduler pattern for leave-now alerts

Each morning, the morning briefing prompt includes a pre-scheduler step: read today's calendar, identify external appointments (location present and not matching home address, not containing "zoom"/"teams"/"meet"/"remote"/"virtual"), compute drive time via the directions plugin, and write one-shot tasks to `pending.json`.

**Due time formula**: `event_start - drive_time_minutes - 15` minutes. If the computed due time is already in the past (e.g., bot started late), skip that event.

**Alternatives considered**:
- Polling task every 30 min: requires deduplication state to avoid repeat alerts — messy.
- Separate daily pre-scheduler task (not embedded in morning briefing): cleaner separation of concerns, but means two tasks firing at ~7am; adds clutter to pending.json.
- Embedded in morning briefing (chosen): single task fires, does briefing + pre-scheduling in one shot. Simpler.

### 3. External appointment detection heuristic

Destination resolution order:
1. **Location field present** → use as destination; skip if it matches home address or contains virtual-meeting keywords
2. **No location field** → scan event name for virtual-meeting keywords first (zoom, teams, meet, google meet, webex, remote, virtual, call, phone); if none found, pass the event name as destination to the directions plugin and let it geocode; if the plugin fails or returns no result, skip the event

**Rationale**: The directions plugin accepts place names (not just addresses), so "Founding Farmers" or "Dentist on Wisconsin Ave" resolves correctly without a structured location field. False negatives (missing an alert) are less annoying than false positives (alert for a Zoom call), so virtual-keyword check runs before any geocoding attempt.

### 4. Email triage is silent when inbox is clear

If the 12:30pm scan finds no actionable email, send nothing. This avoids a useless "all clear" ping at lunchtime every day.

### 5. One-shot tasks clean up automatically

The heartbeat removes one-shot tasks (no `repeat`) after firing. No manual cleanup needed. If the bot is down when a leave-now task fires, it defers to the next heartbeat tick — at worst a 5-minute delay.

## Risks / Trade-offs

- **Calendar AppleScript flakiness** → Leave-now pre-scheduler may miss events if AppleScript times out. Mitigation: the morning briefing already uses AppleScript successfully; same risk profile.
- **Drive time computed at 7am, not at departure time** → Traffic conditions may differ. Mitigation: 15-min buffer absorbs moderate variance; user is aware this is an estimate.
- **Virtual meeting false negatives** → An unusual conferencing tool (e.g., "BlueJeans", "Webex") might not match the keyword list. Mitigation: can extend keyword list over time; no harm done if an occasional Zoom gets a leave-now alert.
- **pending.json write contention** → Pre-scheduler writes new tasks while heartbeat may be reading. Mitigation: `tasks_store.py` uses atomic replace (`os.replace`) — safe.

## Migration Plan

1. Add three entries to `tasks/pending.json`: evening brief, email triage, updated morning briefing (with pre-scheduler step appended to its action prompt).
2. Remove the existing morning briefing entry and replace with the updated one.
3. No rollback complexity — revert `pending.json` to remove any entry.
