---
status: accepted
owner: project
updated: 2026-10-05
tags: [adr, loans, admission, continuation, provenance]
related: [../architecture/ordinary-loan-domain-review-20261005.md, ../plans/unified-loan-domain-correction.md]
---

# One loan domain with explicit admission and continuation

## Status and scope

The owner selected the recommended direction and requested a checkpoint/start on
LD-01 on 5 October, after the analysis-only review. Acceptance authorizes that
read-only slice; the owner subsequently authorized LD-01A calculation alignment
and LD-02 common repayment/full release, then LD-03 completed-payout admission.
These slices are complete locally;
later admission/operation extensions and rollout remain separately planned.
The owner subsequently clarified the shared interest boundary and policy rounding
below. LD-01A implements it through the
[shared monthly contract decision](2026-10-05-shared-monthly-interest-contract.md). LD-01 itself does not change calculations or supersede earlier implemented
profiles before the corresponding correction is delivered. The
[source review](../architecture/ordinary-loan-domain-review-20261005.md) identifies
the reviewed checkout, evidence and limitations. The
[plan](../plans/unified-loan-domain-correction.md) tracks implementation.

## Context

Direct, recorded-paper and imported loans already inhabit `PawnLoan`. They share
events, item allocations, schedules and custody. October work also supplies
retrospective disbursal without digital historical quotes or a fabricated approval.
However, callers repeatedly infer future behavior from entry tags, and some
operations require a specific origin even when their real prerequisites could be
known. The earlier-payout adapter and strict history/opening import profiles impose
additional admission boundaries.

Existing calculation profiles differ in timing, recognition, rounding and item
allocation. Those observed code differences do not establish different intended
agreements based on entry channel. The opening profile also has a reviewed
recognition baseline and unavailable pre-cutover history. Those evidenced amounts
and limits must survive alignment of the shared borrower contract.

### Owner-confirmed shared interest contract

For a monthly loan dated 5 April with its first month paid upfront, the first
month remains covered through 5 May; the next monthly charge starts on 6 May.
This boundary applies to direct entry, backdated paper recording and imported
loans. Use the original loan date as the anniversary anchor, clamping each short
month independently. Rounding follows the standing economic policy captured for
the agreement, including supported quantum and aggregation convention. Current
policy edits cannot silently recalculate an existing agreement.

The earlier recommendation to preserve all differing boundary/rounding behavior
as separate ongoing business contracts is amended by this clarification. Preserve
immutable evidence and reproducibility of old calculations; correct implementation
discrepancies deliberately. Source channel cannot create different borrower terms.
Where an imported agreement lacks an evidenced policy mapping, explicitly review
the supported mapping rather than invent a historical destination policy row or
substitute today's policy. Recognition at cutover remains separate from charge
eligibility, and no pre-cutover charge is replayed.

## Decision

### 1. Keep one operational entity and lifecycle

Use existing `PawnLoan`, items, events, snapshots, schedules, source bindings and
custody records. ACTIVE/CLOSED and the supported paper custody states retain
their current meaning. No paper-loan or imported-loan servicing model is added.
Source labels remain useful audit information; they are not permanent product
categories.

An operational record needs a supported, evidenced financial origin. An archive
record is historical evidence, not automatically a zero-balance closed loan. A
record with unknown current position must disclose that uncertainty; it cannot
give a definitive settlement or borrower claim. Existing provisional paper records
are not automatically deleted, deactivated or recategorized by this decision.

### 2. Separate operation purpose from entry provenance

An action either **performs a transaction now** or **records a completed transaction**.
The purpose applies to origination and later servicing. It does not derive from
the original entry channel. A directly originated loan can later have a paper
receipt, and a paper-origin loan can subsequently be serviced entirely in Rokkad.

The shared New loan screen and standing series/license/Workspace preference remain.
The preference selects presentation, never authorization or a calculation rule.
Purpose-specific fields and adapters are appropriate where actual facts differ.
One experience does not require identical forms for approval and past evidence.

For new advances now, including renewal successors, retain current quote, LTV,
approval, policy, collateral and license checks. For a completed payout, verify
actual date, identity, terms, collateral, amounts and supported position. Retain
any genuine contemporaneous approval, but do not create one merely to admit a
past agreement. Destination historical Rates/policy rows are not required proof
that an external transaction happened.

