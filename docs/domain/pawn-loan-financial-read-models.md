---
status: active
owner: project
updated: 2026-08-13
tags: [loans, pawn-loan, balance, obligations, exposure, risk]
related:
  - ../adr/2026-08-11-loans-product-obligation-and-risk-architecture.md
  - ../implementation/pawn-loan-interest-calculation.md
---

# PawnLoan Financial Read Models

PawnLoan uses layered read models. They answer different questions and must not
be collapsed into one mutable total.

## Recorded balance

`get_pawn_loan_balance` folds finalized immutable loan accounting events through
the requested as-of date. It is authoritative for recorded:

- principal outstanding;
- interest outstanding;
- fees outstanding;
- payments and reversals;
- accounting-delivery readiness.

The identity is `recorded:event-fold-v1`. Projected interest and future schedule
amounts never enter this balance.

## Contractual obligation state

`calculate_obligation_state_as_of` folds the one active repayment-schedule
version, its obligations, allocations, termination evidence, and reversals. It
is authoritative for:

- contractual principal and interest remaining;
- amounts due on or before the as-of date;
- amounts overdue strictly before the as-of date;
- the unpaid rows used to calculate DPD;
- schedule and allocation integrity findings.

The single-schedule selector fetches obligations and date-filtered allocations
in two queries and passes them to the same fold. It does not retain a cross-date
cache; reversal allocations remain filtered by their source effective date.

Fees are not scheduled obligations in the current contract and remain recorded
balance components. An over-allocated obligation is reported and excluded from
aggregate obligation amounts; it is never silently clamped into a valid row.

## Economic exposure

`get_pawn_loan_exposure` composes, but does not replace, the first two models:

```text
recorded total due = recorded principal + recorded interest + recorded fees
total economic exposure = recorded total due + labelled unfinalized interest preview
maturity payoff = contractual remaining principal + contractual remaining interest
                  + recorded fees
```

For bullet/flexible contracts, LTV uses maturity payoff. For amortizing
contracts, LTV uses total economic exposure. Exposure records its calculation,
schedule, and product-contract provenance and reports a variance if contractual
remaining principal disagrees with recorded principal outstanding.

## Delinquency and risk

Delinquency consumes the same canonical unpaid obligation rows used by exposure.
The contractual due date determines DPD; operational grace affects workflow but
does not move that date. The older balance-level overdue flag remains a
reconciliation comparison only.

Live risk consumes exposure, delinquency, collateral valuation, and monitoring
policy. Persisted risk snapshots copy those results and their identities; they
must never recompute money independently. The active portfolio includes loans
without projections. Current means a successful current-contract projection for
today; missing/outdated/error assessments do not contribute to claimed complete
portfolio monetary totals. Unknown collateral coverage is a separate dimension.
Coverage exposure, headroom and shortfall are copied from the valuation/LTV selector.
A refresh reuses its scoped, same-date exposure, delinquency and collateral
results between layers; public reads can still calculate these independently.
Closed loans retain financial/history reads but stop live health calculations.
See [Loan health](../flows/loan-health-monitoring.md).

Current collateral valuation applies the effective monitoring policy's inclusive
quote/appraisal age limits. It retains displayed reference amounts but reports
unknown eligible coverage when evidence required by the loan's frozen valuation
method is stale or missing. Reviewed active-loan appraisals append immutable
versions, retain their reference context, and invalidate saved risk assessments.
See [collateral reassessment](../flows/collateral-reassessment.md). These monitoring
limits do not become origination or settlement rules implicitly.

## Workflow use

- repayment allocation and financial settlement use recorded balance;
- release combines recorded settlement with canonical collateral valuation;
- renewal settles recorded source balances and separately prices the successor;
- reports label recorded amounts, contractual dues, and projections distinctly;
- monitoring and risk use exposure and contractual delinquency.
