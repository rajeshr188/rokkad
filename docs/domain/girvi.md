---
status: active
owner: project
updated: 2026-06-17
tags: [domain, girvi, loans]
related: [../flows/girvi-loan-lifecycle.md, ../implementation/girvi-services.md, ../flows/dea-posting-flow.md]
---

# Girvi

Girvi manages pledged-loan operations: given loans, taken loans, collateral, custody, release, repayment, renewal, repledge, auction, sale, and loan documents.

## Core Concepts

- `GivenLoan`: money lent to a borrower against pledged items.
- `TakenLoan`: money borrowed from a lender, often backed by repledged collateral.
- Loan items/collateral: pledged assets with weights, purity, valuation, and custody state.
- Rates and rate sources: required for collateral valuation.
- License and series: numbering and compliance controls for loan IDs/documents.

## Canonical Lifecycle

`GivenLoan` uses the canonical loan lifecycle:

`Draft -> PendingApproval -> Approved -> ActiveCurrent -> ClosurePending -> Closed`

Additional servicing/recovery states are used when the workflow requires them:

- `ActiveOverdue`
- `ActiveNPA`
- `RenewalPending`
- `Renewed`
- `AuctionInitiated`
- `AuctionInProgress`
- `AuctionComplete`
- `WrittenOff`
- `Rejected`
- `Cancelled`

Legacy values such as `Created`, `Disbursed`, `Released`, `Defaulted`, `Auctioned`,
and `Repledged` are compatibility inputs only. Runtime flows normalize them to
the canonical lifecycle before deciding legal transitions.

`TakenLoan` uses a smaller lifecycle because borrowed/repledged loans do not share
the same release and auction semantics as customer pawn loans:

`Draft -> Active -> SettlementPending -> Closed`

`Cancelled` is allowed before activation.

## Architecture Direction

- Use command/use-case services for lifecycle transitions.
- Keep accounting effects out of models and views; delegate posting to DEA through facade/services.
- Use `girvi.facade` for cross-app reads.
- Standardize lifecycle language; old status values are accepted only through compatibility mappings.
- The side-by-side Loans app release-readiness selector snapshots net weight, purity, appraisal, and as-of public-facade metal-rate inputs. It applies the disbursal-snapshotted valuation method and computes the minimum fees/interest plus principal settlement required to keep retained collateral within the maximum LTV.
- Full release is an atomic, immutable workflow: completed accrual periods and prior accounting must be resolved first; release-day partial-period interest is finalized under the snapshotted slab policy; the exact resulting balance is collected through source-linked DEA events/outboxes; the release header, item valuation evidence, and custody history are persisted; and the loan closes only after every collateral item is returned to the customer.
- Partial release uses the same immutable document, accrual, valuation, accounting, and custody boundaries, but accepts only the calculated minimum settlement and returns only selected vault items. Fees and interest settle first, principal reduces only as needed to keep retained collateral within maximum LTV, mixed custody derives the partially-released condition, and the stored loan state remains active. A rounded partial accrual rebases the next monthly window to the following day.
- Release reversal is administrator-only, reason-required, and newest-first. It preserves the original release and accrual rows, records linked compensating DEA events, restores custody only when the item still matches the original handoff state, reopens a reversed full release to active, and removes the reversed release-day period from future accrual scheduling.

## Current Active Work

The event-driven Girvi/DEA posting plan is active. See [active plan](../plans/active.md).

Archived Girvi sources are preserved in [archive/girvi](../archive/girvi/).
