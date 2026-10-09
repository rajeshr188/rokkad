---
status: accepted
owner: project
updated: 2026-10-09
tags: [loans, portability, admission, migration]
---

# Import ordinary loans from their known position without requiring earlier history

The owner accepts the review following the
[historical-loan origin investigation](../implementation/historical-loan-origin-review-20261009.md)
and authorizes implementation in the recommended order. On 9 October the owner
explicitly confirms, for the retained old Rokkad source used by JCL, JSK and
Lakshmi: **released means the loan was completed, no debt remains, and collateral
was physically handed back to the borrower.** This is a source-scoped business
interpretation, not a universal meaning for arbitrary external release fields.

The owner additionally confirms that the 190 JCL records with an earlier
owner-confirmed closed/zero position and no release row can be considered closed
with collateral returned to the borrower. Preserve unknown closure dates; this
confirmation adds custody knowledge without inventing release transactions.

## Decision

An incoming loan does not need earlier receipts, approval, payout, accrual or
settlement events to become an ordinary loan. Business state, the position
accepted for future operations, and available earlier history are separate.
History coverage is metadata, not an additional loan product or business state.

Active loans use a known outstanding position at an identified cutover and a
supported continuation contract. Missing earlier receipts do not block import;
unknown amounts required for future debt calculations remain actionable. Current
valuation/monitoring evidence is separate from original lending approval.

Closed loans use an accepted zero-debt closed position. Known original details
are retained; missing original principal, rate, tenure, pricing, payment totals
or calculation settings stay unknown. A current monitoring policy and a complete
historic calculation contract are not prerequisites for importing a completed
record. Source custody meaning is captured independently. Owner-accepted source
semantics may establish closed status and returned custody for a reviewed cohort,
without asking for a separate paper receipt for each loan.

An import establishes an audited accepted position, never fabricated cash
collection, payout, approval, charge, concession or physical handover event.
Rokkad records subsequent actions through the same ordinary lifecycle. Full
earlier history remains optional, and complete Rokkad restoration preserves its
existing strict versioned contracts.

## Implementation and existing evidence

Reuse ordinary PawnLoan, current source identity/provenance and existing opening
services where they meet the contract. Permit absent original details narrowly
for evidenced closed-position admissions; preserve native/draft/active constraints
and restricted-role enforcement. No dummy terms, balances, borrowers or current
policy snapshots may be invented solely to satisfy persistence.

First inspect retained source identities, borrower/register mappings, available
details and contradictions. The eligibility question is supported closed position,
not complete historical reconstruction. Prepare eligible batches and isolate
exceptions. Admission preserves every original document/photo and immutable
source identity, prevents duplicate ordinary loans, and never overwrites existing
active or posted records. Counts and exact mappings are verified at commit.

The familiar Loans list and ordinary detail are the main browsing experience.
After conversion, retire the separate archive's routine directory role only when
its remaining records are accounted for. Retained evidence and exports survive.
Simplify and benchmark directory search after admission; conversion alone does
not establish a performance improvement.

Exports and fresh-Workspace imports preserve accepted position, known original
details, unavailable-history declarations, provenance and later Rokkad activity.
Do not reinterpret unavailable receipts as no receipts, or unknown collected
interest as zero. Existing published profiles retain their old meanings.

IP-03 implements the narrowly guarded ordinary closed-position basis in the same
PawnLoan/event/provenance tables, with common position readers and versioned
source/media portability. Its marker is a persistence basis, not a new product
or lifecycle state. See the [delivery record](../implementation/loan-position-import-ip03.md).

See the [ordered delivery plan](../plans/loan-position-import.md). This decision
authorizes the work; it does not claim unperformed schema, conversion, recovery,
compatibility or production acceptance checks complete.
