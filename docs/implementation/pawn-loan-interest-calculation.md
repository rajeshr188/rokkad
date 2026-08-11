---
status: active
owner: loans
updated: 2026-08-11
tags: [loans, interest, accrual, repayment, capitalization, internals]
related:
  - ../domain/loans-regulatory-setup-and-policy.md
  - ../domain/loans-mixed-metal-origination.md
  - ../adr/2026-08-09-loans-effective-dated-calculation-policy.md
  - ../plans/pawn-collateral-risk-and-appraisal.md
---

# PawnLoan Interest Calculation Internals

This document explains the current implemented PawnLoan interest calculation.
It distinguishes read-only previews, immutable finalized accruals, accounting
recognition, repayment allocation, capitalization, overdue classification, and
the known gap between recorded balance and projected current exposure.

## 1. Governing Evidence

PawnLoan interest is monthly and itemized by collateral principal tranche. At
approval, the system freezes each item's allocated principal, metal-specific
monthly rate, and rate-policy identity. At disbursal it persists the approved
tranches and an immutable `LoanPolicySnapshot` containing:

- interest method (`SIMPLE` or `COMPOUND`);
- partial-month method (`FULL_MONTH` or `SLAB`);
- partial-month cutoff and lower fraction;
- capitalization interval;
- accounting recognition (`CASH` or `ACCRUAL`);
- rounding method and currency quantum; and
- the valuation/LTV terms used at origination.

Later setup changes do not alter an existing active loan. Modern PawnLoans must
calculate from frozen item-level evidence; missing or inconsistent evidence
fails closed.

## 2. Core Formula

For each collateral item and interest period:

```text
unrounded item interest
  = item principal outstanding at period start
  × frozen item monthly rate
  ÷ 100
  × period fraction
```

The item amount is rounded to the frozen currency quantum with `ROUND_HALF_UP`:

```text
calculated item interest = quantize(unrounded item interest, currency quantum)
```

The loan-period totals are sums of the independently calculated item lines:

```text
calculated interest = sum(calculated item interest)
recognized interest = calculated interest - advance interest applied
```

The immutable line evidence retains principal base, rate, fraction, unrounded
interest, rounded calculated interest, advance applied, and recognized
interest. Item-level rounding means the result need not equal a single
aggregate-rate calculation rounded once at the loan level.

### Mixed-metal example

| Item | Principal | Monthly rate | Monthly interest |
| --- | ---: | ---: | ---: |
| Gold chain | 60,000 | 2% | 1,200 |
| Silver anklet | 40,000 | 4% | 1,600 |
| **Total** | **100,000** | — | **2,800** |

Interest uses gross principal allocated to collateral, not net cash handed to
the borrower after advance-interest and fee deductions.

## 3. Calendar Period Construction

The first period begins on `loan.loan_date`. Each exclusive period end is one
calendar month after the period start, and the inclusive completed end is one
day earlier. The next period starts the following day.

For a January 31 loan:

```text
Period 1: January 31 through February 27
Period 2: February 28 through March 27
Period 3: March 28 through April 27
```

Calendar-month addition clamps the day to the last valid day of a shorter
month. Periods are contiguous without overlap or gaps.

Preview begins at `loan_date` when nothing is finalized. Otherwise it begins
at the day after the latest non-reversed finalized accrual.

## 4. Completed And Partial Periods

A period whose completed end is on or before `as_of_date` has fraction `1`.
When partial periods are requested and the current period has started, its
fraction follows the frozen policy.

### Full-month policy

Any started partial period has fraction `1`. This is not daily proration.

### Slab policy

```text
elapsed days <= cutoff days  -> lower fraction
elapsed days > cutoff days   -> 1 full month
```

For a 15-day cutoff and `0.5` lower fraction, days 1–15 cost half a month and
day 16 onward costs a full month.

Normal monthly finalization permits completed periods only. Release, renewal,
and auction settlement may calculate and persist a current partial-period
catch-up after every completed period has been finalized.

## 5. Principal Base And Repayment Timing

The aggregate balance and each item principal balance are reconstructed from
immutable events as of the period start. Consequently, a repayment during an
already-started period does not reduce that period's interest base. It affects
the next period.

Example:

```text
Period start principal: 100,000
Mid-period repayment:    20,000

Current period base:     100,000
Next period base:         80,000
```

This is a period-opening-balance method, not a daily reducing-balance method.

Principal repayment is allocated to item tranches in descending monthly-rate
order. In the mixed-metal example, a 3,000 principal payment reduces the 4%
Silver tranche from 40,000 to 37,000 before touching the 2% Gold tranche. The
next monthly interest is therefore:

```text
Gold:   60,000 × 2% = 1,200
Silver: 37,000 × 4% = 1,480
Total:                 2,680
```

A compensating reversal restores the prior tranche balances and calculation.

## 6. Advance Interest

Origination may deduct a configured number of monthly interest periods from
the gross principal before cash handoff:

```text
net cash = gross principal - advance interest - deducted fees
```

Advance interest is frozen per tranche and consumed once against future
calculated interest:

```text
remaining advance = frozen advance - previously applied advance
advance applied = min(remaining advance, calculated interest)
recognized interest = calculated interest - advance applied
```

When preview returns multiple pending periods, it tracks advance consumption
across the in-memory previews. Finalized, non-reversed accrual lines provide
the durable consumed total. A partial period can consume part of the advance
and leave the remainder for the next period.

With one month of 2,800 advance interest:

