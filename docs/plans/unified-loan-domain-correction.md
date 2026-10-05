---
status: active
owner: project
updated: 2026-10-05
tags: [plan, loans, admission, continuation, compatibility]
related: [../architecture/ordinary-loan-domain-review-20261005.md, ../adr/2026-10-05-unified-loan-admission-and-continuation.md]
---

# Unified loan admission and servicing correction

## Scope and checkpoint

The initial 5 October request was **analysis and documentation only** and that
review is complete. The owner subsequently selected the direction and requested a
checkpoint/start on LD-01. Checkpoint `89f7321e` records completed shared-entry work
and the review on `work/loan-servicing-contract-ld01`; unrelated billing/platform/
storage work stays uncommitted. LD-01, LD-01A, LD-02, LD-03, LD-04 and LD-05 are complete
locally; LD-06 and later slices are pending.
The owner's subsequent shared-interest clarification inserts LD-01A before LD-02.
Production and the running candidates are unchanged.

LD-01 verification passes **239 affected tests in 94.193s**, including 16 new
contract tests and restricted-role isolation. See the
[implementation and evidence](../implementation/loan-servicing-contract-ld01.md).

Baseline: current dirty checkout on `release/2026-09-24-rc1`, HEAD
`4b93f67fe9412f6f401db97707e78d7ffaca9566`, including uncommitted UR-15--23 and
unrelated work. See the [evidence-backed review](../architecture/ordinary-loan-domain-review-20261005.md)
and [proposed ADR](../adr/2026-10-05-unified-loan-admission-and-continuation.md).
Prior UR-23 candidate results remain prior delivery evidence, not validation of
this proposal. The September portability audit is not the current capability list.

The objective is one operational PawnLoan and common operations with factual
prerequisites. Preserve source history, admission boundaries, authorization, RLS,
immutable evidence and chronology. Correct implementation differences against the
confirmed agreement without overwriting accepted amounts. No model rewrite is
needed.

**Confirmed business rule (5 October):** for a 5 April loan whose first month is
paid upfront, no second-month charge is added on 5 May; it starts on 6 May. Direct,
backdated paper and imported entry share that boundary. Rounding follows the
standing economic policy captured for the agreement. Today's setup cannot silently
change an existing contract. The old LD-01 profile differences below describe the
checkpoint implementation and are superseded as the target by this clarification.

## Delivery order

| Slice | Status | Coherent result | Schema expectation |
|---|---|---|---|
| LD-01 | Complete locally; 239 tests pass | Common read-only servicing contract and position for repayment preview/reminder balance | None |
| LD-01A | Complete locally; rollout review pending | Shared inclusive anniversary boundary and captured-policy rounding, with explicit financial correction compatibility | Existing evidence plus corrected policy/profile versions; portability migration 0018 |
| LD-02 | Complete locally; rollout pending | Common purpose/eligibility for supported repayment and full release; retain validated writers | None |
| LD-03 | Complete locally; rollout pending | General completed-payout admission, including retained unpaid draft identity, without historical digital-row prerequisites | Existing recorded evidence; narrow forward-only legacy guard migration 0058 |
| LD-04 | Complete locally; source/staff rollout acceptance pending | Explicit reduced-principal/current-period/advance checkpoint and supported continuation | Review/4, opening export/3; additive mixed-origin guard 0059 |
| LD-05 | Complete locally; source preparation/staff acceptance pending | Source-faithful supported history allocation and numbering/setup compatibility | Recorded history/4; immutable source JSON aliases, batch guard migration 0019; no new table |
| LD-06 | Pending; after relevant profiles in LD-02/04/05 | Remaining operations, correction dependencies, coverage transition, risk/schedule parity | Additive capture-transition evidence may require a migration |
| LD-07 | Pending; compatibility substeps accompany each writer slice | Portable documents/export/restore for new supported semantics | Profile/reader versions and recovery fingerprint as needed |
| LD-08 | Pending | Staff acceptance, staging and controlled production rollout | Owner migration only for actual additive changes |