An earlier native draft must retain its identity. A new retrospective adapter
cannot duplicate it or overwrite a frozen approval. A genuinely approved native
transaction may still be validated against its retained approval evidence;
otherwise use the supported retrospective contract after explicit review.

LD-03 implements that adapter through the existing recorded-history writer and
shared paper editor. Saved draft/item identities and genuine frozen evidence are
retained. Current legacy license references remain unable to authorize lending;
migration 0058 permits only owned evidenced completed payouts with a validated
recorded snapshot required before commit. The older retained-native earlier-payout
route remains bounded and separate from this general admission purpose. See the
[implementation](../implementation/completed-payout-admission-ld03.md).

### 3. Admit exactly one financial origin

| Admission | Canonical origin | Evidence and operational boundary |
|---|---|---|
| Supported original transaction/history | DISBURSAL, or existing supported renewal origin | Original terms and actual supported events establish the position. Prospective approval and retrospective verification are distinct evidence bases. |
| Reconciled opening | MIGRATION_OPENING | Item balances, recognized unpaid charges, continuation checkpoint and cutover establish the position. Earlier history remains retained evidence and is unavailable to operational balance queries. |
| No verified operational position | Historical-only/staged evidence, or explicitly provisional original record | Preserve known facts. Resolve missing transactions or a reconciled position before definitive debt-sensitive operations. |

No additional opening may be attached to an already originated loan to repair
missing receipts. Correct its supported history with immutable compensation, or
investigate until the position is established. An opening is not disbursed cash,
does not restart tenure and does not authorize replay of pre-cutover interest.

One origin, conservation, immutable source links, original versus remaining item
principal, Workspace scope, authorization, chronology and idempotency are invariants.
The proposed hardening work will test raw restricted-role DML before deciding
whether additional database exclusivity enforcement is needed.

### 4. Resolve a frozen continuation contract

Use a small Loans-owned read-only resolver over existing frozen evidence first.
It returns the facts required by a specific operation and explicit blockers when
they are missing. It is not a configurable formula engine or a replacement
calculator. Existing native, recorded and opening calculators remain identifiable
for historical reproducibility and will be aligned with the confirmed contract in
LD-01A. Recognition and opening-baseline handling can retain factual differences.

The resolved contract distinguishes:

- Supported calculation rule/version and frozen rates, period calendar, day
  boundary, partial-period convention, rounding quantum/mode and advance treatment.
- Original agreement and maturity/grace, remaining obligations, item identity,
  original principal and current verified item balances.
- Earliest supported effective date; for an opening, cutover recognition baseline,
  recognized unpaid interest, any fees, current-period principal basis and paid or
  advance-covered periods. These are separate amounts, not one interest total.
- Component priority and item allocation rules. Actual historical allocations
  and the rule for subsequent actions are separately evidenced.
- Whether the result is recorded debt, projected exposure or a collectable
  settlement quote, and which unposted recognition is required for the operation.
- Verified transaction coverage and any known missing activity, independently
  of source channel and future capture preference.
- Current monitoring selection/evidence, independently of original valuation.

Resolve only facts present in retained policy/disbursal/opening evidence, events,
allocations and schedules. Unsupported or contradictory versions fail explicitly;
they do not fall back to native semantics. Historical/source-local timestamps and
actors may be unknown. Date-only evidence must not acquire an invented exact time
or operator. Existing timestamp fields may encode a calculation convention;
documents must not portray that convention as a source fact.

Retain exact readers for `recorded-anniversary/1`, `recorded-anniversary/2` and
published opening wire evidence so accepted source amounts remain reproducible.
Align ongoing charge eligibility and rounding through a documented compatible
correction, with supported versioning where needed. Inventory affected loans and
dependent receipts/settlements before changing their financial results. Correct
accepted postings through existing compensation/reversal workflows; do not rewrite
snapshots/events or disguise a software correction as a new borrower agreement.
Broader reduced-principal or period-carry admission remains a separately supported
version. Genuine future agreement changes require an effective-dated amendment.

### 5. Expose common operations with factual prerequisites

Common repayment, release, renewal and recovery interfaces ask the same Loans
commands for eligibility. They evaluate authorization/lifecycle, known position,
supported calculation/allocation semantics, chronology/dependencies, coverage and
operation-specific custody/valuation requirements. They return actionable blockers
such as unsupported fee allocation, missing current-period basis or later release.
They do not reject solely because the loan was imported.

