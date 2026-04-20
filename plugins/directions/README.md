# directions plugin

Turn-by-turn driving directions with live traffic, powered by the Google
Maps Directions API. Answers questions like "how long to get to the
office?", "what's traffic like to <neighborhood>?", "directions from
home to the airport".

## Setup

1. Get a Google Maps API key with the **Directions API** enabled:
   https://console.cloud.google.com/google/maps-apis/credentials
2. Export the key in the shell where you'll run `start.sh`. The easiest
   place is your shell profile (`~/.zshrc` or `~/.bash_profile`):

   ```bash
   export GOOGLE_MAPS_API="AIza…"
   ```

3. Open a new shell so the export takes effect, then run `./start.sh`.
   `plugins/directions/setup.sh` prints a ✅ when the key is detected.

Without the key the plugin loads but every request returns an error.
Jatayu falls back to a generic "I don't have directions access right
now" reply.

## Origin/destination defaults

If the user doesn't specify where they're coming from, the plugin
infers:

- before 9 am → origin = `owner.home_address`, destination = `owner.office_address`
- after 9 am  → origin = `owner.office_address`, destination = `owner.home_address`

Both fields live in `PERSONAL.yaml` (gitignored). Update them there.

## Cost

Google bills per Directions request (see their pricing page). Jatayu
caches nothing, so every question hits the API. If you're cost-sensitive,
set a daily quota in the GCP console.

## Disabling

Remove the plugin directory (`rm -rf plugins/directions/`) and restart.
`framework/build-registry.py` rebuilds `framework/autogen-registry.json` on
every launch, so no other cleanup is needed.
