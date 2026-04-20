#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"

# Preflight: if anything setup.sh installs is missing, run setup first.
# Cheap invariants — no latency when all three pass.
needs_setup=0
[ -f "$DIR/PERSONAL.yaml" ] || needs_setup=1
python3 -c "import yaml" 2>/dev/null || needs_setup=1
[ -f "$HOME/Library/LaunchAgents/com.jatayu.heartbeat.plist" ] || needs_setup=1
if [ "$needs_setup" = 1 ]; then
  echo "One or more prerequisites missing — running setup.sh first..."
  echo ""
  bash "$DIR/setup.sh" || { echo "setup.sh failed — aborting start.sh"; exit 1; }
  echo ""
fi

if [ -z "$TMUX" ]; then
  if tmux has-session -t jatayu 2>/dev/null; then
    echo "Session 'jatayu' already exists. Attach with: tmux attach -t jatayu"
    exit 1
  fi
  tmux new-session -d -s jatayu "bash '$0'"
  echo "Started in tmux session 'jatayu'. Attach with: tmux attach -t jatayu"
  exit 0
fi
mkdir -p "$DIR/tasks" && [ -f "$DIR/tasks/pending.json" ] || echo '[]' > "$DIR/tasks/pending.json"
bash "$DIR/framework/loader.sh" || exit 1

# Bot names from PERSONAL.yaml (gitignored), exposed to the forked iMessage
# plugin so it recognises messages addressed by name without hardcoding
# identity in source. Single parser = scripts/personal.py.
export IMESSAGE_BOT_NAMES="$(python3 "$DIR/scripts/personal.py" bot-names)"

# Owner signature from PERSONAL.yaml — the plugin strips this from the
# echo-dedupe key so a bot-sent reply doesn't slip through consumeEcho
# when chat.db mangles trailing whitespace.
export IMESSAGE_OWNER_SIGNATURE="$(python3 "$DIR/scripts/personal.py" signature 2>/dev/null || true)"

# Single tmux session name shared with scripts/trigger.py (heartbeat, webhooks).
export JATAYU_TMUX_SESSION="jatayu"

CHANNELS=$(cat "$DIR/framework/autogen-channels")

# Inline MCP config — registers the forked iMessage server under the plain name
# "imessage" so the channel tag "server:imessage" resolves. Built via python3
# so $DIR is JSON-encoded regardless of special characters in the path.
MCP_CONFIG=$(python3 -c "
import json, sys
cwd = sys.argv[1]
print(json.dumps({'mcpServers': {'imessage': {'command': 'bun', 'args': ['run', '--cwd', cwd, '--silent', 'start']}}}))
" "$DIR/plugins/imessage-local")

# --dangerously-skip-permissions: tool auto-approval for this trusted session.
# --mcp-config: starts the forked iMessage MCP server under name "imessage".
# --plugin-dir: loads the plugin's skills (/imessage:access, /imessage:configure).
# --dangerously-load-development-channels: required for "server:" channels
#   (bypasses the preview-phase allowlist for locally-developed channels).
#
# Auto-confirm the dev-channels prompt ("I am using this for local
# development"). Poll until the prompt renders, then press Enter. Give up
# after ~30s so a hung launch doesn't block forever.
(for i in $(seq 1 30); do
   if tmux capture-pane -t jatayu -p 2>/dev/null | grep -q "Loading development channels"; then
     tmux send-keys -t jatayu Enter
     break
   fi
   sleep 1
 done) &

claude --dangerously-skip-permissions \
       --dangerously-load-development-channels "$CHANNELS" \
       --mcp-config "$MCP_CONFIG" \
       --plugin-dir "$DIR/plugins/imessage-local" \
       "hello. Remember to process plugins before doing websearch as CLAUDE.md tells you to"

