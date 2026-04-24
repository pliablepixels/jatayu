# iMessage Channel Rules

Applies when `<channel source="plugin:imessage:imessage">` is present.

## Response Rules

1. **Owner DMs**: Use judgment — chime in when you have something genuinely useful, helpful, or well-timed to add. Skip reactions, acknowledgements, and social chatter unless there's a clear reason to engage.
2. **Non-Owner DMs and group chats**: Only respond if explicitly tagged by name (Bot name from PERSONAL.md) or "@claude". Exception: if a message is clearly a direct reaction to something you just said, judgment applies and you may respond without a tag.
3. **Informational messages** (no question, no request, no task) require no response. Do not reply, do not acknowledge. Staying silent is the correct action.
4. **Never forward or summarize** a non-Owner DM to the Owner unless the sender explicitly asks you to, or the content is safety-critical (e.g., emergency, security concern). Do not self-appoint as a courier.
5. For requests that will require multiple steps (searching the Email service, checking the Calendar service, running agents, etc.), send a short "On it..." reply immediately before starting the work.

## Chat GUID Format

DM chat GUIDs use `any;-;+<number>` format (e.g. `any;-;+1XXXXXXXXXX`), not `iMessage;-;+<number>`. Group chats use their own GUIDs from chat.db (e.g. `any;+;chatXXXXXXXXXXXXXXXXXX`). Always use the correct format when calling the reply tool.

The `reply` tool takes a `text` parameter (not `message`). The vendored
iMessage plugin (`plugins/imessage-local/server.ts`) is pre-patched to
deliver the Owner's own outgoing messages in configured chats so the bot
sees both sides of the conversation.

## Formatting

Never use markdown in iMessage replies. Plain text only — no bold, no bullets with **, no headers. iMessage renders markdown as literal characters, not formatting.

## Echo Suppression

When an incoming channel message is word-for-word identical (or near-identical)
to a message you just sent, it is the plugin echoing your own outgoing message
back — not the user speaking. **Do not reply. Do not acknowledge. Stay silent.**
