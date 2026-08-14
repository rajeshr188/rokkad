---
status: implemented
owner: loans
updated: 2026-08-11
tags: [loans, monitoring-policy, risk]
related: [roadmap.md, ../concepts/monitoring-policy.md, ../concepts/risk-assessment.md]
---

# Phase 7: Monitoring policy and risk assessment

Migration `0043` adds immutable, effective-dated workspace monitoring policies
with optional license overrides. Scope/version uniqueness includes the null
workspace-default scope, overlapping periods are rejected, and the resolver
prefers an applicable license policy before the workspace default. No policy
is silently invented when configuration is absent.

The pure assessment calculates facts before interpretation and returns
maturity proximity, performance class, composable flags, explanations,
severity, action hint, policy identity, and a deterministic fingerprint.
Initial interpretations cover maturity, DPD watch/substandard boundaries,
valuation unavailable, LTV warning/breach/critical thresholds, and legacy
overdue/accounting variance. Severity is derived output and never loan state.

The selector composes Phase 4 exposure, Phase 5 delinquency, and Phase 6
collateral valuation. It performs no writes and authorizes no notice, auction,
or accounting action.
