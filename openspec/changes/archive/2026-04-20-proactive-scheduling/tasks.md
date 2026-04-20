## 1. Update Morning Briefing Task

- [x] 1.1 Read the current morning briefing entry in `tasks/pending.json` to understand its full action prompt
- [x] 1.2 Append the pre-scheduler step to the action prompt: after sending the briefing, read today's full calendar; for each event, first check location field and name for virtual-meeting keywords (zoom, teams, meet, google meet, webex, remote, virtual, call, phone) — skip if found; then resolve destination: use location field if present and not home address, otherwise extract a place name from the event title; run the directions plugin from home address to resolved destination; if the plugin returns a result, compute `due = event_start − drive_time_minutes − 15 min` and if due is in the future, write a one-shot task to `pending.json` via `python3 scripts/tasks_store.py`; skip the event silently if the plugin fails or no destination can be resolved
- [x] 1.3 Write the updated morning briefing entry back to `tasks/pending.json` (preserve all existing fields: id, due, repeat, owner, chat_id)

## 2. Add Evening Wind-Down Task

- [x] 2.1 Add a new recurring entry to `tasks/pending.json` with `repeat: "1d"`, due at 8:00pm local time today (or tomorrow if 8pm has already passed), and an action prompt that: (a) fetches tomorrow's weather forecast using `plugins/weather/`, (b) reads tomorrow's calendar events from the Family Shared Calendar via AppleScript, (c) computes tomorrow morning home→office commute via directions plugin (weekdays only — skip entirely on Saturday/Sunday eve), (d) scans Gmail for unread actionable emails received since ~7am today, (e) iMessages the Owner with a concise evening summary omitting any empty sections except calendar (always show tomorrow's calendar or "day clear")

## 3. Add Midday Email Triage Task

- [x] 3.1 Add a new recurring entry to `tasks/pending.json` with `repeat: "1d"`, due at 12:30pm local time on the next weekday, and an action prompt that: checks if today is a weekday (Monday–Friday) — if not, exits silently; scans Gmail for unread actionable/time-sensitive emails received since ~7am today; if any found, iMessages the Owner with a bullet-per-email summary (same format as morning briefing: `• From — Subject — link`); if none found, sends nothing

## 4. Verify

- [x] 4.1 Run `python3 scripts/heartbeat.py --list` and confirm all three new tasks appear with correct due times and repeat intervals
- [x] 4.2 Confirm the morning briefing entry in `pending.json` contains the pre-scheduler step in its action prompt
- [x] 4.3 Manually trigger the evening brief by temporarily setting its `due` to a past time, running a heartbeat tick, and confirming the iMessage arrives with correct content
