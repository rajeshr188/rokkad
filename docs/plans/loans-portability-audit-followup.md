---
status: proposed
owner: project
updated: 2026-09-13
tags: [loans, portability, plan, audit]
---

# Proposed follow-up to Loans portability audit

The owner authorized slice 0A on 2026-09-13. Its generic Loans import containment
and current-grant authorization are complete locally (77 focused tests passed); see the
[decision](../adr/2026-09-13-generic-loans-import-containment.md).
The owner subsequently authorized slice 0B: validation classification without
relaxed admission. It is complete locally: all 94 focused tests passed, including
native lifecycle, import/restore, preview rollback and report presentation.
See the [classification decision](../adr/2026-09-13-portability-validation-classification.md).
The owner authorized the next contract slice: freeze the existing opening v1
wire definition and prove old-file compatibility independently of model fields.
See the [wire-contract decision](../adr/2026-09-13-frozen-opening-wire-contract.md).
This implements slice 1's current opening boundary; new formats and global-ID
redesign are not included. It is complete locally: 93 focused regression tests and
6 standalone contract checks passed, including restore/re-export of frozen files.
The owner authorized slice 2: bounded historical-only retention for incomplete
closed-loan claims. See the [archive decision](../adr/2026-09-13-historical-closed-loan-archive.md).
It is complete locally: all 78 focused tests passed, including restricted SQL/RLS,
snapshot replay, export/reacceptance, cancellation and existing financial imports.
The additive migrations remain unapplied to the main database; no real records
were imported. A representative source preview remains useful before real use.
**Slices 3 onward await separate review.**
Do not start another phase automatically, activate current-source loans, modify
accepted pilot debt, or infer cutover approval from this plan.

Basis: [findings](../architecture/loans-portability-audit.md),
[constraints](../domain/loans-portability-constraints.md),
[target proposal](../architecture/loans-portability-target.md).

## Sequence

