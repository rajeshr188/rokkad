---
status: implemented
owner: loans
updated: 2026-08-11
tags: [loans, monitoring, portfolio, operations]
related: [roadmap.md, phase-8-risk-snapshot.md, phase-9-risk-events.md]
---

# Phase 10: Monitoring orchestration and portfolio selectors

`reassess_pawn_loans` requires an explicit workspace id matching the active
tenant schema, accepts an explicit assessment date, and processes at most
1,000 loans per invocation. Candidate rows are claimed using
`select_for_update(skip_locked=True)`; failures remain visible on snapshots
and in command diagnostics, while subsequent runs retry them.

Transaction-commit invalidation marks a loan projection stale after changes to
the loan, economic events, schedules, obligations, allocations, schedule
changes, collateral, or appraisals. Rate changes invalidate the tenant's
valuation-dependent portfolio and monitoring-policy changes invalidate their
workspace or license scope. The daily command also selects snapshots whose
assessment date is behind the requested business date, capturing time-only DPD
and maturity transitions.

Portfolio selectors query typed snapshots directly and support status,
severity, performance, DPD, LTV, maturity, borrower, and product filters with
bounded pagination. Aggregate exposure/concentration is grouped in SQL by
severity and product; no per-loan risk calculation occurs in a view or
template. Missing, stale, and error projections remain filterable.

The implementation is designed for repeated bounded workers. Before production
rollout, record environment-specific 1,000/10,000-loan timings and query plans;
at 100,000+ loans, retain bounded `skip_locked` workers and add a durable dirty
queue only if measured full-candidate scans become material.
