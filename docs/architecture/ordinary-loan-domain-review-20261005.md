---
status: reviewed-source
owner: project
updated: 2026-10-05
tags: [loans, architecture, admission, continuation, audit]
related: [../adr/2026-10-05-unified-loan-admission-and-continuation.md, ../plans/unified-loan-domain-correction.md]
---

# Review of ordinary loan admission and continuation

## Diagnosis

Rokkad already has one operational `PawnLoan`, shared financial events, allocation
lines, schedules, custody evidence and active/closed lists. The correction is to
finish separating **financial admission**, **calculation semantics**, **source
coverage** and **operation purpose**. It does not require another loan model or
servicing engine. Removing all origin branches would destroy information needed
to prevent double charging opening balances and to reproduce existing contracts.

The current paper path already solves much of the historical-price problem.
The remaining friction includes the older earlier-payout workflow, narrow import
contracts, duplicated servicing decisions, and origin-based eligibility assumptions.
One entry screen does not establish one servicing contract.

This is a source review and proposal, not an implementation or deployment.

## Checkout and evidence boundary

- Reviewed on 5 October 2026: branch `release/2026-09-24-rc1`, HEAD
  `4b93f67fe9412f6f401db97707e78d7ffaca9566`.
- The local `rls-mvp` reference is `a9f793fc40fbc6d3f295acdc7cd16fdbe579e5bd`
  and is HEAD's merge base. There are 514 changed relevant paths between that
  reference and HEAD, including the paper admission/correction work committed
  in `22db74f8`. The exact release commit used in the user's earlier review was
  not supplied; current branch names are not proof of that earlier snapshot.
- The working tree additionally contains UR-15--23: itemized paper agreements,
  version 2 anniversary calculations, standing terms/default purpose and retained
  entry form state. These include untracked migrations 0056/0057 and services.
  Unrelated billing, platform and storage work is also pending.
- Preserved fingerprints cover 94 already modified/untracked application files.
  No checkout, reset, stash, commit, migration, data mutation or application edit
  is part of this review. Only the new review/ADR/plan and status/context are edited.
- Reviewed source fingerprint: 796 Python/template files in Loans,
  data_portability and `templates/loans`; aggregate SHA256
  `b3b5ad70ddf33972075f1664c0157857d53ca0b95f32c22d525ebb83a57a625b`.
  Method: sorted UTF-8 path, NUL, raw SHA256 of file bytes.
- Private read-only evidence is `.tmp/loan-domain-review-20261005`: checkout,
  source/protected-file hashes and branch inventory. Prior test counts in Status
  are prior delivery evidence, not test execution for this review. A small pure
  legacy-calendar calculation was executed; no database-backed tests or browser
  acceptance were rerun. Live production data/configuration was not inspected.

Completion checks confirmed all 94 protected application files and all 796
reviewed source files unchanged. All 762 local Markdown links across the new
documents and Status/Agent Memory resolve, source line anchors are within bounds,
and documentation whitespace checks pass. These checks verify preservation and
documentation integrity, not financial behavior.

Required reading followed Agent Memory, Status, relevant ADRs, control-plane
contracts, domain read models and the constitution. The September
[portability audit](loans-portability-audit.md) remains a dated audit: its claims
of missing archive/admission capabilities cannot describe this working tree.

## Verification of the six earlier findings

| Earlier finding | Current result and evidence |
|---|---|
| Ordinary metal-valued origination uses current-day dates and same-day quotes | **Verified, still applies to new decisions.** `selectors/origination_rates.py`: `require_current_origination_date`, `require_fresh_quotes`, `assert_approved_quotes_current`; `pawn_lifecycle.approve_pawn_loan`, `pawn_disbursal.disburse_pawn_loan` recheck frozen quotes. Appraisal-only bypasses quotes, not economics, LTV, authorization or custody checks. |
| Earlier payout requires previously recorded historical policies/quotes | **Verified for that particular path.** `historical_origination.historical_policies` uses `recorded_before=day_end(actual_date)` or retained approval identities; `historical_quotes` requires same-date positive Rates rows recorded before that cutoff and not corrected/withdrawn. `pawn_disbursal` requires the special approval. This is not the only current retrospective path. |
| Complete-history import reconstructs detailed evidence and matches Rokkad | **Verified, with later v2 support.** `history_import.import_complete_history` calculates disbursal/LTV, exact accruals, fee/interest/principal allocation and highest-rate item allocations, then compares supplied results. `history_accrual` and `history_contract` implement v1/v2, not arbitrary source rules. Source valuation values are supplied in the document; this importer does not require old destination Rates/economic-policy rows. |
| Opening imports are PawnLoan plus MIGRATION_OPENING with separate servicing restrictions | **Verified, but earlier 'no servicing' conclusions are stale.** Current code supports repayment, full release, coupled reversal and current renewal. Native periodic accrual/capitalization, opening auctions and some portable exports/corrections remain restricted. |
| Approval, retrospective verification and future servicing are mixed | **Partially corrected, still fragmented.** RECORDED disbursal explicitly has no approval; earlier-payout still creates an approval. Profiles are inferred repeatedly from `MIGRATION_OPENING`, policy basis and `recording_for` throughout readers/writers/UI. Operation-purpose gates still depend on the original entry channel. |
| Some audit documents predate later changes | **Verified.** The September audit and earlier-payout ADR, opening foundation notes, and early paragraphs in domain read models describe checkpoints superseded by October work. Read later sections/ADRs and current code; do not interpret those notes as current capability lists. |

## Current end-to-end paths

### New decision and older earlier-payout adapter

`web/pawn_draft_actions.pawn_loan_create` saves drafts through `draft_submissions`;
`forms.PawnDraftForm`, `pawn_drafts` and `pawn_economics` validate selected setup,
item facts and economics. `pawn_lifecycle.approve_pawn_loan` freezes approval;
`pawn_disbursal.disburse_pawn_loan` persists policy, DISBURSAL, disbursal snapshot,
schedule and ACTIVE projection. A successful save is not itself a payout.
Simple-workflow review still delegates to these services.

