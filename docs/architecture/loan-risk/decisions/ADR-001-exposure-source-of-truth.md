---
status: proposed
owner: loans
updated: 2026-08-11
tags: [decision-brief, loans, exposure, accounting]
related: [../concepts/loan-exposure.md, ../../../adr/README.md]
---

# ADR-001: Exposure Source of Truth

## Status

Proposed decision brief. Promote to a dated file in `docs/adr/` when accepted.

## Context

Loans already folds immutable events into recorded balances. Accrual preview
can expose additional current economics, while DEA independently owns posted
accounting receivables. Treating any one of these as all three concepts would
misstate the system.

## Proposed decision

- Loans events and frozen contract evidence own contractual/economic balances.
- Recorded and projected unfinalized interest remain separately labelled.
- Obligations own due and overdue interpretation.
- DEA owns accounting receivables.
- `LoanRiskSnapshot` is a rebuildable query projection only.
- A narrow facade reconciles Loans exposure with DEA; neither reads the other's
  internal tables directly.

## Consequences

Dashboards can show current exposure without creating accounting evidence.
Reports must disclose whether interest is finalized or projected. Differences
between contractual exposure and accounting receivable become explicit
reconciliation findings rather than silent adjustments.
