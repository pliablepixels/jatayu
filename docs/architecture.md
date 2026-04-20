# Architecture

Jatayu is a personal assistant that runs as a Claude Code session
inside tmux and communicates with the Owner (and allow-listed others)
over iMessage. It's **single-user, local-first, and iMessage-first** by
design — those constraints shape every other decision.

## Design principles

- **Local-first.** Model API calls go out; everything else (conversation
  history, plugin execution, orchestration) stays on the Owner's machine.
- **Single source of truth for identity.** `PERSONAL.yaml` is parsed
  once by `scripts/personal.py`. Nothing else hardcodes names, phones,
  emails, or addresses.
- **Small core, extensible edges.** The framework is ~6 files. Features
  grow by adding plugins, channels, and skills — not by editing core.
- **Claude is the orchestrator.** Plugins are leaf tools; they don't
  call each other. Claude decides which to call and in what order.
- **No shell.** `dispatch.py` runs plugins via argv with `shell=False`,
  so model-supplied args can never become shell metacharacters.

## Components

```
┌──────────────────────────────────────────────────────────────┐
│ Inbound (iMessage MCP server, emits <channel> tags)          │
└────────────────┬─────────────────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────────────────┐
│ UserPromptSubmit hooks                                       │
│  • context-hook read  → <local-time> <trust> <prior-summary> │
│                         <prior-context>                      │
│  • preclassify       → <route plugin intent confidence/>     │
└────────────────┬─────────────────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────────────────┐
│ Claude (main tmux session) — reads CLAUDE.md + PERSONALITY + │
│ channel-rules + skills; picks a plugin if applicable;        │
│ dispatches; replies via mcp__imessage__reply                 │
└────────────────┬─────────────────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────────────────┐
│ Stop hook                                                    │
│  • context-hook write → per-chat JSON + daily log            │
│                         (compacts on overflow)               │
└──────────────────────────────────────────────────────────────┘

Side channels:
  • check-pii (PreToolUse)          blocks PII leaks into git/Write/Edit
  • check-imessage-reply (PreToolUse) enforces Boundary #8 — blocks
                            personal_docs_dir files attached to a
                            non-owner iMessage chat
  • heartbeat (launchd 5m)  reads pending.json → trigger.send
  • trigger.send            single entrypoint injecting a prompt
                            into the live session (used by heartbeat,
                            future webhooks)
```

## Inbound message flow

1. **iMessage MCP server** delivers `<channel source="plugin:imessage:imessage" chat_id="..." message_id="..." user="..." ts="...">body</channel>`.
2. **UserPromptSubmit** hooks fire in this order:
   - `context-hook.py read` — parses the channel tag, emits `<local-time>`, `<trust>` (resolved by `scripts/trust.py`), `<prior-summary>` if the chat has been compacted, and up to 20 recent turns as `<prior-context>`.
   - `preclassify.py` — keyword-matches the prompt against intents in `framework/autogen-registry.json`; if one dominates, prints `<route plugin="..." intent="..." confidence="..."/>`. Hint only.
3. **Claude** reads the boundaries in CLAUDE.md, the trust tier, the
   channel rules, the suggested route, and decides what to do. If a
   plugin matches, it calls `framework/dispatch.py <plugin> <intent> '<args-json>'`.
4. **dispatch.py** validates args (scalars only), loads the manifest,
   runs the plugin with `subprocess.run(..., shell=False)`, and logs a
   JSONL record to `tasks/dispatch.log`.
5. **Plugin** returns stdout; Claude formats a reply and sends via
   `mcp__imessage__reply(chat_id=..., text=...)`.
6. **Stop hook** runs `context-hook.py write` — appends the exchange to
   `tasks/context/<chat>.json` and to today's `memory/YYYY-MM-DD.md`.
   If the per-chat log exceeds 50 turns, the oldest are archived and a
   rolling summary is regenerated asynchronously via `claude -p`.

## Scheduled task flow

1. **launchd** fires `scripts/heartbeat.py` every 5 minutes.
2. Heartbeat reads `tasks/pending.json`. For each task with `due ≤ now`
   it calls `trigger.send(action, chat_id=...)`.
3. **trigger.send** checks the tmux session exists and isn't busy, then
   types the prompt via `tmux send-keys` (prefix: `[Triggered] chat_id=... —`).
4. The live Claude session receives the triggered prompt and handles it
   exactly like an inbound message — calls plugins, replies via iMessage.
5. Repeating tasks are re-scheduled to the next *aligned* clock boundary
   (a 5-minute repeat fires at :00/:05/:10, not at an arbitrary offset).
6. `trigger.send` returns `sent | busy | no-session`; on anything other
   than `sent` the task is left pending for the next tick.

## Directory layout

```
CLAUDE.md                 operational rules for the bot (read first)
PERSONALITY.md            tone/voice/identity
PERSONAL.yaml             identity + contacts (gitignored)
PERSONAL.example.yaml     template

framework/
  dispatch.py             safe, shell-free plugin invoker
  build-registry.py       merges plugin manifests + channel defs
  loader.sh               orchestrates build + per-plugin setup
  autogen-registry.json           generated (gitignored)
  autogen-channel-rules.md        generated — concatenated channel.md files
  autogen-channels        generated — comma-separated channel plugin list

plugins/<name>/
  manifest.json           intent/arg/env/capabilities declaration
  setup.sh                one-time install
  *.py (or any runtime)   the plugin itself

channels/<name>/
  channel.json            reply_tool / reply_param / source_tag
  channel.md              behavioral rules (merged into autogen-channel-rules.md)

scripts/
  personal.py             PERSONAL.yaml parser (single source of truth)
  trust.py                chat_id → trust tier classifier
  trigger.py              unified "inject prompt into running bot"
  heartbeat.py            launchd-fired scheduler
  tasks_store.py          atomic JSON read/write for pending.json
  context-hook.py         UserPromptSubmit + Stop hooks for memory
  check-pii.py            PreToolUse hook blocking PII leaks
  check-imessage-reply.py PreToolUse hook enforcing Boundary #8
  preclassify.py          UserPromptSubmit hook for plugin routing hint

.claude/
  settings.json           Claude Code hook config
  skills/<name>/          on-demand domain rules

tasks/                    (gitignored) runtime state
  pending.json            scheduled tasks
  context/<chat>.json     per-chat conversation
  context/<chat>.archive.jsonl  trimmed-but-preserved turns
  context/<chat>.summary.md     rolling LLM summary
  dispatch.log            JSONL log of every plugin call
  heartbeat.log           launchd stdout/stderr

memory/                   (gitignored) cross-chat daily logs
  YYYY-MM-DD.md           append-only, one line per exchange

launchd/                  launchd plist templates (rendered by setup.sh)
```

## Where each concern lives

| Concern                    | Code                                  |
|----------------------------|---------------------------------------|
| Identity / contacts        | `PERSONAL.yaml` + `scripts/personal.py` |
| Access control             | `scripts/trust.py`, injected via context-hook |
| Routing a new plugin match | `scripts/preclassify.py`              |
| Calling a plugin safely    | `framework/dispatch.py`               |
| Plugin discovery           | `framework/build-registry.py`         |
| Channel rules              | `channels/*/channel.md` → `framework/autogen-channel-rules.md` |
| Scheduled tasks            | `scripts/heartbeat.py` + `tasks/pending.json` |
| Any prompt injection into  | `scripts/trigger.py` (heartbeat + future webhooks) |
| the live session           |                                       |
| Memory persistence         | `scripts/context-hook.py`             |
| PII hygiene                | `scripts/check-pii.py`                |
