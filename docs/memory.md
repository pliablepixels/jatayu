# Memory

The bot maintains conversation memory on three time scales:

1. **Per-chat recent context** — last ~40 turns, always injected.
2. **Per-chat rolling summary** — LLM-generated; preserves older facts.
3. **Daily cross-chat log** — append-only, one line per exchange.

Everything is file-based. No DB, no background workers. `context-hook.py`
is the only code that reads or writes.

## Per-chat context

Path: `tasks/context/<chat_key>.json`

`chat_key` is `<source>_<chat_id>` with `:` replaced by `_` and any
non-word characters (besides `-`, `+`) replaced with `_`. Example:
`plugin_imessage_imessage_any_-_+1XXXXXXXXXX.json`.

Shape: JSON array of `{ts, role, text}` entries.

```json
[
  {"ts": "2026-04-18T07:15:00-04:00", "role": "user", "text": "…"},
  {"ts": "2026-04-18T07:15:02-04:00", "role": "assistant", "text": "…"}
]
```

- `text` is truncated to 16KB per entry (`MAX_TEXT_BYTES`) with a
  `…[truncated]` marker. Prevents a single huge message from bloating
  the context file.
- Write is atomic via `tempfile` + `os.replace`.
- Read injects the last 20 entries as `<prior-context>` on the next
  prompt for the same chat.

## Rolling summary

Path: `tasks/context/<chat_key>.summary.md`

Plain markdown, under ~300 words. Regenerated when the per-chat log
overflows.

On read (UserPromptSubmit), the summary is injected as:

```
<prior-summary chat_id="…">
  …the summary body…
</prior-summary>
```

The model uses it the same way it uses recent context — facts and
decisions it should remember.

## Compaction

When `tasks/context/<chat>.json` exceeds `MAX_ENTRIES` (50), on the
next write:

1. The oldest `len - TRIM_TO` entries (10+, keeping the newest 40) are
   **archived** to `tasks/context/<chat>.archive.jsonl`. Append-only —
   data is never lost here.
2. `claude -p` is invoked with the existing summary + the newly
   archived entries, instructed to produce an updated summary under
   300 words. Output is atomically written to `.summary.md`.
3. The archive call is **synchronous with a 45-second timeout**. If it
   fails or times out, the prior summary stays, but the archive file
   still has all the data for a future retry.
4. A recursion guard (`CLAUDE_BOT_COMPACTING=1` in the child's env)
   prevents the spawned `claude -p` from triggering another compaction.

## Daily cross-chat log

Path: `memory/YYYY-MM-DD.md`

Append-only, one line per user/assistant message across every chat.
Format:

```
[HH:MM <source> <chat_id>] <role>: <text>
```

Good for: "what did I remind you about last Tuesday?", "how often does
this person ask about X?", quick audit of a day's traffic without
having to open the per-chat JSONs.

Not used by the bot directly today — it's for the Owner / for future
features.

## What gets read on prompt submit

`context-hook.py read` emits, in order:

1. `<local-time>` — current timezone-aware time.
2. `<trust>` — resolved tier (see [trust.md](trust.md)).
3. `<prior-summary>` — if `.summary.md` exists.
4. `<prior-context>` — last 20 entries from the per-chat JSON.

All four are optional blocks. If there's no channel tag on the prompt
(e.g. a direct prompt at the terminal), the hook is a silent no-op.

## What gets written on Stop

`context-hook.py write`:

1. Parses the user message for a `<channel>` tag. Skips silently if
   absent (triggered prompts from heartbeat don't have one, so they
   don't pollute per-chat context).
2. Appends user + assistant entries to the per-chat JSON.
3. Appends both to today's daily log.
4. Compacts if `len > MAX_ENTRIES`.

## Constants (in `scripts/context-hook.py`)

| Const | Default | Purpose |
|-------|---------|---------|
| `MAX_ENTRIES` | 50 | Compaction threshold |
| `TRIM_TO` | 40 | Entries kept after compaction |
| `MAX_TEXT_BYTES` | 16384 | Per-entry text cap |
| `SUMMARY_TIMEOUT_S` | 45 | Max seconds for `claude -p` summary |

## Files (per chat) at steady state

```
tasks/context/
  <chat>.json              recent 40 turns
  <chat>.archive.jsonl     every turn ever trimmed
  <chat>.summary.md        rolling summary
```

## Everything is gitignored

`tasks/` and `memory/` are in `.gitignore`. This is runtime state
that's personal and often large — never checked in.
