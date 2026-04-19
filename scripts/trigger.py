#!/usr/bin/env python3
"""trigger.py — unified entry point for injecting prompts into the running bot.

Any subsystem that needs to hand the bot a prompt (heartbeat, webhook
handler, future cron jobs, etc.) uses `send(prompt, chat_id=...)` instead
of touching tmux directly. Today this routes through tmux send-keys; if
the runtime changes (e.g. headless `claude -p` per task) only this file
needs updating.

CLI:
  trigger.py --chat-id "any;-;+1XXX…" "your prompt here"
  trigger.py "your prompt here"   # chat_id optional
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time

# Set by start.sh so heartbeat/webhook/cron triggers always target the same
# session the bot is running in. Falls back to "jatayu" for ad-hoc CLI use.
TMUX_SESSION = os.environ.get("JATAYU_TMUX_SESSION", "jatayu")
BUSY_MARKERS = ("esc to interrupt",)

# Strip control chars (esp. CR/LF) before feeding to `tmux send-keys`.
# Without this, a newline inside an untrusted pending-task prompt would
# submit the partial text as a prompt and line-inject the remainder as a
# fresh one — arbitrary tool calls in the bot's context.
_CTRL_RE = re.compile(r"[\x00-\x1f\x7f]")


def _sanitize(s: str) -> str:
    return _CTRL_RE.sub(" ", s or "")


def session_exists() -> bool:
    return subprocess.run(
        ["tmux", "has-session", "-t", TMUX_SESSION],
        check=False, capture_output=True,
    ).returncode == 0


def session_busy() -> bool:
    r = subprocess.run(
        ["tmux", "capture-pane", "-t", TMUX_SESSION, "-p"],
        check=False, capture_output=True, text=True,
    )
    if r.returncode != 0:
        return False
    return any(m in r.stdout for m in BUSY_MARKERS)


def send(prompt: str, chat_id: str | None = None) -> str:
    """Deliver a prompt to the running bot.

    Returns one of: "sent", "no-session", "busy".
    """
    if not session_exists():
        return "no-session"
    if session_busy():
        return "busy"

    chat_id = _sanitize(chat_id) if chat_id else None
    prompt = _sanitize(prompt)
    body = f"[Triggered] chat_id={chat_id} — {prompt}" if chat_id else prompt
    # -l forces literal interpretation so values like "Enter" or "C-c" are
    # typed as characters, not treated as tmux key names. Enter is sent as
    # a separate non-literal call to submit the prompt.
    subprocess.run(["tmux", "send-keys", "-l", "-t", TMUX_SESSION, body], check=False)
    time.sleep(0.3)
    subprocess.run(["tmux", "send-keys", "-t", TMUX_SESSION, "Enter"], check=False)
    return "sent"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chat-id", dest="chat_id", default=None)
    ap.add_argument("prompt")
    args = ap.parse_args()
    result = send(args.prompt, chat_id=args.chat_id)
    print(result)
    return 0 if result == "sent" else 1


if __name__ == "__main__":
    sys.exit(main())
