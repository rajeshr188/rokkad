---
status: complete
owner: loans
updated: 2026-08-11
tags: [loans, exposure, projections]
related: [roadmap.md, status.md, ../concepts/loan-exposure.md]
---

# Phase 4 Recorded and Projected Exposure

`get_pawn_loan_exposure(loan_id, as_of_date=...)` is the canonical read-only
economic exposure selector. It does not post or authorize a workflow.

## Separated values

- recorded principal, finalized interest, fees, and total due come only from
  the immutable accounting-event fold;
- projected interest is unfinalized and separately labelled;
- due and overdue amounts come only from the active obligation version and
  allocations effective by the requested date;
- accounting receivable includes principal and fees, plus finalized interest
  only under accrual recognition;
- total economic exposure is recorded total due plus projected interest;
- maturity payoff is remaining scheduled principal and interest plus fees; and
- bullet LTV basis uses maturity payoff, while installment LTV basis uses
  current economic exposure.

## Corrected projection timing

Projection uses actual-outstanding daily segmentation. Every monthly period is
split at effective loan-event dates and calculated from frozen collateral
tranche balances and rates for each segment. A repayment therefore reduces
projected interest from its effective date. Finalized legacy accrual evidence is
never rewritten.

Example: INR 50,000 at 2% monthly from 3 August to 2 September, with INR 10,000
principal repaid on 15 August, projects INR 877.4194: 12/31 days on INR 50,000
and 19/31 days on INR 40,000. The legacy period-opening preview remains INR
1,000 and is intentionally shown by its existing workflow until cutover.

## Safety and provenance

Future events and allocations are excluded. Schedule selection and termination
are evaluated as of the requested date. Results carry event-fold, calculation-
contract, projection-method, obligation-fold, and schedule-fingerprint
provenance. Over-allocated obligations become integrity findings instead of
being silently repaired.
