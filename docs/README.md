# Jatayu design docs

Start with [architecture](architecture.md) for the big picture, then
dive into whichever subsystem you're touching.

| Doc | Read when… |
|-----|-----------|
| [architecture.md](architecture.md) | You want the overall system tour: components, inbound/scheduled flows, directory layout. |
| [plugins.md](plugins.md) | You're adding, modifying, or debugging a plugin. Manifest schema, dispatch, security. |
| [channels.md](channels.md) | You're adding a new messaging surface (Slack, email, etc.) or editing iMessage rules. |
| [skills.md](skills.md) | You're deciding whether your extension should be a skill or a plugin. |
| [trust.md](trust.md) | You're thinking about access control, unknown-sender behavior, or adding a known group chat. |
| [memory.md](memory.md) | You're touching the context pipeline, daily logs, or summarization. |
| [scheduling.md](scheduling.md) | You're adding scheduled tasks, webhooks, or anything that injects a prompt into the running bot. |

Operational rules that govern the bot's own behavior live in
[`CLAUDE.md`](../CLAUDE.md) and [`PERSONALITY.md`](../PERSONALITY.md).
Identity and contacts live in `PERSONAL.yaml` (gitignored — see
`PERSONAL.example.yaml`).
