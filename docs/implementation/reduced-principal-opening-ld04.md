---
status: active
owner: project
updated: 2026-10-05
tags: [implementation, loans, opening, ld-04]
related: [../plans/unified-loan-domain-correction.md, ../adr/2026-10-05-reduced-principal-opening-checkpoint.md]
---

# LD-04: reduced-principal opening continuation

## Supported checkpoint

The existing per-loan opening preview/confirmed commit accepts
`loan-opening-review/4`. It retains original source principal/date, remaining
item principal, original maturity/grace, custody and evidence. The captured
simple/full-month policy must match the shared monthly rule and per-item HALF_UP
quantum. No historical destination price/policy catalog row or fake approval is
created. Original agreement facts still require review.

The strict continuation object contains:

| Fields | Meaning |
|---|---|
| `covered_through`, `additional_months` | Actual cutover and original-anniversary count |
| `period_number`, `period_start`, `period_end`, `next_increase_on` | Exact covered current period and next charge day |
| `bases` | Complete item set, each `item_id` and evidenced `principal_base` |
| `expected_period_interest` | Sum of current item charges rounded using the saved policy |
| `recognized_interest`, `recognized_unpaid_interest` | Cumulative actual recognition and its unpaid balance at cutover |
| `current_period_recognized_interest`, `current_period_unpaid_interest` | Current-period portion of those totals |
| `advance_coverage` | Explicit list of current/future `period_number`, `interest`, `evidence_reference`; empty means none |
| `evidence_reference` | Reviewed checkpoint support |

Each current base lies between remaining and original item principal; first-month
bases are original principal. Opening admission still needs positive remaining
principal; a zero-principal checkpoint is held explicitly rather than failing in
display-rate arithmetic. Supported completed history is a separate admission
route. The eligible current charge minus current advance
equals current recognition. Current and earlier unpaid portions reconcile
separately to cumulative recognition and opening interest. Coverage cannot exceed
its period's charge. Missing/inconsistent fields remain held.

The source review and supplied policy are frozen under the existing
`loan-opening-commit/1` envelope. One MIGRATION_OPENING creates remaining debt and
obligations; no pre-cutover DISBURSAL, approval, receipt, concession or accrued
interest rows are fabricated. Source hash/mapping, authorization, locked retries
and conflict detection retain the existing writer's protections.

## Continuation example

This example is synthetic, not an attestation of a customer book. A loan dated
1 January originally had 1,000 principal. At 20 February it has 800 remaining;
the period 2 February–1 March used 900 at 1%, a charge of 9. Total recognized
interest is 9, with 5 unpaid. Cutover debt is 805, with zero additional charge.
On 2 March another 8 becomes eligible, making debt 813.

A 205 receipt on 21 February clears 5 interest and reduces principal by 200.
The current period's charge stays intact; 2 March then charges 6 on 600 remaining.
A receipt on 2 March first clears 13 interest; its reduction changes the
2 April charge. Reversal restores the checkpoint and recomputes supported later
eligibility without changing original maturity.

Current advance reduces current recognition; future advance reduces that future
charge once. If a subsequent principal reduction would leave advance exceeding
the future charge, preview/write reject it before posting. No refund or movement
of that credit is inferred. Other advance/refund agreements need separate support.

## Reads, servicing and portability

The shared resolver exposes immutable checkpoint bases, period, recognition,
coverage and boundary. At the review/4 cutover it returns recorded checkpoint debt;
financial actions still require a later date. Older profiles retain their existing
cutover read/action boundaries. Current digital collection, supported one-item
completed paper receipts, full release and paired reversals reuse existing writers.
Digital multi-item reductions keep highest-rate-first; wider completed paper
multi-item principal allocation remains a later slice.

Opening detail explains verified recognition/unpaid interest and unavailable
earlier transactions. It does not multiply present remaining principal across all
old months or assert old aggregate whole-rupee rounding.

Opening export/3 requires nested review/4 and always includes repayment_lines,
empty if unserviced. The published row schema reuses export/2 fields. The restore
path validates source-local graph/amounts, remaps identities, performs the same
writer/servicing actions, and reconciles semantic evidence. Old export contracts
remain readable; relabeling a checkpoint as export/2 fails explicitly. Wider
opening paper closure, renewal and auction portability remain LD-06/07.

Migration 0059 rejects mixed opening/payout/renewal origins in both orders, locking
the Workspace-owned parent. Existing unique-opening, immutability and forced RLS
remain in force. Exact native recovery automatically fingerprints the new trigger;
backups from a different guard definition require a matching recovery schema.
There is no new model or data migration.

## Verification and remaining acceptance

Verification runs in disposable `opening-checkpoint-ld04-qa-20261005`,
`test_rokkad_ld04_20261005`, with test settings. Migration 0059 is exercised only
there. Focused tests cover reduced/current bases, shared boundaries and short
months, whole-rupee/paise policy, recognition/unpaid/advance, multiple item rates,
paper dates, receipt retry, coupled reversal, closure, portable restore, exact
recovery, permissions, restricted-role mixed origins/immutability/isolation and
truthful detail text. The affected regression passes **299 tests in 192.437s**.
One pre-existing pilot assertion that expects no renewal link fails independently
on LD-03 source `a8605f3e`; it is retained and excluded from the final list.
Other pilot/renewal cases remain included. The whole repository suite is not
claimed green. System/migration-drift checks, 556-file Python parsing and scoped
whitespace checks pass. Final opening admission/validation follow-up passes
**55 tests in 15.139s**, including all **26 new LD-04 tests** and the established
positive-principal blocker. The first edge-case assertion expected a redundant
new error instead of that existing rule; it was corrected without adding another
validation rule.

The owner supplied the rule example: 10,000 principal on 1 January 2026, 1,000
principal paid on 20 January, then interest on 9,000 from 2 February. Tests cover
that boundary. A test rate of 2% and first-month advance of 200 are explicitly
illustrative assumptions, not supplied book facts. No complete real source
checkpoint was supplied; synthetic examples do not replace owner review and
representative source/staff acceptance before rollout.
Existing reduced-principal loans are not automatically converted. Wider source
rules/aliases, operations, correction/capture transitions and deployment remain
LD-05–08. No application/candidate/production database was migrated.
