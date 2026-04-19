#!/bin/bash
# loader.sh — Discovers plugins and builds framework/registry.json.
# Called by start.sh on every bot launch.

set -e
DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Plugin loader ==="

# Build the registry from all plugin manifests
python3 "$DIR/framework/build-registry.py"

# Run lifecycle setup/activate scripts for each plugin
for setup in "$DIR"/plugins/*/setup.sh; do
  [ -f "$setup" ] && bash "$setup"
done

echo "====================="
