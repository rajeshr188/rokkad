---
status: accepted
owner: project
updated: 2026-08-11
tags: [loans, products, obligations, exposure, risk, rbi]
related:
  - ../architecture/loan-risk/README.md
  - 2026-08-09-loans-effective-dated-calculation-policy.md
  - 2026-08-05-pawn-loan-collateral-tranche-economics.md
  - ../constitution.md
---

# ADR: Loan Products, Obligations, Exposure, and Risk Architecture

## Context

PawnLoan has trustworthy immutable economic events and collateral-tranche
evidence but one implicit repayment structure, maturity-only overdue, no dated
obligations, no current collateral-risk projection, and no explainable
portfolio risk state. The Owner selected four initial repayment products and
directed the application to follow applicable RBI gold-loan guidance.

## Decision

1. Add workspace-owned `LoanProduct` and immutable `LoanProductVersion` before
   obligations. Each PawnLoan freezes exactly one version.
2. Support single-payment bullet, periodic-interest bullet, flexible partial-
   payment bullet, and installment with EMI or equal-principal amortisation.
3. Generate immutable dated obligations from the frozen ProductVersion and
   append immutable allocations from repayments, settlements, and reversals.
4. Keep lifecycle, exposure, delinquency/DPD, collateral valuation, LTV,
   performance, and severity as separate dimensions.
5. Loans events remain contractual/economic truth; DEA remains accounting
   truth; snapshots remain rebuildable projections.
6. Follow the applicable RBI lender/purpose/date compliance profile. Bullet
   principal and interest are due at maturity; consumption bullet tenor is
   capped at 12 months; bullet LTV uses maturity payoff; LTV is ongoing; exact
   due dates drive DPD; operational grace does not move regulatory DPD.
7. Risk assessment is pure and explainable. Workflows react only after their
   own fresh eligibility check.
8. Implement through the phased roadmap under
   `docs/architecture/loan-risk/implementation/roadmap.md`.

## Consequences

- Product and obligation foundations precede exposure/risk rollout.
- Current interest timing must be characterized and corrected if it charges
  beyond the actual outstanding period after disbursal or repayment.
- Policies and compliance profiles remain versioned/configurable rather than
  hard-coded to one regulated-entity category.
- The implementation adds models and projections but removes implicit status
  logic and duplicated report calculations.
- No phase may weaken immutable accounting, reversal, custody, tenant, or
  document evidence.
