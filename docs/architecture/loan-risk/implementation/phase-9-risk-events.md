---
status: implemented
owner: loans
updated: 2026-08-11
tags: [loans, risk, events, audit]
related: [roadmap.md, ../concepts/risk-snapshots-events.md]
---

# Phase 9: Immutable risk transitions

Migration `0045` adds append-only `LoanRiskEvent` evidence linked to its loan
and current projection. Each event records type, occurrence and assessment
dates, old/new values and assessment fingerprints, policy identity, metadata,
and a deterministic trigger key. Workspace/loan/trigger uniqueness makes
concurrent or repeated refreshes idempotent.

Transition detection covers initial assessment, maturity warning/past maturity,
delinquency entry/bucket/cure, LTV warning/breach/critical entry and cure,
valuation failure/cure, performance, severity, policy, and assessment
error/recovery. Events are persisted inside the same locked transaction as the
snapshot update. Rebuild changes only the current projection and appends real
transitions; it never rewrites or deletes history.
