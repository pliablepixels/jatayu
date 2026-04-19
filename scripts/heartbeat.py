#!/usr/bin/env python3
"""heartbeat.py — launchd-fired scheduled-reminder driver.

Launchd fires this every 5 minutes. It reads pending.json, and for each
entry where due<=now, calls `trigger.send` (which currently routes through
tmux send-keys). The action text *is* the prompt — Claude does whatever
it describes (typically: gather data and iMessage the Owner via
mcp__imessage__reply).

Repeating tasks have `due` snapped forward to the next aligned boundary
(e.g. a 5m repeat fires at :00, :05, :10). One-shots are removed.

Skips firing cleanly when the trigger reports no-session or busy — tasks
remain unfired and will be reconsidered on the next tick.

CLI:
  heartbeat.py           # run one tick (what launchd invokes)
  heartbeat.py --list    # print upcoming tasks in human-readable form

Exits quickly when nothing is due — the common case.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from tasks_store import load, save  # noqa: E402
from trigger import send as trigger_send  # noqa: E402


def parse_repeat(spec: str) -> timedelta:
    n, unit = int(spec[:-1]), spec[-1]
    return {
        "s": timedelta(seconds=n),
        "m": timedelta(minutes=n),
        "h": timedelta(hours=n),
        "d": timedelta(days=n),
    }[unit]


def next_aligned_due(now: datetime, delta: timedelta) -> datetime:
    """Return the next due time snapped to a clock boundary (e.g. :00/:05/:10 for 5m)."""
    total_seconds = int(delta.total_seconds())
    if total_seconds >= 86400:
        return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elapsed = int((now - midnight).total_seconds())
    next_slot = ((elapsed // total_seconds) + 1) * total_seconds
    return midnight + timedelta(seconds=next_slot)




def list_tasks() -> int:
    tasks = load()
    if not tasks:
        print("(no tasks scheduled)")
        return 0
    now = datetime.now().astimezone()
    for t in tasks:
        due_s = t.get("due", "(no due)")
        try:
            due = datetime.fromisoformat(due_s) if due_s != "(no due)" else None
            rel = ""
            if due:
                delta = due - now
                if delta.total_seconds() < 0:
                    rel = " (overdue)"
                else:
                    mins = int(delta.total_seconds() // 60)
                    if mins < 60:
                        rel = f" (in {mins}m)"
                    elif mins < 1440:
                        rel = f" (in {mins // 60}h{mins % 60}m)"
                    else:
                        rel = f" (in {mins // 1440}d)"
        except ValueError:
            rel = " (invalid due)"
        repeat = t.get("repeat", "once")
        action = t.get("action", "")[:80]
        print(f"- {due_s}{rel} [{repeat}] {action}")
    return 0


def run_tick() -> int:
    tasks = load()
    now = datetime.now().astimezone()
    remaining: list[dict] = []
    changed = False
    fired: list[str] = []
    skipped_reason: str | None = None

    for t in tasks:
        repeat = t.get("repeat")
        raw_due = t.get("due")
        if raw_due:
            due = datetime.fromisoformat(raw_due)
        elif repeat:
            due = next_aligned_due(now, parse_repeat(repeat))
            t["due"] = due.isoformat()
            changed = True
            remaining.append(t)
            continue
        else:
            remaining.append(t)
            continue

        if due > now:
            remaining.append(t)
            continue

        result = trigger_send(t["action"], chat_id=t.get("chat_id"))
        if result != "sent":
            # no-session or busy — defer to next tick, don't consume the fire
            skipped_reason = result
            remaining.append(t)
            continue

        fired.append(t.get("action", "")[:60])
        changed = True

        if repeat:
            delta = parse_repeat(repeat)
            t["due"] = next_aligned_due(now, delta).isoformat()
            remaining.append(t)
        # one-shots drop off

    if changed:
        save(remaining)

    ts = now.strftime("%Y-%m-%d %H:%M:%S %z")
    if fired:
        for a in fired:
            print(f"[{ts}] fired: {a}")
    elif skipped_reason:
        print(f"[{ts}] tick — skipped ({skipped_reason}, {len(tasks)} pending)")
    else:
        print(f"[{ts}] tick — nothing due ({len(tasks)} task(s) pending)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="print scheduled tasks and exit")
    args = ap.parse_args()
    if args.list:
        return list_tasks()
    return run_tick()


if __name__ == "__main__":
    sys.exit(main())