| Slice | Objective / prerequisites | Components | Schema / migration risk | Required tests and acceptance | Rollback |
| --- | --- | --- | --- | --- | --- |
| 0A: contain generic financial imports | Resolve F01 before widening portability; owner audit review | utils/importing forms/views, slug route, registry use; focused boundary tests | No schema. Compatibility risk for users of generic import, not financial migration | Demonstrate current PawnLoan exposure, then deny financial model POST even with forged model choice; missing grants denied; RLS unchanged; supported Party/Loans staged routes and authorized reads work | Revert presentation changes if needed, retain financial denial; never restore unsafe mutation to recover unrelated export UI |
| 0B: characterize and name existing boundaries | Freeze source facts vs admission vocabulary; after review, independently useful from persistence | Loans history/opening validation contracts and tests; data_portability review presentation | No schema or acceptance changes | Golden cases for native/complete/opening/unsupported closed fact; classify existing errors without converting any rejection to success; operation capabilities reflect actual guards | Revert new reporting layer; old validators/writers remain authoritative |
| 1: version-owned exchange/provenance contract | Address F05/F10 before new generic source formats; 0B accepted | history_contract, opening_export/restore, docs/contracts, golden files | No required database migration. Compatibility risk from strict field/decimal/date semantics | Freeze current v1 decoder independently of `_meta`; preserve old opening fixtures including restore_supported=false; exact supported semantic round-trip after a simulated internal field change; reject unsafe extensions | Keep old reader/writer available; new version opt-in until compatibility proven |
| 2: accepted closed historical evidence | Solve F02 with one bounded released-fact profile; 0A/0B/1 accepted | New Loans-owned evidence model/service; portability staging/review/export; authorized historical browse | New direct Workspace-owned evidence table and optional append-only admission link; no conversion of existing PawnLoan rows. Migration risk low if additive but RLS/retention acceptance mandatory | L123 without payments retains all facts, missing evidence explicit, no PawnLoan/payment/custody/obligation created; unresolved Party refs; contradictory claims; idempotency and changed snapshot history; restricted SQL/RLS; export/import equality; cancellation cannot erase accepted evidence | Disable new admission endpoint; retain accepted rows and export access. Do not roll back by deleting source evidence |
| 3: active reconciliation/admission facade | Reuse reviewed opening, not a new ledger; requires accepted evidence/identity contract | opening_import/validation/obligations/continuation; explicit identity resolver; portability orchestration | Prefer no schema beyond accepted link; any new operation needs its own evidence contract | Exact P/I/F, original dates, continuation and custody; unknown != zero; shared source identity excludes complete/opening double activation; current full-release/reversal remains; unsupported repayment/renewal/auction denied | Stop new admissions; preserve admitted origins and normal supported servicing; no delete/reset of later actions |
| 4: live backfill and evidence enrichment | Add older facts without reposting admitted debt; after slice 3 and owner semantics | Evidence revision/review services; origin links; numbering/collision review | Possibly append-only evidence associations, no mutation of accepted financial origins | New source snapshot after native servicing produces conflict/review, not overwrite; earlier payments already covered by opening never repost; no number rewind; multiple sources and same-name Parties remain distinct | Disable enrichment writes; retain earlier evidence and operational graph |
| 5: exit export and coverage | Resolve F04/F06/F12; can begin permission-only sub-slice after 0A without waiting for archive delivery | Loans export access, control-plane recovery routes, capability report; later wider semantic profiles and package writer | Permission slice no schema. Wider archive may need stable identities/artifact inventory | Export-only allowed roles; archived/suspended policy cases through explicit recovery; no import/settings grant required merely for authorized export; every native action yields full export or truthful named coverage limitation; collector/appraisal/custody evidence tests | Retain existing strict per-loan exporter; roll back new packaging only, keep delivered archive readable |
| 6: remove duplication by measured need | Consolidate after parity/capability tests exist | Identity resolver, import/export private cross-imports, shared pure reconciliation; selected renewal helpers if independently justified | No planned schema. Refactor only proven duplication | Native/complete/opening golden parity, permission-before-replay, fault rollback, same-Workspace wrong-loan SQL guards, no cycles or side effects in preview | Revert bounded module change; no state/data transformation |

## Current implementation boundary

Generic import containment, classification, the frozen opening v1 boundary and
the historical-only archive slice are complete locally.
This does not authorize slice 3's active reconciliation/admission facade or any
real-source activation. The new archive must remain independently readable and
exportable without creating an operational loan.

## Acceptance cases by test family

On September 19 the owner authorized closed-loan archival in the same test
Workspace 10. All 26,474 source-reported closed loans from the September 12 jcl
dump were retained through the existing archive service. Every document, source
identity, digest and review reconciled, with no held archive candidates. Unknown
facts and 16 date-order contradictions remain explicit; no settlement or original
principal was inferred. Representative search/detail/export/retry checks passed,
and full operational-row fingerprints remained unchanged (2,101 operational loans).
Evidence: `outputs/jcl-closed-archive-import-20260919/`. No code/schema changes.

The owner subsequently authorized the full eligible rehearsal in Workspace 10.
On September 17, 2,094 additional openings committed in bounded groups, bringing
the total to 2,101 active loans. Every source/borrower binding and opening balance
reconciled: principal 41,625,093 and interest 3,968,680 at September 12, plus
146,636 projected interest through September 17. There are 362 unique held loans
(payment history, inactive borrowers, nonpositive valuations or invalid descriptions).
Existing jcl-13 records remain unchanged. Evidence and completion marker are in
`outputs/jcl-full-rehearsal-20260917/`. Bounded staging reuses one fresh extraction
for at most 20 loans while retaining per-loan preview, signed approval and commit;
all 16 staging tests pass. This rehearsal does not admit the held cases or settle
live cutover evidence, and does not claim full general-purpose bulk migration.