Existing validated event writers and allocation services are reused. The generic
opening posting prohibition is not simply removed: common commands must first
perform the same validation, catch-up and coupling enforced by dedicated writers.

Lakshmi's settled agreement remains: 12-month standing tenure; interest paid before
principal for total-only receipts; a mid-period principal reduction applies from
the next loan anniversary; actual principal per collateral item is always available;
staff specify the item principal split for completed multi-item paper payments.
Do not invent original allocations. Current direct payments keep their existing
highest-rate-first behavior. Whether staff are recording a completed receipt or
performing one now determines evidence needs, together with the agreed contract;
an origin label alone cannot choose the allocation.

Financial closure, physical return, retained custody and relabelling remain distinct.
An unknown paper handover stays unknown until evidenced. A renewal may be recorded
as independent supported loans when ancestry is unknown. Rokkad's Renew now uses
linked settlement and current approval for its successor. Preserve actual net cash,
deductions and carried principal; never invent separate gross physical cash flows.

Earlier transactions with later dependencies require supported correction/replay
and fresh review. Do not silently insert a receipt ahead of a renewal, auction or
release, mutate accepted events or discard dependent custody records.

### 6. Separate capture coverage and risk from original channel

Verified original history or an opening establishes a position at a date. It does
not prove that all subsequent off-system transactions were entered. Keep immutable
checked-through claims, fingerprints and send-time checks where needed.

An explicit reviewed transition to future Rokkad-only capture can change future
coverage expectations, without claiming nonexistent past history. Paper origin
must not permanently require renewed paper-book attestations after that transition.
Conversely, native origin cannot imply completeness if later activity occurred
off-system. Do not automatically make this transition during migration or infer
it from a recent digital receipt.

Current risk uses verified debt/exposure, remaining obligations, custody and
eligible date-appropriate current quotes/appraisals under the monitoring contract.
Original LTV may be unknown while current coverage is assessable. Current prices
must not overwrite the old agreement or be represented as old approval evidence.
Missing current valuation is unknown coverage, not zero collateral value.

### 7. Retain identity and versioned portability

Keep unique Workspace-local loan identity and counters, stable source namespace/id,
retained original numbers, signed review bindings and exact retry semantics. Two
different source books may legitimately use the same original number. Support
scoped aliases with explicit conflict review when a concrete case requires it;
do not automatically merge or renumber existing loans/issued documents.

Reuse `HistoricalLoanImport` and retained evidence for existing bindings. Do not
introduce an alias registry or new Workspace-owned tables before a supported
current use case requires them. New tables would require direct ownership, forced
RLS, registry coverage and isolation tests.

Local servicing setup can express an actual historical agreement/continuation
without claiming that the destination catalog existed then. Known source license
identity and unknown historical validity remain truthful. Inactive legacy-reference
licenses still prohibit new lending; a future guard exception for an evidenced
retrospective disbursal must be narrow and separately tested.

Existing history v1/v2 and opening contracts retain strict semantics. Broader
admission or post-cutover operations require new named profiles/readers and truthful
export support. Whole-Workspace native recovery remains exact-identity disaster
recovery, not a way to bypass import validation or move foreign Workspace IDs.

## Current-to-target mapping

| Current component | Disposition | Target responsibility |
|---|---|---|
| PawnLoan/events/items/snapshots/schedules/custody | Retain | Canonical operational identity and immutable facts. |
| Native drafts, approval, quote freshness, disbursal | Reuse | Prospective controls unchanged; same financial domain. |
| Recorded history, origination evidence, standing terms, shared collateral form | Reuse/refactor | Supported retrospective admission and source facts, distinct from approval. |
| Earlier-payout historical quote/policy gate | Eventually retire as general prerequisite | Preserve genuine approval validation; general delayed entry uses retrospective verification. |
| Complete-history importer | Retain old versions; extend adapters | Strict native-compatible reconstruction plus separately supported real source rules. |
| Opening importer/validation/restore | Reuse/extend named profiles | Verified checkpoint, no pre-cutover replay, explicit continuation and remaining maturity. |
| Repeated `recording_for`/opening tests in readers | Refactor | One read-only frozen-contract/position resolver; preserve actual calculators. |
| Repayment/release/renewal/auction commands | Reuse/refactor incrementally | Common purpose/eligibility, existing validated posting/coupling. |
| UI action gates keyed to origin | Eventually replace | Command-provided prerequisites; source labels remain. |
| Completeness inferred from origin forever | Refactor | Explicit checked coverage and future capture transition. |
| Archive/admission | Retain/extend only supported cases | Truthful historical-only evidence or fully reconciled operational admission. |
| Documents/export/native recovery | Retain/version extensions | Truthful provenance and bounded published wire contracts; recovery remains separate. |

