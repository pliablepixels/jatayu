## ADDED Requirements

### Requirement: Morning briefing includes leave-now pre-scheduler step
After sending the morning briefing, Jatayu SHALL run the leave-now pre-scheduler as an additional step: read today's full calendar, identify external appointments, compute drive times, and write one-shot tasks to `pending.json`.

#### Scenario: External appointments present
- **WHEN** today's calendar contains one or more external appointments (non-empty location, not home address, not virtual)
- **THEN** after sending the briefing message, Jatayu writes one-shot leave-now tasks to `pending.json` for each qualifying appointment

#### Scenario: No external appointments
- **WHEN** today's calendar has no external appointments
- **THEN** no leave-now tasks are written; the briefing is otherwise unchanged

#### Scenario: Pre-scheduler failure does not block briefing
- **WHEN** the pre-scheduler step encounters an error (calendar unavailable, directions plugin failure)
- **THEN** the morning briefing message is still sent; the error is noted briefly in the briefing or silently skipped