On September 17 the owner rejected the zero-interest balance match and confirmed
all calculated interest after the upfront first month remains unpaid. A corrected
seven-loan sample is now ACTIVE in the previously empty operational Workspace 10,
`test-jcl-current-20260912`, with 13,682 unpaid interest and 58,230 principal.
Source matching, retry, continuation boundaries, release rollback, export and
persisted UI balance checks passed. jcl-13's earlier sample and subsequent C07432
release remain unchanged. Evidence: `outputs/jcl-corrected-rehearsal-20260917/`.
The earlier zero-interest checks below prove the original simulation only, not
parity with the user's intended source balances. Production reconciliation and
the held payment cases remain outside this corrected sample.

Following owner review of C07432, the user authorized a small varied rehearsal
batch. Six additional loans (R05856, B03795, C00045, RA00532, C03982, C04872) are
ACTIVE in jcl-13, seven total. Original principal, zero unpaid interest/fees,
settled interest through September 12 and simulated custody are explicit rehearsal
assumptions. Source matching, retry, cutover/anniversary continuation, rollback-only
release, export and persisted rendered-detail checks passed for all six. B03343
remains held for nonpositive source valuation; payment/inactive-borrower holds remain.
Evidence: `outputs/jcl13-batch-rehearsal-20260915/verification.json`. The remaining
2,456 candidates are unimported; wider facade and production admission remain
separate from this authorized use of the existing one-loan bridge.

The user subsequently confirmed rehearsal scope on 2026-09-15. One source-matched
opening, C07432 (loan 23), is ACTIVE in jcl-13 using explicitly simulated September
12 balances (12,000 principal, zero unpaid interest/fees), first-month paid coverage
and custody. No verified production claims are inferred. Retry, persisted state,
collection calculation, rollback-only full release, export and rendered list/detail
checks passed. Evidence: `outputs/jcl13-opening-rehearsal-20260915/verification.json`.
The first loan attempt rolled back due to a script assertion expecting RELEASED
instead of CLOSED; corrected verification and admission completed successfully.
The remaining 2,462 candidates are not admitted. This uses the existing one-loan
bridge and does not implement or authorize the wider slice 3 facade.

Active preparation advanced on 2026-09-15: all 2,463 current jcl candidates are
bound to imported Parties in jcl-13; two inactive legacy licences and seven reserved
inactive series are created. C07432 is the proposed first opening pilot. The
private handoff is `outputs/jcl13-active-preparation-20260915/review.html`.
At that preparation checkpoint, scope and opening facts remained unanswered.
No financial rows were created then; the 11 payment cases and source
inactive borrower cases remain visible for separate review.

Party prerequisite completed in jcl-13 on 2026-09-15 under user-delegated conflict
resolution: 5,880 Parties, 1,893 phones and 3,992 addresses committed through
existing services. Source IDs remain separate across matching names; one unknown
relationship and two conflicting default-address flags preserve raw evidence
without invented facts. All source/parent bindings and completed review views
verified. Evidence: `outputs/jcl13-party-import-20260915/verification.json`.
No active-loan admission was performed; jsk-13 and lsp-13 Party imports remain
separate future work.

Pilot staging completed 2026-09-15 after the user selected punba: Workspaces 11
(`jcl-13`), 12 (`jsk-13`) and 13 (`lsp-13`) each contain three source-matched
STAGED archive batches. The two archive migrations are now applied to the main
database. All nine review views rendered, persisted hashes and forced-RLS
visibility were checked, and no evidence was accepted or financial rows created.
The review handoff is `outputs/archive-pilots-staged-20260915/review.html`.
The next step is explicit review/acceptance of these nine historical claims;
active financial admission and bulk acceptance remain outside this pilot.

Destination clarification (2026-09-13): user selected `jcl-13`, `jsk-13`, and
`lsp-13`, with lsp explicitly meaning source `lakshmipawnbroker`. All three source
reports and nine proposed pilot files are prepared in the private combined review
`outputs/archive-pilots-20260913/review.html`. Workspace creation awaits owner
selection between the existing-business and migration-test accounts. Nothing has
been staged or accepted. The jcl source weight attestation remains source-scoped.

