#!/usr/bin/env python3
"""check-pii.py — Claude Code PreToolUse hook.

Blocks the model from leaking identifiers from PERSONAL.yaml into either:
  1. a `git commit` / `git push` (Bash)
  2. a file body written via Write / Edit / MultiEdit

The PII values come from scripts/personal.py (single source of truth).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from personal import pii_values  # noqa: E402

tool_name = os.environ.get("CLAUDE_TOOL_NAME", "")
tool_input = json.loads(os.environ.get("CLAUDE_TOOL_INPUT") or "{}")

try:
    patterns = pii_values()
except FileNotFoundError:
    sys.exit(0)


_DIGITS_RE = re.compile(r"\D+")
_WS_RE = re.compile(r"\s+")


def _variants(p: str) -> list[str]:
    """Return the canonical value plus normalized variants.

    Catches obfuscation the plain substring check misses:
      - phones split by formatting ("+1 (240) 344-3286" vs raw digits)
      - addresses/multi-word values with collapsed/expanded whitespace
    """
    out = [p]
    digits = _DIGITS_RE.sub("", p)
    if len(digits) >= 7:  # phone-like only — short digit strings cause FPs
        out.append(digits)
    if _WS_RE.search(p):
        out.append(_WS_RE.sub(" ", p).strip())
    return out


_PATTERN_VARIANTS = [(p, _variants(p)) for p in patterns]


def block(haystack: str) -> None:
    digits_only = _DIGITS_RE.sub("", haystack)
    ws_normalized = _WS_RE.sub(" ", haystack)
    hits: set[str] = set()
    for canonical, variants in _PATTERN_VARIANTS:
        for v in variants:
            if v in haystack or v in ws_normalized or (len(v) >= 7 and v.isdigit() and v in digits_only):
                hits.add(canonical)
                break
    if hits:
        print(f"\n🚫 BLOCKED: PII in {tool_name}: {sorted(hits)}\n", file=sys.stderr)
        sys.exit(1)


if tool_name == "Bash":
    cmd = tool_input.get("command", "")
    if "git" in cmd and any(op in cmd for op in ("commit", "push")):
        staged = subprocess.run(
            ["git", "diff", "--cached"], capture_output=True, text=True
        ).stdout
        block(staged)
elif tool_name == "Write":
    block(tool_input.get("content", ""))
elif tool_name == "Edit":
    block(tool_input.get("new_string", ""))
elif tool_name == "MultiEdit":
    for edit in tool_input.get("edits", []) or []:
        block(edit.get("new_string", ""))

sys.exit(0)
