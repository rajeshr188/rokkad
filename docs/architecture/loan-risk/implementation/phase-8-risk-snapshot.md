---
status: implemented
owner: loans
updated: 2026-08-11
tags: [loans, risk, projection]
related: [roadmap.md, ../concepts/risk-snapshots-events.md]
---

# Phase 8: Current risk snapshot projection

Migration `0044` adds one typed `LoanRiskSnapshot` projection per workspace and
loan. Exposure, due, overdue, DPD, maturity, collateral value, LTV,
performance, severity, action, policy, flags, explanations, assessment and
input fingerprints are directly queryable. `CURRENT`, `STALE`, and `ERROR`
states make projection health explicit.

Refresh calculates from the pure selectors without locks, then locks the loan
and snapshot and compares a source fingerprint covering the loan, economic
events, schedules, obligations, allocations, schedule changes, collateral,
appraisals, rates, and monitoring policies. Changed input is never published;
an existing projection is marked stale and the caller is told to retry.
Repeated refresh updates the same row, while failures are retained as
diagnostic error state and a later successful refresh repairs it.

The bounded rebuild service processes the current tenant only and returns
per-loan diagnostics. Snapshots remain rebuildable read models and are not
legal, lifecycle, notice, auction, or accounting authority.