Each slice is reviewable and useful independently. LD-07's compatibility checks
are prerequisites for activating new writer profiles in earlier slices, not work
deferred until after incompatible data has been written. No bulk conversion of
accepted events is scheduled. Existing unsupported cases remain explicit until
the corresponding slice is implemented and verified.

## LD-01: exact recommended first implementation

This completed read-only slice deliberately characterized the old calculators.
Its boundary/rounding parity criteria are historical checkpoint criteria, not
acceptance of the newly confirmed common business contract. LD-01A addresses that.

### Boundary

Introduce a small read-only `selectors/servicing_contract.py` and a Loans-owned
servicing-position function using existing calculator outputs. The file is now
implemented with plain immutable dataclasses and ordinary functions. Avoid a
plugin registry, generic policy engine,
new model, new table, middleware or persistent derived balance cache.

Resolve supported origin, frozen calculation/version, original/cutover dates,
item bases, schedule, recognition/advance coverage, allocation semantics and
coverage metadata from existing evidence. Unsupported versions, contradictory
origins and missing required facts return/raise explicit domain blockers. Channel
is retained as provenance, independently of these facts.

Start by replacing only duplicated **read-side selection**, preserving current
eligibility and all writer paths. Readiness/coverage metadata is exposed, but this
slice does not newly block existing provisional loans or grant new operations.

### Exact existing paths to replace and reuse

| Existing path/function | LD-01 action |
|---|---|
| `services/pawn_repayment.preview_pawn_loan_repayment` | Replace repeated origin/profile selection with common position resolution; keep current-date, amount, priority and allocation validation. |
| `services/notice_delivery_readiness.notice_balance` | Replace its recorded/opening/native dispatch with the same position resolver; preserve ACTIVE/closed distinctions, unsupported recorded-profile refusal and send-time review guards. |
| `web/pawn_financial_actions.pawn_loan_repay` | Reuse the resolved preview/balance context; do not change `allow_paper` eligibility yet or move posting into the view. |
| `selectors/balances.get_pawn_loan_balance` and `calculate_pawn_loan_balance` | Reuse canonical recorded-debt fold, cutover unavailability and mixed-origin rejection. |
| `services/recorded_collections.recording_for`, `collection_state`, `collection_balance` | Reuse exact profile 1/2 detection and anniversary calculation inside one resolver; no rounding/calendar change. |
| `services/opening_servicing.opening_payment_balance`, `opening_continuation.preview_opening_collection`, `opening_payment_evidence` | Reuse supported opening calculation and baseline/catch-up; do not enable other checkpoint profiles. |
| `services/pawn_tranches.get_pawn_principal_tranche_balances`, existing schedules and `selectors/transaction_completeness` | Reuse item bases and coverage without inventing fields or changing current completeness policy. |
| `_record_pawn_loan_repayment_at`, `_record_opening_servicing_event`, release/renewal/reversal writers | Leave posting/authorization/coupled reversal behavior intact in this first slice. |

The resolver must not call repayment preview recursively, invoke a writer,
recognize interest, record a review, issue documents or call notifications.
Dependency direction is selectors/fact resolution -> existing calculation helpers
-> consumer preview; restructure tiny helpers if necessary to avoid import cycles.
Do not combine read-only dispatch with a new admission API.

### Acceptance criteria

1. Native repayment quotes remain based on the current recorded balance. Do not
   make unposted projected interest collectable merely to make profiles look equal.
   Recorded/opening quotes retain their exact operation-specific recognition delta.
2. Profile 1 and itemized profile 2 keep their different rounding. The existing
   opening inclusive calendar still changes after its anniversary, while paper
   recognition changes on its anniversary. Tests preserve the old behavior; the
   shared interface does not erase those differences.
