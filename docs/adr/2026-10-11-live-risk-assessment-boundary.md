---
status: accepted
owner: loans
updated: 2026-10-11
tags: [monitoring, risk, projections, history]
---

# ADR: Live risk assessment date and Workspace failure boundaries

The owner accepted the [combined monitoring correction](../plans/combined-loan-monitoring-20261011.md).
The existing one-to-one snapshot represents current operational health. Its writer
also creates risk transitions and updates staff alerts. Allowing an earlier or
future date into that writer can replace today's assessment and incorrectly open
or resolve current work items.

## Decision

Only today's local date can be persisted by live refresh, rebuild, bounded batch
and worker services. Reject another date before source selection or writes. The
single-loan writer checks again after obtaining its write lock; an error recorder
also checks before saving, so a calculation crossing midnight cannot save a
previous-day success or failure as a live attempt. The next worker round calculates
the new date through the existing command behavior.

HTTP validates dates and reports the same boundary. Routine refresh forms omit
the hidden rendered date: the server determines today when submitted, including
when a page was opened before midnight. Explicit current-date POST/CLI requests
remain supported; non-today `--as-of` requests fail before any Workspace turn.

Read-only selectors retain their reporting-date input. Such a result is a
restatement from the available source knowledge, not proof of what an assessment
said at the time. It cannot replace a live projection or cause alerts. A future
immutable full-assessment history is separate work; this change does not simulate
that history or invent missing transactions.

The command treats an expected `PermissionDenied` as a failed Workspace turn,
reports it, and continues the other explicitly selected Workspaces. It preserves
the original lifecycle/commercial authorization checks. A one-shot run returns
failure after all turns if any failed; a repeated run keeps bounded retries.
Unexpected programming failures are not swallowed by a blanket exception handler.

## Consequences

No model, migration, financial event, agreement, appraisal or borrower message is
changed. Existing old snapshots are retained and stay outdated under the existing
read predicates until an ordinary today refresh. Restricted-role isolation and
one committed Workspace context per worker loan remain unchanged.

See the [MR-02 implementation and validation](../implementation/live-risk-boundaries-mr02.md).
