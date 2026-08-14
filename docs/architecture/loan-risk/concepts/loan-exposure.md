---
status: proposed
owner: loans
updated: 2026-08-11
tags: [loans, exposure, balances]
related: [../architecture-plan.md, repayment-obligations.md]
---

# Loan Exposure

Loan exposure answers: **what is the lender economically exposed to on this
loan as of a date?** It is broader than the amount currently overdue.

## Fit with current Loans

The canonical recorded position already comes from the immutable event fold in
`loans/selectors/balances.py`. It derives disbursed, capitalized, paid, and
outstanding principal; finalized interest; fees; and reversals.

The missing layer is a read-only value object that combines:

- the recorded balance;
- separately labelled unfinalized accrual preview;
- what is contractually due now;
- what is overdue;
- total economic exposure; and
- the exposure basis selected for LTV monitoring.

## Source-of-truth boundary

- Immutable Loans events remain contractual/economic truth.
- Accrual preview is calculated, non-posted exposure and must remain labelled.
- Repayment obligations determine due and overdue amounts.
- DEA remains authoritative for accounting receivables.
- A risk snapshot is a rebuildable projection, never another balance ledger.

## Proposed interface

```python
calculate_pawn_loan_exposure(loan_id, *, as_of_date) -> PawnLoanExposure
```

The result should explain recorded principal, finalized and projected interest,
fees, due now, overdue, total exposure, and accounting-readiness facts. It must
perform no writes.

## Important constraints

- Do not rename the existing recorded `total_due` into exposure silently.
- Do not post accrual merely to refresh a dashboard.
- Exclude events after `as_of_date`.
- Fail closed on inconsistent event or tranche evidence.
- Reconcile, but do not couple, Loans exposure with DEA balances.
