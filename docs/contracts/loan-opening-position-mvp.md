---
status: draft
owner: project
updated: 2026-09-12
tags: [loans, portability, opening-position, mvp]
---

# Loans opening-position MVP contract

Operational pilot update: opening commit setup accepts optional
`local_loan_number`, a nonempty destination number of at most 64 characters.
Operators should propose the readable source number where it is unique and outside
future numbering ranges. Preview and commit validate it; the approved input digest
covers its value. Omitted values preserve older generated-number semantics.
Source identity and accepted historical evidence are independent of the displayed
number. See the [pilot decision](../adr/2026-09-12-opening-pilot-operational-readiness.md).


This defines the next financial migration capability for active loans whose earlier
history is incomplete. It is a design contract, not a released JSONL schema or
import command. The existing `loan-history/1` contract stays unchanged. See the
[source review](../implementation/legacy-dump-source-review.md) and
[design decision](../adr/2026-09-12-loans-opening-position-contract.md).

The [offline opening review format](loan-opening-review-v1.md) now implements
missing-information and document reconciliation checks. It is not a canonical
opening importer or implemented servicing rule.

The internal `loan-opening-evidence/1` read foundation is implemented: one
`MIGRATION_OPENING` on the existing immutable event table freezes the full reconciled
review and a distinct source-item to destination-item map. Its envelope carries
contract version 1, INR, destination loan identity, cutover effective date and
principal/interest/fees exactly matching the review. Readers verify destination
Workspace/borrower/licence revision/series/product references and original date.
They keep opening totals separate, reject pre-cutover queries and mixed origins,
and reconstruct per-item remaining principal. Migration 0010 adds the event choice
and one-opening-per-loan constraint; it adds no table. Document reconciliation
still does not authenticate source claims or authorize a write. Generic event
posting and native monthly interest previews on opening loans remain blocked. This internal
envelope is not a public upload format or acceptance of the legacy continuation
rule. The [v2 checkpoint](loan-opening-review-v2.md) now implements inclusive
anniversary collection continuation previews and exposure projection. Reviewed
remaining obligations can be materialized with original dates, owner authorization,
retry comparison and atomic rollback in existing tables. Dedicated full release
now posts collection catch-up and settlement, with atomic coupled reversal,
original-schedule restoration and custody return. Partial repayment/renewal/auction
and native monthly accrual remain unsupported for this origin. An owner-authorized
[opening commit](../adr/2026-09-12-authorized-opening-commit.md) now persists reviewed
v2 inputs atomically with shared source identity and safe replay; its preview
rolls back all financial writes. Unknown gross and Bronze mapping are supported.
Source verification and browser approval are implemented for one reviewed jcl
opening, and opening evidence export is available. Unresolved due terms, actual
source/destination/cutover review and an actual reconciled pilot remain pending
before actual migration. See the
[servicing decision](../adr/2026-09-12-opening-full-release-servicing.md).

## Owner-selected scope

- First source: the legacy dump, selected tenant `jcl`; Excel adapters follow.
- Preserve each retained loan's existing billing dates and agreed interest rules.
  Do not reset the billing anniversary or silently switch its interest basis.
- Propose skipping loans with incomplete structured collateral for the initial
  migration. Preserve the whole source graph and show the exclusion's count and
  stored-principal effect. This is a review proposal, not debt settlement/deletion.
- Start with active, simple-interest flexible repayment loans and complete usable
  current collateral. Origination history need not be fabricated. Released-record
  import remains a separate capability; a released loan never becomes an opening.
- No general-ledger restoration, arbitrary formula engine, bulk financial runner,
  renewal/auction chains, capitalization, installment products or external funding
  graphs in this first opening contract. Future actions unsupported for an opening
  loan must fail explicitly until their evidence paths are implemented.

## Migration boundary and required facts

Use a single approved business cutover date C and timezone for a selected migration.
The opening represents the position after all source activity included through C.
Subsequent ordinary financial events must be after C. Same-day overlap between
systems is excluded from the first contract; the actual final write handover must
make source and destination coverage unambiguous. The April dump is rehearsal input,
not an instruction to use April as the final cutover.