3. An opening's as-of date before cutover is unavailable; querying at/after cutover
   does not re-add its recognized baseline. Mixed origins, unsupported recorded
   versions and missing continuation facts never silently fall back to native.
4. Both read consumers produce exactly equal Decimal amounts and the same
   supported/blocked outcomes as their characterized old implementations for
   supported profiles, ACTIVE/CLOSED and as-of cases. The one intentional error
   clarification is fail-closed handling of unknown/contradictory contracts:
   reminder balance already rejects unsupported recorded profiles, whereas the
   repayment preview's failed `recording_for` detection can reach the native fold.
   Test an explicit unsupported-contract error instead of preserving that fallback.
   This does not grant new writer eligibility or change a supported loan's amounts.
   Common facts are reused rather than querying origin for each amount.
5. Equivalent evidenced contracts from different channels have equal operation
   results. Test admission-independent fixtures initially if today's admission
   routes cannot express that same contract; do not mislabel synthetic parity as
   a complete import end-to-end pass. See the audit's 8,200/164/1,000 worked fixture.
6. Read calls leave events, policy/disbursal/approval snapshots, schedule rows,
   allocations, source bindings and issued-file bytes unchanged. Foreign Workspace
   resolution is unavailable under the restricted runtime role; no owner lookup.
7. Existing authorization, signed reviews, retries, allocation validation and all
   native origination quote/LTV checks are unchanged. No new table or migration.
8. Preserve old unitemized native loans and earlier snapshot versions; unsupported
   historical versions fail explicitly. Bound/query-count checks prevent repeated
   per-field/per-item origin queries; no request-global cross-Workspace cache.

### Verification and rollback

Add meaningful characterization tests before routing consumers: native rules
with advance/fee variations, recorded profiles 1/2, supported opening profile,
cutover and exact anniversary dates, paise/rupee rounding ties, partial repayment,
unpaid/advance baseline, reversal/as-of results and unknown profile errors. Existing
validation-only opening review v1 stays unsupported for operational commit.

Run targeted repayment/recorded collection/opening/notice tests, then affected
cross-Workspace and read-model regressions under `django_project.settings.test`.
Use restricted-role adversarial checks for RLS. No database-backed tests were
executed in this documentation task. Characterize old output first; a discovered
writer/display mismatch becomes a separate documented fix, not a silent LD-01
behavior change.

Rollback restores the old read dispatch because the slice creates no persistent
financial changes. Deploy only after parity passes. No automatic production
conversion or new feature-flag infrastructure is needed. This first slice does
not depend on resolving new external calculation rules or reduced cutover history.

## LD-01A: shared monthly boundary and policy rounding

### Scope and implementation order

1. Add a small shared original-date anniversary helper using the existing inclusive
   opening calendar as the reference. For the confirmed upfront monthly agreement,
   month one is covered through the first anniversary; the next charge starts the
   following day. Preserve the original anchor across short months; never chain
   clamped dates into a drifting anniversary. Retain actual partial-month product
   conventions where applicable, separately from entry channel.
2. Resolve quantum and rounding aggregation from the agreement's saved economic
   policy. Existing policy represents quantum and aggregation; arithmetic uses
   HALF_UP. Check actual supported fields before proposing any additional setting.
   Replace paper/opening channel-hardcoded rounding for the corrected contract.
   For an imported loan without a policy mapping, review its evidenced agreement
   and freeze a supported mapping without claiming that local setup existed then.
3. Integrate the helper and saved-policy rounding with native period/advance
   handling, paper collection and opening continuation. Align schedules, exposure,
   notices and repayment/full-release/renewal/auction settlement where they depend
   on those calculations. Distinguish charge eligibility from posting recognition.
   A one-day shift in a preview alone cannot establish consistent servicing.
4. Verify period principal bases against the settled next-anniversary reduction
   rule, including payments on 5 May and 6 May. Do not accidentally defer a valid
   reduction by another month or change actual staff-specified item allocations.
