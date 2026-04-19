#!/usr/bin/env python3
"""personal.py — single parser for PERSONAL.yaml (gitignored).

Every other script imports from here so a shape change lands once.

Usage:
  from scripts.personal import load, pii_values
  p = load()
  owner_phone = p["owner"]["phone"]
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
PERSONAL_YAML = Path(os.environ.get("CLAUDE_BOT_PERSONAL", ROOT / "PERSONAL.yaml"))


@lru_cache(maxsize=1)
def load() -> dict[str, Any]:
    if not PERSONAL_YAML.exists():
        raise FileNotFoundError(
            f"{PERSONAL_YAML} not found. Copy PERSONAL.example.yaml and fill it in."
        )
    with open(PERSONAL_YAML) as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{PERSONAL_YAML} must be a YAML mapping at the top level")
    return data


def pii_values() -> list[str]:
    """Return every identifier that must never leak into committed files.

    Walks the tree and collects strings that look like identifiers: phones,
    emails, names, absolute paths, chat GUIDs, addresses.
    """
    p = load()
    out: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, str):
            s = node.strip()
            if len(s) > 3:
                out.add(s)

    walk(p)

    sys_user = os.environ.get("USER") or os.environ.get("LOGNAME")
    if sys_user:
        out.add(f"/Users/{sys_user}/")
        out.add(f"/home/{sys_user}/")

    return sorted(out)


def bot_names() -> list[str]:
    """Names the bot answers to (lowercased), for the iMessage filter."""
    p = load()
    names: list[str] = []
    bot = p.get("bot") or {}
    if isinstance(bot.get("name"), str):
        names.append(bot["name"].lower())
    extras = bot.get("aliases") or []
    if isinstance(extras, list):
        names += [str(a).lower() for a in extras]
    return names


def signature() -> str:
    """Bot signature appended to outbound replies (for echo-dedupe stripping)."""
    p = load()
    bot = p.get("bot") or {}
    sig = bot.get("signature")
    return str(sig).strip() if isinstance(sig, str) else ""


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "pii":
        print("\n".join(pii_values()))
    elif len(sys.argv) > 1 and sys.argv[1] == "bot-names":
        print(",".join(bot_names()))
    elif len(sys.argv) > 1 and sys.argv[1] == "signature":
        print(signature())
    else:
        print(json.dumps(load(), indent=2, default=str))