| Required group | Meaning |
| --- | --- |
| Identity | Stable source installation namespace, tenant schema, source loan key, unchanged original number, source document/hash and selected-loan scope fingerprint |
| Borrower/setup | Exact Party source reference and explicit destination Workspace, licence/series and compatible product/calculation mapping; retain the source licence label/ID without inventing its number or legal validity dates |
| Original terms | Known original loan date, original amount as a source claim, original maturity/due dates, agreed periodic rates/amounts, grace and calculation rule identity; cutover never renews the loan or restarts its tenure |
| Opening balances | Explicit approved outstanding principal P, recognized unpaid interest I and fees F at C, each with source/reconciliation basis; zero must be supplied deliberately, not substituted for unknown |
| Collateral | Stable item IDs, physical description/quantity, explicit metal, gross/net weight and purity meaning, current custody declaration at cutover, per-item remaining principal and agreed interest inputs |
| Current valuation | A dated reviewed assessment, or an explicit v2 UNVERIFIED source claim that creates no appraisal/current LTV; no claim of an original appraisal or historic verification |
| Interest continuation | Original billing anchor and period-construction rule; the next/current period's boundaries, agreed basis for each item, and already-recognized/advance-covered amounts for that period |
| Remaining obligations | Unpaid principal and interest obligations with their real due dates, plus supported future schedule rules; distinguish already recognized interest from interest only projected into future obligations |
| Review attribution | The local owner/importer, actual review/recording time and approved source balances/terms; original actors remain source claims and need not have local accounts |

P must be positive; I/F nonnegative; all numbers finite, within model bounds and
the reviewed precision rules. Sum of per-item remaining principal must equal P.
Sum of remaining principal obligations must equal P. Recognized interest is not
necessarily all scheduled future interest; those totals must not be equated blindly.
Originally overdue obligations keep their due dates and DPD; migration cannot make
them newly due. Unknown due dates or an unsupported remaining schedule block active
servicing until reviewed, rather than creating an arbitrary fresh three-month loan.

The source's one weight column is not automatically both gross and net weight.
Opening review v2 and the destination model now support null for unknown gross
weight and explicit Bronze, while ordinary native draft/approval remains strict.
See the [collateral decision](../adr/2026-09-12-legacy-collateral-evidence.md).
The owner's corrected answer establishes legacy source weight as net weight,
excluding stones/non-metal parts. It supersedes the earlier gross interpretation;
do not deduct stones again. Gross weight remains unknown, and net weight is not
automatically pure-metal weight: source purity is a separate input. A passing
source collateral check does not establish full destination collateral readiness.
Missing images alone do not count as incomplete structured collateral in the skip
rule. Current custody confirmation does not manufacture past custody movements.

An explicit inactive legacy licence reference now supports unrecorded source
validity, with null dates and a source grouping label. It cannot authorize new
lending and is not verified regulatory evidence. An opening with UNVERIFIED values
may settle all debt and return all collateral without relying on those values;
partial-release valuation requirements remain. See the
[evidence-gap decision](../adr/2026-09-12-legacy-opening-unknown-evidence.md).

## Preserve interest without replaying unavailable history

The agreed rule must specify period boundaries, complete/partial-month treatment,
interest basis, payment effect, rounding quantum/mode and whether rounding is per
item or aggregate. Distinguish a fixed original monthly amount/original-principal
basis from outstanding-principal-at-period-start. Loan-level source `interest` is
money in the inspected legacy calculation path; item `interestrate` is a percentage.

Neither an old report's derived total nor an existing destination product name is
sufficient evidence of the agreed rule. The legacy model and query/report paths
disagree, and payment allocation can depend on entry time. Preserve stored payments
as source evidence; do not rerun legacy save methods, choose the more convenient
formula, or silently apply the current decreasing-principal/item-rounding behavior.
Implement only a named, reviewed rule needed by the pilot; no user-entered formulas.
If that rule is not yet supported, the loan stays in review.

For a cutover inside a billing period, freeze a continuation checkpoint:

1. The actual original period start/end and next anniversary. Do not replace the
   period start with C+1 merely because the software starts servicing then.
2. The basis required to calculate that period, including any required per-item
   principal at the period start. An outstanding balance at C alone cannot prove
   the principal at an earlier period start.
3. Interest already recognized for this period (whether paid or still unpaid),
   its covered fraction if applicable, and any prepaid/advance amount already
   covering the period. These are separate from the outstanding-interest balance.