`web/valuation_review` handles the authorized earlier-payout review using
`historical_origination`, then existing approval/disbursal. It distinguishes
actual date from recording time and protects historical digital evidence, but
requires proof that Rokkad's policies/quotes already existed. It is unsuitable
as the general route for an evidenced paper agreement predating adoption.

### Current paper admission

`web/entry_presentation` selects presentation purpose; `web/recorded_history`
builds the request. `paper_entry_terms` uses dated setup only as defaults; missing
setup can be replaced by explained supported actual terms. Its current monitoring
selection is separate. `recorded_history.validate_input`, preview and admission
reconcile transactions under a signed review and commit atomically.

`_make_contract` creates ordinary PawnLoan/items, RECORDED_CONTRACT policy and
RECORDED DISBURSAL snapshot, with original date/number and no approval. The local
item profile is `recorded-anniversary/2`; existing profile 1 is preserved.
`recorded_origination_evidence` and migration 0041 bind source, terms, actor,
deductions and monitoring. They perform no historical quote lookup or original
LTV approval. Proceeds are distinguished from confirmed physical cash.

Limits are concrete: simple FULL_MONTH anniversary rules, zero/one advance month,
one identified deducted document charge, gold/silver with complete positive
weights/purity and actual principal per item; selected active non-amortizing
product/tenure compatibility; bounded timeline. Multi-item principal receipts
need an explicit split. Known linked paper renewal and archive admission retain
single-group limits. Routine origination can be entered without a complete-book
claim; its calculated current position remains provisional. This does **not**
prove that unknown earlier payments are zero.

### Complete-history import

`data_portability/loan_history` stages/rolls back preview and calls the Loans
writer. `history_setup.preview_history_setup` validates source Party identity,
license revision, series, compatible active/retired product and number aliases.
`history_import` reconstructs canonical history and stores immutable
`HistoricalLoanImport`. Original actors/approval timestamps live in source
evidence; new rows record today's import actor/time. The approval snapshot created
here has `approved_by=None` and a `historical_approval` payload; treating its
auto-generated `approved_at` as the original approval time would be misleading.

V2 solves exact fractional accrual/advance-covered period serialization. It still
requires source approval/time/valuation and matching calculations/allocations;
it does not accept every valid external contract. A mismatch can mean an unsupported
source convention, not dishonest or impossible history. Do not label all such
mismatches historical inconsistency in a future general admission adapter.

### Opening import and restore

`guided_openings` and `legacy_opening` retain source, mappings and owner review;
`opening_import._document/_write` creates ordinary PawnLoan/items, servicing
policy, MIGRATION_OPENING, remaining obligations and HistoricalLoanImport.
The opening is not cash lent, an accrual or a receipt. Pre-cutover balance queries
are unavailable, not zero. `opening_restore` validates/remaps source-local links
and reconstructs supported post-cutover actions through Loans commands.

The current committer requires reconciled `loan-opening-review/2` and a
LATEST_APPRAISAL servicing policy, although individual source valuations may be
UNVERIFIED. The broader period-carry review v1 validator is not a general operational
importer. `_validate_collection_checkpoint` requires unchanged principal at cutover,
first month paid, original-anniversary inclusive rule, aggregate HALF_EVEN rounding
to whole rupees and the exact cumulative recognized baseline. Opening unpaid
interest is separate from that baseline. Later principal reductions are supported
by `opening_payment_evidence`; this does not enable reduced principal **at** cutover.

Opening reuse of `history_setup` also requires matching product calculation version,
grace, tenure and original availability dates. A verified legacy continuation
allows future issuance after separate checks; an inactive legacy reference does
not authorize lending. The SQL legacy-origination guard currently rejects any
DISBURSAL under a legacy reference, including a retrospective RECORDED disbursal.
That is another exact boundary to change deliberately, not disable globally.

The existing opening review additionally requires a timezone-aware original source
`loan_timestamp` (`opening_validation.validate_opening`). The guided register already
accepts a date and encodes midnight in Asia/Kolkata (`opening_register.loan_inputs`);
this is an adapter convention, not a known source clock time. A future profile must
represent precision truthfully and documents must not portray that convention as
exact historical evidence. The existing paper disbursal evidence supports DAY
precision; not every current import requires staff to know the original clock time.

### Future operations, correction, custody and archive

- `pawn_repayment` shares canonical allocation lines/events but selects opening
  balance/catch-up and writer separately. Native payments use recorded balance;
  recorded agreements recognize anniversary delta at collection. `paper_repayments`
  accepts only opening or recorded-origin loans, even if a native loan has a genuine
  later paper receipt. Outstanding fees block paper allocation until a rule exists.
  The opening replay validator additionally rejects multi-item paper principal
  payments and reconstructs highest-rate-first item lines; passing staff splits
  through the ordinary form does not make that old profile compatible.
  Reminder balance explicitly refuses a RECORDED_CONTRACT with no supported
  profile, while repayment preview can reach the native fold when `recording_for`
  returns no profile. A common resolver must fail closed for unknown semantics;
  this is a read-side validation discrepancy, not an observed corrupt posted loan.
- `pawn_interest` correctly avoids native periodic accrual for collection-recognition
  contracts; its opening error wording ('continuation is not enabled') is broader
  than current dedicated support. Capitalization cannot be enabled merely by
  removing a UI check: simple-interest contracts do not imply compound terms.
- `pawn_release` shares full release/custody records with opening/recorded catch-up
  adapters. `release_readiness` allows full settlement without original valuation,
  but retained collateral/partial release needs its own supported current safety
  assessment. Unknown customer handover uses PAPER_CLOSED; closure is not proof of
  physical return. `paper_closures` has a separately administered transition date;
  `recorded_closures` has its supported financial/custody profile. Keep these facts
  distinct rather than treating every closure as a new cash receipt and return.
- `pawn_renewals` now supports recorded and imported-opening sources. Source
  settlement uses its continuation; a successor decision now uses current product,
  approval and quotes. `recorded_renewal_actions` is a bounded already-completed
  renewal adapter. Unknown ancestry remains optional. Retained custody and net
  settlement must not be replaced by invented gross cash movements.