5. Inventory affected loan evidence before activation. Separate unposted forecasts
   from accepted accruals, receipts, concessions and dependent settlements. Retain
   exact old wire readers and reproduce accepted amounts. Use supported immutable
   correction/reversal and dependency review for financial errors; never edit
   earlier events, silently reallocate a paper receipt or reissue saved documents.
   Document compatible export/restore and rollback for corrected rule evidence.

The historical checkpoint should remain reproducible, but observed early charging
must not become a permanent entry-channel contract. A software correction does
not imply a new agreement with the customer. Preserve opening recognized/unpaid
baselines and unavailable pre-cutover history; do not add an extra financial origin
or reconstruct pre-cutover activity to implement this change.

### Acceptance and release evidence

- Equivalent 10,000 principal / 2% monthly agreements, with month one paid upfront,
  show no additional charge through 5 May and 200 starting 6 May in all three
  channels. Repeat later anniversaries, advance-month counts and closure dates.
- Original 31 January anchors clamp February individually and return to 31 March;
  test leap years and day-after boundaries without date drift.
- Captured economic policy produces equal rounded charges for equivalent item
  facts across channels. Test paise/whole-rupee ties, aggregation and cumulative
  recognition; later standing-policy edits leave saved terms unchanged.
- Mid-month and boundary-day principal reductions, staff item splits, reversals,
  full settlement and closure/reopening preserve principal and interest conservation.
- Opening cutover recognition is subtracted exactly once; unsupported mappings
  remain explicit. No pre-cutover replay, fabricated history or duplicate origin.
- Native advance coverage, partial-period calculation, schedule/risk/reminder debt
  and settlement quotes agree with the shared eligible charge dates. Posted and
  projected debt remain distinguishable.
- Old evidence/export/restore stays readable; corrected evidence round-trips.
  Restricted-role isolation, review fingerprints, authorization, retries and
  correction dependencies retain their existing protections.

Run targeted calendar/policy tests and affected collection, accrual, schedule,
settlement, opening, correction, risk and notice regressions under test settings.
Characterization tests intentionally asserting the old early boundary must be
identified as old-version tests or updated for the correction, not presented as
proof that the new contract already works. The owner subsequently authorized LD-01A;
its shared calendar, captured-policy arithmetic, native atomic recognition, reviewed
paper correction, inventory and versioned portability are now implemented locally.
The final affected-module verification passes 159 tests (216.110s), after the
1,753-test broad run identified stale anniversary fixtures and five independently
confirmed checkpoint failures/errors. The broad run is not claimed wholly green.
Verification details and rollout limits are tracked in
[the implementation note](../implementation/loan-interest-contract-ld01a.md).
Existing cohorts are not converted and deployment remains separate.

## LD-02: supported common repayment and full release

Implemented locally on 5 October; **256 final targeted tests pass in 251.059s**.
`services/servicing_eligibility.py` supplies
read-only factual blockers reused under locks by the existing validated writers.
Native shared monthly bullet contracts with disbursal snapshots accept reviewed
completed paper receipts; existing recorded and opening loans retain current
digital collection. Full settlement removes valuation prerequisites and recognizes
native completed shared-monthly charges atomically. Completed paper closure and
later evidenced handover work on supported ordinary loans regardless of origin.
Legacy recorded event-fold current repayments remain compatible without inventing
an anniversary profile. Opening multi-item completed principal allocations remain
explicitly unsupported by their existing reviewed profile, before posting.

New native paper activity requires explicit book verification; known debt can still
be serviced without a fabricated complete-book claim. Existing immutable wire
profiles are unchanged: bounded history export blocks paper receipts/closures it
cannot preserve, while Loans recovery retains exact source identity. Wider
correction, native re-recognition after coupled reversal, coverage transition and
portable profile expansion remain later work. See the
[implementation and verification](../implementation/loan-servicing-eligibility-ld02.md).

