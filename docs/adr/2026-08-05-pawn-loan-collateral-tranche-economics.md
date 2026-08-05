---
status: accepted
owner: project
updated: 2026-08-05
tags: [adr, loans, collateral, interest, ltv, disbursal, accounting]
related: [2026-07-15-loans-rewrite-domain-and-cutover-architecture.md, ../plans/loans-rewrite-roadmap.md, ../domain/accounting.md, ../constitution.md]
---

# ADR: PawnLoan Collateral-Tranche Economics

## Context

The first Loans implementation stores one principal and one monthly interest
rate on `PawnLoan`, while collateral stores physical and appraisal facts only.
The clarified pawn business rule is different: every collateral item raises a
specific portion of principal, and that portion earns interest at the rate for
the item's metal. A mixed gold/silver loan therefore has multiple calculation
tranches even though it remains one customer loan and one accounting document.

Disbursal normally withholds one period of interest plus configured fees from
cash paid to the borrower. The gross collateral-backed principal remains owed.
Drafting must also reject an item allocation above its own valuation/LTV limit.

## Decision

1. `PawnLoan` remains the aggregate and regulatory document. Each
   `PawnCollateralItem` is an economic tranche with allocated principal and a
   resolved monthly metal rate.
2. Loan principal is the exact sum of item allocations. Loan interest is the
   sum of item calculations. Any loan-level effective rate is derived display
   data and never the calculation authority.
3. Effective-dated workspace metal-rate policies may be overridden by a
   license-specific policy. The resolved item rate is frozen in approval and
   disbursal evidence.
4. Item valuation uses the configured calculated-metal, appraisal, or
   lower-of-both method. Item allocation must not exceed selected value times
   maximum LTV. Draft forms preview this rule; draft and approval services
   enforce it independently and fail closed on missing rates/appraisals.
5. Advance-interest periods are a workspace default with optional license
   override, default `1`, allowed from `0` through `12`, and frozen at
   disbursal. Advance interest is calculated and currency-rounded per item.
6. Effective-dated fee policies support fixed or gross-principal percentage
   amounts and explicitly declare whether they are withheld at disbursal.
7. Gross principal minus advance interest and withheld fees equals net cash.
   Deductions never reduce principal. Net cash must remain positive.
8. An immutable disbursal snapshot preserves gross principal, net cash,
   advance-interest coverage, item calculations, fee lines, and source-event
   identity.
9. `PawnLoanInterestAccrual` remains the period header. Immutable item lines
   preserve principal base, frozen rate, period fraction, calculated interest,
   recognized interest, and advance interest applied. Pre-collected interest
   offsets the covered period and is not charged twice.
10. Cash accounting recognizes deducted interest when collected. Accrual
    accounting credits unearned interest at disbursal and recognizes it as
    periods are finalized. DEA remains the only posting owner.
11. Repayment retains fees, overdue interest, current interest, principal
    priority. General principal payments allocate highest-rate tranche first;
    partial release explicitly settles selected-item principal first and then
    any additional retained-LTV reduction by the general rule.
12. Capitalized unpaid interest remains attributable to the tranche that
    generated it. Renewal creates a fresh successor allocation/rate/valuation
    snapshot rather than copying one opaque loan-level rate.
13. Existing development PawnLoans will be recreated or explicitly corrected.
    No migration may invent allocations for historical multi-collateral loans.

## Consequences

- Draft, approval, disbursal, accrual, repayment, release, renewal, documents,
  reports, and reconciliation all consume the same item-level economics.
- DEA may post aggregate control totals, but every payload retains immutable
  item and deduction detail that reconciles exactly to those totals.
- The July 2026 ADR remains authoritative except where its single-rate wording
  conflicts with this collateral-tranche decision.
- FundingLoan work must not start until this correction is complete because
  repledging depends on trustworthy collateral-level principal balances.

## Rejected Alternatives

- One blended rate as calculation authority: rejected because it loses the
  contractual metal-specific calculation and makes partial release ambiguous.
- Form-only LTV validation: rejected because non-UI callers could bypass it.
- Treating net cash as principal: rejected because withheld interest and fees
  do not reduce the borrower's gross principal obligation.
- Auto-distributing old principal equally or by appraisal: rejected because it
  would fabricate historical business facts.

