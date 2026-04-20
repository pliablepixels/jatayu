# Channels

A channel is a **messaging surface** — the transport the bot listens
on for inbound messages and uses to send replies. Today there's one:
iMessage. The abstraction is deliberately thin — the heavy lifting
(receiving, filtering, sending) happens inside the underlying MCP
server, not the framework.

## Anatomy

```
channels/<name>/
  channel.json      how the framework sees the channel
  channel.md        behavioral rules (merged into autogen-channel-rules.md)
```

## channel.json schema

```json
{
  "name": "imessage",
  "description": "Apple iMessage via the Claude iMessage plugin",
  "plugin": "server:imessage",
  "source_tag": "server:imessage",
  "reply_tool": "mcp__imessage__reply",
  "reply_param": "text"
}
```

| Field | Purpose |
|-------|---------|
| `name` | Unique — directory name. |
| `description` | One-liner. |
| `plugin` | The MCP plugin or server that provides this channel. Passed to `claude --dangerously-load-development-channels`. |
| `source_tag` | Matches the `source=` attribute on inbound `<channel>` tags. How Claude knows which channel a message arrived on. |
| `reply_tool` | The MCP tool Claude calls to send a reply. |
| `reply_param` | The parameter on `reply_tool` that carries the message body. |

## channel.md

Behavioral rules specific to this channel. On every start,
`build-registry.py` concatenates all `channels/*/channel.md` into
`framework/autogen-channel-rules.md`, which `CLAUDE.md` @-imports. Rules apply
when the `<channel source="…">` tag matches.

Keep rules to behavior that's *specific to the channel* — identity,
trust logic, and plugin dispatch rules belong in CLAUDE.md and
PERSONALITY.md, not here.

## Current channels

### iMessage (`channels/imessage/`)

Plain text + file attachments, via the forked
[iMessage plugin](../plugins/imessage-local/). Key facts:

- **Plain text only** at the protocol level. Markdown, HTML, inline
  replies, and tapbacks are *not* rendered. Newlines, emoji, and URLs
  (auto-linked) are the only formatting available.
- **Attachments** via `files: ["/absolute/path.png"]` on the `reply`
  tool. Sent as separate messages after the text.
- **chat_id format** is iMessage-specific:
  - DM: `any;-;+<phone>` (note: `-`, not `iMessage`)
  - Group: `any;+;chat<hash>` (from `chat.db`)
- **Outgoing echo**: the vendored fork delivers the Owner's own
  outgoing messages in allowlisted chats back to the bot's session so
  it sees both sides of the conversation. No runtime patching needed —
  the fix is already in `plugins/imessage-local/server.ts`.

Full rules in [`channels/imessage/channel.md`](../channels/imessage/channel.md).

## Adding a channel

1. If there's a vendored MCP server (Slack, Telegram, email), install it
   under `plugins/<server-name>/` and make sure it's in the inline
   `--mcp-config` block in `start.sh`.
2. Create `channels/<name>/channel.json`. Pick a stable `source_tag`
   (what the server emits on `<channel source=…>`).
3. Write `channels/<name>/channel.md` with behavioral rules: when to
   reply, how threads/IDs work, any platform-specific rendering quirks.
4. Extend `scripts/trust.py` if the new channel has a different
   `chat_id` shape (today's classifier parses iMessage's `any;-;+<phone>`
   format).
5. Restart the bot. `build-registry.py` picks up the channel.

## Future extensions

When more than one channel is live, channel.json may need to carry
richer metadata so replies can address threads/users correctly:

- `thread_param` — the manifest's name for a thread/message ID
- `author_param` — for channels where you reply to a specific person in
  a group without addressing the whole group
- `capabilities` — rich-text support, attachment types, max length

These aren't in the schema today — no second channel needs them yet.
Add them when the concrete case arrives.