Build shared prerequisite results on LD-01 and LD-01A: operation purpose, effective date,
known position, supported allocation, coverage, lifecycle, custody and later
dependencies. Reuse `pawn_repayment`, `paper_repayments`, `opening_servicing`,
`pawn_release`, `paper_closures` and `recorded_closures`; views/templates display
their results. Keep dedicated internal validated writers until their checks can
be safely shared. Do not open generic `record_loan_event` for arbitrary openings.

Permit a completed paper receipt on a native-origin loan when its frozen semantics
and actual evidence can be represented. Permit a current digital collection on a
paper/opening loan through ordinary repayment. Unsupported fees or item allocation
receive precise blockers. In particular, merely passing item splits into the form
does not overcome `opening_payment_evidence`'s old replay validator: either retain
that profile limit or add an explicitly supported new allocation profile.

Preserve fees/interest/principal priority where agreed. For completed multi-item
paper receipts, require actual item principal splits. Keep direct current
highest-rate-first behavior. Full settlement can use unknown original valuation;
partial retained-collateral release still needs the relevant safety evidence.
Unknown physical handover uses supported paper closure, not fabricated return.

Tests: equal-contract multi-channel collect/release, conservation, zero/advance
period handling, full/no-extra-cash closure, actual item splits, unknown handover,
cross-Workspace/unauthorized/signed-review failures, same-key retries, stale preview,
later-event blockers, paired reversal and race/lock behavior. Preserve all existing
posting row shapes unless a versioned evidence extension is essential.

Rollback: old writers remain usable for old profiles. Disable newly admitted action
purposes rather than undo accepted payments. A binary unable to read a newly written
profile is not a safe rollback; supply a compatible reader first.

## LD-03: one completed-payout admission purpose

Implemented locally after the owner's authorization. An unpaid DRAFT/APPROVED loan
uses the shared editor and recorded-history writer while retaining its saved
identity, collateral, genuine approvals, photos and issued copies. Posted or
reversed origins require correction. Migration 0058 narrowly permits legacy
completed-payout evidence with a validated matching snapshot required before commit;
new-lending authority is unchanged. See the
[implementation and verification record](../implementation/completed-payout-admission-ld03.md).
Application/candidate/production migrations and rollout remain pending. LD-04 is next.

Reuse the shared New loan editor, standing terms, per-item agreed amounts,
`recorded_history`, `recorded_origination_evidence`, recorded numbering and signed
preview/atomic commit. Extend only where the older native draft/earlier-payout
route cannot admit supported actual facts without historical destination rows.

`historical_origination`, `web/valuation_review` and `pawn_disbursal` keep legitimate
retained-approval validation. The general record-completed path stops requiring
preexisting Rates/economic-policy rows and does not fake an approval. Preserve the
draft identity and frozen genuine evidence. A new draft created for the same
source is rejected under locked source/idempotency checks.

Actual terms may differ from standing defaults; record supported exceptions with
source basis. Monitoring selection is current and independent. Do not expand the
paper calculator beyond its named supported contract in this slice.

Review migration 0015's legacy-reference origination guard: if retrospective
admission genuinely needs that reference, make a narrow exception tied to valid
RECORDED evidence and original scope. Current DISBURSAL/new-lending prohibition
remains. No global license, RLS or authorization exemption.

Tests: today prospective remains quote/LTV guarded; yesterday/old paper without
destination quotes/policies; existing approved native evidence; no fabricated
actors/times/LTV; missing current history remains provisional with exact blockers;
source duplicate/counter races and authorization. Migration only if a changed
guard is actually needed; adversarial restricted-role DML must exercise it.

Rollback: stop new admission adapter; accepted RECORDED contracts remain ordinary
loans readable by the old compatible profile. Do not erase them or restore an
old database backup over later legitimate business transactions.

