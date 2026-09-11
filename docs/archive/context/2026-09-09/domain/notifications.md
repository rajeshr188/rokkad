---
status: archived
owner: project
updated: 2026-06-17
tags: [domain, notifications]
related: [../plans/backlog.md]
---

> Historical snapshot from docs/domain/notifications.md before the 2026-09-09 documentation cleanup.
> Old priorities and architecture statements are preserved as evidence, not current instructions.
> Use [current documentation](../../../../README.md) first.


# Notifications

Notifications handle user-facing alerts, workflow messages, batching, and future Notify V2 improvements.

## Direction

- Prefer explicit notification events over ad hoc messages scattered through views.
- Keep batching and delivery workflows testable.
- Preserve V2 redesign notes until the app is fully consolidated.
- See [implementation audit](../../../../implementation/whatsapp-notifications-architecture-audit.md) for the current state, risks, and target WhatsApp architecture.

Archived notification sources are preserved in [archive/notifications](../../../notifications).
