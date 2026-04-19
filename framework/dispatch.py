#!/usr/bin/env python3
"""dispatch.py — safe plugin invoker (no shell).

Given a plugin name, intent, and a JSON blob of args, runs the plugin's
`invoke` argv with `--<arg> <value>` flags appended. No shell parsing —
the model's args can't turn into shell metacharacters.

Invoke modes (declared per-intent in the manifest via `invoke_mode`):
  - "args"       (default) — args become --<name> <value> CLI flags
  - "stdin_json" — full args dict is piped to the plugin on stdin as JSON

Usage from bash (the model runs this):
  python3 framework/dispatch.py <plugin> <intent> '{"origin":"...","destination":"..."}'

Stdout of the plugin is relayed; exit code mirrors the plugin. Every call
is logged as a JSONL record to tasks/dispatch.log for observability.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "tasks" / "dispatch.log"

SCALAR_TYPES = (str, int, float, bool)


def load_registry() -> dict:
    with open(ROOT / "framework" / "registry.json") as f:
        return json.load(f)


def find_intent(plugin_name: str, intent_name: str) -> dict:
    reg = load_registry()
    for plugin in reg.get("plugins", []):
        if plugin.get("name") != plugin_name:
            continue
        for intent in plugin.get("intents", []):
            if intent.get("name") == intent_name:
                return intent
        raise SystemExit(f"intent '{intent_name}' not found on plugin '{plugin_name}'")
    raise SystemExit(f"plugin '{plugin_name}' not found in registry")


def log_call(plugin: str, intent: str, duration_ms: int, exit_code: int) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "plugin": plugin,
            "intent": intent,
            "duration_ms": duration_ms,
            "exit_code": exit_code,
        }
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps(record) + "\n")
    except OSError:
        pass  # never fail dispatch because logging broke


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: dispatch.py <plugin> <intent> '<args-json>'", file=sys.stderr)
        return 2

    plugin, intent_name, args_json = argv
    try:
        args_dict = json.loads(args_json)
    except json.JSONDecodeError as e:
        print(f"args must be valid JSON object: {e}", file=sys.stderr)
        return 2
    if not isinstance(args_dict, dict):
        print("args must be a JSON object", file=sys.stderr)
        return 2

    # Reject non-scalar values up front — no dict/list can ever reach argv
    # or the plugin's JSON input, closing the str(value) coercion hole.
    for name, value in args_dict.items():
        if not isinstance(value, SCALAR_TYPES) and value is not None:
            print(
                f"arg '{name}' must be a scalar (str/int/float/bool), got {type(value).__name__}",
                file=sys.stderr,
            )
            return 2

    intent = find_intent(plugin, intent_name)
    invoke = intent.get("invoke")
    if not isinstance(invoke, list) or not invoke:
        raise SystemExit(
            f"intent '{intent_name}' has no argv-style 'invoke' list; update the manifest"
        )

    allowed = set((intent.get("args") or {}).keys())
    for name in args_dict:
        if name not in allowed:
            print(f"unknown arg '{name}' for intent '{intent_name}'", file=sys.stderr)
            return 2

    mode = intent.get("invoke_mode", "args")
    cmd = list(invoke)
    stdin_payload: str | None = None

    if mode == "args":
        for name, value in args_dict.items():
            if value is None:
                continue
            cmd += [f"--{name}", str(value)]
    elif mode == "stdin_json":
        stdin_payload = json.dumps(args_dict)
    else:
        print(f"unknown invoke_mode '{mode}' on intent '{intent_name}'", file=sys.stderr)
        return 2

    started = time.monotonic()
    proc = subprocess.run(cmd, cwd=ROOT, text=True, input=stdin_payload)
    duration_ms = int((time.monotonic() - started) * 1000)
    log_call(plugin, intent_name, duration_ms, proc.returncode)

    if proc.returncode != 0:
        print(f"(dispatch) {shlex.join(cmd)} exited {proc.returncode}", file=sys.stderr)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
