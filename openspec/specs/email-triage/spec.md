# Email Triage

## Purpose

Jatayu performs a midday email triage on weekdays at 12:30pm, surfacing only actionable or time-sensitive emails that arrived after the morning briefing. Silent when nothing requires the Owner's attention.

## Requirements

### Requirement: Midday email triage fires on weekdays at 12:30pm
Jatayu SHALL scan the Owner's inbox at 12:30pm on weekdays (Monday–Friday) for emails that arrived since the morning briefing and are actionable or time-sensitive.

#### Scenario: Actionable emails found
- **WHEN** the triage task fires and there are unread emails requiring action or response
- **THEN** Jatayu sends an iMessage to the Owner listing only those emails (one bullet per email, same format as morning briefing)

#### Scenario: No actionable emails
- **WHEN** the triage task fires and there are no actionable emails
- **THEN** Jatayu sends no message (completely silent)

#### Scenario: Weekend suppression
- **WHEN** the task is due on a Saturday or Sunday
- **THEN** Jatayu sends no message and the task reschedules normally for the next weekday at 12:30pm

### Requirement: Triage scope is limited to post-morning emails
The triage SHALL focus on emails received after the morning briefing was sent, not the full inbox, to avoid re-surfacing items the Owner already saw.

#### Scenario: Email received before morning briefing
- **WHEN** an email arrived before today's morning briefing time
- **THEN** it is excluded from the triage results

#### Scenario: Email received after morning briefing
- **WHEN** an email arrived after today's morning briefing time
- **THEN** it is eligible for inclusion if actionable
