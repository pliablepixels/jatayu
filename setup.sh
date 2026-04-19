#!/bin/bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
OK="✅"
WARN="⚠️ "
FAIL="❌"

pass() { echo "$OK  $1"; }
warn() { echo "$WARN $1"; }
fail() { echo "$FAIL $1"; exit 1; }

echo ""
echo "=== Jatayu setup ==="
echo ""

# ── 1. Claude Code ────────────────────────────────────────────────────────────
if command -v claude &>/dev/null; then
  pass "Claude Code found: $(claude --version 2>/dev/null | head -1)"
else
  fail "Claude Code not found. Install it from https://claude.ai/code then re-run setup."
fi

# ── 2. tmux ───────────────────────────────────────────────────────────────────
if command -v tmux &>/dev/null; then
  pass "tmux found"
else
  warn "tmux not found — installing via Homebrew..."
  if command -v brew &>/dev/null; then
    brew install tmux
    pass "tmux installed"
  else
    fail "Homebrew not found. Install tmux manually (brew install tmux) then re-run setup."
  fi
fi

# ── 3. Python 3 ───────────────────────────────────────────────────────────────
if command -v python3 &>/dev/null; then
  pass "Python 3 found: $(python3 --version)"
else
  fail "Python 3 not found. Install it from https://python.org then re-run setup."
fi

# ── 4. Python dependencies ────────────────────────────────────────────────────
if python3 -c "import yaml" 2>/dev/null; then
  pass "PyYAML found"
else
  warn "PyYAML not found — installing..."
  python3 -m pip install --user --quiet pyyaml && pass "PyYAML installed" \
    || fail "pip install pyyaml failed; install manually then re-run setup"
fi

# ── 5. bun (runs the vendored iMessage MCP server) ────────────────────────────
if command -v bun &>/dev/null; then
  pass "bun found: $(bun --version)"
else
  warn "bun not found — installing via Homebrew..."
  if command -v brew &>/dev/null; then
    brew install oven-sh/bun/bun
    pass "bun installed"
  else
    fail "Homebrew not found. Install bun manually (https://bun.sh) then re-run setup."
  fi
fi

# ── 6. PERSONAL.yaml ──────────────────────────────────────────────────────────
# If freshly created from template, exit so the user fills it in before
# start.sh launches a session with placeholder identity.
FRESH_PERSONAL=0
if [ -f "$DIR/PERSONAL.yaml" ]; then
  pass "PERSONAL.yaml exists"
else
  cp "$DIR/PERSONAL.example.yaml" "$DIR/PERSONAL.yaml"
  warn "PERSONAL.yaml created from template"
  FRESH_PERSONAL=1
fi

# ── 8. tasks/pending.json ─────────────────────────────────────────────────────
mkdir -p "$DIR/tasks"
if [ -f "$DIR/tasks/pending.json" ]; then
  pass "tasks/pending.json exists"
else
  echo '[]' > "$DIR/tasks/pending.json"
  pass "tasks/pending.json created"
fi

# ── 9. launchd heartbeat agent ────────────────────────────────────────────────
# Renders launchd/*.plist.template → ~/Library/LaunchAgents and (re)loads it.
# The agent fires scripts/heartbeat.py every 5 min to process pending.json,
# independent of any tmux session. Remove with `launchctl unload` + file delete.
PLIST_TEMPLATE="$DIR/launchd/com.jatayu.heartbeat.plist.template"
PLIST_DEST="$HOME/Library/LaunchAgents/com.jatayu.heartbeat.plist"
if [ -f "$PLIST_TEMPLATE" ]; then
  mkdir -p "$HOME/Library/LaunchAgents"
  START_CALENDAR_INTERVAL=$(python3 -c "
import yaml
d = yaml.safe_load(open('$DIR/PERSONAL.yaml'))
secs = int(d.get('heartbeat', {}).get('interval_seconds', 300))
mins = max(1, round(secs / 60))
entries = ['<dict><key>Minute</key><integer>' + str(m) + '</integer></dict>' for m in range(0, 60, mins)]
print('<array>' + ''.join(entries) + '</array>')
")
  sed -e "s|__REPO__|$DIR|g" \
      -e "s|__HOME__|$HOME|g" \
      -e "s|__PATH__|$PATH|g" \
      -e "s|__START_CALENDAR_INTERVAL__|$START_CALENDAR_INTERVAL|g" \
      "$PLIST_TEMPLATE" > "$PLIST_DEST"
  # Owner-readable only — plist paths reveal home dir layout and agent
  # config, and a world-readable LaunchAgent file lets any local user on
  # a multi-user box inspect Jatayu's runtime surface.
  chmod 600 "$PLIST_DEST"
  launchctl unload "$PLIST_DEST" 2>/dev/null || true
  launchctl load "$PLIST_DEST" && pass "launchd heartbeat agent loaded (every 5 min)"
else
  warn "launchd template missing — heartbeat will not fire"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
if [ "$FRESH_PERSONAL" = 1 ]; then
  echo ""
  echo "=== Setup incomplete ==="
  echo ""
  echo "PERSONAL.yaml was just created from the template with placeholder"
  echo "values. Fill it in (name, phone, email, family, services), then"
  echo "re-run ./start.sh."
  echo ""
  exit 1
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit PERSONAL.yaml with your identity and contacts"
echo "  2. Run: bash start.sh"
echo ""
echo "Heartbeat runs via launchd — independent of the tmux session."
echo "  Logs:   tasks/heartbeat.log"
echo "  Stop:   launchctl unload ~/Library/LaunchAgents/com.jatayu.heartbeat.plist"
echo ""
