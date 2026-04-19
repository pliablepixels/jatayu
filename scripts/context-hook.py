#!/usr/bin/env python3
"""context-hook.py — UserPromptSubmit + Stop hooks for per-chat context.

read  — UserPromptSubmit. If the prompt carries `<channel source=...
        chat_id=...>`, emit:
          * <local-time>   — current time
          * <trust>        — resolved trust tier (owner_dm, family_dm, …)
          * <prior-summary> — rolling LLM summary of archived turns (if any)
          * <prior-context> — recent exchanges

write — Stop hook. Appends the exchange to per-chat JSON and the daily
        running log (memory/YYYY-MM-DD.md). When the per-chat log exceeds
        MAX_ENTRIES, the oldest turns are archived to .archive.jsonl and
        a rolling summary is regenerated via `claude -p`.

Per-chat files under tasks/context/<chat_key>.{json,archive.jsonl,summary.md}.
Daily cross-chat log under memory/YYYY-MM-DD.md.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo  # noqa: F401  (loaded lazily via astimezone())

ROOT = Path(__file__).resolve().parent.parent
CONTEXT_DIR = ROOT / "tasks" / "context"
MEMORY_DIR = ROOT / "memory"
MAX_ENTRIES = 50
TRIM_TO = 40
MAX_TEXT_BYTES = 16 * 1024
SUMMARY_TIMEOUT_S = 45

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trust import classify as classify_trust  # noqa: E402


def _truncate(text: str) -> str:
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= MAX_TEXT_BYTES:
        return text
    return encoded[:MAX_TEXT_BYTES].decode("utf-8", errors="ignore") + "…[truncated]"


def _chat_path(chat_key: str) -> Path:
    safe = re.sub(r"[^\w\-+]", "_", chat_key)
    return CONTEXT_DIR / f"{safe}.json"


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def _save(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


_CHANNEL_RE = re.compile(
    r'<channel[^>]*\bsource="(?P<source>[^"]+)"[^>]*\bchat_id="(?P<chat_id>[^"]+)"'
)
_CHANNEL_USER_RE = re.compile(r'<channel[^>]*\buser="(?P<user>[^"]+)"')
_CHANNEL_TS_RE = re.compile(r'<channel[^>]*\bts="(?P<ts>[^"]+)"')


def _extract_channel(text: str) -> tuple[str, str, str] | None:
    """Return (chat_key, source, chat_id) if a channel tag is present."""
    m = _CHANNEL_RE.search(text or "")
    if not m:
        return None
    source = m.group("source")
    chat_id = m.group("chat_id")
    return (f"{source.replace(':', '_')}_{chat_id}", source, chat_id)


def _extract_user(text: str) -> str | None:
    m = _CHANNEL_USER_RE.search(text or "")
    return m.group("user") if m else None


def _extract_ts(text: str) -> str | None:
    m = _CHANNEL_TS_RE.search(text or "")
    return m.group("ts") if m else None


def _to_local(ts_iso: str) -> str | None:
    """Parse an ISO-8601 timestamp (e.g. '2026-04-19T10:29:20.964Z') and
    return it in the host's local timezone. Returns None on parse failure."""
    if not ts_iso:
        return None
    try:
        # Python <3.11 doesn't accept the trailing 'Z'; normalise.
        normalised = ts_iso.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalised)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone().isoformat(timespec="seconds")
    except (ValueError, TypeError):
        return None


def _summary_path(chat_path: Path) -> Path:
    return chat_path.with_suffix(".summary.md")


def _archive_path(chat_path: Path) -> Path:
    return chat_path.with_suffix(".archive.jsonl")


def _daily_log() -> Path:
    return MEMORY_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.md"


def _append_daily(source: str, chat_id: str, role: str, text: str) -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    hhmm = datetime.now().strftime("%H:%M")
    line = f"[{hhmm} {source} {chat_id}] {role}: {_truncate(text)}\n"
    with open(_daily_log(), "a") as f:
        f.write(line)


def _regenerate_summary(chat_path: Path, dropped: list[dict]) -> None:
    """Blocking LLM call via `claude -p`. Skipped if already compacting
    (recursion guard) or if dropped is empty. Best-effort: on failure or
    timeout we keep the prior summary — archived turns are still on disk."""
    if not dropped or os.environ.get("CLAUDE_BOT_COMPACTING") == "1":
        return

    summary_path = _summary_path(chat_path)
    existing = summary_path.read_text() if summary_path.exists() else "(none yet)"

    new_lines = [
        f"[{(e.get('ts') or '')[:16]}] {e.get('role','?')}: {e.get('text','')[:500]}"
        for e in dropped
    ]
    dropped_text = "\n".join(new_lines)[:50_000]

    prompt = (
        "You maintain a rolling summary of a single iMessage conversation for a "
        "personal-assistant bot. Output ONLY the updated summary — no preamble, "
        "no markdown headers. Keep under 300 words. Preserve: key facts about the "
        "person, decisions made, open threads, preferences, recurring topics.\n\n"
        f"EXISTING SUMMARY:\n{existing}\n\n"
        f"NEWLY ARCHIVED MESSAGES:\n{dropped_text}"
    )

    try:
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=SUMMARY_TIMEOUT_S,
            env={**os.environ, "CLAUDE_BOT_COMPACTING": "1"},
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return

    out = (result.stdout or "").strip()
    if result.returncode == 0 and out:
        tmp = summary_path.with_suffix(".md.tmp")
        tmp.write_text(out + "\n")
        os.replace(tmp, summary_path)


