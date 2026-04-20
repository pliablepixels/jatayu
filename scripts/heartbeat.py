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
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from tasks_store import load, save  # noqa: E402
from trigger import send as trigger_send  # noqa: E402


def _local_tz() -> ZoneInfo | None:
    """Resolve the system's IANA timezone by reading /etc/localtime's target.
    Returns None if undetectable — callers fall back to fixed-offset local time."""
    tz_path = Path("/etc/localtime")
    if tz_path.is_symlink():
        target = os.readlink(tz_path)
        marker = "zoneinfo/"
        if marker in target:
            name = target.split(marker, 1)[1]
            try:
                return ZoneInfo(name)
            except ZoneInfoNotFoundError:
                pass
    return None


def _now() -> datetime:
    """Aware 'now' in the system's local timezone. Prefers IANA ZoneInfo so
    DST transitions resolve correctly; falls back to fixed-offset local time."""
    tz = _local_tz()
    return datetime.now(tz=tz) if tz else datetime.now().astimezone()


def _as_local(dt: datetime) -> datetime:
    """Normalize `dt` into local time. Treats naive values as already local.
    After this call, wall-clock arithmetic on the result is DST-correct when
    IANA zone detection succeeded."""
    tz = _local_tz()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz) if tz else dt.astimezone()
    return dt.astimezone(tz) if tz else dt


def _advance_wallclock(dt: datetime, delta: timedelta) -> datetime:
    """Advance `dt` by `delta` in *wall-clock* time.

    A daily 7:15 AM task rescheduled with this helper stays 7:15 AM on the
    next day — even across spring-forward/fall-back — because the addition
    happens on the naive wall component and ZoneInfo resolves the result."""
    local = _as_local(dt)
    tz = local.tzinfo
    naive_next = local.replace(tzinfo=None) + delta
    return naive_next.replace(tzinfo=tz)


def parse_repeat(spec: str) -> timedelta:
    n, unit = int(spec[:-1]), spec[-1]
    return {
        "s": timedelta(seconds=n),
        "m": timedelta(minutes=n),
        "h": timedelta(hours=n),
        "d": timedelta(days=n),
    }[unit]


def next_aligned_due(now: datetime, delta: timedelta) -> datetime:
    """Return the next due time for a repeating task.

    For intervals >= 1 day, anchor at `now + delta` in wall-clock time so the
    time-of-day is preserved on subsequent reschedules (and survives DST).
    For sub-day intervals, snap to a clock boundary (e.g. :00/:05/:10 for 5m)."""
    total_seconds = int(delta.total_seconds())
    if total_seconds >= 86400:
        return _advance_wallclock(now, delta)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elapsed = int((now - midnight).total_seconds())
    next_slot = ((elapsed // total_seconds) + 1) * total_seconds
    return midnight + timedelta(seconds=next_slot)




def list_tasks() -> int:
    tasks = load()
    if not tasks:
        print("(no tasks scheduled)")
        return 0
    now = _now()
    for t in tasks:
        due_s = t.get("due", "(no due)")
        try:
            due = _as_local(datetime.fromisoformat(due_s)) if due_s != "(no due)" else None
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
    now = _now()
    remaining: list[dict] = []
    changed = False
    fired: list[str] = []
    skipped_reason: str | None = None

    for t in tasks:
        repeat = t.get("repeat")
        raw_due = t.get("due")
        if raw_due:
            due = _as_local(datetime.fromisoformat(raw_due))
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
            if delta.total_seconds() >= 86400:
                # Preserve time-of-day across days and DST: advance the last
                # scheduled time in wall-clock, not a UTC-second offset from now.
                t["due"] = _advance_wallclock(due, delta).isoformat()
            else:
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