## LD-04: reviewed opening with reduced principal and period coverage

Local implementation adds review/4, explicit remaining item principal/current
period bases, separate cumulative/current recognized/unpaid amounts, actual
current/future advance coverage and original boundary/maturity. The owner supplied
the 1 January 2026 / 10,000 principal / 1,000 principal paid 20 January example:
the next charge on 2 February uses 9,000. Test rate/advance assumptions are labeled
as illustrative; a full actual source checkpoint is still required for rollout.

The existing writer, common read/servicing path, detail explanation, export/3 and
restore/recovery now preserve this evidence without earlier financial replay.
Migration 0059 protects one origin in either insertion order. Earlier profiles
are not converted or reinterpreted; future advance over-coverage needs explicit
resolution. No application/candidate/production migration is included. Final
verification evidence is in STATUS and the
[LD-04 implementation record](../implementation/reduced-principal-opening-ld04.md).
LD-05 is next.

Use verified source examples to add one named continuation version at a time.
Reuse `opening_validation`, `_document/_write`, `opening_obligations`, opening
baseline/item lines, source evidence and restore adapters. Preserve existing v2
unchanged-principal/whole-rupee behavior; the broader v1 descriptor's existence is
not proof of a working writer.

The review must explicitly support item remaining principal, current-period
principal basis, original versus recognized unpaid interest, advance/paid coverage,
next charge boundary, remaining maturity/grace and exact rounding/allocation.
Unknown charge-affecting fields block that profile; principal plus one interest
total is not enough to infer a checkpoint. Do not invent pre-cutover payments.

Update one validated writer/read/export/restore path together. Prefer versioned
existing JSON evidence over new tables. If database checks must recognize the new
version, use an additive ordinary owner migration and keep old rules intact.

Tests: reduced principal before/on boundary, unpaid plus recognized baseline,
advance covering current/future periods, item rates/splits, zero additional charge
at cutover, next period on correct base, no maturity reset, as-of/reversal, source
restore round trip, mixed-origin raw DML and retry conservation.

Rollback: keep new-profile readers and origin guard support; stop new-profile
admission until fixed. Do not revert checkpoints to the old unchanged-principal
rule or reinterpret their accepted events.

## LD-05: supported source history, setup and aliases

**Complete locally (5 October).** New history/4 reuses recorded origination,
receipt and full-release writers for supported shared flexible-payment agreements.
Actual source item allocations and monetary checkpoints reconcile without old
Rokkad approval/valuation catalog evidence. Compatible retired/later-created
servicing products, explicit inactive legacy references, source-book aliases,
exact Party identity and live number reservations are supported. Full export/restore
accompanies this writer, including later paper/current receipts and closure;
unknown source actors/time/physical cash remain unknown. Verified book coverage
is required; corrections and wider operation/custody graphs remain explicit
blockers. Native v1/v2/v3 contracts and ordinary issuance are unchanged. See the
[delivery record](../implementation/recorded-source-history-ld05.md) and
[contract decision](../adr/2026-10-05-recorded-source-history-v4.md).

Original scope and acceptance criteria follow.

Keep strict `history_contract`, `history_accrual`, `history_import` v1/v2 behavior.
Add a separate version for verified source rules that are needed now. Validate
actual event/item conservation, chronology and supported future continuation;
do not recompute a historical receipt using native highest-rate-first and overwrite
its supplied allocation. If replay semantics cannot be supported, retain the full
source history as evidence and offer reconciled opening admission instead.

Review `history_setup`'s historical destination product availability requirements.
Select a compatible local servicing contract without attesting a past local policy.
Keep current issuance readiness separate from inactive legacy identity. No catalog
row created today may masquerade as contemporaneous original approval evidence.

For genuine duplicate original numbers from different books/licenses, retain a
unique local number and scoped searchable source aliases. Reuse immutable source
identity fields first; add a model only for a proven representation gap, with RLS
and ownership tests. Old manual numbers, counters and issued documents are frozen.

