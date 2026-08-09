---
status: accepted
owner: project
updated: 2026-08-09
tags: [loans, notices, notify-v2, license, verification]
related: [../plans/loan-operational-parity-pilot.md, 2026-08-09-loans-physical-verification-evidence.md]
---

# Loans Operational Notice Intents

## Context

PawnLoan already owns auditable customer notice intents for repayment reminder,
interest due, overdue, release confirmation, and auction. Notify v2 owns their
templates, provider jobs, attempts, and delivery state. The parity audit found
only two missing pilot intents: regulatory-license expiry and confirmed
physical-verification discrepancy. Neither naturally belongs to one PawnLoan.

## Decision

1. Keep existing `PawnLoanNotice` behavior unchanged.
2. Add a separate immutable `LoanOperationalNotice` intent for
   `LICENSE_EXPIRY` and `VERIFICATION_DISCREPANCY`.
3. Operational alerts are internal and addressed to the workspace Owner's
   snapshotted email. The pilot does not infer a regulator or customer as the
   recipient.
4. License alerts may be created from 30 days before expiry onward. Their
   payload freezes license identity, authority, expiry date, and days remaining.
5. Verification alerts require a completed session and a missing, misplaced,
   or unexpected observation. Their payload freezes session, scope, item, loan,
   classification, observed location, and notes.
6. Loans owns intent identity, source links, recipient snapshot, schedule, and
   payload. Notify v2 exclusively owns event/template/job/provider state.
7. Delivery creation is idempotent by workspace request key. Scheduled
   operational alerts share the existing tenant notice dispatcher and retry UI.
8. PostgreSQL enforces exact source shape, source/workspace agreement, and
   append-only intent data. Only the initial Notify event/job link attachment is
   permitted after insert.

## Consequences

- Delivery failure never changes regulatory or verification truth.
- OP6 can render notice registers from Loans intent plus Notify delivery state
  without copying provider status into Loans.
- Broader reminder automation and recipient escalation are post-pilot policy,
  not hidden assumptions in this slice.