- `pawn_auctions` supports recorded-origin current recovery after coverage checks,
  statutory readiness and coupled interest/custody reversal. Imported openings
  still encounter the general opening financial-action guard. No source tag alone
  should permanently prohibit a future auction once those semantics are supported.
- `recorded_corrections`, contract/settlement/batch correction services compensate
  and replay supported earlier receipts/terms. Ordinary backdated receipts/closures
  reject later activity. Native/opening generic reversal is newest-first; opening
  coupled reversal and immutable cutover remain protected. Unification must not
  silently insert an earlier payment behind a completed release or successor.
- `transaction_completeness` currently infers ongoing paper coverage from the origin
  or a review. Even imported loans subsequently serviced only in Rokkad need a
  new dated confirmation for definitive reminders. Actual coverage is necessary;
  permanent off-system activity assumptions based solely on origin are avoidable.
- `exposure`, `obligation_state`, `delinquency`, `collateral_valuation`, `risk`
  and dashboard readers preserve recorded debt, projection, obligations, current
  valuation and provisional coverage separately. Risk uses dated eligible current
  quotes/appraisals and monitoring freshness. Missing original LTV need not make
  verified principal unknown; missing current valuation does make coverage unknown.
- `loan_documents`, document builders and issuance retain source labels and issued
  bytes. Recorded contracts and imported ticket previews do not attest native
  approval. `history_export` refuses recorded origins; opening exports refuse paper
  closures and broader later profiles. Portable history/opening contracts differ
  from whole-Workspace `pawn_recovery` exact-identity, owner-only disaster recovery.
- `loan_archive`/`archive` retain immutable historical-only claims/media without
  balances or ordinary events. `archive_admission` can now reconcile a supported
  fully closed loan and link it to the retained archive. Unknown settlement details
  alone do not become a verified zero balance or operational closure.

## Rule classification

I = fundamental domain invariant; P = prospective lending control;
R = retrospective evidence requirement; S = future servicing prerequisite;
L = current implementation limitation. A rule can have more than one responsibility.

| Rule | Class | Correct application |
|---|---|---|
| Workspace parent identity, forced RLS, actor authorization, writable lifecycle | I | Every entry/operation, including preview, retry, correction and export. |
| One active financial origin; no opening plus original disbursal; no pre-cutover replay | I | Every admission and reader/writer; opening does not erase its history boundary. |
| Immutable evidence, reversal/correction links, conservation, lock/idempotency | I | All channels; changing origin tags cannot waive them. |
| Positive principal, exact item sums, no negative balances/overpayment, allocation conservation | I | Original or reconciled position and every later event. |
| Current-day/same-day quotes, proposal LTV, approved valuation/photo/setup readiness | P | Decisions and cash advances being performed now, including new renewal successors. Not proof that a past advance occurred. |
| Recorded-before-original-date policy/quote rows and retrospective approval creation | L/P | Keep as interpretation of an existing native approval; unnecessary gate for supported external past facts. |
| Original date/precision, number/source identity, actual terms, amount/custody evidence | R | Required facts of admission; unknown times/actors/valuation remain unknown. Attachment is not universally required. |
| Historical source license/product identity | R | Retain known identity and unknown validity separately. Present local catalog availability is not proof of past external terms. |
| Known current balance and continuation checkpoint with recognition/advance coverage | S/I | Required to give definitive current settlement/future debt; no unpaid-interest or period-base guessing. |
| Historical LTV unknown | R | Disclosure, not a financial-origin blocker when current debt is verified. |
| Current valuation for risk, retained collateral safety, custody/physical verification | S/P | Date-appropriate evidence for the operation. Full debt settlement need not require original market prices. |
| Actual item receipt split where not uniquely determined | R/S/I | Preserve source split, or derive only using an evidenced rule. Future deterministic allocation is frozen separately. |
| Native highest-rate-first imposed on different source allocation | L | Valid native rule; not a universal historical fact. |
| Unchanged principal and one advance paid at opening cutover; rupee aggregate rule only | L/S | Named supported profile, not a universal loan invariant. Reject unsupported continuation accurately. |
| Single-group archive/known renewal, gold/silver/full weights, active paper product only | L | Existing supported scope; extend deliberately where actual business cases require. Do not invent item identity/weights. |
| Later activity prevents ordinary backdated posting | I plus L | Dependency review is essential; existing correction profile limits are implementation boundaries. |
| Origin permanently determines which action-purpose choices are offered | L | A native-origin loan can later have a paper transaction; a paper-origin loan can later be serviced digitally. |
| Coverage required for definitive borrower claims/recovery | S/R | Keep evidence-based protection; distinguish known missing activity, a checked position and future off-system capture. |
| Wire bounds, exact profile matching, schema/guard recovery fingerprints | I/L | Preserve published readers; new financial semantics require explicit new versions. Do not masquerade recovery as import. |

## Numbering, setup and database guards

`recorded_numbers.identity/claim_number` normalize NFKC/whitespace/case, reject
existing source numbers and reserve live sequence space under Workspace/sequence
locks. `history_setup` normally assigns deterministic H/namespace/hash local numbers;
`HistoricalLoanImport` retains original numbers. `find_source_origin` handles older
and schema-scoped source identities; `(Workspace, namespace, source_id)` is unique.
Exact retry returns the existing origin only if accepted facts/mapping match.

These protections must survive. The broad original-number rejection is stricter
than stable source identity: two legitimate source books/licenses can both contain
number 17. The target keeps unique local numbers and searchable scoped source aliases,
with an explicit collision decision, not silent renaming or automatic merging.
Paper manual entry's original number equals local number today; do not renumber
existing loans or alter issued documents to implement future alias admission.

Models have direct Workspace ownership. Migration 0003 installs forced RLS;
0004/database guards protect license links, reversals, collateral, storage and
other cross-object boundaries; 0008 protects immutable evidence/parent loan scope;
0009/0010 protect source registry and unique opening; 0041 binds recorded payouts;
0042 links archive admission; 0043 protects reviews; 0045/0048 and 0052--55 protect
paper custody, corrections and one active item opening. Those constraints are
retained. Mixed-financial-origin rejection is currently enforced by commands and
balance/tranche readers, not demonstrated here as one universal SQL exclusivity
constraint. A later DB-hardening slice should test raw restricted-role DML first.