## Relationship to existing ADRs

These are proposed effects on implementation, not changes to accepted statuses now.

| Existing ADR | Proposed effect |
|---|---|
| [Origination quote freshness](2026-09-12-origination-quote-freshness.md) | Retain for prospective decisions. |
| [Earlier payout and daily-price confirmation](2026-09-26-earlier-payout-and-daily-price-confirmation.md) | Partially supersede the historical digital-row gate as the general past-entry path; retain genuine approval validation and daily-price confirmation controls. |
| [Unified recording](2026-10-02-unified-loan-recording.md), [standing terms](2026-10-03-standing-terms-and-routine-paper-entry.md), [shared collateral](2026-10-03-shared-collateral-entry.md) | Extend common entry to common continuation/eligibility; retain actual item agreements, defaults and purpose-specific evidence. |
| [Opening position](2026-09-12-loans-opening-position-contract.md), [authorized commit](2026-09-12-authorized-opening-commit.md) | Amend operational supported scope with new reviewed profiles; retain one origin and cutover coverage. |
| [Opening continuation](2026-09-12-opening-collection-continuation.md), [full release](2026-09-12-opening-full-release-servicing.md), [partial payments](2026-09-23-opening-partial-payments.md) | Retain existing versions; move eligibility/dispatch into common commands and separately version wider continuation. |
| [Canonical history](2026-09-12-loans-canonical-history-import.md), [complete-history MVP](2026-09-12-loans-complete-history-mvp.md) | Amend broader admission scope, while preserving the old native-compatible wire and reconstruction rules. |
| [Exact history v2](2026-09-30-exact-interest-history-v2.md), [frozen opening wire](2026-09-13-frozen-opening-wire-contract.md) | Retain exact published contracts; do not change their meaning in place. |
| [Transaction completeness](2026-10-03-loan-transaction-completeness.md) | Amend origin-based ongoing capture assumption; retain coverage and send-time protections. |
| [Recorded auction recovery](2026-10-03-recorded-loan-auction-recovery.md) | Extend to eligible supported openings after settlement/coupled reversal is implemented. |
| [Contract corrections](2026-10-03-recorded-contract-corrections.md), [receipt corrections](2026-10-02-recorded-receipt-corrections.md), [settlement corrections](2026-10-02-recorded-settlement-corrections.md) | Retain compensation/dependency evidence; extend supported semantics deliberately through common operations. |
| [Independent paper loans/renewal](2026-10-03-independent-paper-loans-and-renewal.md) | Retain unknown ancestry and optional linkage; extend source eligibility without inventing cash or custody. |
| [Historical closed archive](2026-09-13-historical-closed-loan-archive.md), [archive admission](2026-10-03-archive-admission.md) | Retain historical-only fallback; broaden admission only for reconciled supported cases. |
| [Native recovery](2026-10-03-ordinary-loan-native-recovery.md) | Retain exact-identity purpose; update supported inventory/fingerprint only as schemas evolve. |

## Consequences and rejected alternatives

The common interface can expand incrementally without rewriting existing loans.
Unknown facts and unsupported calculations remain visible blockers. Entry channel
stops deciding every later operation, while genuine financial differences remain.

Rejected: removing quote/LTV controls globally; copying today's approval into past
transactions; generic postings around opening guards; replaying full old history
on top of an opening; imposing native allocation on verified foreign receipts;
duplicating servicing engines; broad nullable schema changes; overwriting accepted
amounts while aligning the shared contract; silently inserting transactions behind
dependencies.

The first change is deliberately read-only. Schema work and new eligibility come
later, with characterization, versioned evidence, restricted-role tests and a
compatible rollback plan. Material business decisions are listed in the plan;
none requires guessing missing historical facts to begin the first slice.
