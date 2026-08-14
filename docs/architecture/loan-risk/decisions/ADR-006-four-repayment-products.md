---
status: accepted
owner: loans
updated: 2026-08-11
tags: [decision-brief, loans, products, repayment]
related: [../concepts/loan-products.md, ../concepts/repayment-obligations.md]
---

# ADR-006: Four Initial Repayment Products

## Status

Accepted by the Owner and promoted to
`docs/adr/2026-08-11-loans-product-obligation-and-risk-architecture.md`.

## Context

The exposure/risk blueprint originally deferred LoanProduct and assumed one
bullet obligation. The Owner has selected four materially different repayment
structures, so obligation generation can no longer be hard-coded to one
PawnLoan shape.

## Proposed decision

Introduce workspace-owned `LoanProduct` and immutable `LoanProductVersion`
before repayment obligations. Initially support:

1. single-payment bullet;
2. periodic-interest bullet;
3. flexible partial-payment loan; and
4. installment loan with explicitly supported amortisation methods.

Every PawnLoan freezes one product version. Each structure uses a deterministic,
versioned obligation generator. Existing economic policy, Series/License,
collateral-tranche, accounting, lifecycle, and monitoring boundaries remain
separate.

## Consequences

The architecture supports all four through a common obligation/allocation and
DPD engine. Product foundation becomes Phase 1 and obligation implementation
must cover each approved schedule. More business rules must be resolved before
schema and service design are decision-complete.

## Decisions recorded

- Single-payment bullet makes all remaining principal and earned interest due
  at maturity if redemption has not occurred.
- Periodic-interest bullet uses monthly interest dues and principal at maturity.
- A zero-to-three-day grace facility is desired; its DPD versus charges/workflow
  effect remains to be confirmed.
- Installment supports both EMI and equal-principal methods.

## Accepted standard defaults

- Flexible partial-payment has no mandatory interim installment; voluntary
  payments settle components and reduce principal, with all residue due at
  maturity.
- Installment extra principal keeps the periodic payment unchanged and shortens
  tenure. Any reduced-payment alternative is a frozen ProductVersion rule.
- Exact contractual due dates drive DPD. The three-day grace affects customer
  charges/escalation only.
