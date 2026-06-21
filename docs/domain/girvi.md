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

## Current Active Work

The event-driven Girvi/DEA posting plan is active. See [active plan](../plans/active.md).

Archived Girvi sources are preserved in [archive/girvi](../archive/girvi/).
