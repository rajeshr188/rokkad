---
status: proposed
owner: loans
updated: 2026-08-11
tags: [loans, collateral, valuation, appraisal, rates]
related: [ltv-monitoring.md, ../../../../docs/plans/pawn-collateral-risk-and-appraisal.md]
---

# Collateral Valuation

Collateral valuation answers: **what is the eligible security worth as of a
date, using which evidence?** It must remain separate from exposure and risk
classification.

## Current foundation

Pawn collateral already stores metal, net weight, purity, appraisal, allocated
principal, and custody. Origination and release readiness can resolve Rates
buying values and apply calculated, appraisal, or lower-of-both policy.

## Required evolution

- Extract workflow-neutral, read-only per-item valuation.
- Introduce immutable appraisal versions with actor, effective time, review,
  evidence, and supersession.
- Resolve historical rates/appraisals at `as_of_date` with explicit provenance.
- Mark missing, stale, rejected, or disputed evidence explicitly.
- Include only custody states that policy says continue securing the loan.

## Proposed result

Return each eligible item's calculated value, appraisal value, selected value,
method, rate/appraisal identity, timestamp, freshness, and blockers. Aggregate
only complete eligible values; do not silently invent or fall back.

## Historical gap

Rates currently support timestamp-based historical lookup, while mutable
`latest_appraised_value` is not historical evidence. Deterministic historical
assessment requires immutable appraisal history and a stronger business-
effective rate contract.
