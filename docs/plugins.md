# Plugins

Plugins are **out-of-process tools** that fetch data or take actions
against external systems (APIs, local databases, shell commands). If
your extension needs the network, a secret, or the filesystem, it's a
plugin. If it's words the model should follow, it's a [skill](skills.md).

## Anatomy

```
plugins/<name>/
  manifest.json     declares the plugin to the framework
  setup.sh          one-time install (optional)
  <your code>       any runtime (Python, Node, Go, shell…)
```

## Manifest schema

```json
{
  "name": "directions",
  "description": "Get driving directions and real-time traffic via Google Maps",
  "version": "1.0",

  "env": {
    "GOOGLE_MAPS_API": {
      "required": true,
      "purpose": "Google Maps Directions API key"
    }
  },

  "required_capabilities": [
    "network:maps.googleapis.com",
    "env:GOOGLE_MAPS_API"
  ],

  "intents": [
    {
      "name": "driving_directions",
      "description": "…",
      "examples": ["how do I get to the airport?", "…"],
      "args": {
        "origin":      "Starting location…",
        "destination": "Destination…",
        "waypoint":    "Optional via waypoint"
      },
      "invoke": ["python3", "plugins/directions/directions.py"],
      "invoke_mode": "args"
    }
  ],

  "lifecycle": {
    "setup": "bash plugins/directions/setup.sh"
  }
}
```

### Field reference

| Field | Purpose |
|-------|---------|
| `name` | Unique key; must equal the directory name. |
| `description` | One-line — shown to Claude in the registry. |
| `env` | Required environment variables. `build-registry.py` warns at boot if a required var is missing. |
| `required_capabilities` | Declarative list for operator review. Strings like `network:<host>`, `env:<var>`, `fs_read:<path>`. Not enforced today, but declared capabilities are the unit of audit when you install a third-party plugin. |
| `intents[]` | One per user-facing action. Each intent has its own args and invoke. |
| `intents[].examples` | User phrasings. `preclassify.py` keyword-matches against these to suggest a `<route>` hint. |
| `intents[].args` | Map of arg name → description. **Only listed args are accepted** by dispatch. |
| `intents[].invoke` | argv list. Paths are relative to repo root. |
| `intents[].invoke_mode` | `"args"` (default) — each arg becomes `--<name> <value>`. `"stdin_json"` — the full args dict is piped as JSON on stdin. |
| `lifecycle.setup` | Shell command run by `loader.sh` on every start (idempotent). |

## Dispatch

The model never shells out directly. It calls:

```bash
python3 framework/dispatch.py <plugin> <intent> '<args-json>'
```

`dispatch.py` guarantees:

1. **Args are valid JSON object.** Reject anything else.
2. **Only scalar values** (str/int/float/bool). Nested dicts/lists are rejected — closes the `str(value)` coercion hole where a list would silently stringify.
3. **Only declared args.** An `args` key not in the manifest is rejected.
4. **No shell interpolation.** `subprocess.run(argv, shell=False)`.
5. **Every call is logged** to `tasks/dispatch.log` as one JSONL record:
   ```json
   {"ts":"…","plugin":"directions","intent":"driving_directions","duration_ms":247,"exit_code":0}
   ```

## Invoke modes

### `args` (default)

Arguments become CLI flags. Good for small, scalar inputs.

Manifest:
```json
"invoke": ["python3", "plugins/directions/directions.py"],
"invoke_mode": "args"
```

Dispatch expands to:
```
python3 plugins/directions/directions.py --origin "…" --destination "…"
```

### `stdin_json`

The full args dict is piped as JSON on stdin. Use when an arg is naturally
structured or large enough that flag-per-field gets awkward.

Manifest:
```json
"invoke_mode": "stdin_json"
```

Plugin reads:
```python
import json, sys
args = json.load(sys.stdin)
```

## Adding a plugin

1. `mkdir plugins/weather`
2. Write `plugins/weather/manifest.json` with intents, args, and `invoke`.
3. Implement the CLI (e.g. `plugins/weather/weather.py --zip 90210`).
4. Write `plugins/weather/setup.sh` if you need deps or API keys
   (idempotent — it runs on every `start.sh`).
5. Restart the bot. `loader.sh` picks it up.
6. Verify: `python3 framework/build-registry.py` lists it; try
   `python3 framework/dispatch.py weather forecast '{"zip":"90210"}'`.

## Observability

- **Registry at build time:**
  ```
  plugin: directions (1 intent(s))
    caps: network:maps.googleapis.com, env:GOOGLE_MAPS_API
  ```
  Missing required env → printed as `⚠ plugin/directions: required env var GOOGLE_MAPS_API is not set`.

- **Call log:** `tasks/dispatch.log` — JSONL. Quick queries:
  ```bash
  # most-called plugin in the last 24h
  jq -r '.plugin' tasks/dispatch.log | sort | uniq -c | sort -rn
  # slow calls
  jq -c 'select(.duration_ms > 2000)' tasks/dispatch.log
  # failures
  jq -c 'select(.exit_code != 0)' tasks/dispatch.log
  ```

## Security notes

- Plugins run with the bot's full user privileges today. `required_capabilities`
  is declarative — operator discipline, not sandboxing. If you ever install
  a third-party plugin, read the manifest's capability list and the code.
- Never leak the Owner's PII in plugin stdout (the PreToolUse PII guard
  doesn't cover plugin output — it covers the model's tool-use inputs).
  Plugins that return secrets or addresses should do so only when the
  request came from `owner_dm` (the model enforces this via trust tier).
- A plugin's `setup.sh` runs on every bot start. Keep it idempotent and
  fast. Don't print secrets.
