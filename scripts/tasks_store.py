#!/usr/bin/env python3
"""tasks_store.py — atomic read/write for the pending-tasks JSON file.

Use this anywhere pending.json is written so a crashing/concurrent writer
can't leave a torn file.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from personal import load as load_personal  # noqa: E402


def path() -> Path:
    p = load_personal().get("paths", {}).get("pending_tasks")
    if not p:
        raise RuntimeError("paths.pending_tasks missing in PERSONAL.yaml")
    return Path(p)


def load() -> list[dict[str, Any]]:
    p = path()
    if not p.exists():
        return []
    with open(p) as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{p} must be a JSON array")
    return data


def save(tasks: list[dict[str, Any]]) -> None:
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".pending.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(tasks, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, p)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "load":
        print(json.dumps(load(), indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "save":
        save(json.load(sys.stdin))
    else:
        print("usage: tasks_store.py load | save < payload.json", file=sys.stderr)
        sys.exit(2)
