---
status: proposed
owner: loans
updated: 2026-10-01
tags: [loans, khata, agreements, collateral, planning]
related: [../plans/khata-agreements.md, 2026-08-05-pawn-loan-release-and-renew-only.md, 2026-08-11-loans-product-obligation-and-risk-architecture.md, ../constitution.md]
---

# Khata agreements with staged withdrawals and collateral exchange

## Status

Foundation architecture accepted for local implementation on 1 October 2026,
following the owner's instruction to proceed with the foundation/calculator slice.
Business rules below remain confirmed. Broader servicing architecture is still
subject to the recorded review gates. Production migration/activation is not part
of this slice. See the [implementation checkpoint](../implementation/khata-foundation.md).

The later instruction to proceed authorizes the next local opening/custody/payout
slice, now implemented; see its [checkpoint](../implementation/khata-opening.md).
Opening approval, receipt and actual payout are separate immutable operations.
Valuation uses existing same-day Rates evidence. Further servicing and production
activation remain subject to their delivery gates.

The next continuation accepts the completed-period/interest-receipt architecture
for local implementation; see the [collection checkpoint](../implementation/khata-interest-collection.md).
Three guarded, directly owned tables preserve monthly charges, exact segments and
oldest-due allocations. Accrual and cash receipt are separate source operations,
committed together when receipt catch-up finalization is needed. Active agreement
changes, settlement and compensating corrections remain subsequent delivery gates.

The following continuation accepts local implementation of separately approved
and activated limit/rate changes, with atomic principal repayment for formal
reductions. See the [agreement-change checkpoint](../implementation/khata-agreement-changes.md).
It extends the existing source operations and exact-segment guards, preserving
current-term selection independently of pending proposals. Only the financial
reduction is implemented here; outgoing custody, settlement and compensation
remain later delivery gates. Production activation remains outside these slices.

The next instruction accepts local collateral exchange, reduction-return and
settlement implementation; see the [custody/settlement checkpoint](../implementation/khata-custody-settlement.md).
Use one guarded through table for typed IN/OUT memberships, separate immutable
handover operations for actual returns, and a financial SETTLE source with closing
periods and allocations. A nullable charged-through date extends existing monthly
period evidence without rewriting billed history. Account settlement and closure
projections follow actual financial/custody sources. Corrections and integration
remain delivery gates; this acceptance does not enable production.

The later instruction accepts bounded correction safeguards locally. See the
[correction ADR](2026-10-01-khata-bounded-corrections.md) and
[checkpoint](../implementation/khata-corrections.md). Whole interest receipt
compensation and unhanded exchange cancellation append uniquely linked CORRECT
sources. Later dependencies and unsupported financial/physical histories are
refused. Current paid/custody readers recognize compensation without modifying
original evidence. Integration and pilot acceptance remain pending.

## Context

Customers offer a khata with an agreed limit. Borrowers bring collateral and
collect money gradually. Interest uses the agreed limit, not the amount collected.
Collateral can be exchanged while the same account continues.

The four current products describe repayment patterns. Periodic-interest bullet
is the closest. It does not by itself provide repeated disbursals, limit-based
interest or substitution. Current pawn economics allocate principal and metal
interest to items. Current ordinary-loan release rules prohibit selected-item
return under a continuing contract. Khata needs an explicit separate contract.

## Decision

### Confirmed requirements

1. One continuing khata account has an agreed borrowing limit and rate.
2. Collateral and withdrawals may arrive in stages, up to that limit.
3. Interest on the full agreed limit starts when the agreement opens on the
   first withdrawal. Draft preparation alone does not start interest.
4. Choose monthly or annual interest payment when making the agreement.
   Interest is paid in arrears on agreement anniversaries. A 10 October start
   has its first monthly due date on 10 November, or its first annual due date
   on 10 October the following year. Staff always enter a monthly percentage
   in the initial version, clearly labelled "Interest rate (% per month)".
   Monthly/annual payment is a separate choice and never changes the rate unit.
   Annual rate entry is deferred. For short months, use the last valid day and
   then restore the original anniversary: 31 January, February's last day,
   31 March. Annual leap-day treatment still needs an explicit rule.
5. This is not a revolving repay-and-redraw account. Partial repayments must
   not automatically restore borrowing capacity. Partial principal repayment
   is allowed only as part of formal limit reduction/renewal.
6. The interest base stays fixed until a formally agreed limit change/renewal.
   Exhausting a limit does not authorize an overdraft or automatic increase.