`apps/tenant_apps/utils/importing/views.py` rejects generic Loans writes. Keep this
containment: model import is not financial admission. Nothing in this proposal
reintroduces retired accounting/Girvi models or runtime owner privileges.

## Scenarios and precise blockers

| Scenario | Current behavior | Target admission/operation |
|---|---|---|
| New loan issued today | Native draft/approval/disbursal, current controls | Retain; freeze native contract and prospective evidence. |
| Payout yesterday, entered today | Native earlier-payout needs contemporaneous digital rows; paper route can accept supported actual terms | One record-completed purpose; reuse valid approval if present, otherwise retrospective verification without claiming approval. Existing draft identity must be retained, not duplicate admission. |
| Six-month paper loan, no historical quote/policy | Already supported within the paper profile using actual explained terms; current position may be provisional without checked history | Supported original history with verified position, or reconciled cutover opening; no invented Rates/policy rows. Original LTV may be unknown. |
| Original principal known, current balance unknown | Routine paper original transaction can be entered with provisional coverage; completeness does not imply zero unseen payments | Retain source/original facts; do not certify a current position. Debt-sensitive servicing needs reconciled history or a verified opening. Unknown current debt is not zero. Existing provisional records are not silently rewritten/deactivated. |
| Complete import, different original allocations | Strict importer recalculates/rejects mismatches | Preserve actual verified allocations under an explicitly supported history contract; if historical semantics cannot be replayed, retain history as evidence and admit a verified opening with supported future terms. Neither choice creates two financial origins. |
| Partial history plus reconciled opening | Supported narrow v2 checkpoint; pre-cutover unavailable | Reuse origin/event/schedule; extend named continuation coverage only as needed. Retained partial history does not become canonical pre-cutover postings. |
| Reduced principal, unpaid interest, advance coverage at cutover | Unpaid interest supported under v2; reduced principal rejected; general v1 carry descriptor is not operationally committed | Explicit item balance, current-period base, unpaid recognized amounts, paid/advance coverage and next boundary. Hold if any charge-affecting fact/rule is unknown. Never restart tenure or replay baseline. |
| Backdated payment/closure after later activity | Direct posting blocked; recorded correction/replay supports bounded receipts/settlements/terms | Common dependency preview; supported compensating replay, explicit restated allocations, preserved terminal/custody evidence. Otherwise exact unsupported dependency blocker. |
| Closed archive with incomplete payments | Historical-only; qualified single-group complete admission now exists | Retain archive unless exact financial settlement position is evidenced. A source CLOSED label alone is insufficient. Never fabricate receipts or handover. |
| Number collision, duplicate submission | Reserved counters/local aliases and source checks; broad number collision blocks some genuine distinct books | Unique canonical local identity, scoped original aliases, conflict review, locked exact retry. Source identity remains stronger than a number string. |
| Foreign Workspace or unauthorized actor | Explicit request/context, RLS, service checks and signed binding | Retain every boundary for all channels and idempotent returns; no migration/import privilege bypass. |

## Equivalence, and differences that must remain

Entry channel alone must not change a calculation. Identical **supported contract**,
effective history/item allocations, recognized/advance coverage, obligations,
custody and current evidence must yield identical operational amounts/eligibility.
An opening can match only on/after its cutover; its lifetime disbursed totals and
earlier history will intentionally differ. Snapshot IDs, audit actors and source
labels also differ. A schedule comparison concerns remaining due dates/components
and maturity, not equal historical row counts or fabricated prior allocations.

Proposed parity fixture (not a claim that current admission can select every rule):
one item, original principal 10,000, agreed 2% monthly, maturity 5 April 2027,
first month covered, identical named anniversary/rounding convention. At a verified
cutover immediately after a charge boundary, principal is 8,200 and recognized
unpaid interest is zero, with the same next-period base in all three cases.

| Output | Direct history | Delayed history | Opening at cutover |
|---|---:|---:|---:|
| Recorded principal at cutover | 8,200 | 8,200 | 8,200 opening, not disbursed cash |
| Next full charge under the same supplied convention | 164 | 164 | 164 incremental, no cutover replay |
| Total receipt 1,000 after that charge | 164 interest + 836 principal | Same | Same |
| Remaining principal/unpaid interest | 7,364 / 0 | Same | Same |
| Remaining schedule | Same maturity/due components under same contract | Same | Same from cutover; earlier history unavailable |
| Full settlement at that position | 7,364 before any later charge | Same | Same |
| Risk using current value V and the same payoff basis E | E/V, same freshness/custody/coverage status | Same | Same; original LTV can remain unknown |

Three origin fixtures and as-of/reversal/rounding boundary tests must prove this
before activation. Fee priority, valuation or unknown coverage cannot be silently
changed to manufacture equality.

Existing rules are **not** already equivalent: for a 10,000 loan at 2%, dated
5 April 2026 with one first month covered, executing the current opening pure
calculator gives additional interest 1,000 on 4 and 5 October, 1,200 on 6 October.
The recorded-anniversary loop starts the next full charge on the anniversary itself;
source inspection therefore predicts 1,200 on 5 October. Opening additionally uses
cumulative aggregate whole-rupee HALF_EVEN; item paper v2 uses item-rounded paise
HALF_UP. Native projections use outstanding daily segments and native accrual has
its frozen period rules. These differences represent contracts/versions, not a
reason to silently switch an existing loan's formula when it is imported or entered.

## Verified limits versus hypotheses

Verified means current source explicitly enforces the condition, with references
above and in the inventory below. The opening calendar figures were executed in
isolation. The paper comparison is a code-derived prediction, not a database test.
Current staging, commands, published tests and SQL guards were inspected; their
presence is not a fresh end-to-end pass.

Still to characterize during implementation: parity across writer and display
catch-up paths (especially opening renewal), production cohort profile distribution,
any raw-DML mixed-origin gap, old unitemized native compatibility, exact PDF labels
for reconstructed/imported approval timestamps, and performance/query counts of
a shared resolver. No observed production corruption, balance loss or exploitable
guard bypass is asserted by this review.

