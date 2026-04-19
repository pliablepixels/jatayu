---
name: data-access
description: Use when an inbound message asks for personal data (email, documents, any Owner-private info). Decides whether the sender is allowed to see it.
---

# Data access rules

Service names resolve from `PERSONAL.yaml` (`services.email`, etc.).

- **Owner** asks: search the Email service and any relevant tools to
  answer.
- **Family** asks: Shared Calendar allowed (see `calendar` skill). Email
  and other personal data are NOT allowed.
- **Friends** or **anyone else** asks: no access to personal data. Treat
  as any other contact.

Before replying with private data, confirm the sender's identity via the
`<channel user="…">` tag and compare to `PERSONAL.yaml` (`owner.email`,
`owner.phone`, `family[].phone`).

When in doubt, decline silently or say "I can't share that."
