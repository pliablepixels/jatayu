#!/usr/bin/env python3
"""trust.py — resolve chat_id → trust tier.

Single source of truth for "who is this sender, and what are they allowed
to do?" Callers (context-hook, future webhook handlers) use this instead
of re-implementing the owner/family/friends matching.

Tiers (least → most trusted):
  unknown_group  — group chat we don't recognize
  unknown_dm     — DM from a number not in PERSONAL.yaml
  friend_dm      — DM from a `friends[].phone`
  family_group   — group chat explicitly listed in `groups` map
  family_dm      — DM from a `family[].phone`
  owner_dm       — DM from `owner.phone`

The chat_id format is the iMessage plugin's:
  DM:    any;-;+<phone>
  Group: any;+;chat<hash>
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from personal import load as load_personal  # noqa: E402


def _dm_phone(chat_id: str) -> str | None:
    if ";-;" not in chat_id:
        return None
    return chat_id.split(";-;", 1)[1]


def _is_group(chat_id: str) -> bool:
    return ";+;chat" in chat_id


def classify(chat_id: str) -> dict[str, Any]:
    """Return {'tier': str, 'name'?: str, 'phone'?: str} for the given chat_id."""
    p = load_personal()

    phone = _dm_phone(chat_id)
    if phone:
        owner_phone = (p.get("owner") or {}).get("phone", "")
        if phone == owner_phone:
            return {"tier": "owner_dm", "name": (p["owner"] or {}).get("name", "Owner")}
        for member in p.get("family") or []:
            if member.get("phone") == phone:
                return {"tier": "family_dm", "name": member.get("name")}
        for friend in p.get("friends") or []:
            if friend.get("phone") == phone:
                return {"tier": "friend_dm", "name": friend.get("name")}
        return {"tier": "unknown_dm", "phone": phone}

    if _is_group(chat_id):
        groups = p.get("groups") or {}
        entry = groups.get(chat_id)
        if entry:
            return {
                "tier": entry.get("tier", "family_group"),
                "name": entry.get("name", "group"),
            }
        return {"tier": "unknown_group"}

    return {"tier": "unknown"}


if __name__ == "__main__":
    import json

    if len(sys.argv) != 2:
        print("usage: trust.py <chat_id>", file=sys.stderr)
        sys.exit(2)
    print(json.dumps(classify(sys.argv[1]), indent=2))
