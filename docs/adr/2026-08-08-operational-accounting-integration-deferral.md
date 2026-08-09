---
status: accepted
owner: project
updated: 2026-08-08
tags: [accounting, dea, loans, girvi, integration, outbox]
related: [2026-08-08-girvi-loans-permanent-independent-coexistence.md, ../domain/accounting.md, ../constitution.md]
---

# ADR: Operational Accounting Integration Deferral

Date: 2026-08-08
Status: Accepted

## Context

Operational modules need to remain usable while DEA and the standalone
accounting successor are still being understood and matured. Deleting DEA
integrations would destroy tested posting contracts, historical explanation,
and the least risky path to later activation. Pretending deferred events are
posted would be financially false.

Loans already has a durable source-event and outbox boundary. Girvi has a
versioned posting-contract outbox that can be adopted one workflow at a time.
Those boundaries can capture business intent without requiring immediate
delivery to DEA.

## Decision

1. The audited workspace preference `accounting__integration_mode` controls
   operational accounting delivery. Its supported values are `DEFERRED` and
   `DEA`; the default is `DEFERRED`.
2. In `DEFERRED` mode, Loans persists its immutable source event and outbox but
   does not run DEA readiness checks or automatic DEA delivery.
3. Deferred outboxes remain `PENDING`. They are not posted, failed, reconciled,
   or represented as accounting truth.
4. A caller-supplied delivery handler remains available for explicit tests and
   controlled integrations. Normal direct delivery without a handler is a
   no-op while the workspace is deferred.
5. Pending or failed DEA delivery does not block later Loans business actions
   while deferred. In `DEA` mode, the existing readiness, automatic delivery,
   posting, dependency blocking, idempotency, and reversal contracts remain.
6. Existing DEA vouchers, journals, reversals, and source links are untouched.
   DEA remains independently available and authoritative for workspaces that
   explicitly select `DEA`.
7. Re-enabling DEA requires an explicit audited preference change. Replay or
   migration of events captured while deferred requires a separately designed,
   reconciled activation process; this ADR does not authorize bulk replay.
8. A deferred event cannot use DEA reversal semantics because no DEA effect
   exists. Domain correction must remain compensating source evidence and must
   never fabricate a posted reversal.
9. Girvi must be decoupled in a separate vertical slice. Its payment-voucher
   dependencies also carry operational payment evidence, so they must not be
   deleted until an independent durable replacement exists.
10. The first Girvi vertical slices cover `GivenLoan` disbursal and `TakenLoan`
   activation. In `DEFERRED` mode they record canonical versioned `DISBURSAL`
   or `TAKEN_LOAN_ACTIVATION` outbox contracts idempotently and do not resolve
   a DEA party account or create/post a DEA `PaymentVoucher`. The loan
   transition remains the operational truth and user messaging says the
   accounting event is recorded for deferred delivery, never posted.
11. `TakenLoan` repayment now uses immutable Girvi-owned `LoanRepayment`
   evidence. New repayment idempotency and settlement reads use that evidence;
   historical DEA-only vouchers remain readable, while vouchers linked from
   new evidence are excluded from the compatibility fold to prevent double
   counting. In `DEA` mode the payment voucher and evidence are created in one
   transaction. In `DEFERRED` mode one `TAKEN_LOAN_REPAYMENT` outbox event
   remains `PENDING` and no payment voucher is fabricated.
12. Repayment evidence cannot be updated or deleted, including through bulk
   SQL paths. A reversal is a separate one-to-one compensating row for the same
   loan, direction, and exact total/principal/interest split. The original is
   never mutated, and a reversal cannot itself be reversed.
13. Girvi repayment and posting idempotency keys permit exact replay only.
    Reusing a key with different economic or source details fails closed rather
    than silently returning earlier evidence.
14. `GivenLoan` repayment, releases, accruals, auction/sale recovery, renewal,
   write-off, and their accounting reversals remain on existing DEA paths until
   separate slices provide equivalent operational evidence and lifecycle
   coverage.

## Consequences

- MVP workflows can continue without forcing users through incomplete central
  accounting setup.
- Durable source evidence preserves a future integration path without claiming
  accounting completion.
- Reports and UI must distinguish business events from posted accounting
  effects and must not include deferred `PENDING` events as ledger truth.
- Activation back to DEA needs readiness, replay ordering, idempotency,
  reversal, and reconciliation design before any deferred event is delivered.
- This refines accounting delivery while the temporary parity-selection ADR's
  strict source-ownership rules remain in force.