Exception review follow-up (2026-09-13): revision 2 resolves all 121 description
holds through provenance-recorded whitespace mapping, retaining raw text. All
26,474 released candidates are schema-valid. The private
`outputs/jcl-closed-archive-review-20260913-v2/case-review.html` lists 24 loans with
raw timestamp findings and proposes R00001, R02505 and A00049 as a three-record
pilot without source ERRORs or timeline findings. Destination and acceptance
remain pending; zero records staged or accepted. This supersedes the initial
held-count result below while preserving that report as evidence.

Offline source preparation is also complete locally (2026-09-13): the current
`jcl` snapshot yields 26,353 schema-valid archive candidates and 121 held documents.
The private report is `outputs/jcl-closed-archive-preview-20260913/review.html`.
All extracted rows remain retained, and database queries were blocked throughout
preparation. Nothing was accepted or activated. Next is review of held collateral
and source contradictions, followed by a selected historical-retention pilot;
this does not authorize the active-admission facade or bulk acceptance.

| Family | Existing evidence | Add when corresponding slice is approved |
| --- | --- | --- |
| Native lifecycle | Loans test_pawn_lifecycle_service, test_pawn_economics_service, test_repayment_allocation, test_release_concessions | Every historical tolerance remains denied where native approval requires evidence; no new quote/photo/tenure bypass |
| Complete historical | portability test_loan_history | Source policy disagreement preserves evidence under archive mode while operational restore still rejects; no fake operator required by archive |
| Incomplete historical | opening validation/evidence-gap tests | Closed fact with no payments; unknown dates/rates; aggregate collateral; retained contradictory claims; no financial rows |
| Reconciliation | test_opening_import, test_opening_obligations, test_opening_continuation, test_opening_release | Capability-specific admission and immutable review decision, accepted archive → one opening, failure at each late write point |
| Canonical contract | published schema/examples and parser tests | Schema does not change with ORM refactor; profile migrations preserve precision/unknownness/aliases; extension behavior explicit |
| Round-trip | complete history and opening restore suites | Native release collector/appraisal history; reversals/concessions/storage/funding/renewal coverage report; repeated restore ancestry bounds; retained historical claim round-trip |
| RLS/auth | test_history_evidence_guards; portability RLS tests | Accepted archive and admission links restricted-role INSERT/UPDATE/DELETE, same-Workspace wrong parent, revoked access before retry; export recovery matrix |
| Idempotency | existing source identity/approval/replay tests | Multiple source snapshots share one financial origin; same cash amount/date with distinct IDs survives; no duplicate admission under concurrent requests |
| Collisions/live use | numbering and history_setup tests | Native creation racing backfill number checks/reservations; source numbers across licences/namespaces; successor ranges and exhausted series |
| Temporal | month-end/offset/opening coverage tests | Date-only versus time-known source claims; source timezone; >10-year archive accepted; current-source conflict after later servicing |
| Deletion/retention | batch cancellation, child tombstones, immutable evidence tests | Accepted archive survives stage cancellation; actor erasure behavior explicit; full export manifest before any future approved erasure |
| Side effects/performance | rollback previews, risk invalidation tests | No inline provider/filesystem effects in preview; bounded Workspace lock durations measured on representative batches before throughput claims |

## Decisions needed at review, not repeated migration questions

Approve or revise the architecture boundary and priority of F01. Select the first
historical archive profile and whether normalized status is an assertion alongside
raw source status. Decide desired discoverability of historical-only records and
role policy for their acceptance/export. Confirm the intended export guarantee
(financial profile versus complete evidence archive) before widening formats.

Do not re-ask settled jcl source-weight, missing licence-date, pilot number, grace
or owner-provided missing-maturity instructions. Current source balances, selected
destination, final cutover and activation remain separate unapproved migration
decisions under [the first-import plan](first-legacy-import.md). This audit does
not certify or supersede them.
