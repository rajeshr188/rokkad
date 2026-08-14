---
status: completed
owner: loans
updated: 2026-08-13
tags: [loans, notices, notify, scheduling, phase-7]
related: [../plans/loans-rewrite-roadmap.md, ../apps/loans/architecture-and-girvi-parity.md, ../adr/2026-07-15-loans-rewrite-domain-and-cutover-architecture.md]
---

# PawnLoan E7.1 Notices

## Boundary

Loans owns why and when a PawnLoan notice exists. Notify v2 owns how it is
rendered, sent, retried, and observed at the provider boundary.

`PawnLoanNotice` stores the workspace, loan, notice kind, channel, idempotency
key, schedule, recipient snapshot, financial payload snapshot, actor, and the
linked Notify event/job IDs. It deliberately does not store delivery status,
provider reference, failure reason, or sent time. Those values are derived from
the linked `NotificationJob` by the notice read selector.

## Supported Workflows

- Repayment reminder: active loan with an amount due.
- Interest due: active loan with outstanding interest.
- Overdue notice: active loan whose canonical event-folded balance is overdue.
- Release confirmation: closed loan with recorded release evidence.

Email requires the Party email snapshot. SMS and WhatsApp require the Party
phone snapshot. E7.2 now permits an auction notice only when it references the
same loan's Loans-owned `PawnLoanAuction`; staff still cannot create a detached
auction notice from the general notice form.

## Delivery

Creating an immediate notice commits its intent and Notify job atomically, then
dispatches after commit. Future notices are selected against an explicit clock:

```powershell
.\.venv314\Scripts\python.exe manage.py tenant_command dispatch_pawn_loan_notices --schema=jcl1
```

The scheduler dispatches only Notify jobs still in `QUEUED` state. A failed job
is visible and retryable from the PawnLoan detail. Provider setup and attempt
evidence remain in Notify v2.

Customer and internal operational notices intentionally remain separate Loans
intent aggregates. Their shared `notice_dispatch` coordinator owns only the
mechanical Notify lifecycle: schedule enforcement, linked-job resolution,
idempotent SENT handling, cancelled fail-closed behavior, deterministic queued
selection, batch limits, and sent/failed counts. It does not decide whether a
notice should exist or who receives it.

## Verification

- Tenant migration: `loans.0009_pawnloannotice`
- Focused tests: six notice domain/service/command tests
- UI regressions: active-loan notice action and form dispatch
- Full regression: 160 tenant-aware Loans tests
- Django system check and migration-drift check pass
- Migration applied with `migrate_schemas --tenant`
