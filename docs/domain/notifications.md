---
status: active
owner: project
updated: 2026-09-22
tags: [domain, notifications]
---

# Notifications

Notify v2 is the supported delivery app. Loans owns notice intent and the financial
facts behind it; delivery attempts and provider outcomes do not determine loan
state. Customer notice creation/retry and internal scheduled delivery have separate
authorization boundaries. Keep batching, retries and delivery evidence testable.

The operator opens Notifications, filters batches by name/event or status and
reviews a batch's recipients, documents and attempts. Sending eligible digital jobs
is an explicit edit-authorized POST; already sent/cancelled jobs are skipped.
Printing/posting buttons record handling and do not themselves print or send.
Batch status and a job's Sent status do not prove receipt. Connection checks and
stored credentials likewise do not replace provider delivery acceptance. Advanced
template/policy administration stays behind its existing staff/domain requirements.

Read [action permissions](../implementation/action-permission-review.md),
[Workspace operator commands](../implementation/loans-operator-commands.md), and
[private media](../implementation/private-media-access.md) before changing delivery,
exports or attachments. Provider acceptance must not be inferred from mocked tests.

Legacy Notify is retired. Prior redesign notes and integration investigations remain
in the [historical snapshot](../archive/context/2026-09-09/domain/notifications.md)
and [notification archive](../archive/notifications/).