The [proposed ADR](../adr/2026-10-05-unified-loan-admission-and-continuation.md)
and [incremental plan](../plans/unified-loan-domain-correction.md) define the correction.

## Origin and purpose reference inventory

The inventory appended below covers all 188 matching references in 69 non-test,
non-migration Python/template files from the declared search. It includes envelope
tags and labels as well as behavioral gates; those are not all defects. SQL,
admission defaults/numbering, archive, authorization and remaining obligations are
reviewed separately above. Search terms and line-level matches are retained privately;
the grouped table names functions and classifies each file's responsibilities.
This is an explicit static search boundary, not a claim that every conceivable
dynamic origin dependency has been proven absent.

| File and matching lines | Functions containing matches | Classification and disposition |
|---|---|---|
| [forms.py](../../apps/tenant_apps/loans/forms.py#L371) (371, 393, 395, 401, 402, 403, 414) | `(module/template)`, `__init__`, `clean` | **S/L**. Keep validated item splits and explicit purpose; replace origin-only availability with common operation eligibility. |
| [documents/payloads.py](../../apps/tenant_apps/loans/documents/payloads.py#L152) (152, 202, 239) | `loan_ticket`, `loan_kfs_schedule`, `recorded_contract` | **R/S**. Keep truthful recorded/opening labels and schedule semantics; reuse resolved contract without claiming historical approval. |
| [domain/vocabulary.py](../../apps/tenant_apps/loans/domain/vocabulary.py#L27) (27) | `(module/template)` | **I/R**. Keep canonical event and evidence names; these tags do not independently establish eligibility. |
| [models/core.py](../../apps/tenant_apps/loans/models/core.py#L873) (873, 921, 1099) | `(module/template)` | **I/R**. Keep frozen policy/disbursal bases and ownership; resolve semantics centrally, do not delete source distinctions. |
| [models/history.py](../../apps/tenant_apps/loans/models/history.py#L10) (10) | `(module/template)` | **I/R**. Keep immutable source bindings and unique opening evidence. |
| [selectors/balances.py](../../apps/tenant_apps/loans/selectors/balances.py#L58) (58, 98, 103, 229, 254) | `(module/template)`, `calculate_pawn_loan_balance`, `_apply_event` | **I/S**. Keep opening baseline, pre-cutover unavailability and mixed-origin rejection; shared callers must preserve the fold. |
| [selectors/collateral_valuation.py](../../apps/tenant_apps/loans/selectors/collateral_valuation.py#L118) (118) | `get_pawn_loan_collateral_valuation` | **R/S**. Keep unknown original valuation and current valuation distinct; do not invent historical LTV. |
| [selectors/delinquency.py](../../apps/tenant_apps/loans/selectors/delinquency.py#L42) (42, 44) | `get_pawn_loan_delinquency` | **S**. Keep remaining obligations and original maturity; use supported contract resolution. |
| [selectors/exposure.py](../../apps/tenant_apps/loans/selectors/exposure.py#L65) (65, 66, 141, 156) | `get_pawn_loan_exposure`, `_project_interest_periods` | **S**. Keep profile-specific projections; centralize dispatch without changing recognition or rounding. |
| [selectors/pledge_book.py](../../apps/tenant_apps/loans/selectors/pledge_book.py#L21) (21, 74, 242, 261) | `(module/template)`, `_entry`, `pledge_book_report` | **R**. Keep source particulars and opening labels; same ordinary register. |
| [selectors/release_readiness.py](../../apps/tenant_apps/loans/selectors/release_readiness.py#L115) (115, 117) | `get_pawn_loan_release_readiness` | **S/I**. Keep custody, physical verification and retained-collateral safety; make prerequisites factual. |
| [selectors/reports.py](../../apps/tenant_apps/loans/selectors/reports.py#L405) (405, 651) | `_loan_issues`, `_event_amount` | **I/R/S**. Keep opening out of new-lending cash totals and disclose coverage; provenance labels remain. |
| [selectors/transaction_completeness.py](../../apps/tenant_apps/loans/selectors/transaction_completeness.py#L39) (39, 40, 41) | `transaction_completeness` | **R/S/L**. Keep checked coverage/fingerprint; replace permanent origin-inferred future paper capture with an explicit reviewed capture mode. |
| [services/event_recording.py](../../apps/tenant_apps/loans/services/event_recording.py#L58) (58) | `record_loan_event` | **I/L**. Keep refusal of unvalidated generic opening postings; replace blanket gate only through validated common commands. |
| [services/history_contract.py](../../apps/tenant_apps/loans/services/history_contract.py#L1) (1, 13, 85, 258, 260) | `(module/template)`, `parse` | **R/S**. Keep published v1/v2 evidence contracts; add explicit versions for newly supported semantics. |
| [services/history_export.py](../../apps/tenant_apps/loans/services/history_export.py#L40) (40, 51, 52, 56, 112, 122, 124) | `_export_history` | **R/L**. Keep old wire exact and truthful; new profiles needed for recorded/other unsupported histories. |
| [services/history_import.py](../../apps/tenant_apps/loans/services/history_import.py#L266) (266, 395) | `import_complete_history` | **I/R/L**. Keep atomic verification and actual lines; native allocation matching is a bounded contract, not a universal historical rule. |
| [services/history_setup.py](../../apps/tenant_apps/loans/services/history_setup.py#L95) (95) | `preview_history_setup` | **I/R/L**. Keep scoped identities/valid current authorization; decouple original external terms from destination historical catalog availability. |
| [services/imported_ticket_preview.py](../../apps/tenant_apps/loans/services/imported_ticket_preview.py#L21) (21, 22, 88) | `imported_ticket_payload`, `_render_imported_ticket` | **R**. Keep non-issued source preview and unknown facts; do not fabricate an issued native ticket. |
| [services/notice_delivery_readiness.py](../../apps/tenant_apps/loans/services/notice_delivery_readiness.py#L10) (10, 12, 16) | `notice_balance` | **S**. Keep verified amount/coverage checks; reuse common servicing position. |
| [services/opening_continuation.py](../../apps/tenant_apps/loans/services/opening_continuation.py#L41) (41, 69) | `opening_interest_breakdown`, `preview_opening_collection` | **I/S**. Keep cutover baseline and exact old calendar/rounding; adapt as a named supported calculator. |
| [services/opening_contract.py](../../apps/tenant_apps/loans/services/opening_contract.py#L1) (1, 15, 17, 250) | `(module/template)` | **I/R/S**. Keep frozen opening evidence schema and version identity. |
| [services/opening_evidence.py](../../apps/tenant_apps/loans/services/opening_evidence.py#L8) (8, 9) | `(module/template)` | **I/R**. Keep source fingerprint and reviewed ownership bindings. |
| [services/opening_export.py](../../apps/tenant_apps/loans/services/opening_export.py#L57) (57, 84, 183) | `export_loan_data`, `_export_opening` | **I/R/L**. Keep coverage and published opening wire; version new post-cutover operations instead of mislabelling. |
| [services/opening_import.py](../../apps/tenant_apps/loans/services/opening_import.py#L29) (29, 145, 212) | `(module/template)`, `_write`, `adopt_opening_source_number` | **I/R/S/L**. Reuse ordinary origin/items/schedule; extend explicitly reviewed continuation profiles, not arbitrary openings. |
| [services/opening_obligations.py](../../apps/tenant_apps/loans/services/opening_obligations.py#L20) (20, 32) | `(module/template)`, `persist_opening_repayment_schedule` | **I/S**. Keep original maturity and remaining schedule at cutover. |
| [services/opening_repairs.py](../../apps/tenant_apps/loans/services/opening_repairs.py#L28) (28) | `restore_opening_quantities` | **I/R**. Keep guarded source-backed quantity repair; no broad mutation privilege. |
| [services/opening_restore.py](../../apps/tenant_apps/loans/services/opening_restore.py#L32) (32, 90, 96, 102) | `(module/template)`, `parse_opening_export` | **I/R/S**. Keep schema/source validation, actor remapping and supported post-cutover replay; extend readers before writers. |
| [services/opening_servicing.py](../../apps/tenant_apps/loans/services/opening_servicing.py#L86) (86) | `_record_opening_servicing_event` | **I/S**. Reuse validated writer and coupled bindings; common command must preserve restricted event profiles. |
| [services/opening_validation.py](../../apps/tenant_apps/loans/services/opening_validation.py#L13) (13, 14) | `(module/template)` | **I/S/L**. Keep reconciliation; unchanged-principal/advance/rounding restrictions describe old supported scope, not universal invariants. |
| [services/paper_repayments.py](../../apps/tenant_apps/loans/services/paper_repayments.py#L88) (88, 89) | `_preview` | **I/R/S/L**. Keep actual-date, chronology and paper evidence; permit by supported action semantics rather than original channel. |
| [services/pawn_auctions.py](../../apps/tenant_apps/loans/services/pawn_auctions.py#L566) (566) | `_recorded_coverage` | **I/S/L**. Keep statutory/custody/coverage and coupled reversal; extend opening eligibility only after settlement semantics are supported. |
| [services/pawn_disbursal.py](../../apps/tenant_apps/loans/services/pawn_disbursal.py#L202) (202) | `assert_pawn_loan_financial_actions_allowed` | **I/P/L**. Keep current approval/quotes and financial-origin guards; replace broad future opening gate operation by operation. |
| [services/pawn_interest.py](../../apps/tenant_apps/loans/services/pawn_interest.py#L99) (99, 103, 114, 389, 391) | `preview_pawn_loan_accruals`, `finalize_pawn_loan_accrual` | **S/L**. Keep no native periodic accrual for collection profiles; clarify unsupported actions instead of denying all continuation. |
| [services/pawn_recovery.py](../../apps/tenant_apps/loans/services/pawn_recovery.py#L195) (195) | `_position` | **I/R/S**. Keep exact identity and full native recovery inventory; not cross-workspace portability. |
| [services/pawn_release.py](../../apps/tenant_apps/loans/services/pawn_release.py#L180) (180, 188, 189, 235, 273, 305, 308, 484, 495, 565) | `_release_pawn_loan_in_full_at`, `_build_full_release_preview`, `_record_release_accrual` | **I/S**. Reuse full release/custody and profile-specific catch-up; unify prerequisites without inventing handover. |
| [services/pawn_renewals.py](../../apps/tenant_apps/loans/services/pawn_renewals.py#L200) (200, 201, 416, 417, 1203) | `preview_pawn_loan_renewal_source`, `renew_pawn_loan`, `_reverse_catch_up` | **I/P/S**. Reuse source settlement and current successor approval; keep coupled reversal and actual net cash. |
| [services/pawn_repayment.py](../../apps/tenant_apps/loans/services/pawn_repayment.py#L96) (96, 103, 143, 151, 159, 228) | `preview_pawn_loan_repayment`, `_record_pawn_loan_repayment_at` | **I/S/L**. Reuse common allocations/writer; centralize balance selection while preserving recorded versus collectable amounts. |
| [services/pawn_reversal.py](../../apps/tenant_apps/loans/services/pawn_reversal.py#L81) (81, 155, 156, 199, 232, 256, 409) | `assess_pawn_loan_event_reversal`, `_reverse_pawn_loan_event_at`, `_reverse_release_catch_up` | **I/S**. Keep immutable origin, dependencies and coupled reversal; extend only evidenced supported profiles. |
| [services/pawn_tranches.py](../../apps/tenant_apps/loans/services/pawn_tranches.py#L33) (33) | `get_pawn_principal_tranche_balances` | **I/S**. Keep original versus remaining item bases and exact item balances; no guessed allocations. |
| [services/recorded_batch_corrections.py](../../apps/tenant_apps/loans/services/recorded_batch_corrections.py#L92) (92) | `_snapshot` | **I/R/S**. Keep locked dependent snapshots and compensation/replay; share dependency facts later. |
| [services/recorded_closures.py](../../apps/tenant_apps/loans/services/recorded_closures.py#L38) (38) | `_source` | **I/R/S/L**. Keep supported settlement and unknown-handover facts; replace source-only gate with required profile support. |
| [services/recorded_collections.py](../../apps/tenant_apps/loans/services/recorded_collections.py#L14) (14, 15, 23, 119) | `recording_for`, `collection_state`, `recorded_obligation_state` | **I/S**. Keep profiles 1/2 and exact calendar/item rounding; centralize detection, not calculator replacement. |
| [services/recorded_contract_corrections.py](../../apps/tenant_apps/loans/services/recorded_contract_corrections.py#L97) (97) | `_source` | **I/R/S/L**. Keep frozen facts and dependent replay; source restriction is current supported correction scope. |
| [services/recorded_corrections.py](../../apps/tenant_apps/loans/services/recorded_corrections.py#L86) (86, 225) | `dependencies`, `_run` | **I/R/S/L**. Keep compensation/dependency limits; broader admission does not authorize blind historical insertion. |
| [services/recorded_history.py](../../apps/tenant_apps/loans/services/recorded_history.py#L283) (283) | `_make_contract` | **I/R/S**. Reuse retrospective ordinary-loan admission, no approval and source/current monitoring separation. |
| [services/recorded_origination_evidence.py](../../apps/tenant_apps/loans/services/recorded_origination_evidence.py#L46) (46) | `_validate` | **I/R**. Keep actual payout/deductions/source and no-approval distinction; day precision is truthful. |
| [services/recorded_renewals.py](../../apps/tenant_apps/loans/services/recorded_renewals.py#L38) (38, 40, 112, 119) | `record_admission_renewal` | **I/R/S/L**. Keep exact linked source settlement; optional single-group shortcut need not represent every independent paper loan. |
| [services/recorded_renewal_actions.py](../../apps/tenant_apps/loans/services/recorded_renewal_actions.py#L49) (49, 70, 83) | `_source`, `_write` | **I/R/S/L**. Reuse completed-renewal evidence and net cash; eligibility follows supported semantics and dependencies. |
| [services/recorded_settlement_corrections.py](../../apps/tenant_apps/loans/services/recorded_settlement_corrections.py#L74) (74, 113) | `terminal_for`, `dependent_state` | **I/R/S**. Keep terminal dependencies and replay/custody bindings; do not mutate accepted closure. |
| [services/transaction_reviews.py](../../apps/tenant_apps/loans/services/transaction_reviews.py#L25) (25) | `_facts` | **I/R/S**. Keep immutable checked-through claims and exact financial fingerprint. |
| [web/entry_presentation.py](../../apps/tenant_apps/loans/web/entry_presentation.py#L20) (20, 77) | `entry_presentation` | **R/L**. Keep standing defaults and read-only explicit purpose; presentation does not approve or admit. |
| [web/loan_documents.py](../../apps/tenant_apps/loans/web/loan_documents.py#L127) (127, 156) | `pawn_loan_ticket_pdf`, `pawn_loan_kfs_schedule_pdf` | **R/S**. Keep truthful source document choices; future common resolver supplies semantics, not historical approval. |
| [web/pawn_financial_actions.py](../../apps/tenant_apps/loans/web/pawn_financial_actions.py#L123) (123, 125, 131, 132, 133, 137, 182, 186, 193, 210, 211, 212, 213) | `pawn_loan_repay` | **S/L**. Replace origin-only paper choice and duplicated balance resolution with common eligibility/position; view never posts directly. |
| [web/pawn_reads.py](../../apps/tenant_apps/loans/web/pawn_reads.py#L100) (100, 210, 219, 227, 293) | `pawn_loan_detail`, `_primary_action` | **R/S/L**. Keep source labels; replace origin-based primary action/hiding with common prerequisite results. |
| [web/pawn_renewal_actions.py](../../apps/tenant_apps/loans/web/pawn_renewal_actions.py#L63) (63, 110) | `pawn_loan_renew` | **R/S**. Keep now-versus-record-completed purpose; delegate to validated commands. |
| [web/recorded_servicing.py](../../apps/tenant_apps/loans/web/recorded_servicing.py#L49) (49) | `__init__` | **R/S/L**. Keep actual item evidence fields; common operation purpose should determine availability. |
| [apps/tenant_apps/data_portability/linode_run.py](../../apps/tenant_apps/data_portability/linode_run.py#L370) (370, 475) | `replay_package`, `verify_package` | **I/R**. Keep verification/replay envelope dispatch; packaging identity is not a servicing restriction. |
| [apps/tenant_apps/data_portability/loan_history.py](../../apps/tenant_apps/data_portability/loan_history.py#L19) (19) | `get_batch` | **I/R**. Keep staged batch identity and preview/commit boundary. |
| [apps/tenant_apps/data_portability/loan_history_views.py](../../apps/tenant_apps/data_portability/loan_history_views.py#L54) (54) | `upload` | **I/R**. Keep authorized upload schema dispatch and review. |
| [apps/tenant_apps/data_portability/models.py](../../apps/tenant_apps/data_portability/models.py#L175) (175, 176) | `(module/template)` | **I/R**. Keep owned staging envelope choices and source identity; no duplicate operational model. |
| [templates/loans/pawn/action_form.html](../../templates/loans/pawn/action_form.html#L112) (112) | `(module/template)` | **S/L**. Keep explicit paper allocation controls; show from common operation eligibility. |
| [templates/loans/pawn/detail.html](../../templates/loans/pawn/detail.html#L11) (11, 65, 68, 73, 91, 109) | `(module/template)` | **R/S/L**. Keep source/coverage disclosure; remove redundant origin-only action gates after command support. |
| [templates/loans/pawn/form.html](../../templates/loans/pawn/form.html#L18) (18) | `(module/template)` | **R/P**. Keep explicit purpose and prospective review labels; defaults do not waive controls. |
| [templates/loans/pawn/paper_history.html](../../templates/loans/pawn/paper_history.html#L12) (12) | `(module/template)` | **R/S**. Keep reviewed actual agreement/activity facts; presentation adapter may remain. |
| [templates/loans/pawn/paper_servicing.html](../../templates/loans/pawn/paper_servicing.html#L13) (13) | `(module/template)` | **R/S**. Keep actual paper receipts/closure and item split; share common operation screen when supported. |
| [templates/loans/pawn/release_and_renew.html](../../templates/loans/pawn/release_and_renew.html#L8) (8) | `(module/template)` | **R/P/S**. Keep completed-versus-now purpose and current successor checks. |
| [templates/loans/pawn/_detail_header.html](../../templates/loans/pawn/_detail_header.html#L19) (19) | `(module/template)` | **R**. Keep opening/source labels, original dates and number aliases. |
| [templates/loans/pawn/_recorded_by.html](../../templates/loans/pawn/_recorded_by.html#L5) (5) | `(module/template)` | **R**. Keep actual recording actor/time distinct from unknown original actor/time. |

### Supplemental admission, setup and coverage references

The narrow term inventory is supplemented by direct workflow tracing and a second
search for legacy-reference, opening-review and recorded-profile terms. These
references cover gates outside that inventory; some are necessary source adapters,
not origin-based servicing restrictions. Khata account-opening hits are a separate
account workflow and are not a second PawnLoan servicing engine.

| File/function | Classification and disposition |
|---|---|
| [origination_rates](../../apps/tenant_apps/loans/selectors/origination_rates.py#L73): `require_current_origination_date`, `assert_approved_quotes_current` | **P**. Retain for decisions now; appraisal-only excludes quote lookup, not approval economics. |
| [historical_origination](../../apps/tenant_apps/loans/services/historical_origination.py#L65): `historical_policies`, `historical_quotes`, `assert_historical_approval` | **P/R/L**. Keep genuine retained native approval validation; replace historical destination-row prerequisites for general completed entry. |
| [paper_entry_terms](../../apps/tenant_apps/loans/services/paper_entry_terms.py#L14): `paper_entry_terms`, `preferred_paper_product` | **R/S/L**. Reuse actual agreement defaults and separate monitoring; selected active product is current supported admission scope. |
| [recorded_numbers](../../apps/tenant_apps/loans/services/recorded_numbers.py#L26): `identity`, `reject_existing_source`, `claim_number` | **I/R/L**. Keep normalization/locks/counters; scoped distinct-source aliases can relax broad number-string rejection without merging. |
| [import_identity](../../apps/tenant_apps/loans/services/import_identity.py#L23): `source_binding_id`, `find_source_origin` | **I/R**. Keep stable source identity and old/schema-scoped lookup compatibility. |
| [opening_payment_evidence](../../apps/tenant_apps/loans/services/opening_payment_evidence.py#L73): `baseline`, `position`, `_validate_payment`, `collection_history` | **I/S/L**. Keep baseline separation and next-anniversary reductions; old fee/item/native-allocation replay restrictions need explicit new support. |
| [archive_admission](../../apps/tenant_apps/loans/services/archive_admission.py#L91): `_claims`, `_prepare`, `admit_archive_history` | **I/R/L**. Keep retained-source reconciliation and closed-position evidence; single-group profile is a bounded current limitation. |
| [obligation_state](../../apps/tenant_apps/loans/selectors/obligation_state.py#L137): `_fold_obligation_state` | **I/S**. Keep dynamic recorded-profile adjustment and immutable schedule capacity/maturity; centralize semantic detection later. |
| [document_issuance](../../apps/tenant_apps/loans/services/document_issuance.py#L166): `issue_recorded_document` | **I/R**. Keep actor/Workspace lock, source fingerprint and issued bytes; source-specific document evidence is legitimate. |
| [license_series](../../apps/tenant_apps/loans/services/license_series.py#L423): `create_legacy_license_reference`, `_require_verified_license`, `assert_series_can_issue` | **P/R/S**. Unknown license cannot authorize new lending; existing release-document exception is operationally appropriate. |
| [license_continuation](../../apps/tenant_apps/loans/services/license_continuation.py#L30): `verify_legacy_license` | **I/P/R**. Keep explicit owner review, document/attestation and numbering safety; not automatic imported-loan approval. |
| [regulatory](../../apps/tenant_apps/loans/selectors/regulatory.py#L51): `get_loan_license_register` | **P/R**. Keep unknown legacy expiry/status instead of invented dates. |
| [operational_notices](../../apps/tenant_apps/loans/services/operational_notices.py#L49): `create_license_expiry_notice` | **R/S**. Unknown expiry correctly prevents an expiry-specific notice; this is not a debt-servicing prohibition. |
| [guided_openings](../../apps/tenant_apps/data_portability/guided_openings.py#L117): `_product`, `_evaluate`, `preview`, `commit` | **I/R/S/L**. Keep source review and Loans-owned commit; fixed upfront profile and unchanged principal are supported-scope limits. |
| [opening_register](../../apps/tenant_apps/data_portability/opening_register.py#L83): `loan_inputs` | **R/S/L**. Keep source item facts and conversion; midnight/date precision and narrow rule assumptions must remain explicit. |
| [legacy_opening](../../apps/tenant_apps/data_portability/legacy_opening.py#L25): `source_evidence`, `stage`, `preview`, `commit` | **I/R**. Keep immutable source extraction, review bindings and authorized commit; no separate loan domain. |
| [legacy_preview](../../apps/tenant_apps/data_portability/legacy_preview.py#L84): `build_preview` | **R**. Keep source errors/unknowns and evidence preparation; do not treat a preview as verified debt. |
| [legacy_opening_views](../../apps/tenant_apps/data_portability/legacy_opening_views.py#L26): `review` | **I/R**. Keep owner review and staging boundary; delegate financial admission to Loans. |
| [opening detail](../../templates/loans/pawn/_opening_interest_breakdown.html#L18) | **R/S**. Keep explicit cutover brought-forward amounts; source labels do not decide future action eligibility. |

License continuation views/templates, opening-validation/staging management commands
and recorded-correction forms expose these same reviewed services. Their separate
presentation/envelope choices are retained; they do not grant alternate posting
privileges. Database-only branch coverage remains the migrations/guards described
above, with restricted-role exclusivity testing explicitly pending.
