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

## Architecture Direction

- Use command/use-case services for lifecycle transitions.
- Keep accounting effects out of models and views; delegate posting to DEA through facade/services.
- Use `girvi.facade` for cross-app reads.
- Standardize lifecycle language; avoid mixing old statuses such as `Created`, `Approved`, `Disbursed` with next-generation states such as `Draft`, `PendingApproval`, and `ActiveCurrent`.

## Current Active Work

The event-driven Girvi/DEA posting plan is active. See [active plan](../plans/active.md).

Archived Girvi sources are preserved in [archive/girvi](../archive/girvi/).
