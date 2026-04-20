## ADDED Requirements

### Requirement: Pre-scheduler creates one-shot leave-now tasks each morning
Each morning, after the briefing is sent, Jatayu SHALL read today's calendar and create a one-shot `pending.json` task for each external appointment, timed to fire when the Owner needs to leave. The destination is resolved from the location field if present, otherwise inferred from the event name.

#### Scenario: Event has a location field
- **WHEN** today's calendar contains an event with a non-empty location that does not match the home address and does not contain virtual-meeting keywords
- **THEN** Jatayu uses the location as destination, calls the directions plugin, and writes a one-shot task with `due = event_start − drive_time − 15 minutes`

#### Scenario: Event has no location — destination inferred from name
- **WHEN** an event has no location field but its name contains a recognizable place or destination (e.g., "Lunch at Founding Farmers", "Dentist on Wisconsin Ave")
- **THEN** Jatayu passes the inferred place name from the event title as destination to the directions plugin and, if the plugin returns a result, writes a one-shot task normally

#### Scenario: Virtual or remote appointment
- **WHEN** an event's location or name contains any of: zoom, teams, meet, google meet, webex, remote, virtual, call, phone (case-insensitive)
- **THEN** no leave-now task is created for that event

#### Scenario: Home-address appointment
- **WHEN** an event's location matches the Owner's home address (from PERSONAL.yaml)
- **THEN** no leave-now task is created for that event

#### Scenario: Due time already passed at scheduling time
- **WHEN** the computed due time (event_start − drive_time − 15 min) is earlier than the current time when the pre-scheduler runs
- **THEN** the task is skipped; no one-shot entry is written

### Requirement: Leave-now alert message is concise and actionable
The leave-now iMessage SHALL name the event, state the departure time, and include estimated drive time so the Owner has everything needed at a glance.

#### Scenario: Alert fires on time
- **WHEN** a leave-now one-shot task fires
- **THEN** Jatayu sends an iMessage to the Owner with the event name, recommended departure time ("leave now" or a specific time), and estimated drive duration

### Requirement: Drive time is computed at pre-scheduler time using live traffic
The directions plugin SHALL be invoked during morning pre-scheduling with the Owner's home address as origin and the event's resolved destination (location field if present, otherwise inferred place name from the event title) as destination.

#### Scenario: Directions plugin returns drive time
- **WHEN** the pre-scheduler calls the directions plugin for an external appointment
- **THEN** the returned drive time (in minutes) is used to compute the task due time

#### Scenario: Directions plugin fails
- **WHEN** the directions plugin returns an error or no result for a given destination
- **THEN** the pre-scheduler skips creating a leave-now task for that event and notes the failure in the morning briefing message
