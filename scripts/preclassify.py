#!/usr/bin/env python3
"""preclassify.py — UserPromptSubmit hook for cheap plugin routing.

Scans the incoming prompt for keyword hits against registry.json intents
(name, examples, description). If a single intent dominates, prints a nudge:

    <route plugin="…" intent="…" confidence="high"/>

Claude Code injects the nudge as additional system context. The model can
still disagree; this is just a shortcut to avoid re-reading the full
registry every turn.

No hit → silent exit 0, no cost.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "framework" / "registry.json"


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z']{3,}", text.lower()))


def main() -> int:
    if not REGISTRY.exists():
        return 0

    try:
        payload = json.load(sys.stdin) if not sys.stdin.isatty() else {}
    except json.JSONDecodeError:
        return 0
    prompt = payload.get("prompt") or payload.get("user_prompt") or ""
    prompt_tokens = tokens(prompt)
    if not prompt_tokens:
        return 0

    with open(REGISTRY) as f:
        reg = json.load(f)

    scores: list[tuple[int, str, str, str]] = []
    for plugin in reg.get("plugins", []):
        pname = plugin.get("name", "")
        for intent in plugin.get("intents", []):
            iname = intent.get("name", "")
            corpus = " ".join(
                [iname, intent.get("description", ""), *(intent.get("examples") or [])]
            )
            intent_tokens = tokens(corpus) - {"the", "a", "to", "is", "are", "how", "what", "with"}
            hits = len(prompt_tokens & intent_tokens)
            if hits >= 2:
                scores.append((hits, pname, iname, intent.get("description", "")))

    if not scores:
        return 0
    scores.sort(reverse=True)
    top = scores[0]
    if len(scores) > 1 and scores[1][0] >= top[0]:
        return 0

    confidence = "high" if top[0] >= 3 else "medium"
    print(
        f'<route plugin="{top[1]}" intent="{top[2]}" confidence="{confidence}"/>'
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
