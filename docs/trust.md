# Trust tiers

Every inbound channel message is classified by `scripts/trust.py` into a
trust tier. The resolved tier is injected into Claude's context as a
`<trust>` tag on every prompt, so the model doesn't have to re-derive
trust from phone numbers or chat IDs.

## Tiers

Ordered from most to least trusted:

| Tier            | Resolved when…                                  | Default posture |
|-----------------|-------------------------------------------------|-----------------|
| `owner_dm`      | DM from `owner.phone`                           | Full access per `CLAUDE.md` Boundaries |
| `family_dm`     | DM from a `family[].phone`                      | Calendar read; no email/personal docs; ask Owner first for external actions |
| `family_group`  | Group chat listed in `groups[<chat_id>]`        | Family-level access; respond only when tagged |
| `friend_dm`     | DM from a `friends[].phone`                     | Polite, helpful; no special access |
| `unknown_dm`    | DM from a number not in PERSONAL.yaml           | **Pairing required** |
| `unknown_group` | Group chat not in PERSONAL.yaml `groups`        | **Pairing required** |

The tag looks like this in context:

```
<trust tier="family_dm" name="<Family member name>"/>
```

For unknown senders, the phone is included so the Owner can identify:

```
<trust tier="unknown_dm" phone="+19995551234"/>
```

## The classifier

`scripts/trust.py` reads `PERSONAL.yaml` via `scripts/personal.py` and
pattern-matches the `chat_id`.

iMessage `chat_id` formats:

- DM: `any;-;+<phone>` — parses the phone out, matches against
  owner/family/friends.
- Group: `any;+;chat<hash>` — looks up the full chat_id in the
  `groups` map.

Anything that doesn't match a known shape returns `{"tier": "unknown"}`.

CLI for debugging:

```bash
python3 scripts/trust.py "any;-;+1XXXXXXXXXX"
# → {"tier": "family_dm", "name": "<Family member name>"}
```

## Unknown-sender pairing

When the resolved tier is `unknown_dm` or `unknown_group`, CLAUDE.md
says the bot must:

1. Reply **once** with "I don't recognize this sender. I'll only reply
   if the Owner confirms."
2. **Notify the Owner** in the Owner's DM with the sender's
   `chat_id`/phone and the first message — so the Owner can whitelist
   them in `PERSONAL.yaml` if legitimate.
3. **Do nothing else** — no plugin calls, no data sharing, no reply to
   the sender's actual question.

This is a soft guardrail enforced by the model following CLAUDE.md. For
a hard gate you'd need to filter at the channel/MCP layer — not done
today because the iMessage plugin already has its own allowlist
mechanism (managed via `/imessage:access`).

## Adding a known contact

Edit `PERSONAL.yaml`:

```yaml
family:
  - name: <Name>
    relation: <relation — e.g. spouse, parent, child>
    phone: "+1XXXXXXXXXX"

friends:
  - name: <Name>
    phone: "+1XXXXXXXXXX"
```

The change takes effect on the next message (no restart — `personal.py`
re-reads on each invocation, cached only within a single hook process).

## Adding a known group

Groups need explicit entry since there's no phone number to match:

```yaml
groups:
  "any;+;chat1234567890abcdef":
    name: "Family group"
    tier: family_group
```

Get the `chat_id` from `chat.db` or from an inbound group message in
the bot's pane. Unlisted groups stay `unknown_group` and get the
pairing response.

## Extending the classifier

When a new channel is added, extend `scripts/trust.py` with the new
chat_id shape. Keep the tier enum stable — CLAUDE.md and the skills
switch on tier names.

Any subsystem (webhooks, scheduled triggers that want to check who a
prompt is for) should `import trust.classify` rather than re-deriving
from raw phone numbers.
