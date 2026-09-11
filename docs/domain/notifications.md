---
status: active
owner: project
updated: 2026-09-09
tags: [domain, notifications]
---

# Notifications

Notify v2 is the supported delivery app. Loans owns notice intent and the financial
facts behind it; delivery attempts and provider outcomes do not determine loan
state. Customer notice creation/retry and internal scheduled delivery have separate
authorization boundaries. Keep batching, retries and delivery evidence testable.

Read [action permissions](../implementation/action-permission-review.md),
[Workspace operator commands](../implementation/loans-operator-commands.md), and
[private media](../implementation/private-media-access.md) before changing delivery,
exports or attachments. Provider acceptance must not be inferred from mocked tests.

Legacy Notify is retired. Prior redesign notes and integration investigations remain
in the [historical snapshot](../archive/context/2026-09-09/domain/notifications.md)
and [notification archive](../archive/notifications/).