| Period | Calculated | Advance applied | Newly recognized |
| --- | ---: | ---: | ---: |
| 1 | 2,800 | 2,800 | 0 |
| 2 | 2,800 | 0 | 2,800 |

## 7. Preview Versus Finalization

`preview_pawn_loan_accruals()` is a tenant-scoped, read-only calculation. It
does not create accruals, events, outboxes, vouchers, or journals.

Regular finalization:

1. locks and revalidates the active loan;
2. permits only the next sequential completed period;
3. recalculates from current immutable evidence rather than trusting an old UI
   preview;
4. checks accounting readiness;
5. creates an immutable `PawnLoanInterestAccrual` and item lines;
6. records the required interest-accrual event/outbox; and
7. appends change-log evidence.

Finalization is idempotent by loan and period number. Existing finalized
accruals are returned instead of duplicated. Accrual headers and lines cannot
be edited or deleted; corrections use compensating reversals.

An event is recorded when newly recognized interest is positive. When a period
is fully covered by advance interest, an event is still required under accrual
recognition to represent advance consumption from unearned treatment; the
immutable accrual and lines exist in either case.

## 8. Cash And Accrual Recognition

Recognition policy does not change the item interest formula. It changes the
accounting treatment of advance interest and earned interest.

- Under `CASH`, advance interest follows the cash-oriented disbursal treatment.
- Under `ACCRUAL`, advance interest begins as unearned and is consumed as
  periods are earned.

Loans owns the immutable source event and calculation evidence. Accounting
delivery occurs through the configured outbox/DEA boundary; rendering a
preview never creates accounting evidence.

## 9. Repayment Allocation

Repayment uses the current **recorded** balance and a fixed allocation order:

```text
1. fees
2. overdue interest
3. current interest
4. principal
```

Repayment itself does not automatically finalize every missing interest period.
Operators or servicing workflows must finalize eligible completed accruals for
them to enter the recorded balance.

## 10. Simple And Compound Interest

### Simple

Unpaid interest remains interest. Future periods continue to use outstanding
principal reduced by principal repayments.

### Compound

Compounding requires an explicit immutable capitalization command at the
frozen interval boundary. All required boundary accruals must already exist.
The command moves unpaid interest into capitalized principal:

```text
principal outstanding
  = original principal outstanding
  + capitalized-interest principal outstanding
```

The same amount leaves interest outstanding, so it is never counted in both
principal and interest.

Preview stops at a due capitalization boundary until capitalization occurs.
There is also a current limitation: capitalized principal does not yet have
immutable allocation across mixed-rate collateral tranches. Itemized accrual
after such capitalization therefore fails closed instead of guessing an item
rate. Repayment of separately classified capitalized principal remains
supported.

## 11. Release-Day Catch-Up

Full release first requires every completed period to be finalized. It then
previews the current partial period and adds its newly recognized interest to
the settlement. Confirmation persists that partial calculation as immutable
release-catch-up accrual evidence before the release receipt.

Example:

```text
Principal:             10,000
Monthly rate:              2%
Full monthly interest:    200
Slab fraction:            0.5
Release catch-up:         100
```

Unused advance interest is applied before any new catch-up becomes payable.

## 12. Recorded Balance Fold

The canonical balance selector folds non-future immutable events, including
exact inverse effects from reversals:

```text
principal outstanding
  = disbursed principal
  + capitalized-interest principal
  - principal paid

interest outstanding
  = finalized accrued interest
  - capitalized interest
  - interest paid

fees outstanding
  = fees assessed
  - fees paid

total due
  = principal outstanding
  + interest outstanding
  + fees outstanding
```

Stored loan totals are not mutated as an alternative to this event fold.

## 13. Due Date And Overdue Classification

The contractual due date is `loan_date + tenure_months`, using the same
calendar-month clamping rule. Current overdue means:

```text
as_of_date > due_date and recorded total_due > 0
```

The loan is not overdue on the due date itself. After maturity, all recorded
outstanding interest is classified as overdue interest; before maturity it is
classified as current interest.

Collateral margin breach and market-value shortfall are separate future risk
signals. They must not silently redefine `balance.is_overdue`, because overdue
currently gates notices and auction eligibility.

## 14. Recorded Balance Versus Projected Exposure

The ordinary balance and portfolio report include finalized accrual events,
not every previewed but unfinalized month. If accrual operations are behind,
recorded `interest_outstanding` and `total_due` can be lower than the economic
exposure through today.

Future collateral-risk monitoring must therefore calculate and disclose:

```text
projected current exposure
  = recorded total due
  + previewed unfinalized interest through the as-of date
```

Recorded interest and projected interest must remain separately labeled. A
dashboard calculation must not create accrual, voucher, outbox, or journal
evidence merely to make the projection current. See
`docs/plans/pawn-collateral-risk-and-appraisal.md` for the proposed risk read
model and refresh design.

## 15. Primary Code Boundaries

- `apps/tenant_apps/loans/services/pawn_interest.py`: preview, period fraction,
  item calculations, finalization, advance consumption, and capitalization.
- `apps/tenant_apps/loans/services/pawn_tranches.py`: item principal balance
  reconstruction.
- `apps/tenant_apps/loans/selectors/balances.py`: immutable event fold, total
  due, and overdue classification.
- `apps/tenant_apps/loans/services/pawn_repayment.py`: payment allocation and
  highest-rate-first principal reduction.
- `apps/tenant_apps/loans/services/pawn_release.py`: completed-period gate and
  partial-period release catch-up.
- `apps/tenant_apps/loans/services/pawn_disbursal.py`: frozen policy/tranche and
  advance-interest evidence.

