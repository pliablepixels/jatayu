# weather plugin

Current conditions and a short-range forecast. Two free, keyless
backends:

- **[Nominatim](https://nominatim.openstreetmap.org)** (OpenStreetMap)
  for geocoding. Handles full postal addresses, city names,
  neighborhoods, landmarks.
- **[Open-Meteo](https://open-meteo.com)** for the forecast. Takes
  lat/lon and returns current + up-to-7-day data.

## Setup

**None.** Both services are free and keyless — no signup, no env var.
The plugin's `setup.sh` just prints a ✅ on launch so you can tell the
plugin loaded.

If a residential address isn't in OSM, the plugin peels off leading
comma-separated segments (street number, street) and retries until it
finds a match — worst case it falls back to the city.

If the machine is offline or DNS fails, the plugin returns an error and
Jatayu falls back to a generic reply.

## Attribution & rate limits

Nominatim's [usage policy](https://operations.osmfoundation.org/policies/nominatim/)
asks for a distinguishing `User-Agent` (we send `jatayu-weather/1.0`)
and no more than 1 request/second. A personal bot stays well under
that. Open-Meteo's free tier is ~10k requests/day.

## Location defaults

If the user doesn't say where, the plugin uses `owner.home_address` from
`PERSONAL.yaml`. A plain question like "what's the weather?" → home.
"Weather at the office" → `owner.office_address`. "Weather in Bangalore"
→ geocodes "Bangalore".

## Units

Fahrenheit / mph / inches — hardcoded for a US-default bot. Change in
`weather.py` (`fetch_forecast()`) if you want metric: swap
`temperature_unit`, `wind_speed_unit`, `precipitation_unit`.

## Rate limits

Open-Meteo's free tier is ~10k requests/day, easily enough for a
personal bot. Their [terms](https://open-meteo.com/en/terms) ask for
attribution only for non-commercial heavy use — not needed for a
private assistant.

## Disabling

Remove the plugin directory (`rm -rf plugins/weather/`) and restart.
`framework/build-registry.py` rebuilds `framework/autogen-registry.json` on
every launch.
