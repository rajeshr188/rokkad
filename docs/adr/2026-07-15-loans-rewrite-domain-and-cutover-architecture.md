---
status: accepted
owner: project
updated: 2026-07-15
tags: [adr, loans, girvi, dea, accounting, cutover]
related: [../plans/loans-rewrite-roadmap.md, ../domain/girvi.md, ../domain/accounting.md, ../constitution.md, 2026-07-05-girvi-series-number-sequence.md, 2026-06-27-girvi-release-accrual-lifecycle-boundary.md]
---

# ADR: Loans Rewrite Domain And Cutover Architecture

Date: 2026-07-15
Status: Accepted

## Context

The existing `girvi` app carries production loan workflows and compatibility
history. Rewriting it in place would mix stabilization, migration, and new
domain design. Rokkad therefore needs a side-by-side `loans` app with explicit
ownership of new PawnLoans, strict DEA boundaries, and a reversible cutover.

## Decision

### Domain And Rollout

1. `PawnLoan` represents customer pawn/gold loans. A future `FundingLoan`
   represents lender/repledge funding. They are separate aggregates.
2. The production MVP is PawnLoan-first. FundingLoan/repledging, notices,
   auctions, renewals, and portal integration are essential post-MVP work.
3. New-app collateral cannot be repledged until FundingLoan servicing is
   implemented.
4. After enablement, new loans are created only in `loans`. Existing Girvi loans
   remain writable and owned by Girvi until they close. No imported record may
   become a second writable copy.
5. A unified read layer combines both systems for dashboards and reports,
   labels source ownership, and routes mutations to the owning app.

### License And Numbering

1. A regulatory `LoanLicense` belongs to one workspace; a workspace may have
   multiple active licenses.
2. Each license owns multiple `LoanSeries`. Each series owns locked, bounded
   sequences for pawn loans and pawn-loan releases.
3. Official loan numbers allocate at draft creation, never recycle, and never
   wrap. Reaching the series maximum requires a new or different series.
4. Expiry blocks new drafts and disbursements. Existing loans retain their
   original license and may still be serviced, released, reversed, reported,
   and reprinted.
5. An approved, undisbursed loan under an expired license must move to an active
   license/series and be approved again.
6. Future FundingLoans use a workspace-wide sequence such as `FL-000001` and do
   not depend on a regulatory pawn license.

### Policy And Lifecycle

1. Workspace preferences supply defaults; a license may override selected loan
   policies. Series control numbering only.
2. Resolved economic policy is snapshotted at disbursal. Approval freezes the
   economic payload; reopening an approved loan requires a reason and reapproval.
3. Disbursed economic facts are immutable.
4. Zero balance is closure-ready. `CLOSED` requires completed return of every
   collateral item through a release document.
5. Release owns collateral custody handoff. A lender-held item cannot be
   released to its pawn borrower.

### Interest, Repayment, And Partial Release

1. Rates are monthly. Simple/compound method, partial-month slab,
   capitalization interval, valuation method, maximum LTV, and cash/accrual
   accounting policy are resolved from workspace/license policy and snapshotted.
2. Calculations retain high precision; finalized monthly accrual rows store
   currency-rounded amounts. Compound capitalization is an explicit event after
   a configurable interval, default 12 periods.
3. Cash interest accounting is the default and recognizes income when collected.
   Accrual policy posts finalized receivable/income accruals through DEA.
4. MVP repayments use the current business date and allocate fees/charges,
   overdue interest, current interest, then principal. Backdating and staff
   allocation override are deferred.
5. Partial release first settles fees and interest, then reduces principal as
   needed to keep retained-collateral LTV within policy, default 80 percent.
6. Valuation policy may use current metal rate times net weight times purity,
   latest staff appraisal, or the lower of both. Release snapshots all inputs.

### DEA Delivery And Corrections

1. DEA remains the only owner of vouchers, posting rules, period locks,
   immutable journal entries, and accounting reversals.
2. Each accounting-relevant loan event and a durable outbox row commit
   atomically. Posting is attempted immediately with a deterministic idempotency
   key. Failure is visible and safely retryable.
3. Pending or failed posting blocks dependent financial operations but does not
   erase the committed loan-domain event.
4. Disbursal, repayment, accrual/capitalization, and release have explicit
   reversals. Dependent events must be reversed newest-first. Every reversal is
   administrator-only and requires a reason.
5. Accounting setup gates disbursal, not setup or drafting. Disbursal requires
   an open period and all required funding, receivable, income, and fee mappings.

## Consequences

- The new app can be developed and enabled incrementally without dual writes.
- Temporary Girvi/Loans coexistence is a supported product state, not merely a
  migration accident.
- Outbox, reversal, readiness, and unified-read work are MVP dependencies.
- FundingLoan schema is deferred until a complete funding workflow slice is
  planned.
- Tenant schema changes must be rolled out with `migrate_schemas`.

## Rejected Alternatives

- In-place Girvi rewrite: rejected because rollback and ownership would be
  ambiguous.
- Big-bang migration of active Girvi loans: rejected because legacy loans remain
  operational in Girvi until closure.
- Direct journal creation or mutable posted entries: rejected by the accounting
  constitution.
- Sequence wrap/reuse: rejected because regulatory document identity must remain
  stable and unique.
- Financial closure without custody return: rejected because settlement and
  physical handoff are separate required facts.

## Review Triggers

Review this ADR before implementing FundingLoans, active-loan operational
migration, repayment backdating, staff allocation overrides, or branch-scoped
license authorization.