def cmd_read() -> int:
    payload = json.load(sys.stdin) if not sys.stdin.isatty() else {}
    prompt = payload.get("prompt") or payload.get("user_prompt") or ""
    parsed = _extract_channel(prompt)
    if not parsed:
        return 0
    chat_key, _source, chat_id = parsed

    local_now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    print(f"<local-time>{local_now}</local-time>")

    # The channel `ts` attribute is always UTC (Z-suffix). Past mistake:
    # treating UTC ts as wall-clock. We pre-convert here so the model never
    # has to do the conversion itself — anchor "now"/"X ago" reasoning on
    # the local fields below, never on the raw channel ts.
    raw_ts = _extract_ts(prompt)
    local_msg = _to_local(raw_ts) if raw_ts else None
    if local_msg:
        print(
            f'<message-time local="{local_msg}" utc="{raw_ts}">'
            "Inbound message wall-clock time (local). The channel tag's "
            "ts attribute is UTC — use this local value for any "
            "now/recency/'X minutes ago' reasoning."
            "</message-time>"
        )

    trust = classify_trust(chat_id)
    attrs = " ".join(f'{k}="{v}"' for k, v in trust.items() if v is not None)
    print(f"<trust {attrs}/>")

    # Hard reminder: replies must go through the channel's reply tool, not
    # stdout. CLAUDE.md + framework/channel-rules.md say this, but a prose
    # rule in a session-start doc is easy to drift from. Repeating it per
    # turn keeps it front-of-mind.
    print(
        f'<delivery chat_id="{chat_id}" reply_tool="mcp__imessage__reply">'
        " This message arrived via iMessage. Your reply MUST go through "
        "mcp__imessage__reply with the chat_id above — terminal output is "
        "NOT delivered to the sender. If the task needs multiple steps, "
        "send a short acknowledgement (\"On it...\") via mcp__imessage__reply "
        "FIRST, then do the work."
        "</delivery>"
    )

    # Stamp who triggered this turn so PreToolUse hooks (Boundary #8 reply
    # check, trust-tier gate) can tell whether the request came from the
    # Owner vs. a family member in the same group chat. Per-chat files
    # keyed by chat_id avoid a race where chat B's turn overwrites chat
    # A's stamp between the hook and a tool call still attributed to A.
    # `latest-turn.json` is kept for callers that need "what was the most
    # recent turn anywhere" (e.g. trust-tier gate for a Bash dispatch).
    user = _extract_user(prompt)
    if user:
        CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
        latest = {
            "chat_id": chat_id,
            "user": user,
            "ts": local_now,
        }
        blob = json.dumps(latest)
        safe_key = re.sub(r"[^\w\-+]", "_", chat_key)
        for target in (
            CONTEXT_DIR / "latest-turn.json",
            CONTEXT_DIR / f"latest-turn-{safe_key}.json",
        ):
            tmp = target.with_suffix(target.suffix + ".tmp")
            tmp.write_text(blob)
            os.replace(tmp, target)

    chat_path = _chat_path(chat_key)
    summary_path = _summary_path(chat_path)
    if summary_path.exists():
        print(f'<prior-summary chat_id="{chat_key}">')
        print(summary_path.read_text().rstrip())
        print("</prior-summary>")

    entries = _load(chat_path)
    if entries:
        recent = entries[-20:]
        print(f'<prior-context chat_id="{chat_key}" entries="{len(recent)}">')
        for e in recent:
            role = e.get("role", "?")
            ts = (e.get("ts") or "")[:16]
            print(f"[{ts}] {role}: {e.get('text','')}")
        print("</prior-context>")
    return 0


def cmd_write() -> int:
    try:
        payload = json.load(sys.stdin) if not sys.stdin.isatty() else {}
    except json.JSONDecodeError:
        return 0

    messages = payload.get("messages") or payload.get("transcript") or []
    user_text = ""
    assistant_text = ""
    channel_blob = ""
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        text = content if isinstance(content, str) else json.dumps(content)
        if role == "user" and not user_text:
            user_text = text
            channel_blob = text
        elif role == "assistant":
            assistant_text = text

    parsed = _extract_channel(channel_blob)
    if not parsed or not (user_text or assistant_text):
        return 0
    chat_key, source, chat_id = parsed

    chat_path = _chat_path(chat_key)
    entries = _load(chat_path)
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    if user_text:
        entries.append({"ts": now, "role": "user", "text": _truncate(user_text)})
        _append_daily(source, chat_id, "user", user_text)
    if assistant_text:
        entries.append({"ts": now, "role": "assistant", "text": _truncate(assistant_text)})
        _append_daily(source, chat_id, "assistant", assistant_text)

    if len(entries) > MAX_ENTRIES:
        dropped = entries[:-TRIM_TO]
        entries = entries[-TRIM_TO:]
        archive = _archive_path(chat_path)
        archive.parent.mkdir(parents=True, exist_ok=True)
        with open(archive, "a") as f:
            for e in dropped:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        _regenerate_summary(chat_path, dropped)

    _save(chat_path, entries)
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "read":
        sys.exit(cmd_read())
    if cmd == "write":
        sys.exit(cmd_write())
    print("usage: context-hook.py read | write", file=sys.stderr)
    sys.exit(2)
