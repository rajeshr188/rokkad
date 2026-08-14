---
status: in-progress
owner: loans
updated: 2026-08-11
tags: [loans, products, compliance, characterization]
related: [roadmap.md, status.md, ../architecture-plan.md]
---

# Phase 0 Current-Behavior and Conformance Baseline

This document freezes the behavior that exists before product, obligation,
exposure, or risk schema is introduced. It is a characterization record, not a
claim that every current behavior is the desired regulatory result.

## Compliance profile inputs

Later phases must select a versioned profile using at least lender category,
loan purpose, sanction date, jurisdiction, and collateral type. The profile
must supply tenor limits, LTV limits and denominator rules, bullet eligibility,
monitoring requirements, disclosure rules, and effective dates. These values
must not become scattered constants.

For the initially accepted gold-loan profile:

- a bullet loan settles principal and interest at maturity;
- an applicable consumption bullet loan is limited to a 12-month tenor;
- bullet LTV uses the total amount repayable at maturity;
- LTV is monitored throughout the tenor;
- contractual dates, not operational grace, determine overdue and DPD;
- the three-day grace may delay charges or escalation only;
- interest begins at actual disbursal and repayments affect interest from their
  effective dates; and
- penal charges, if enabled, apply only to the defaulted amount, are disclosed,
  and are never capitalized.

The applicable lender-category profile must be confirmed before Phase 1 seed
configuration is treated as deployable compliance policy.

## Current behavior inventory

| Area | Current source of truth | Characterized behavior | Decision |
| --- | --- | --- | --- |
| Contract dates | `PawnLoan.loan_date` and `tenure_months` | Maturity is calendar-month addition with end-of-month clamping. | Keep as legacy evidence; replace new-contract derivation with frozen product terms and exact dates. |
| Overdue | Balance selector | A positive balance becomes overdue the day after maturity. No grace shift is applied. | Keep; obligations will generalize this rule and add DPD. |
| Interest periods | Interest preview service | Consecutive calendar-month periods begin on the loan date. Partial periods use the frozen policy method. | Keep as a versioned legacy calculation contract. |
| Interest base | Balance at period start | A repayment during a period does not reduce that period's interest base. | Change for new RBI-aligned contracts to effective-date/time-weighted outstanding principal. Never rewrite finalized legacy accruals. |
| Repayment allocation | Repayment service | Fees, overdue interest, current interest, then principal; item principal uses highest rate first. | Preserve as legacy policy; make allocation waterfall explicit and versioned per product. |
| Balance | Immutable accounting-event fold | Posted/effective events are folded; future events are excluded; reversals apply the exact inverse. | Keep as recorded-balance source of truth. |
| Accounting | Loan event/outbox to DEA | Loans records the business event; DEA owns vouchers and journals. | Keep unchanged. |
| Collateral release | Release workflow | Financial settlement and custody return are distinct; release has explicit evidence. | Keep; products do not bypass release authority. |
| Renewal and auction | Dedicated services/events | Commands recalculate authority and append evidence. | Keep; later consume exposure/risk projections without letting projections authorize actions. |
| Risk and DPD | Maturity-overdue boolean only | No obligation-level DPD, LTV-monitoring state, risk snapshot, or performance classification exists. | Add in later phases without overloading contractual lifecycle state. |
| Tenant boundary | Tenant-scoped models/services | Operations execute inside the active tenant schema. | Keep and add explicit two-workspace regression coverage before schema work. |

## Golden examples

### Month-end maturity and overdue

A loan dated 31 January 2026 with a three-month tenor matures on 30 April
2026. It is not overdue on 30 April and is overdue at the 1 May day-end view if
an amount remains due. A three-day customer grace does not move either date.

### Current mid-period repayment behavior

A loan disbursed on 3 August 2026 for INR 50,000 at 2% monthly starts its first
period on 3 August. If INR 10,000 principal is repaid on 15 August, the current
implementation still calculates the 3 August-2 September period on INR 50,000,
producing INR 1,000 interest. The INR 40,000 balance affects the next period.

