#!/usr/bin/env python3
"""
directions.py — Google Maps Directions plugin for Jatayu.

Usage:
  python3 plugins/directions/directions.py --origin "..." --destination "..."

Requires:
  GOOGLE_MAPS_API environment variable
"""

import argparse
import os
import sys
import json
import re
import urllib.request
import urllib.parse


def _strip_html(text: str) -> str:
    # Replace block-level tags with a space so words don't run together
    text = re.sub(r"</?(div|span|b|wbr)[^>]*>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r" {2,}", " ", text).strip()


def get_directions(origin: str, destination: str, waypoint: str = None) -> str:
    api_key = os.environ.get("GOOGLE_MAPS_API")
    if not api_key:
        return "Error: GOOGLE_MAPS_API not set."

    params_dict = {
        "origin": origin,
        "destination": destination,
        "departure_time": "now",
        "traffic_model": "best_guess",
        "key": api_key,
    }
    if waypoint:
        params_dict["waypoints"] = f"via:{waypoint}"

    params = urllib.parse.urlencode(params_dict)

    url = f"https://maps.googleapis.com/maps/api/directions/json?{params}"

    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        return f"Error fetching directions: {e}"

    if data.get("status") != "OK":
        return f"Directions error: {data.get('status')} — {data.get('error_message', '')}"

    route = data["routes"][0]
    leg = route["legs"][0]

    distance = leg["distance"]["text"]
    duration = leg["duration"]["text"]
    duration_traffic = leg.get("duration_in_traffic", {}).get("text", duration)
    via = route.get("summary", "")

    delay_sec = (
        leg.get("duration_in_traffic", {}).get("value", 0)
        - leg["duration"]["value"]
    )
    delay_min = round(delay_sec / 60)

    lines = [
        f"From: {leg['start_address']}",
        f"To:   {leg['end_address']}",
        f"Distance: {distance}",
    ]

    if delay_min > 2:
        lines.append(f"Travel time: {duration_traffic} with traffic (+{delay_min} min vs {duration} without)")
    elif delay_min < -2:
        lines.append(f"Travel time: {duration_traffic} — faster than usual ({duration} typical)")
    else:
        lines.append(f"Travel time: {duration_traffic} — no significant delays")

    if via:
        lines.append(f"Via: {via}")

    steps = leg.get("steps", [])
    if steps:
        lines.append("Route:")
        for step in steps:
            instruction = _strip_html(step.get("html_instructions", ""))
            dist = step.get("distance", {}).get("text", "")
            lines.append(f"  • {instruction} ({dist})")

    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get driving directions via Google Maps")
    parser.add_argument("--origin", required=True, help="Starting location")
    parser.add_argument("--destination", required=True, help="Destination location")
    parser.add_argument("--waypoint", default=None, help="Optional via waypoint (forces route through this point)")
    args = parser.parse_args()

    print(get_directions(args.origin, args.destination, waypoint=args.waypoint))