Tests: differing valid item allocations, unsupported versus inconsistent evidence,
same-number distinct books, same-source changed-payload retry rejection, namespace
cross-schema compatibility, source Party binding, local prefix reservations,
retired compatible products and unknown original valuation. Every new history
writer must have truthful export/restore support before activation.

## LD-06: remaining operations, coverage and risk

Extend common prerequisites and resolved position into renewal, auction, correction,
obligations/delinquency/exposure and action presentation. Reuse `pawn_renewals`,
`recorded_renewal_actions`, `pawn_auctions`, `pawn_reversal`, recorded correction
services and custody safeguards. Support each operation only after its continuation,
settlement/catch-up and reversal behavior is characterized. Opening auction needs
this work; removing its general financial-action guard alone is not sufficient.

Linked Renew now still approves new lending against current evidence. Unknown
paper ancestry remains optional independent entry. Opening renewal preview versus
writer catch-up is an unverified parity concern to characterize before refactoring.

Backdated insertion with later activity goes through a shared dependency preview
and supported compensation/replay. Unsupported dependency graphs remain blocked;
old accepted events/PDFs are untouched. Keep final closure/renewal/auction and
physical custody evidence coupled to its financial settlement.

Separate checked-through history from future capture mode. Add the smallest
immutable reviewed transition to Rokkad-only capture if the owner selects it;
do not infer transition from origin or quietly attest missing past transactions.
Read models, borrower statements and reminder dispatch retain amount/coverage
fingerprints. Dashboard known totals continue to disclose provisional/unavailable
cohorts rather than inventing their balances.

Risk parity compares current dated evidence and identical contract/payoff bases,
not original approval labels. Unknown original LTV is distinct from unknown current
value. Preserve monitoring selection/freshness, custody and statutory auction rules.

Tests: native/paper/opening operation matrix, exact linked/net-cash renewal,
statutory auction/paired reverse, correction dependencies and locks, no original
formula change, unchanged original maturity with partial payments, coverage rollover
and explicit capture transition, current risk freshness/unknowns, send-time stale
amount/review rejection and cross-Workspace races. Additive capture evidence, if
required, needs direct Workspace ownership and RLS coverage.

## LD-07: documents and portable compatibility

Keep source labels, original date precision, true recording actors and prior issued
bytes. Audit imported approval snapshot `approved_at` labels: its row is created
now, while source approval time is in historical evidence. A date convention is
not an exact paper timestamp. Do not issue retrospective native approval attestations.

Keep current strict history/opening exporters and wire versions readable. Introduce
truthful versions for newly supported recorded history, opening paper closure,
later operations or allocation semantics. Bounds remain explicit. Never silently
omit unsupported accepted events to produce an apparently complete export.

Update native recovery's supported schema/guard fingerprint as actual migrations
change. Test exact same-identity recovery and source-local cross-Workspace portable
remapping separately. Recovery is not a replacement for financial admission.

Tests: golden old-wire read/restore and exact PDF bytes; new profile full round trip,
source identity/idempotency, actor remapping, all post-cutover actions, no pre-cutover
fake replay, unsupported-version errors and independent closed archive retention.
Reader support must precede writer activation and old consumers must reject new
versions clearly. A backward reader-compatible deployment remains available.

## LD-08: acceptance and production protections

Inventory actual profile cohorts through authorized read-only selectors before
rollout; do not derive them solely from entry labels. Preserve dirty work by
isolating the approved implementation and reviewing its exact source scope.

Use representative staff paper documents for today, yesterday, old active, closed,
renewed independent loans, multiple items, advance interest, reduced cutover and
number collisions. Prove balances, remaining schedules, allocation, release and
risk parity for equal contracts through real admission routes, not only synthetic
fixtures. Explain unsupported cases accurately in the interface.

