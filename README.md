<img src="images/jatayu.jpg" align="left" width="220" hspace="16" vspace="8" alt="Jatayu" />

# Jatayu
### A first party personal agent that leverages your existing Claude CLI subscription

A personal AI assistant that runs as a Claude Code session and
communicates via iMessage. Answers questions, manages reminders, checks
calendar/email, and acts on behalf of the Owner and their family. Uses
the Claude CLI directly, so nothing here violates Claude's usage policy.

<br clear="left" />

**macOS only.** Jatayu reads iMessage's local `chat.db` and sends via
AppleScript to Messages.app, so it runs on the Mac where you're signed
into iMessage.

**iMessage is the only channel today.** You talk to Jatayu from an
iPhone (or any Apple device signed into the same iMessage account) via
iMessage — there's no SMS, WhatsApp, web, or voice interface yet. The
architecture is channel-agnostic (see [`docs/channels.md`](docs/channels.md)),
but the only channel currently shipped is the vendored iMessage MCP
server in `plugins/imessage-local/`.

### Who is Jatayu?

Jatayu is the pen name of [Lalmohan Ganguly](https://en.wikipedia.org/wiki/Lalmohan_Ganguly) — the devoted, ever-enthusiastic
sidekick to [Feluda](https://en.wikipedia.org/wiki/Feluda), Satyajit Ray's fictional detective. He tags along on every
case, means well, occasionally fumbles, but is completely loyal and always shows
up. A personal assistant that handles your calendar, email, and messages felt
like exactly his energy.

## Prerequisites

- [Claude Code](https://claude.ai/code) installed and authenticated
- macOS with iMessage configured
- `tmux` (`brew install tmux`)
- `bun` (`brew install oven-sh/bun/bun`) — runs the vendored iMessage MCP server

## Setup

```bash
./start.sh                 # auto-runs setup.sh if prerequisites are missing
```

If this is a fresh clone, `setup.sh` will create `PERSONAL.yaml` from the
template and then exit with a warning. Fill it in, then run `start.sh` again:

```bash
# Edit PERSONAL.yaml — name, phone, email, family, service names
./start.sh                 # now starts the tmux session
```

Once the session is running, attach and approve iMessage access:

```bash
tmux attach -t jatayu
# Inside the session, run:
/imessage:access           # approve your phone number and any group chats
```

You can also run `setup.sh` directly any time you need to re-apply it
(e.g. after changing the heartbeat interval in `PERSONAL.yaml`):

```bash
bash setup.sh              # idempotent — installs deps, reloads launchd agent
```

Attach to the live session any time:

```bash
tmux attach -t jatayu
```

## Startup notes

`start.sh` launches Claude Code with `--dangerously-load-development-channels`.
Channels are Claude Code's inbound-message transport — they push iMessage
messages into the session as `<channel source="...">` notifications so the
model can reply through a tool. The flag is currently required because
channels are in preview; locally-developed channels (like our vendored
iMessage MCP server) are gated behind it until the feature ships. The
one-time "I am using this for local development" prompt is auto-confirmed
by `start.sh`.

You'll see this on the first second of boot:

```
  server:imessage · no MCP server configured with that name
```

It's cosmetic. Claude Code resolves the channel list before the MCP
server (`plugins/imessage-local/server.ts`, booted via `--mcp-config`)
finishes its stdio handshake. Once the server connects, the channel
binds to it and messages start flowing — which is why the bot still
works despite the warning.

## Plugins

Plugins live under `plugins/<name>/` and are auto-discovered on launch.
Each one ships its own `README.md` with setup (API keys, env vars,
prerequisites) and disable instructions — read those before first use.

| Plugin | What it does | Setup notes |
|--------|--------------|-------------|
| [`imessage-local`](plugins/imessage-local/README.md) | Vendored MCP server that makes iMessage the bot's channel | Required. No extra keys. |
| [`directions`](plugins/directions/README.md) | Google Maps driving directions + live traffic | Needs `GOOGLE_MAPS_API` env var |
| [`weather`](plugins/weather/README.md) | Current conditions + short forecast via Open-Meteo | No key, no signup |

Writing your own plugin: see [`docs/plugins.md`](docs/plugins.md).

## Design

The full design is in [`docs/`](docs/). Start with
[`docs/architecture.md`](docs/architecture.md) for the big picture,
then branch out:

| Topic | Doc |
|-------|-----|
| System tour, data flow, directory layout | [architecture.md](docs/architecture.md) |
| Adding or modifying a plugin | [plugins.md](docs/plugins.md) |
| Adding a messaging channel | [channels.md](docs/channels.md) |
| Skills vs plugins, writing a skill | [skills.md](docs/skills.md) |
| Trust tiers, unknown-sender pairing | [trust.md](docs/trust.md) |
| Conversation memory, summarization, daily logs | [memory.md](docs/memory.md) |
| Heartbeat, scheduled tasks, triggers | [scheduling.md](docs/scheduling.md) |

Operational rules the bot itself follows live in
[`CLAUDE.md`](CLAUDE.md) and [`PERSONALITY.md`](PERSONALITY.md).
Identity and contacts live in `PERSONAL.yaml` (gitignored — see
`PERSONAL.example.yaml`).

## Reminders

Set reminders via iMessage:

- `"Remind me at 3pm to call the dentist"` — one-shot
- `"Remind me every morning to check my tasks"` — recurring
- `"What are my reminders?"` — list pending
- `"Cancel the dentist reminder"` — delete by fuzzy match

Stored in `tasks/pending.json`; fired by `scripts/heartbeat.py` every
5 minutes. See [scheduling.md](docs/scheduling.md) for details.

## Top-level layout

```
CLAUDE.md                   operational rules for the bot (read first)
PERSONALITY.md              tone and identity
PERSONAL.example.yaml       template — copy to PERSONAL.yaml (gitignored)

start.sh                    launch tmux + live chat session
setup.sh                    one-time setup (deps, launchd agent)

docs/                       design documentation (see table above)
framework/                  plugin + channel loader, dispatcher
plugins/<name>/             individual plugin implementations
channels/<name>/            individual channel configs + rules
scripts/                    runtime helpers (heartbeat, trust, memory, …)
.claude/                    Claude Code hooks + on-demand skills
launchd/                    launchd plist templates

tasks/                      runtime state (gitignored)
memory/                     daily logs (gitignored)
```

Stop the heartbeat launchd agent with:

```bash
launchctl unload ~/Library/LaunchAgents/com.jatayu.heartbeat.plist
```
