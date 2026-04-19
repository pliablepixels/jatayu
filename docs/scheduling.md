# Scheduling & triggers

The bot has two ways to receive input:

1. **Inbound channel messages** (the hot path — iMessage today).
2. **Triggers** — scheduled tasks and any future non-user event
   (webhooks, email-push, etc.). All triggers route through one
   function: `trigger.send(prompt, chat_id=...)`.

This keeps "something woke the bot up" as a single seam — easy to
extend, easy to monitor.

## The trigger pipeline

```
┌─────────────────────────────────────────────────────────┐
│ launchd (every 5 min) → scripts/heartbeat.py             │
│   ├── reads tasks/pending.json                          │
│   ├── for each task with due <= now:                    │
│   │     trigger.send(task.action, chat_id=task.chat_id) │
│   └── reschedules repeating tasks to next aligned tick  │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│ (future) webhook handler                                │
│   trigger.send(prompt, chat_id=…)                        │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│ scripts/trigger.py                                      │
│   checks tmux session exists and is idle                │
│   types the prompt via tmux send-keys                   │
│   returns "sent" | "busy" | "no-session"                 │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│ Live Claude session                                     │
│   prompt arrives prefixed "[Triggered] chat_id=… — …"    │
│   handled like any inbound message: plugins, reply      │
└─────────────────────────────────────────────────────────┘
```

## Heartbeat

`scripts/heartbeat.py` is launched every 5 minutes by
`launchd/com.jatayu.heartbeat.plist` (installed by `setup.sh`).

- **Logs** to `tasks/heartbeat.log`.
- **Fires** every due task in one pass.
- **Skips cleanly** when the tmux session is missing or busy — tasks
  stay pending and retry next tick.
- **`--list`** prints upcoming tasks with relative times:

  ```bash
  $ python3 scripts/heartbeat.py --list
  - 2026-04-19T07:15:00-04:00 (in 10h20m) [1d] Morning briefing…
  ```

### pending.json shape

`tasks/pending.json` is a JSON array. `scripts/tasks_store.py` provides
atomic read/write.

```json
[
  {
    "id": "b7e4d3a2-…",
    "due": "2026-04-19T07:15:00-04:00",
    "action": "Morning briefing — …",
    "repeat": "1d",
    "chat_id": "any;-;+1XXXXXXXXXX",
    "owner": "owner@example.com"
  }
]
```

| Field | Purpose |
|-------|---------|
| `id` | Free-form unique string. |
| `due` | ISO-8601 with timezone. When the action should fire. |
| `action` | The prompt handed to the bot. Can be multi-line. |
| `repeat` | Optional. `Nm/Nh/Nd/Ns` for minutes/hours/days/seconds. |
| `chat_id` | Where the bot should reply. Prefixed on the prompt as `[Triggered] chat_id=… — …`. |
| `owner` | Metadata only — who asked for this task. |

### Aligned repeats

When a repeating task fires, the next `due` is snapped to the next
clock boundary, not computed as `now + delta`. So a `5m` repeat fires
at `:00/:05/:10/:15…` (aligned to local midnight), not at whatever
offset the first fire happened on.

For intervals ≥ 1 day, alignment snaps to the next local midnight. The
morning briefing is unaffected because it has an explicit `due` of
`07:15:00` — the `while due <= now: due += delta` logic preserves the
original anchor across day boundaries.

Logic in `scripts/heartbeat.py:next_aligned_due`.

### If a task has no `due`

When a task has `repeat` but no explicit `due`, heartbeat sets `due`
to the next aligned boundary and saves. So "remind me every 5 minutes"
always starts at the next `:00`/`:05`/`:10`, never at `:07` because
that's when heartbeat happened to run.

## trigger.send

Single entry point. The interface:

```python
from trigger import send
result = send(prompt, chat_id="any;-;+1XXX…")
# result in {"sent", "busy", "no-session"}
```

What it does:

1. **Check session:** `tmux has-session -t claude-chatbot`. Returns
   `"no-session"` if missing (caller should defer, not mark done).
2. **Check busy:** `tmux capture-pane` — if "esc to interrupt" is
   showing, returns `"busy"` (Claude is mid-response).
3. **Build body:** `f"[Triggered] chat_id={chat_id} — {prompt}"` if
   `chat_id` is given, else just the prompt.
4. **Send keys:** type the body, sleep 300 ms, send Enter.
5. Returns `"sent"`.

CLI:
```bash
python3 scripts/trigger.py --chat-id "any;-;+1XXX…" "your prompt"
```

## Why the split?

- **Heartbeat** = scheduler. Knows about time, `pending.json`, aligned
  boundaries, retry-on-busy.
- **trigger.send** = delivery. Knows about tmux, send-keys, sleep
  timing, session liveness.

A new trigger source (webhook, file-watcher, email-push) only needs to
know `trigger.send`. The delivery mechanism can swap later (e.g.
`claude -p` per task instead of send-keys) without touching heartbeat
or any future webhook code.

## Future triggers

When you add a webhook handler:

1. The handler does whatever HTTP/auth dance.
2. It resolves a `chat_id` (usually the Owner's primary DM).
3. It calls `trigger.send(summarized_event, chat_id=owner_dm)`.

The bot sees `[Triggered] chat_id=… — …` and handles it like any other
message. No special codepath needed.
