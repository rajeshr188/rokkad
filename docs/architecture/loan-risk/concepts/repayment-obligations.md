---
status: proposed
owner: loans
updated: 2026-08-11
tags: [loans, obligations, repayment, allocation]
related: [../architecture-plan.md, loan-exposure.md, delinquency-dpd.md]
---

# Repayment Obligations

The current app records what economically happened. Obligations add what the
contract required to be paid, when it was due, and how it was satisfied.

## Three different allocations

```text
Repayment event
   +-- component allocation: fee / interest / principal
   +-- tranche allocation: which collateral principal was reduced
   +-- obligation allocation: which dated contractual due was satisfied
```

All three are necessary. `ObligationAllocation` does not replace the existing
component allocation or `PawnLoanRepaymentAllocationLine`.

## RepaymentObligation

Immutable evidence should identify the loan/workspace, due date, supported
component amounts, source contract/accrual evidence, type, and sequence. Derive
outstanding, satisfied, and overdue state from allocations; do not maintain
mutable truth fields for them.

Generate the schedule from the frozen ProductVersion. Single-payment bullet,
periodic-interest bullet, flexible partial-payment, and installment products
share the same obligation/allocation model but require different deterministic
schedule strategies. Their exact contractual rules must be approved before
implementation.

## ObligationAllocation

An immutable allocation links a repayment, release, renewal settlement,
auction recovery, approved waiver, or reversal to one obligation component.
Apply eligible payments deterministically, normally oldest due component first.
Reject over-allocation. A reversal appends exact compensating allocations.

## What it simplifies

- deterministic due, overdue, oldest unpaid date, and DPD;
- explainable partial payments;
- historical as-of reconstruction;
- common delinquency logic for future repayment structures;
- auditable cure and bucket transitions; and
- proof of how release, renewal, or auction settled old dues.

## What remains unchanged

- Accounting events remain economic money-movement truth.
- The balance fold remains recorded-balance truth.
- Tranche lines remain collateral-principal movement truth.
- DEA remains voucher/journal truth.
- Notice and auction authority changes only through an accepted ADR.
