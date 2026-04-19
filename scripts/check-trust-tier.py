#!/usr/bin/env python3
"""check-trust-tier.py — PreToolUse gate for untrusted senders.

The unknown-sender pairing rule in CLAUDE.md is prose — soft guidance the
model can drift from under social-engineering pressure. This hook makes
it a hard gate: when the current turn was triggered by an unknown sender,
plugin dispatches are blocked outright, and iMessage replies are
constrained to (a) the Owner's DM, for the out-of-band notification, and
(b) the originating unknown chat itself, for the one-line "I don't
recognize this sender" reply.

Tier is resolved from `tasks/context/latest-turn.json` (stamped by
context-hook on UserPromptSubmit) via scripts/trust.py. If no turn is
stamped we're not in a channel-triggered context — terminal/CLI use —
and the hook is a no-op.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from personal import load as load_personal  # noqa: E402
from trust import classify as classify_trust  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LATEST_TURN = ROOT / "tasks" / "context" / "latest-turn.json"

UNKNOWN_TIERS = {"unknown_dm", "unknown_group", "unknown"}


def _block(msg: str) -> None:
    print(f"\n🚫 BLOCKED (trust-tier gate): {msg}\n", file=sys.stderr)
    sys.exit(1)


def _load_turn() -> dict | None:
    if not LATEST_TURN.exists():
        return None
    try:
        return json.loads(LATEST_TURN.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def main() -> int:
    tool_name = os.environ.get("CLAUDE_TOOL_NAME", "")
    try:
        tool_input = json.loads(os.environ.get("CLAUDE_TOOL_INPUT") or "{}")
    except json.JSONDecodeError:
        return 0

    turn = _load_turn()
    if not turn:
        return 0  # no channel context — terminal use, not gated here
    origin_chat = (turn.get("chat_id") or "").strip()
    if not origin_chat:
        return 0

    tier = classify_trust(origin_chat).get("tier", "unknown")
    if tier not in UNKNOWN_TIERS:
        return 0

    # Owner's DM GUID — the one destination we always allow for the
    # out-of-band "unknown sender wants to talk to you" notification.
    try:
        cfg = load_personal()
    except Exception:
        cfg = {}
    owner_chat = ((cfg.get("owner") or {}).get("primary_chat_guid") or "").strip()

    if tool_name == "mcp__imessage__reply":
        target = (tool_input.get("chat_id") or "").strip()
        if target == owner_chat:
            return 0  # notifying the Owner — allowed
        if target == origin_chat:
            # Replying to the unknown sender itself. Block attachments
            # regardless; a text reply is fine (the "I don't recognize"
            # line). Boundary #8 hook handles attachment policy too, but
            # enforce here for belt-and-suspenders.
            if tool_input.get("files"):
                _block(
                    f"attachments to an unknown sender (chat_id={target!r}, "
                    f"tier={tier}) are never allowed"
                )
            return 0
        _block(
            f"reply to chat_id={target!r} while the current turn is from an "
            f"untrusted sender (tier={tier}, origin={origin_chat!r}). Only "
            f"the Owner's DM or the originating chat may be replied to."
        )

    if tool_name == "Bash":
        cmd = tool_input.get("command", "") or ""
        # Plugin dispatch is the main escalation path — cover both the
        # canonical invocation and any variant that routes through it.
        if "framework/dispatch.py" in cmd:
            _block(
                f"plugin dispatch while the current turn is from an "
                f"untrusted sender (tier={tier}, chat_id={origin_chat!r}). "
                f"Unknown senders must not be able to trigger plugins."
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
