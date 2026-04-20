# Skills

Skills are **in-context domain rules** loaded into Claude's prompt on
demand. They shape how the bot decides and behaves. No subprocess runs;
the content of a skill file becomes part of the reasoning context for
that turn.

## Skills vs plugins

Two extension points, different jobs — pick the right one.

|                | Skill                           | Plugin                                |
|----------------|---------------------------------|---------------------------------------|
| **What it is** | Words the model reads           | A process the model invokes           |
| **Runs?**      | No                              | Yes (argv via dispatch.py)            |
| **Good for**   | Access rules, lookup order, response format, decision trees | Fetching data, calling APIs, running shell commands |
| **Triggers**   | Invoked via the `Skill` tool when the model recognizes a match from the skill's description | Invoked when Claude matches an intent in `autogen-registry.json` |
| **Example**    | `calendar` — tells the bot to check Apple Calendar before Gmail for flight questions | `directions` — actually calls Google Maps Directions API |

**Rule of thumb**: if the extension needs the network, a secret, or the
filesystem → plugin. If it's guidance the model should follow → skill.
Plugins are leaf tools; skills shape orchestration.

Claude is always the orchestrator. Plugins don't call other plugins.
Skills don't call plugins either — they describe *when* the model should.

## Anatomy

```
.claude/skills/<name>/
  SKILL.md         frontmatter + body
  (optional supporting files)
```

Frontmatter:

```markdown
---
name: calendar
description: Use when the inbound message asks about events, schedules, itineraries, flights…
---

# Calendar rules

1. Always check the Apple Calendar via AppleScript first…
2. Fall back to Gmail only if the calendar has no matching event.
…
```

The `description` field is what Claude matches on — write it as a
trigger sentence so the model knows *when* to invoke the skill, not
what the skill contains.

## Current skills

| Skill | Triggered when… |
|-------|-----------------|
| `calendar` | The message asks about events, schedules, itineraries, flights. |
| `data-access` | The message asks for personal data (email, documents, anything Owner-private). Decides whether the sender is allowed to see it. |
| `tasks` | The message creates, lists, or removes reminders ("remind me", "what are my reminders"). |

See [`.claude/skills/*/SKILL.md`](../.claude/skills/) for the bodies.

## Adding a skill

1. `mkdir -p .claude/skills/<name>`
2. Write `.claude/skills/<name>/SKILL.md` with a frontmatter `name`
   and a **trigger-style** `description` (the model matches on it).
3. Write the body as operational rules the model should follow. Keep it
   focused on decisions, not implementation.
4. Restart the bot. The skill shows up in the available-skills list on
   the next prompt.

## When to lift rules into CLAUDE.md instead

Skills load on demand. CLAUDE.md is always in context. Use CLAUDE.md for:

- **Non-negotiable boundaries** that apply to every message (don't
  share Owner data with others; don't do financial transactions).
- **Routing rules** that govern which skill/plugin to reach for
  (trust tiers, channel classification).

Use skills for:

- **Domain-specific logic** that only matters when a matching message
  arrives (calendar lookup order, task-store format, access-control
  decision trees).

Splitting this way keeps CLAUDE.md small (always loaded) while domain
specifics stay out of the hot path until relevant.