Stage with restricted runtime role, real migration settings and physical
database/media backup. Run affected lifecycle/posting/RLS suites, migration guard
checks, exporter/restore tests and staff acceptance. Only use owner credentials
for ordinary migrations through `django_project.settings.migration`; web/workers
stay restricted. No manual journals or retrospective event mutation.

Before any approved production rollout, provide the exact additive migrations,
profile compatibility matrix, recovery verification, remaining blockers and
reader-compatible rollback artifact. No production rollout is authorized by this
review task. A source rollback cannot discard legitimate payments recorded since
deployment; retain compatible readers and suspend an unsupported new workflow
while repairing it through approved correction semantics.

## Required scenario acceptance matrix

| Scenario | Required result | Primary slices |
|---|---|---|
| Today new advance | Current quotes/LTV/approval unchanged | LD-01/03/08 regression |
| Yesterday payout | Actual date and supported completed facts, no invented approval | LD-03 |
| Six-month paper/no old local policies or quotes | Original terms or reconciled opening; original LTV unknown allowed | LD-03/04 |
| Known original amount, unknown current balance | Retained facts/provisional disclosure; precise debt-sensitive blocker | LD-02/03/06 |
| Full source history/different allocation | Preserve verified actual lines under named support, or offer opening without double origin | LD-05 |
| Partial history/reconciled opening | Correct cutover balance and remaining maturity, earlier operational history unavailable | LD-01/04 |
| Reduced cutover/unpaid/advance | Exact checkpoint, no pre-cutover replay or guessed basis | LD-04 |
| Backdated action with later activity | Dependency preview and supported immutable correction; otherwise clear blocker | LD-02/06 |
| Closed archive/incomplete settlement | Remains historical-only, no fabricated zero/cash/handover | LD-03/05/07 |
| Numbers/retries | Unique local identity, truthful scoped aliases, exact locked idempotency | LD-03/05 |
| Cross-Workspace/unauthorized | Denied before preview/write/idempotent return; restricted-role RLS | Every slice |
| Equivalent evidenced contracts | Equal balance, remaining schedule, repayment, release and risk at supported dates; provenance/audit/lifetime totals can differ | LD-01/02/04/06/08 |

## Material business decisions

LD-01 is complete. The owner has settled the common day-after-anniversary boundary
and captured-economic-policy rounding for direct, paper and imported entry.
Do not re-ask those choices, Lakshmi tenure, next-anniversary principal treatment,
actual item principal or completed-paper item split rules. LD-01A implements the
clarified agreement before common writer eligibility expands in LD-02.

The following decisions affect later extensions and require actual evidence:

1. **Exceptional external agreements:** which verified source agreements actually
   differ from the confirmed shared contract? Entry channel alone is not such an
   exception. Obtain source examples of any genuinely different period boundary,
   rounding, advance coverage, fee priority and actual allocation. Prefer one
   named supported rule over generic configurability.
2. **Reduced-principal checkpoints:** for affected legacy loans, what current-period
   principal base and paid/recognized/advance coverage can be evidenced? Do not
   infer them from a principal/interest balance alone. A review must distinguish
   unknown facts from genuinely absent charges.
3. **Future capture transition:** will each admitted book continue paper-first,
   switch entirely to Rokkad, or remain mixed? Who attests the verified transition
   date/position? Recommended default is explicit reviewed transition, never an
   automatic origin-based assumption.
4. **Distinct books with duplicate numbers:** which source license/book identifier
   is stable for staff search and printed references? Recommended behavior is a
   unique local number plus the original scoped alias; never automatic merging.
5. **Existing provisional loans:** how will staff establish their missing position
   before definitive statements/settlement? Recommended behavior is a review of
   actual history or supported reconciliation, not deleting their records or
   treating an unconfirmed balance as verified.

These decisions do not justify inventing source values or blocking read-only
centralization. LD-01 is the selected first implementation; broader writer/admission
changes remain separate slices.
