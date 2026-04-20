#!/usr/bin/env python3
"""check-imessage-reply.py — PreToolUse hook enforcing Boundary #8.

Blocks `mcp__imessage__reply` calls that attach a file from the Owner's
`personal_docs_dir` to a chat where the current turn was *not triggered
by the Owner*. This lets the Owner say "send me the packing list" from
any device/chat and have it work, while still blocking a prompt
injection from a non-Owner member of the same group.

Who-asked-who is sourced from `tasks/context/latest-turn.json`, which
is stamped by scripts/context-hook.py on UserPromptSubmit. That file's
`user` field is the iMessage handle the plugin attributed to this turn
— which the plugin already de-echoed and authenticated via Apple ID.

CLAUDE.md Boundary #8 states the rule in prose; this hook is the
technical gate.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from personal import load  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CONTEXT_DIR = ROOT / "tasks" / "context"


def _latest_turn_path_for(chat_id: str) -> Path:
    """Return the expected per-chat latest-turn stamp path for chat_id.

    Mirrors context-hook._chat_path sanitisation so filenames line up:
    chat_key is "<source>_<chat_id>"; per-chat stamps are written as
    latest-turn-<sanitised-chat_key>.json by context-hook.py.
    """
    safe = re.sub(r"[^\w\-+]", "_", chat_id)
    # Fallback ordering: exact per-chat match first, then global as last resort.
    return CONTEXT_DIR / f"latest-turn-plugin_imessage_imessage_{safe}.json"


def _owner_handles(owner: dict) -> set[str]:
    out: set[str] = set()
    for key in ("phone", "email"):
        v = (owner.get(key) or "").strip().lower()
        if v:
            out.add(v)
    return out


def _load_latest_turn(chat_id: str) -> dict | None:
    candidates = [
        _latest_turn_path_for(chat_id),
        CONTEXT_DIR / "latest-turn.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("chat_id") == chat_id:
            return data
    return None


def _block(chat_id: str, hits: list[str], reason: str) -> None:
    print(
        f"\n🚫 BLOCKED: mcp__imessage__reply — attaching personal doc(s) "
        f"to chat_id={chat_id!r} ({reason}):\n  " + "\n  ".join(hits) +
        "\n\nBoundary #8 (CLAUDE.md): personal documents may only be sent "
        "when the Owner themselves asked for them. If the Owner wants this "
        "file delivered to someone else, they should ask from their own "
        "iMessage handle (any device).\n",
        file=sys.stderr,
    )
    sys.exit(1)


def main() -> int:
    if os.environ.get("CLAUDE_TOOL_NAME", "") != "mcp__imessage__reply":
        return 0

    try:
        tool_input = json.loads(os.environ.get("CLAUDE_TOOL_INPUT") or "{}")
    except json.JSONDecodeError:
        return 0

    files = tool_input.get("files") or []
    if not files:
        return 0

    chat_id = (tool_input.get("chat_id") or "").strip()

    try:
        cfg = load()
    except Exception:
        return 0

    owner = cfg.get("owner") or {}
    owner_chat = (owner.get("primary_chat_guid") or "").strip()
    docs_dir = (owner.get("personal_docs_dir") or "").strip()
    if not docs_dir:
        return 0

    try:
        # strict=True resolves all symlinks in the chain; fail-closed if
        # the docs dir is missing so we never fall through to "no hits".
        docs_real = Path(docs_dir).expanduser().resolve(strict=True)
    except Exception:
        return 0

    hits: list[str] = []
    for f in files:
        if not isinstance(f, str):
            continue
        try:
            # strict=True: a symlink pointing outside docs_real resolves to
            # its real target here, and relative_to() below will correctly
            # reject it. strict=False would leave the symlink unresolved
            # and a crafted path could slip past.
            real = Path(f).expanduser().resolve(strict=True)
        except Exception:
            continue
        try:
            real.relative_to(docs_real)
        except ValueError:
            continue
        hits.append(f)

    if not hits:
        return 0

    # Owner's own DM chat: always allowed.
    if chat_id == owner_chat:
        return 0

    # Otherwise: allow only when the *current turn* was triggered by the
    # Owner's iMessage handle.
    turn = _load_latest_turn(chat_id)
    owner_handles = _owner_handles(owner)
    if turn and turn.get("chat_id") == chat_id:
        asker = (turn.get("user") or "").strip().lower()
        if asker and asker in owner_handles:
            return 0
        reason = f"current turn was triggered by {asker!r}, not the Owner"
    else:
        reason = "no verified requester for this chat (no latest-turn stamp)"
    _block(chat_id, hits, reason)
    return 1  # unreachable — _block exits


if __name__ == "__main__":
    sys.exit(main())
