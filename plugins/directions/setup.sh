#!/bin/bash
if [ -n "$GOOGLE_MAPS_API" ]; then
  echo "✅  directions: GOOGLE_MAPS_API is set"
else
  echo "⚠️   directions: GOOGLE_MAPS_API not set — plugin will not work."
  echo "     Add to your shell profile: export GOOGLE_MAPS_API=your_key_here"
fi