This is frozen by a characterization test so the Phase 3 calculation-contract
change is intentional and reviewable. The target for new RBI-aligned contracts
is effective-date segmentation: interest before 15 August uses INR 50,000 and
interest from 15 August uses the post-payment balance under the chosen day-count
and payment-effective-time convention.

### Immutable correction

A repayment reversal restores exactly the principal, interest, and fee effects
of the original repayment. Finalized accruals and posted DEA evidence are not
edited in place.

## Four-product schedule fixtures

These examples freeze the contract semantics that Phase 2 schedule generation
must implement. Unless stated otherwise, use INR 120,000 principal, actual
disbursal on 31 January 2028, 12 monthly periods, simple 1% monthly interest,
INR 0.01 rounding per obligation, and no fees. The leap year is intentional.

| Product | Contractual obligations | Golden expectations |
| --- | --- | --- |
| Single-payment bullet | One maturity obligation on 31 January 2029. | Principal INR 120,000 plus INR 14,400 interest is due at maturity. No amount is overdue before the following day. The disclosed bullet LTV denominator includes INR 134,400. |
| Periodic-interest bullet | Interest is due on each monthly anniversary; principal is due at maturity. | INR 1,200 interest is due on 29 February 2028, then on each clamped anniversary, with INR 120,000 principal plus the final INR 1,200 interest due on 31 January 2029. A missed February interest obligation starts DPD on 1 March even though principal has not matured. |
| Flexible partial-payment bullet | No scheduled interim principal; residue and unpaid interest mature on 31 January 2029. | A voluntary INR 20,000 principal reduction effective 15 April segments interest on that effective date for the new calculation contract. Later interest uses INR 100,000. Payment does not authorize partial collateral release. |
| Installment, EMI | Twelve monthly-anniversary installments under the frozen EMI formula and rounding/residue rule. | At 1% monthly, the unrounded level payment is approximately INR 10,661.85. The final obligation absorbs rounding residue so scheduled principal totals exactly INR 120,000. An extra principal payment keeps the installment amount and shortens tenure. |
| Installment, equal principal | INR 10,000 principal each period plus interest on opening principal. | First installment is INR 11,200; second is INR 11,100; final is INR 10,100. Scheduled principal totals exactly INR 120,000. |

Additional boundary fixtures:

- A 31 January monthly anniversary becomes 29 February in leap year and 28
  February otherwise; the contract must state whether subsequent dates recover
  the original day or remain clamped. The accepted default is original-day
  recovery when that day exists.
- A payment on its exact due date is timely. DPD becomes one only after the
  unpaid obligation crosses the next day-end boundary.
- A configured three-day grace changes neither the due date nor DPD; it only
  suppresses configured charges and escalation through the grace window.
- An early payment is allocated only to obligations eligible under the frozen
  product waterfall. It cannot silently create a collateral-release right.
- Final rounding residue belongs to the last applicable obligation and must not
  create or destroy principal.

## Event and DEA reconciliation

The mid-period golden test now reconciles the accepted INR 10,000 principal
payment to the immutable repayment event: its effective date is 15 August 2026
and its payload carries INR 10,000 principal. Existing DEA integration coverage
then proves that this same payload produces a balanced repayment voucher,
credits the borrower/principal controls, debits cash, and leaves collateral in
the vault. This preserves the boundary: schedule and allocation decide the
economic split; DEA posts that split without becoming the loan calculator.

## Phase 0 verification

- Balance lookup and repayment-command regressions prove that the same local
  loan identifier is always combined with the active workspace identifier.
- Balance, interest formula, repayment allocation, due-date, reversal, future
  event, and mid-period repayment characterizations pass.
- The golden repayment event reconciles its economic values and effective date;
  existing DEA integration coverage reconciles that event to a balanced voucher.
- Django system checks pass and no migration is introduced.

The regulated lender category remains an explicit deployment input rather than
an implementation blocker: Phase 1 may model and seed draft compliance profiles,
but none may be activated for lending until its lender category and effective
RBI profile are selected and approved.
