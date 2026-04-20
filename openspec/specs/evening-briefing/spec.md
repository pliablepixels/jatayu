# Evening Briefing

## Purpose

Jatayu sends the Owner a daily evening summary at 8pm covering tomorrow's calendar, next morning's weather and commute forecast, and any actionable emails received since the morning briefing.

## Requirements

### Requirement: Evening brief fires daily at 8pm
Jatayu SHALL send the Owner an evening summary each day at 8pm local time covering tomorrow's calendar, the next morning's weather and commute forecast, and any actionable emails that arrived since the morning briefing.

#### Scenario: Standard evening brief
- **WHEN** the heartbeat fires at or after 8:00pm and the evening-brief task is due
- **THEN** Jatayu sends an iMessage to the Owner with tomorrow's calendar events, tomorrow morning weather, commute estimate, and any actionable emails (if any)

#### Scenario: No actionable emails
- **WHEN** there are no unread actionable emails since the morning briefing
- **THEN** the email section is omitted from the brief (not replaced with "Inbox clear")

#### Scenario: No calendar events tomorrow
- **WHEN** tomorrow has no calendar events
- **THEN** the calendar section says the day is clear

### Requirement: Evening brief includes commute forecast
The evening brief SHALL include a drive-time estimate for tomorrow morning's home→office commute using the directions plugin, so the Owner can plan departure time.

#### Scenario: Commute included on weekday eve
- **WHEN** tomorrow is a weekday (Monday–Friday)
- **THEN** the brief includes tomorrow morning commute time (both routes if directions plugin returns alternatives)

#### Scenario: Commute omitted on weekend eve
- **WHEN** tomorrow is Saturday or Sunday
- **THEN** the brief omits the commute section entirely
