---
status: proposed
owner: loans
updated: 2026-08-11
tags: [decision-brief, loans, ltv, policy]
related: [../concepts/ltv-monitoring.md, ../concepts/monitoring-policy.md]
---

# ADR-003: Monitoring LTV Policy

## Status

Proposed decision brief.

## Context

Frozen origination LTV proves approval economics. Current collateral monitoring
needs prospective thresholds, freshness, and valuation eligibility without
rewriting the contract.

## Proposed decision

- Keep frozen origination LTV as contractual evidence.
- Resolve monitoring thresholds from an effective-dated workspace policy with
  optional license override.
- Distinguish warning, policy breach, critical breach, and 100% market-value
  shortfall.
- Return unknown/blocked when required valuation is missing or stale.
- A breach is a risk signal, not maturity delinquency or automatic auction
  authority.

## Consequences

Policy can evolve prospectively while historical assessments record the exact
version used. Workflow consequences and cure periods require separate approval.
