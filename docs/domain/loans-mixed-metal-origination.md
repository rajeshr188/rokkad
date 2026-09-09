---
status: active
owner: loans
updated: 2026-08-09
tags: [loans, collateral, interest, ltv, disbursal]
related:
  - ../adr/2026-08-05-pawn-loan-collateral-tranche-economics.md
  - ../adr/2026-08-09-loans-collateral-identity-media-and-labels.md
  - ../implementation/loans-girvi-operator-parity-pilot.md
---

# Loans Mixed-Metal Origination

## Extracted Business Rules

| Rule or outcome | Decision | Loans expression |
| --- | --- | --- |
| One PawnLoan may contain gold and silver items | PORT | Every collateral item is an independently identified tranche inside one PawnLoan aggregate. |
| Each item raises an allocated part of the loan principal | PORT | `allocated_principal` is required per item; the loan principal is their exact sum. |
| Interest depends on both metal and that item's principal | REPLACE | An effective-dated workspace/license metal-rate policy is resolved for each item. Monthly interest is the sum of each `allocated_principal * metal_rate`. The aggregate rate is derived display evidence, never an editable authority. |
| An item cannot raise more than its safe value | REPLACE | The configured valuation method selects calculated metal value, latest appraisal, or lower-of-both; `allocated_principal <= selected value * maximum LTV` is service-enforced before number allocation. |
| Collateral must have visual evidence | PORT | Every new draft item requires a JPEG/PNG photograph. Approval independently fails closed without media and freezes the exact photo identity/hash. |
| One month's interest is normally deducted upfront | REPLACE | Effective policy owns zero to twelve advance-interest periods. Fees separately declare whether they are deducted at disbursal. |
| Cash handed to the customer must be explainable | REPLACE | `gross item principal - advance interest - deducted fees = net cash`; approval and disbursal preserve the component and tranche evidence. |
| Staff may type an arbitrary loan-level interest rate | RETIRE | The loan-level value is derived from frozen tranches for compatibility/display and cannot override item policy. |
| Formal appraisal workflow and appraiser evidence | DEFER | The MVP captures latest appraisal value on the item. A later slice may add a source-linked appraisal command without mutating approved evidence. |

## Operator Flow

Draft collateral rows offer an editable suggested appraisal when gross/net weight
and purity are entered. HTMX retrieves the latest usable Workspace INR 24k buying
rate at or before the loan date, multiplied by net weight and purity percentage,
rounded down to paise. Gross weight is checked but does not value stones/non-metal.
The rate date is displayed. This is a metal-value estimate for operator review,
not an automatically approved appraisal. Manually entered or persisted values are
not overwritten; Use suggestion explicitly adopts the estimate. Missing rates or
invalid inputs never become a zero valuation. Only normal draft saving persists
the entered appraisal, and approval still validates/freezes the required evidence.

1. Select Party, license, series, loan date, and tenure. Before saving, the
   page shows the non-consuming next expected PawnLoan number for every
   available series. After saving, the edit page shows the permanently
   allocated official number.
2. Add every collateral item with metal, net weight, purity, appraisal value,
   allocated principal, and at least one photograph.
3. Preview economics. The page shows each item's rate, selected value, maximum
   principal at LTV, and monthly interest, plus gross principal, deductions,
   and estimated net cash.
4. Correct an over-LTV allocation on the offending item's allocated-principal
   field. Failed validation does not allocate or consume a loan number.
5. Save the draft, approve it, and disburse on the effective date. Approval
   freezes policy, tranche, valuation, and photo evidence; disbursal freezes the
   actual gross/deduction/net calculation and creates the configured accounting
   event disposition.

For a saved draft containing several items, the operator may select one or
more collateral items and preview **Split to new loan**. At least one item must
remain on the source. Confirmation moves the selected item identities and
photographs to one newly numbered draft, recalculates both drafts independently,
and leaves the source number unchanged. The split is atomic and creates no
accounting event.

## Invariants

- Item allocated principals sum exactly to gross loan principal.
- Item interest sums exactly to aggregate monthly interest.
- Each item passes its own LTV; excess value on one item cannot conceal an
  over-allocation on another.
- Later policy, metal-rate, valuation, or gallery changes do not reinterpret an
  approved or disbursed loan.
- Draft validation completes before official number allocation.
- In `DEFERRED` accounting mode, a pending outbox is the expected disposition;
  it must not be described as a posted voucher.

## P2 Software Evidence

- Mixed gold/silver preview proves independent 2% and 4% item rates, item
  interest, aggregate monthly interest, advance-interest deduction, and net
  cash without creating a draft or consuming a number.
- Over-LTV allocation is rendered on the offending allocated-principal field;
  the draft and number sequence remain unchanged.
- Service tests prove item-level LTV, mixed-metal principal/rate derivation,
  approval revalidation/freeze, immutable disbursal tranche evidence, atomic
  policy snapshot/outbox creation, and use of policy frozen at approval.
- The complete 18-test draft UI suite and 11 focused domain/service tests pass.
- The workspace Owner accepted P2 on 2026-08-09 after executing the browser
  workflow and verifying the number and deferred-accounting corrections.
