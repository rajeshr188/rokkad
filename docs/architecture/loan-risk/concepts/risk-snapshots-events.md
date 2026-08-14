---
status: proposed
owner: loans
updated: 2026-08-11
tags: [loans, risk, projection, events, monitoring]
related: [risk-assessment.md, ../implementation/roadmap.md]
---

# Risk Snapshots and Events

Calculating every loan for every dashboard request will not scale. A current
snapshot makes risk queryable while remaining a rebuildable projection.

## LoanRiskSnapshot

Maintain one current row per workspace and active loan. Store typed columns for
exposure, overdue, DPD, maturity, valuation, LTV, classifications, severity,
freshness, assessment date, policy version, and input fingerprint. JSON may
hold explanations, but must not replace filterable columns.

Snapshot refresh should calculate without locks, then lock the snapshot row,
compare source fingerprints, and update only if inputs remain current. Mark
errors/staleness explicitly. Commands must not use a stale snapshot as legal
authority.

## LoanRiskEvent

Append immutable events for meaningful changes: maturity, delinquency entry or
exit, bucket change, LTV warning/breach/cure, performance change, and severity
change. Deduplicate by workspace, loan, transition type, and old/new
fingerprints.

## Recalculation

Refresh after committed economic, obligation, collateral, appraisal, rate,
custody, contract, or policy changes. A daily tenant-aware command handles
time-only changes. Process one tenant schema at a time and fail closed without
tenant/workspace context.

At larger scale, select dirty loans in bounded batches and use
`select_for_update(skip_locked=True)`. Kafka and event sourcing are not needed.
