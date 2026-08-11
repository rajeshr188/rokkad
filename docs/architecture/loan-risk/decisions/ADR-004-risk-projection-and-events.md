---
status: proposed
owner: loans
updated: 2026-08-11
tags: [decision-brief, loans, projection, events]
related: [../concepts/risk-snapshots-events.md]
---

# ADR-004: Risk Projection and Events

## Status

Proposed decision brief.

## Context

Portfolio queries cannot recalculate full event, accrual, and collateral state
for every loan on every request. Time alone can also change maturity and DPD.

## Proposed decision

- Maintain one rebuildable current `LoanRiskSnapshot` per workspace and loan.
- Persist meaningful transitions as immutable `LoanRiskEvent` rows.
- Refresh after source changes and through a daily tenant-aware command.
- Protect refresh with source fingerprints, row locking, idempotency, and event
  uniqueness.
- Commands recheck current authority; snapshots never authorize adverse action.

## Consequences

Portfolio filtering and aggregation become efficient while facts remain
reconstructable. Failed or stale rows are visible and repairable by rebuild.