7. An agreed increase from INR 1 crore to INR 1.5 crore changes the interest
   base to INR 1.5 crore from the effective change. It does not itself pay out
   INR 50 lakh or create that amount of principal outstanding. For a mid-period
   increase, calculate interest on the old limit before the effective date and
   on the new limit from that date. Prorate by actual elapsed days divided by
   actual days between monthly anniversaries. Include the start/effective day,
   exclude the next anniversary/closure day, sum exact segments per monthly
   period and round once to paise using half-up. Annual bills sum monthly amounts.
8. A limit change/renewal keeps the same khata number and payment anniversary,
   with a new agreement revision. A reduction below actual principal outstanding
   requires repayment of the difference. Reductions use the same dated old/new
   limit split as increases. Add increases to unused entitlement and subtract
   decreases down to zero; principal repayments never restore it independently.
9. Compare outgoing and incoming collateral using the same current approved
   rates. At least equivalent assessed value is the target, not equal weight.
   Higher purity can compensate for lower weight. By default a lower incoming
   value produces a passive warning and the exchange can continue; the borrower
   may supply the missing collateral later. The workspace owner can choose
   strict enforcement. Use one simple exchange policy: allow with a warning/flag
   despite a value shortfall or account-LTV breach, or disallow the exchange
   when either condition fails. Strict means at least equivalent value, not
   exact equality. This refines rounds 1 and 2; do not introduce an independent
   hard LTV gate for an exchange allowed by warning mode.
10. Collateral exchange continues the same account. It does not itself change
    principal outstanding, the limit, the agreed rate or interest start date.
11. Collateral covers actual money withdrawn at the agreed LTV, not the whole
    undrawn limit. The exchange exception is not permission for an unsupported
    cash withdrawal or a higher borrowing limit.
12. An annually paying borrower who closes after four months pays interest for
    those four months, not a full year. After the first-month minimum, charge
    actual days for a partial month, over the actual days between monthly
    anniversaries, using the day-boundary and rounding rule above.
13. The workspace owner selects warn or block for overdue interest. Block mode
    blocks new withdrawals and collateral exchanges, while allowing interest
    payments, collateral deposits and valid settlement. Default to warn; unpaid
    interest becomes overdue the day after its due date, with no implicit grace.
    No automatic penalties are implied.
14. Use simple interest in the initial version. Unpaid interest stays separate;
    it does not itself earn interest or increase principal or the agreed limit.
15. Charge at least one full first month, never deducted upfront. Monthly payers
    pay it at the first monthly anniversary. Annual payers pay it within the
    annual bill, with no separate first-month bill. If the account closes before
    month one ends, collect the full first-month minimum at closure.
    Apply this minimum once per account, based on opening limit and rate. Charge
    the greater of the minimum and actual segmented interest; never restart the
    minimum after a revision or cap higher actual first-month interest at it.
16. Changed workspace warn/block policies apply to subsequent operations on
    existing khatas. Preserve completed operations and the policy used for each.
    This does not retroactively change agreed rates, limits or interest evidence.
17. Khata has no fixed maturity date. It continues until the borrower settles.
    Monthly/annual due dates are interest dues, not automatic principal maturity.
18. Allow one-for-many and many-for-one collateral exchanges, comparing combined
    values and preserving all item identities. Replacement must be the same
    metal; gold cannot replace silver or vice versa. Warning mode does not waive
    the same-metal rule. Do not offset one metal's shortfall with another metal.
19. Collateral can be returned during formal reduction or settlement. The owner
    has not chosen a standalone excess-collateral return workflow; exclude it
    from the proposed initial scope. For reduction returns, retained eligible
    collateral value x agreed LTV must cover actual principal remaining after
    repayment. Block the return if this fails, even when exchanges use warning
    mode. This is a mandatory check, not an owner-selectable exchange exception.
20. A newly agreed monthly rate can take effect through a dated agreement
    revision. Apply it from the agreed effective date and preserve all earlier
    calculations. Keep the same account number and payment anniversary.
21. Allocate partial interest receipts to oldest unpaid due interest first.
    Defer advance/excess interest payments in the first version until a credit
    workflow is selected. Do not redirect interest receipts to principal.
22. Clear due/overdue interest before collateral return during reduction.
    Not-yet-due accrued interest stays on its existing schedule; full settlement
    collects all applicable interest.
23. Preserve existing flexible loans and product settings in JCL, JSK and Lakshmi,
    including future ordinary flexible originations and their current policies.
    Khata is a distinct offering within Loans, not a conversion or replacement.
    No khata rate, minimum, collection or exchange rule applies to ordinary loans.
