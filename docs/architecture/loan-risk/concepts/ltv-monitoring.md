---
status: proposed
owner: loans
updated: 2026-08-11
tags: [loans, ltv, collateral, monitoring]
related: [loan-exposure.md, collateral-valuation.md, monitoring-policy.md]
---

# LTV Monitoring

LTV monitoring compares a policy-selected exposure with current eligible
collateral value. It is independent from maturity delinquency.

```text
current LTV = LTV exposure / eligible collateral value
LTV buffer  = eligible collateral value * allowed LTV - LTV exposure
```

If collateral value is zero, missing, or stale beyond policy, return an unknown
or blocked result rather than an artificial percentage.

## Separate thresholds

- Frozen origination LTV proves the contract was acceptable when approved.
- Monitoring LTV interprets current risk and may change prospectively by
  effective-dated policy.
- 100% coverage identifies an economic shortfall, not the earlier policy margin
  breach.

Keep warning, breach, critical breach, and full shortfall as separate facts or
flags. Do not turn them into `PawnLoan.state` or redefine overdue.

## Cure

A repayment or collateral-price recovery can cure a breach. Persist the
entered/cured transition, but derive the current status from the latest facts
and policy. A workflow may react only after its own authority and cure-period
rules are approved.
