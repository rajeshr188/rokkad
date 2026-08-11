---
status: proposed
owner: loans
updated: 2026-08-11
tags: [loans, delinquency, dpd, maturity]
related: [repayment-obligations.md, monitoring-policy.md]
---

# Delinquency and Days Past Due

Delinquency is independent from contractual lifecycle. An `ACTIVE` loan can be
matured, overdue, in a DPD bucket, and LTV-breached at the same time.

## Proposed calculation

```text
oldest unpaid due date
    = earliest due date before as_of_date with an outstanding obligation

DPD = as_of_date - oldest unpaid due date
```

An obligation due today has `DPD = 0`. It becomes one day past due tomorrow.
No unpaid overdue obligation means `DPD = 0` and delinquency `CURRENT`.

## Current compatibility

Current `balance.is_overdue` means maturity has passed and recorded total due
remains. Notices and auction depend on it. Keep this definition during the
compatibility period. Compare it with obligation-derived delinquency and report
variance before changing workflow authority.

## Derived classifications

DPD buckets and performance classes are policy interpretations. They should be
calculated from DPD and policy version, not stored as mutable loan flags.
Transitions such as entering 30+, moving back to current, or changing
performance class should be immutable risk events.

## Business decisions required

- whether current PawnLoan interest is payable only at maturity or periodically;
- grace-period treatment;
- exact DPD and NPA bucket boundaries;
- whether a cure is immediate after allocation; and
- when delinquency can authorize notices, collection, or auction.
