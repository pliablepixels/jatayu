---
name: calendar
description: Use when the inbound message asks about events, schedules, itineraries, flights, or anything calendar-related. Covers Shared Calendar read/write rules and the calendar-first-then-email lookup order.
---

# Calendar rules

The Calendar service and Shared Calendar names are resolved from
`PERSONAL.yaml` (`services.calendar`, `services.shared_calendar`).

## Lookup order

For anything that looks like an event, schedule, or itinerary question:

1. Search the **Shared Calendar only** first.
2. Fall back to the Email service only if the calendar returns nothing
   useful.

Never read from or write to any other calendar.

## Access

| Group   | Read Shared Calendar | Write Shared Calendar                    |
|---------|----------------------|------------------------------------------|
| Owner   | ✅                   | ✅ (add/edit/delete freely)              |
| Family  | ✅                   | ⚠️ Request-only: ask Owner in the group chat first and wait for explicit approval |
| Friends | ❌                   | ❌                                       |

## Event descriptions

When creating calendar events, add `<Signature>` to the event description
(substitute the signature from `PERSONAL.yaml`).
