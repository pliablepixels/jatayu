#!/usr/bin/env python3
"""
build-registry.py — Builds framework/registry.json from plugins and channels.

Also writes:
  framework/.channels  — comma-separated plugin strings for start.sh --channels flag
  framework/channel-rules.md — concatenated channel.md files for Claude to read

Called by framework/loader.sh on every bot start. Skips the rebuild when
all source files are older than the existing registry.json.

Validates each manifest:
  - Required env vars: warn if missing from the current environment.
  - Declared capabilities: print for operator review.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
PLUGINS_DIR = ROOT / "plugins"
CHANNELS_DIR = ROOT / "channels"
FRAMEWORK_DIR = ROOT / "framework"
REGISTRY_FILE = FRAMEWORK_DIR / "registry.json"
CHANNELS_FILE = FRAMEWORK_DIR / ".channels"
CHANNEL_RULES_FILE = FRAMEWORK_DIR / "channel-rules.md"


def source_files() -> list[Path]:
    """All inputs whose mtime should invalidate the cached registry."""
    files = list(PLUGINS_DIR.glob("*/manifest.json"))
    files += list(CHANNELS_DIR.glob("*/channel.json"))
    files += list(CHANNELS_DIR.glob("*/channel.md"))
    files.append(Path(__file__))  # rebuild if this script itself changes
    return files


def up_to_date() -> bool:
    if not REGISTRY_FILE.exists() or not CHANNELS_FILE.exists() or not CHANNEL_RULES_FILE.exists():
        return False
    reg_mtime = REGISTRY_FILE.stat().st_mtime
    for f in source_files():
        if f.stat().st_mtime > reg_mtime:
            return False
    return True


def validate_plugin(name: str, manifest: dict) -> list[str]:
    """Return a list of warning strings (empty if clean)."""
    warnings: list[str] = []
    env_decl = manifest.get("env") or {}
    for var, spec in env_decl.items():
        required = bool(spec.get("required")) if isinstance(spec, dict) else False
        if required and not os.environ.get(var):
            purpose = (spec or {}).get("purpose", "no purpose declared")
            warnings.append(f"plugin/{name}: required env var {var} is not set ({purpose})")
    return warnings


def print_capabilities(name: str, manifest: dict) -> None:
    caps = manifest.get("required_capabilities") or []
    if caps:
        print(f"    caps: {', '.join(caps)}")


def main() -> int:
    if up_to_date():
        print("=== Plugin loader === (registry up-to-date, skipping rebuild)")
        return 0

    errors: list[str] = []
    warnings: list[str] = []

    # ── Plugins ─────────────────────────────────────────────────────────────
    plugins = []
    for manifest_path in sorted(PLUGINS_DIR.glob("*/manifest.json")):
        plugin_name = manifest_path.parent.name
        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
            plugins.append(manifest)
            print(f"  plugin:  {plugin_name} ({len(manifest.get('intents', []))} intent(s))")
            print_capabilities(plugin_name, manifest)
            warnings += validate_plugin(plugin_name, manifest)
        except Exception as e:
            errors.append(f"plugin/{plugin_name}: {e}")
            print(f"  error:   plugin/{plugin_name} — {e}", file=sys.stderr)

    # ── Channels ────────────────────────────────────────────────────────────
    channels = []
    channel_plugins = []
    channel_rules_parts = []

    for channel_json in sorted(CHANNELS_DIR.glob("*/channel.json")):
        channel_name = channel_json.parent.name
        try:
            with open(channel_json) as f:
                channel = json.load(f)
            channels.append(channel)
            channel_plugins.append(channel["plugin"])
            print(f"  channel: {channel_name} → {channel['plugin']}")

            channel_md = channel_json.parent / "channel.md"
            if channel_md.exists():
                channel_rules_parts.append(channel_md.read_text())
        except Exception as e:
            errors.append(f"channel/{channel_name}: {e}")
            print(f"  error:   channel/{channel_name} — {e}", file=sys.stderr)

    # ── Write registry.json ─────────────────────────────────────────────────
    registry = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "plugin_count": len(plugins),
        "channel_count": len(channels),
        "plugins": plugins,
        "channels": channels,
    }

    FRAMEWORK_DIR.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_FILE, "w") as f:
        json.dump(registry, f, indent=2)
    print(f"  registry: {REGISTRY_FILE.name} ({len(plugins)} plugin(s), {len(channels)} channel(s))")

    with open(CHANNELS_FILE, "w") as f:
        f.write(",".join(channel_plugins))
    print(f"  channels: {','.join(channel_plugins) or '(none)'}")

    with open(CHANNEL_RULES_FILE, "w") as f:
        f.write("\n\n---\n\n".join(channel_rules_parts) if channel_rules_parts else "")
    print(f"  channel-rules.md: {len(channel_rules_parts)} rule file(s) merged")

    if warnings:
        print(f"\nWarnings: {len(warnings)} plugin config issue(s):", file=sys.stderr)
        for w in warnings:
            print(f"  ⚠ {w}", file=sys.stderr)

    if errors:
        print(f"\nErrors: {len(errors)} item(s) failed to load", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
