---
status: accepted
owner: loans
updated: 2026-08-11
tags: [loans, products, contracts, repayment]
related: [repayment-obligations.md, ../decisions/ADR-006-four-repayment-products.md]
---

# Loan Products and Repayment Structures

Rokkad will initially support four customer PawnLoan products. A product is a
versioned contract definition, not an individual loan, balance, or risk state.

## Initial product families

### Single-payment bullet

Principal and interest are settled when collateral is redeemed. The product
has a contractual maturity. If the customer has not redeemed by that date, all
outstanding principal and contractually earned interest become due. Partial
settlement is not the ordinary servicing path; full settlement releases the
collateral.

### Periodic-interest bullet

Interest is contractually due at monthly intervals. Principal is due at
maturity. Each interest due date and the maturity principal become separate
repayment obligations. Monthly anniversaries are the proposed due-date rule. A
configurable payment grace of zero to three days may suppress customer charges
or workflow escalation, but must not silently change the contractual due date
or regulatory DPD calculation.

### Flexible partial-payment loan

The customer may pay interest or reduce principal at any time. To keep this
distinct from periodic-interest bullet, the proposed contract has no mandatory
interim installment: all residual principal and earned interest are due at
maturity. Before maturity, a payment follows the normal component priority and
any principal portion reduces future interest exposure under the frozen
calculation method. Partial payment does not release collateral.

### Installment loan

Principal and interest are due through a fixed schedule. The version identifies
EMI or equal-principal amortisation; both are approved initial methods.
Generated installments become immutable obligations.

For extra principal, the recommended default is to keep the periodic payment
amount and shorten the remaining tenure. A future ProductVersion may instead
choose reduced payment with unchanged tenure, but the rule must be frozen and
deterministic rather than selected ad hoc for each receipt. Re-amortisation
supersedes future obligations with explicit schedule-version evidence; it never
edits obligations that were already due or satisfied.

## Model boundary

```text
LoanProduct
    workspace identity, code, name, active state

LoanProductVersion
    immutable repayment structure
    obligation-generation rules
    allowed tenure and payment rules
    effective/availability metadata

PawnLoan
    references one frozen product version
    retains exact resolved contractual/economic evidence
```

Product does not own Series/License numbering, economic-policy calculations,
collateral tranches, mutable balances, accounting journals, monitoring policy,
or risk classifications.

## Schedule generation

Each supported repayment structure has an explicit obligation generator. The
generator consumes the frozen product version, loan date, maturity, principal,
and approved economic terms and produces an immutable schedule. It must be
deterministic and versioned; do not implement arbitrary formulas stored in JSON
or executable configuration.

## Changes to current Loans

- Product selection becomes required during draft creation.
- Approval freezes product identity, version, structure, and schedule rules.
- Disbursal creates the obligation schedule idempotently.
- Renewal selects an eligible current product version for the successor.
- Repayments keep current component and collateral-tranche allocation, then
  allocate satisfied amounts to dated obligations.
- Reports can group exposure, delinquency, and concentration by product.

## Confirmed direction

- Single-payment bullet makes all residual principal and earned interest due at
  maturity when not redeemed earlier.
- Periodic-interest bullet uses monthly-anniversary interest dues and principal
  at maturity.
- Periodic payment grace may be configured from zero to three days, subject to
  the final decision on whether it affects only charges/workflows or contractual
  DPD.
- Installment products support both EMI and equal-principal amortisation.

## Accepted servicing defaults

- Define flexible partial-payment as maturity-due with voluntary interim
  component/principal payments and no mandatory interim installment.
- Default installment extra-principal treatment to unchanged payment plus
  shorter tenure.

## Calculation details fixed by the roadmap

Schedules use exact contractual dates, actual outstanding time, frozen currency
rounding, and an explicit final-installment rounding adjustment. Schedule
changes supersede future obligations only. The regulatory compliance profile
selects applicable LTV, tenor, disclosure, and lender-category limits.