4. For each later recognition, charge only the additional amount under the frozen
   rule after crediting what is already recognized/covered. Never create an accrual
   before the opening or charge the covered part twice. Missing or inconsistent
   continuation evidence blocks activation; do not clamp a negative remainder.

At a clean billing boundary, this checkpoint can be simple: the next original
period starts after C with zero recognition carried into it. Nonzero advance credit
or a more complex partial-period basis may remain unsupported until its exact
continuation is tested. Preserve source data instead of inventing an advance amount.

Synthetic reconciliation example (not proposed production balances): P=900, I=24,
F=0; I includes four already recognized but unpaid units for the current period.
If the reviewed total charge for that period is ten, only six more are recognized
when it completes. Interest then becomes 30; a subsequent five-unit interest
payment leaves 25. Importing another full ten would double-charge the carried four.
An already-paid four would still be recognized carry, but would not be in I.

## Canonical opening evidence and subsequent servicing

The owner's first-month example now confirms 200 interest and a 10 document charge
collected at disbursal of a 10,000 loan dated January 10, followed by principal-only
collection on January 20 release. Preserve that first-month coverage and settled
fee; do not charge either again after migration. Collection does not by itself
specify accounting recognition timing: represent coverage once under the reviewed
opening contract, never both as paid recognition and as separate advance coverage.
No missing old payment event needs to be fabricated. For the same loan released
February 20 the owner specifies collection of 10,200, including 200 additional
interest. The owner confirmed February 11 as the first release date requiring that
additional 200: first-month coverage includes February 10. Do not shift the charge
to February 10 or delay it until the next completed month. For a January 31, 2026
loan, the owner confirms first-month coverage through February 28 and additional
monthly interest from March 1. The owner confirmed April 1 as the first release
date requiring 10,400: restore the original anniversary after the shortened month,
with collection increasing the day after that inclusive boundary. Do not carry
February 28 forward permanently. The owner confirmed net cash of 9,790 after
deducting 200 interest and the 10 document charge; principal remains 10,000.
The owner's rounding examples match whole-rupee HALF_EVEN (148.20/148.50 -> 148,
148.80 -> 149, 149.50 -> 150); preserve them as acceptance cases. Aggregation across
items/months was subsequently addressed for rehearsal by the owner clarification
that collections can be negotiated and accepted shortfalls treated as interest lost.
The Loans-owned `original-anniversary-upfront-inclusive/1` pure collection
calculator and source-scoped `jcl-owner/1` preparation profile are now implemented.
Version 1 provides whole-rupee-only illustrations. Explicit `jcl-owner/2` and
calculation version 2 now sum item monthly charges, multiply by additional months
and round once to whole rupees with HALF_EVEN, removing fractional preview holds.
This deterministic rehearsal baseline is separate from actual cash collected and
accepted interest loss, whose missing amounts stay unknown. The owner has not
authorized a fixed 50-rupee tolerance or automatic principal/fee reduction.
Single-loan full release now supports explicit authorized interest concessions
with immutable separate cash/loss evidence and reversal/idempotency/isolation
tests. This native workflow still requires the migration-opening integration
before it can serve imported opening loans. Above-baseline cash
also requires explicit allocation; never treat it as a negative interest loss.
See the [decision](../adr/2026-09-12-legacy-collection-estimates-and-concessions.md).
These calculators do not supply certified opening balances,
accounting accruals or active servicing. Net weight is mapped with owner evidence,
while gross, due terms, custody/valuation and other missing facts remain unresolved.
The current review descriptor is not an implemented
servicing rule; align its eventual financial behavior with these examples. See the
[owner's example](../implementation/legacy-reconciliation-worksheet.md#first-month-collection-clarified-in-chat-2026-09-12).


Loans owns a distinct immutable `MIGRATION_OPENING` event and opening snapshot,
proposed for implementation. They initialize P/I/F and per-item principal/custody,
freeze the selected calculation/continuation and remaining-obligation evidence,
and retain source references plus local approval attribution.

Do not reuse DISBURSAL, RENEWAL_OPENING or approval snapshots as fictional historic
actions. The opening produces no cash disbursal, origination fee, original approval,
notification or recreated document issue. Opening principal is reported separately
from new lending and historical disbursal totals; differences between original
source principal and P are not invented repayments or write-offs.

After opening, canonical balances are opening amounts plus subsequent immutable
events. Payment allocation, tranche balances, full release/custody return, remaining
obligations, delinquency and risk must read that same evidence. Existing live
commands must accept a valid opening origin explicitly; no disabled guards or
dummy disbursal rows. Interest begins/resumes from the continuation checkpoint,
while original loan and due dates remain visible and authoritative for their roles.

Queries before C must say financial history is unavailable, not return a misleading
zero balance or fabricate a complete graph. Opening evidence must export with
declared partial coverage; complete-history export cannot relabel it `loan-history/1`.
The eventual opening profile must round-trip the opening and supported later events.
The implemented [export and dedicated restore](loan-opening-export-v1.md) retains
that graph with unavailable earlier history declared. The restore rebuilds and
reconciles the supported graph using explicit destination mappings and preserves
original source identities; source-local keys are not used as destination keys.

## Source selection and exclusion proposal

The implemented preview's opt-in `incomplete-collateral/1` proposal skips the whole
loan when it lacks structured item rows, any item lacks a description, or item
weight/quantity/allocated principal/purity is missing, invalid or nonpositive;
purity above 100 or nonintegral quantity also qualifies. No age cutoff is inferred.
Payment absence, a Bronze/OTHER mapping question or a missing photo is not itself
a reason under this rule. Mixed loans keep all their items together; never omit an
invalid item and leave its loan balance silently reduced.

All loan/item/payment/release source rows remain in the review with a proposed
disposition. Customers and licence/series rows stay available. Source loan amount
sums are labelled as stored amounts, not verified outstanding balances. A separate
manifest identifies every proposed exclusion, reason, source hash and original
number. Future approved selection must bind the exact source snapshot and loan set;
editing/retrying a proposal is not financial import authorization.

Skipping is for this initial migration. It does not forgive, close, delete or
rewrite a source loan, and it does not claim a complete Workspace migration.
Excluded source identities remain eligible for a separately reviewed later import;
the exclusion proposal does not create accepted identity bindings or tombstones.

## Authorization, replay and correction

Use explicit destination Workspace/actor authorization and the existing historical
import/setup access boundaries before staging, approval, commit and replay. Final
approval binds source scope, mappings, balances, original billing terms, continuation
and obligations; commit rechecks those facts and permissions under locks.

One accepted financial origin per source loan: a complete-history restore and an
opening cannot both activate it. Identical accepted input is an authorized no-op;
changed input conflicts. Importing earlier history later cannot add a second opening
or double-count source payments already represented in P/I/F. Historical evidence
backfill would need separate semantics and is not part of this MVP.

Preview retains no business rows. A failed commit rolls back the complete loan,
items, opening, obligations and identity evidence. Correcting an accepted opening
requires an explicit audited correction/void operation with dependency checks;
ordinary edits/deletes are forbidden. Do not invent a cash refund as its inverse.
After later servicing, fail closed until the supported compensating path is defined.

## Implementation boundaries and acceptance gates

Balance settlement checks and tranche construction now recognize migration openings.
Native interest still starts unaccrued history at `loan.loan_date`; opening loans
explicitly fail that preview until continuation is implemented. Relevant owners:

- `models/core.py`, domain event kinds and evidence guards: opening origin and scope.
- `selectors/balances.py`, `services/pawn_tranches.py`: opening amounts and item bases.
- `services/pawn_interest.py`: original-period continuation without historic replay.
- `services/obligations.py`, obligation selectors: cutover obligations/due dates.
- `services/pawn_repayment.py`, `pawn_release.py`, financial-action guards: servicing.
- Portability staging/provenance/export: reviewed mapping, confirmation and replay.

New Workspace-owned evidence needs direct non-null ownership, forced RLS, registry
coverage, immutable guards and restricted-role isolation tests. Tests must prove:
exact opening balance/tranche/obligation reconciliation; full and partial-period
continuation (including month ends/rounding); repayments and full release; historic
date coverage; original-number lookup without live-counter changes; unchanged native
and complete-history paths; source identity conflicts across both origins; permission
revocation and cross-Workspace rejection; rollback and repeated-import safety.

Before actual `jcl` activation, still establish: the final C/timezone/handover,
destination setup/Party bindings, approved P/I/F and due-date evidence, the agreed
source calculation rule and any period carry, weight interpretation/current custody,
and approved exclusion membership. The owner has selected preservation of existing
rules; exact disputed legacy calculations have not been approved by that preference.