24. Use a separate workspace-owned khata series, either independent or associated
    with a licence in the same workspace. Round 11 supersedes the earlier required
    licence association. KH00001 remains the proposed default presentation. The
    series owns its counter; khata numbers are unique across the workspace,
    irrespective of licence. Keep ordinary loan sequences untouched. Freeze the
    licence association (including none) once the first account number is issued;
    a later association change requires a new series with a distinct prefix.
25. Existing authorised loan approvers may approve khata opening and limit/rate
    changes. Do not impose an additional owner-only approval requirement.
26. First release supports new khatas with newly agreed terms and recorded
    collateral. Historical/paper-account import is not required. This does not
    authorize treating already-paid paper debt as a new cash disbursal.
27. Routine entries use today's business date initially. Earlier transactions
    require a separately reviewed workflow; unrestricted backdating is excluded.
    Completed financial/custody evidence is never edited in place.
28. Additional charges, automatic penalties and funding/repledging workflows
    remain outside the first release. Do not inherit them from ordinary products.

### Proposed system direction

Offer a distinct Khata choice within Loans. Reuse Party, permissions, custody,
receipts, rates and immutable evidence where their contracts fit. Decide the
model shape after scenarios are agreed; do not force khata through ordinary
loan item-principal or release-and-renew assumptions.
The [delivery design](../plans/khata-delivery-design.md) recommends explicit
khata records/services within Loans after checking current disbursal, obligation
and collateral contracts. The [concrete technical design](../architecture/khata-technical-design.md)
specifies candidate tables, numbering, states, permissions, calculation contract,
atomic commands and verification cases. The series/draft/proposal foundation and
pure calculator are implemented locally; the broader servicing design remains
pending. Saved proposals are append-only evidence; editing appends a successor.
Approval/activation evidence will be separate, so saving terms cannot activate debt.

Independent series require no placeholder licence. Select the khata series at
opening; display licence details only when associated. Both modes use approved
khata agreement terms and workspace access/policies. Licence-specific eligibility
checks apply only to associated series. Capture lender identity/address in issued
agreement evidence even without a licence; reports include both modes and expose
a "No licence associated" filter. No ordinary-loan policy inheritance is implied.

Track agreed limit, actual principal outstanding, unused drawing entitlement,
collateral-backed draw availability, interest calculation base and interest due
as separate values. Rate units and collection frequency must also be separate.
Preserve the monthly unit explicitly in agreement evidence and documents so a
future annual-rate option cannot reinterpret existing rates. No unit selector
or annual-rate input is needed in the initial interface.

Retain a stable account identity with immutable agreement revisions and linked
withdrawal, interest, payment and collateral movement evidence. Keep the same
khata number and anniversary through limit changes/renewals; identify each
agreement revision separately without issuing a new khata account number.

Accept and record replacement custody before handing back outgoing items.
Evaluate both exchange equivalence and resulting account coverage. Apply the
confirmed warning/strict choice to exchange-value shortfalls; do not silently
restore a hard equivalence gate in warning mode. Keep old items and valuations
in history; never overwrite them with replacements.

Proposed evidence includes the policy used, outgoing/incoming values, exchange
shortfall, resulting account coverage and later top-ups. A shortfall is not a
cash payment, fee or additional principal. Keep initial shortfall handling to
the owner's allow-with-warning or disallow choice; promised top-up dates and a
separate follow-up workflow are deferred. Apply current workspace warn/block
policies at operation time, retaining their identity in the completed evidence.

These are khata-specific extensions. The four existing products, frozen loans,
ordinary partial-release prohibition and historical calculations retain their
meaning. No retired accounting/DEA integration is introduced; the current
constitution governs operational financial evidence.
Shared borrower summaries may include explicitly labelled actual khata debt once
khata exists, without changing existing loan contributions or counting unused
limits. Regression evidence is required before delivery; it is not yet produced.

## Consequences

Khata requires more than a fifth product label. Calculation, obligation dates,
withdrawal controls, custody, reversals, documents, reporting and data portability
must understand the agreement and its revisions. An uncollected limit must never
appear as disbursed principal or cash paid.

The [living plan](../plans/khata-agreements.md) records scenarios, open choices
and acceptance gates. The [screen and calculation review](../plans/khata-screen-review.md)
proposes the interface and records the five D1-D5 servicing/calculation choices,
explicitly accepted by the owner on 1 October. Other unconfirmed recommendations
remain proposals. Architecture remains under review. This ADR
does not yet supersede the ordinary-loan ADRs or approve delivery.
