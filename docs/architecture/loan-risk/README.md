---
status: accepted
owner: loans
updated: 2026-08-11
tags: [loans, exposure, risk, architecture, index]
related: [architecture-plan.md, ../../plans/pawn-collateral-risk-and-appraisal.md]
---

# Loan Risk Architecture

This package breaks the Loan Exposure, Risk Assessment, and Portfolio
Monitoring blueprint into smaller documents without discarding the complete
master plan.

The architecture is accepted in
`docs/adr/2026-08-11-loans-product-obligation-and-risk-architecture.md`.
Implementation remains phase-gated by the roadmap.

## Start here

1. [Complete architecture plan](architecture-plan.md) — canonical master plan.
2. [Implementation roadmap](implementation/roadmap.md) — phased delivery order.
3. [Architecture status](implementation/status.md) — review and decision state.

## Concepts

- [Loan products and repayment structures](concepts/loan-products.md)
- [Loan exposure](concepts/loan-exposure.md)
- [Repayment obligations](concepts/repayment-obligations.md)
- [Delinquency and DPD](concepts/delinquency-dpd.md)
- [Collateral valuation](concepts/collateral-valuation.md)
- [LTV monitoring](concepts/ltv-monitoring.md)
- [Risk assessment](concepts/risk-assessment.md)
- [Monitoring policy](concepts/monitoring-policy.md)
- [Risk snapshots and events](concepts/risk-snapshots-events.md)

## Proposed decision briefs

- [ADR-001: Exposure source of truth](decisions/ADR-001-exposure-source-of-truth.md)
- [ADR-002: DPD calculation](decisions/ADR-002-dpd-calculation.md)
- [ADR-003: Monitoring LTV policy](decisions/ADR-003-monitoring-ltv-policy.md)
- [ADR-004: Risk projection and events](decisions/ADR-004-risk-projection-and-events.md)
- [ADR-005: Keep risk inside Loans](decisions/ADR-005-keep-risk-inside-loans.md)
- [ADR-006: Four initial repayment products](decisions/ADR-006-four-repayment-products.md)

These focused briefs explain individual decisions. The canonical accepted
record is the dated ADR under `docs/adr/`; future amendments must update that
record and the affected brief together.

## Reading model

```text
Contract + economic events + obligations
                    |
                    v
               Exposure

Collateral + custody + rates + appraisals
                    |
                    v
          Collateral valuation

Exposure + valuation + tenure + monitoring policy
                    |
                    v
             Risk assessment
                    |
                    v
       Current snapshot + transition events
                    |
          +---------+----------+
          v         v          v
      Portfolio  Collections  Notices/Auction
```
