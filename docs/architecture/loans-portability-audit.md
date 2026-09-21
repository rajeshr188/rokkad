---
status: audit
owner: project
updated: 2026-09-12
tags: [loans, architecture, portability, audit]
---

# Loans architecture and portability audit

## Conclusion and scope

Loans is appropriately strict for an operational pawn-lending system, but its
accepted import representations are too narrow to represent all legitimate
external history. The largest gap is **accepted historical evidence without
operational admission**. A released loan with unknown repayments has no supported
destination today. Do not solve that by constructing fictional disbursal,
approval, accrual or settlement records.

The repository already distinguishes complete-history restoration from a reviewed
opening position. Extend that distinction rather than rewrite Loans or add
import-related business states. The recommended target is **retained source facts,
explicit reconciliation/admission, and the existing operational aggregate**, with
versioned exchange contracts between them. The recommendation is proposed, not an
accepted ADR or authorization to implement.

Audit date: 2026-09-12. Base commit: `92aa3600`; the subject is the **working tree**,
including substantial pre-existing modified and untracked Loans/portability code.
Commit-only inspection would miss most of the opening subsystem. No application
behavior, schema, migration, configuration or business data is changed by this
audit. Test execution uses test settings; validation details are recorded below.

Source snapshot fingerprint for the 375 Python files under Loans/data_portability:
`d88aad7bd8d808f87df30f4378dedf970a261cc7682c017333302a0b2086f920`.
Method: sort repository-relative paths, feed UTF-8 path + NUL + raw SHA-256 digest
of each file to an aggregate SHA-256. Measurements were rechecked at closeout.
Concurrent migration-preparation documentation advanced during the audit; its
Workspace 10 preparation and approvals are separate work, not this audit's actions.

Read this package in order:

1. This current-architecture audit and prioritized findings.
2. [Lifecycle and dependency map](../flows/loans-lifecycle-and-portability.md).
3. [Classified constraints and applicability matrix](../domain/loans-portability-constraints.md).
4. [Portability friction, identity, time and examples](loans-portability-friction.md).
5. [Alternatives and proposed target](loans-portability-target.md).
6. [Incremental implementation proposal](../plans/loans-portability-audit-followup.md).
7. [Declared schema inventory](../implementation/loans-portability-schema-inventory.md).

## Critical finding: a second write path still exists

Follow-up (2026-09-13): F01's generic Loans write path is now blocked locally by
the owner-authorized [containment slice](../adr/2026-09-13-generic-loans-import-containment.md).
The finding below records the audited pre-fix behavior. Wider generic-tool/export
authorization and later historical-admission architecture remain separate work.

Containment validation also characterized an existing non-Loans generic-create
limitation: ModelResource attempts a sequence reset that the restricted role
denies. The transaction rolls back; runtime privileges were not broadened.
See the containment decision for the intentionally preserved boundary.

**F01 / P0: the legacy generic model importer remains a reachable alternative to
domain admission.** This is an integrity/authorization design defect, not a claim
of a demonstrated cross-Workspace breach.

Evidence chain:

- [Shared URLs](../../django_project/shared_urlpatterns.py) retain
  `workspace_slug_data_tools_import`; [slug_routes.py](../../apps/orgs/web/slug_routes.py)
  dispatches it to the old importer. The new portability URL set does not consume
  the generic `import/` path.
- [ImportForm and model enumeration](../../apps/tenant_apps/utils/importing/forms.py)
  expose models from all four business apps, including Loans.
- [Generic importer](../../apps/tenant_apps/utils/importing/views.py),
  `import_data` / `_import_resource_for_model`, falls back to
  `resources.modelresource_factory(model=model)`, then imports directly through
  the model resource. There is no Loans lifecycle command, reconciliation,
  preview approval or immutable source binding in that path.
- `owner_or_admin_required` checks membership role names. It does not require
  current `data.import`, `loan.approve`, `loan.repay`, etc. grants.
- [PawnLoan.save/clean](../../apps/tenant_apps/loans/models/core.py) protect some
  relationships and product immutability, but do not enforce the lifecycle graph
  or require the evidence implied by `ACTIVE`/`CLOSED`.
- [Registry tests](../../apps/tenant_apps/utils/importing/tests.py) explicitly
  assert that `PawnLoan` is selectable. The
  [evidence guard test](../../apps/tenant_apps/loans/tests/test_history_evidence_guards.py),
  `test_append_reversal_does_not_mutate_original_and_loans_remain_mutable`,
  deliberately preserves aggregate mutability while protecting event rows.

Consequently the architecture allows a role-qualified generic importer to attempt
changes that command authorization and lifecycle validation would reject. RLS and
FK/trigger constraints still apply; those are not sufficient to reconstruct
missing financial causality. Exact accepted payloads and installed resource
behavior need a dedicated HTTP characterization before remediation; no exploit
against customer data was attempted. Do not broaden model lockdown as a shortcut.
First proposed security slice: deny financial models on the generic import route
and converge on explicit action authorization, preserving needed nonfinancial
compatibility. This audit only documents the defect.

## What exists today

Loans is an operational aggregate with immutable evidence and derived projections,
not a general ledger and not a pure event-sourced application. `PawnLoan` and
collateral maintain mutable current state. Financial events, allocation lines,
snapshots and custody records explain completed operations. Reads fold those
records; they do not obtain authoritative debt from an editable total.

Static measurements across current source:

| Measurement | Loans | data_portability |
| --- | ---: | ---: |
| Python files, including tests/migrations | 299 | 76 |
| Physical Python lines, including tests/comments | 64,428 | 10,747 |
| `test_*.py` files | 81 | 21 |
| Syntactically declared `test_*` functions/methods | 691 | 300 |

The model inventory contains 87 concrete/abstract declarations, 871 directly
declared fields and 170 named constraint declarations across both apps. These are
source counts, not independent rules, test pass counts or verified deployed tables.
Largest Loans services: renewal 1,453 lines, funding 1,333, interest 649, release
624, auctions 584. Size motivates navigation and characterization, not a rewrite.

| Layer | Implementation and responsibility | Architectural observation |
| --- | --- | --- |
| Vocabulary/calculation | [domain](../../apps/tenant_apps/loans/domain/vocabulary.py), interest, schedules, collateral economics, LTV, delinquency | Five business states; most operational conditions are derived. Pure calculations are reusable. |
| Aggregate/evidence | [models/core.py](../../apps/tenant_apps/loans/models/core.py), products, obligations, regulatory, appraisals, history | Required setup/Party relations; evidence plus mutable projections, not one status table. |
| Commands | pawn_drafts, pawn_lifecycle, pawn_disbursal, pawn_repayment, pawn_release, pawn_renewals, pawn_auctions, pawn_reversal under [services](../../apps/tenant_apps/loans/services/__init__.py) | Commands own actor checks, locking, calculations, evidence and transitions. Internal event storage is not a staff API. |
| Read models | [balances](../../apps/tenant_apps/loans/selectors/balances.py), obligation_state, exposure, collateral_valuation, delinquency, risk_portfolio | Recorded debt, contractual obligations, projected exposure and collateral coverage are deliberately different answers. |
| UI | [forms.py](../../apps/tenant_apps/loans/forms.py), web feature modules, [urls.py](../../apps/tenant_apps/loans/urls.py), templates | Forms have Workspace-filtered choices and native completeness rules; views call services. SIMPLE workflow combines approval/disbursal without removing evidence. |
| Complete restore | [history_contract](../../apps/tenant_apps/loans/services/history_contract.py), history_setup, history_import, history_export | Two JSONL records per loan. Rebuilds evidenced history with current supported calculation implementations; no live clock replay or live number allocation. |
| Opening migration | [opening_validation](../../apps/tenant_apps/loans/services/opening_validation.py), opening_import, opening_evidence, opening_continuation, opening_obligations, opening_servicing | One explicit migration event initializes reviewed balances. Earlier history stays unavailable. Limited servicing is intentional. |
| Opening restore | [opening_export](../../apps/tenant_apps/loans/services/opening_export.py), [opening_restore](../../apps/tenant_apps/loans/services/opening_restore.py) | Rebuilds dated supported servicing and compares semantic graphs; source-local IDs are mapped, never copied as destination FKs. |
| Party portability | parsers, xlsx, mapping, normalization, services, children, bundles under [data_portability](../../apps/tenant_apps/data_portability/services.py) | Bounded CSV/XLSX/JSONL and six Party profiles; not a generic Loans spreadsheet importer. |
| Source adapter | [legacy_dump](../../apps/tenant_apps/data_portability/legacy_dump.py), legacy_preview, legacy_owner_rules, legacy_reconciliation, legacy_opening | Parses selected source data, retains hashes/raw facts, applies explicit source-specific interpretation, prepares reviewed openings. |
| Staging/approval | [loan_history](../../apps/tenant_apps/data_portability/loan_history.py), legacy_opening, LoanHistoryBatch | Signed actor/Workspace/input approval; commit revalidates under locks; preview rolls back business rows. |
| Side effects | [risk_signals](../../apps/tenant_apps/loans/risk_signals.py), notice/document services | Saves invalidate active risk snapshots in the same transaction. Financial import writers do not send historical notices or issue fictional documents. |
| Jobs | [risk_jobs](../../apps/tenant_apps/loans/services/risk_jobs.py), reassess/dispatch/integrity commands | Explicit Workspace context; bounded risk work. Capacity acceptance remains separately shelved. |
| Database enforcement | [0003 RLS](../../apps/tenant_apps/loans/migrations/0003_enable_workspace_rls.py), [0004 guards](../../apps/tenant_apps/loans/migrations/0004_database_guards.py), migrations 0006–0012 and db_guards | Important constraints live outside model Meta/clean. Migration 0008 protects 15 evidence tables; 0009 protects accepted import origins. |

No custom model manager/queryset declarations were found in the Loans model
package or data_portability models; explicit service/selector scope and forced RLS
remain important even for ordinary `.objects` access. No Loans/data_portability
admin module or dedicated REST serializer layer was found
in the inspected apps. Do not mistake that for absence of the generic ModelResource
surface above. Browser JSON endpoints, forms, schemas, management commands and
internal services are distinct entry points. Factories and fixtures principally
live in Loans tests/factories.py, portability tests/fixtures.py and test modules;
published history examples live under docs/contracts/examples.

## Entity responsibilities and mutability

Field-by-field required/optional values, precision, FKs, uniqueness and deletion
actions are in the [schema inventory](../implementation/loans-portability-schema-inventory.md).
The important semantic boundaries are:

| Entity/family | Responsibility and dependency | Lifecycle/mutation/history |
| --- | --- | --- |
| PawnLoan | Workspace, borrower Party, licence, series, frozen product version; number, original/effective starting principal, loan date, rate, tenure | DRAFT/APPROVED/ACTIVE/CANCELLED/CLOSED. Draft edits through commands; completed operations append evidence. Product FK immutable in save; whole row is not SQL-immutable. |
| PawnCollateralItem | One owning loan, UUID, description, metal, weight/purity; nullable original allocation/rate/appraisal fields | Current custody/location mutable through commands. Renewal creates a successor item with protected one-to-one lineage; physical continuity is not two simultaneous live claims. Unknown gross is supported for opening, not native approval. |
| Party | Borrower identity and optional contact/KYC children | Loan FK PROTECT. Import must bind exact source identity; names are not identity. Missing contact metadata is different from an unresolved borrower. |
| LoanLicense / LoanLicenseRevision / LoanSeries | Regulatory identity/history and register grouping | Immutable revisions; legacy reference inactive with unknown dates. Expiry blocks origination, not ordinary servicing. Series counters are separate from historical aliases. |
| LoanProduct / LoanProductVersion | Repayment shape, availability, tenor, grace, calculation contract | Versioned product; compatible active/retired versions may serve historical mapping. Historical mapping still checks original availability and tenor. |
| Approval / policy / disbursal snapshots | Frozen approval economics and gross-to-net evidence | Approval versioned; policy/disbursal one per loan. Disbursal snapshot requires approval, policy and event. An opening deliberately has no historical approval/disbursal snapshot. |
| PawnLoanEvent | Immutable financial action, effective date, fingerprint and idempotency identity | Opening/disbursal/repayment/accrual/capitalization/release/auction/renewal/reversal. Only reversal links to an original event. JSON content also needs semantic command validation. |
| InterestAccrual / lines | Recognized interest with period/tranche calculation evidence | Immutable periods and allocations. Some native zero-recognition periods can have no event, which the bounded history exporter rejects. |
| RepaymentAllocationLine / PrincipalClosingLine / PrincipalOpeningLine | Explain per-item principal movement and renewal successor basis | Immutable linked evidence; event and collateral must agree. These are not redundant loan totals. |
| RepaymentScheduleVersion / Obligation / Allocation / ScheduleChange | Contractual promise, fulfillment, termination and reversal | Versioned immutable schedule graph; current/as-of state derived. Future contractual interest need not equal currently recognized interest. |
| PawnLoanRelease / ReleaseItem / CustodyEvent | Cash settlement and actual return of specific collateral | Immutable completed evidence. Full return closes loan; public partial release currently fails explicitly. Return facts cannot be reduced to a boolean. |
| PawnLoanRenewal / items / reversal | Source settlement plus a new successor and retained/returned/additional collateral | Atomic cross-loan graph, reversible only with dependent-state checks. No supported general import/export profile. |
| PawnLoanAuction / items / reversal | Notice, auction progress, buyer/recovery and disposal | Separate auction state machine; completed recovery closes loan. Current implementation requires exact debt recovery; shortfall/surplus unsupported. |
| FundingLoan / pledge / return | External borrowing and repledged custody | Real cross-aggregate dependencies; current loan portability excludes the graph rather than discard it. |
| CollateralAppraisal / risk / monitoring | Dated reviewed valuations versus rebuildable current risk | Appraisals append; risk snapshots invalidate/recompute. Current rates do not rewrite frozen lending evidence. |
| LoanChangeLog / issued documents / media / storage / verification | Operator history, exact issued bytes, physical evidence and locations | Different retention/protection rules. Financial JSON exports are not media/issued-document archives. |
| HistoricalLoanImport | Immutable accepted source document, namespace/key, checksum, destination refs and local importer | One per loan and one financial origin per Workspace/source key. Cannot represent a historical record without PawnLoan. Changed retry is a conflict, not an update. |
| ImportBatch / ImportRow / LoanHistoryBatch | Pending mapping/review and completed import receipt | Not an accepted archive. Unfinished cancellation can clear raw/staged values; completed provenance is guarded. |

## Prioritized gap analysis

Priority denotes impact, not authorization to implement. P0 is an integrity or
security exposure; P1 blocks faithful portability; P2 concerns major maintainability;
P3 is a smaller improvement. Source-confirmed behavior and inferred impact are
distinguished explicitly.

| ID / priority | Area/current behavior | Problem and root cause | Import impact | Native impact | Recommendation / evidence |
| --- | --- | --- | --- | --- | --- |
| F01 P0 | Generic ModelResource import remains reachable | Bypasses command admission and action-grant policy; aggregate mutability is exposed as an import API | Can attempt structurally valid but semantically unsupported writes | Can attempt updates to existing loans without lifecycle service | Contain financial generic writes; characterize exact HTTP boundary. Evidence chain above. |
| F02 P1 | Only full history or reconciled active opening accepted | No durable accepted historical-fact destination without operational graph | Bare released/cancelled/auctioned history stays outside accepted product data | No need to weaken native rules | Add bounded historical-evidence acceptance, separate from activation. history_import._chronology; opening_import._document. |
| F03 P1 | Complete import recomputes economics, periods, payment ordering and schedules | A supported calculation dialect is treated as a condition of complete history admission | Legitimate external allocations/rounding cannot restore operationally | Strict financial checks correctly protect commands | Preserve discrepancies as source assertions; choose evidenced replay or reconciled opening, never fabricate. history_import.import_complete_history. |
| F04 P1 | Export reuses require_history_setup_access | Owner + ACTIVE + import/settings permissions needed even for download | No Loans recovery export for suspended/archived Workspace; export-only staff denied | Exit capability depends on unrelated write authority | Separate export policy using existing lifecycle recovery contract. history_export; opening_export._access. |
| F05 P1 | Opening exchange is FIELDS plus model-derived typing | External contract depends on `_meta.fields`, internal IDs and exact graph arrangement | Refactoring/nullability changes can change old-file acceptance | Restore writers coupled to export internals | Freeze version-owned semantic schema; retain v1 decoder. opening_restore._typed/semantic_evidence. |
| F06 P1 | History export accepts limited events, 20 items, 240 events, ten years | Ordinary supported servicing can exceed export capability; time alone can exclude an old loan | No universal export/re-import guarantee | Valid reversals, concessions, renewal/funding/storage can make a native loan unexportable by this profile | Capability/coverage report; wider profiles only with evidence contracts. history_export._export_history; history_contract; history_import._chronology. |
| F07 P1 | Setup checks original licence validity, product availability, exact grace/calculation version | Destination configuration is also asked to explain source history | Missing licence/terms require special reference or hold; closed fact needs no live product | Native origination restrictions remain justified | Historical source references separate from current servicing mapping. history_setup.preview_history_setup. |
| F08 P2 | Opening issue list is all ERROR; history errors are strings | Parser invalidity, absent evidence and operational unsupportedness share failure shape | Difficult to distinguish retainable fact from impossible activation | Harder consistent UI diagnostics | Typed issue category and operation-specific blocking, preserving every existing rejection initially. opening_validation.Review.issue; HistoryError. |
| F09 P2 | Loans imports call portability.children.parent_for; exports import portability identities | Financial domain depends on child-profile implementation; restore/export/import also cross-import private helpers | New adapters inherit Party pipeline internals | Fragile maintenance, not a proven runtime import-cycle failure | Small explicit identity resolver; public Loans admission facade. history_import/opening_import/history_export. |
| F10 P2 | Provenance comprehensive but uneven | Raw source, normalized document, reviewed rule and restore ancestry use different envelopes | No universal value-level lineage; repeated restore embeds ancestry under a 5 MiB ceiling | Operator attribution differs from historic actor claims | Common provenance semantics; bounded explicit ancestry strategy. HistoricalLoanImport; legacy_opening; opening_restore. |
| F11 P2 | Coarse Workspace lock and full rolled-back command preview | Safety depends on all invoked effects being transactional; preview consumes surrogate sequence IDs | Bulk contention and long review transactions; no measured throughput guarantee | Can contend with other Workspace setup/bundle operations | Preserve safety; measure bounded batches before narrowing locks. loan_history.preview; opening_import.preview_opening_import. |
| F12 P2 | Complete native export projects limited collector/appraisal/audit information | `collector=None` for newly exported release; full appraisal/change-log history not represented | Round-trip equality of JSON does not mean full evidence fidelity | Customer exit can omit facts outside financial profile | Declare omitted evidence explicitly; acceptance tests for evidence coverage before archive claims. history_export release branch. |
| F13 P2 | Historical docs mix delivered and proposed statements | Existing contract pages say “not implemented” beside implemented paths | Operators may choose obsolete constraints or falsely infer approval | Maintenance risk | Add current capability entry point; retain historical decisions without rewriting accepted history. rokkad-data-v1; opening-position-mvp. |
| F14 P3 | Native date/quote/photo rules are sometimes described as general loan requirements | Presentation/workflow language obscures admission distinctions | Users infer fake photos/current quotes are required for old facts | Rules themselves are useful | Describe native creation, supported restoration and historical acceptance independently. pawn_lifecycle; origination_rates. |

No cross-Workspace exploit, missing deployed trigger, or corrupted real balance was
established. The prior missing-evidence-trigger issue is already addressed in
migration 0008; do not report that historical finding as an unfixed defect.

## Essential versus accidental complexity

**Keep:** financial event immutability; fees/interest/principal separation; per-item
principal allocation where rates differ; dated recognition versus future promises;
custody distinct from debt; source/successor renewal lineage; reversals and downstream
dependency checks; immutable issued documents; frozen policy/valuation evidence;
current risk freshness; Workspace and action boundaries; idempotent admission.

**Change at boundaries:** requiring an approval/disbursal proof merely to retain a
released claim; requiring current product availability to store old source facts;
ORM-driven exchange typing; generic model import; import permissions for export;
scattered profile checks that obscure capabilities; repeated source/normalization
envelopes; historical/proposed/current documentation ambiguity.

The five business states are not excessively granular. APPROVED is meaningful even
when SIMPLE mode hides a separate screen. A repayment does not require a new stored
state; overdue, partial payment and risk are derived. Separate accrual, allocation
and custody records protect different facts. No evidence supports collapsing them
or replacing the whole model. The renewal service's size warrants bounded review,
not an unsupported claim that all its branches are accidental.

## Security, deletion and operational boundaries

New staging/evidence rows must retain direct non-null Workspace ownership, registry
coverage, forced RLS, explicit context, action authorization and restricted-role
tests. Native model `save()` checks are not a substitute for RLS; RLS is not a
substitute for admission. Imported source users never become local memberships.
Canonical source IDs never grant access to destination objects.

The offline dump path preserves selected source artifacts outside database RLS;
filesystem access/retention therefore matters independently. No access-control
acceptance for deployment storage or temporary output directories is established
by this code audit. Browser review/download wrappers use explicit Workspace routes
and private/no-store responses. Background import/restore commands must retain
their explicit Workspace/actor context and no ambient tenant inference.

Loan/source FKs generally use PROTECT; many historical actor FKs declare SET_NULL,
but evidence UPDATE guards reject actor clearing. A schema-level SET_NULL is
therefore not an erasure guarantee. Party child identities retain tombstones;
there is no equivalent complete Workspace archive/loan erasure workflow. Staging
cancellation is not accepted-evidence deletion. Preserve the existing retention
boundary; decide archival export and retention erasure together before promising
customer exit. This is an engineering observation, not legal retention advice.

## Test architecture and confidence

Tests do not exclusively overfit native workflows. Existing suites cover complete
active/closed history, exact JSON round-trips, cross-Workspace restoration, missing
evidence rejection, native servicing after import, unknown gross/valuation/licence
evidence, opening release/reversal, month-end continuation, tampering, immutable
provenance, revoked permissions and restricted-role DML.

Representative evidence: `LoanHistoryTests` in
[test_loan_history.py](../../apps/tenant_apps/data_portability/tests/test_loan_history.py);
`OpeningRestoreTests` in
[test_opening_restore.py](../../apps/tenant_apps/loans/tests/test_opening_restore.py);
[test_opening_validation.py](../../apps/tenant_apps/loans/tests/test_opening_validation.py);
[test_history_evidence_guards.py](../../apps/tenant_apps/loans/tests/test_history_evidence_guards.py).

Gaps: accepted closed facts without settlement detail; capability classification
independent of provenance; previously native export after each supported action;
collector/appraisal evidence fidelity; older profile compatibility after ORM
changes; archive recovery permissions; generic financial import denial; concurrent
backfill versus live numbering across successor ranges; source-snapshot conflict
resolution without changing accepted debt. Proposed tests are in the follow-up plan.

Focused validation on 2026-09-12: **54 tests passed in 60.485 seconds**, covering
`data_portability.tests.test_loan_history`, `loans.tests.test_opening_restore`,
`loans.tests.test_opening_validation`, `loans.tests.test_history_evidence_guards`
and `utils.importing.tests`, under `django_project.settings.test`. The measured
run used `DB_MIGRATION_NAME=rokkad_loans_audit_20260912`, yielding a separate
disposable test database. The first default-database attempt did not yield a
retained completion result and is not counted. The measured runner log reports
`OK` and database teardown; PowerShell's redirection wrapper returned 1 after
classifying Django's normal stderr progress as NativeCommandError. No test
failure is present in that log. Evidence: local `.tmp/loans-audit-tests.log`.

Source/field inventory was rechecked; 564 local links across 21 documentation
files passed. Tracked diff whitespace and new artifact whitespace/fences were
checked separately, including the generated untracked schema inventory.
No new tests or application code were added. Static inspection and this focused
run do not prove deployed migration state, whole-repository correctness,
production capacity, source balances/authenticity, or a selected live cutover.

## Direct answers to the architectural questions

1. **Over-constrained?** Operationally not in general; as the only representation
   of arbitrary history, yes. F02/F03/F07 identify the exact overreach.
2. **Fundamental versus workflow?** Ownership, reference integrity, truthful
   provenance and conservation in admitted finances are fundamental; today's
   quote, photo, approval and allocation procedures are workflow/policy.
3. **Historical blockers?** Full event/approval evidence, strict source calculation
   parity, item detail, required terms and setup availability; see the matrix.
4. **Persistence/lifecycle coupling?** Significant evidence graph coupling, but no
   universal SQL rule that every ACTIVE row has replayed the native workflow.
5. **Contract coupling?** Complete history is semantically narrower than ORM;
   opening restore explicitly depends on ORM field definitions and graph shape.
6. **Portable facts beyond workflow?** Yes; accepting a source claim must not mean
   executing or certifying its claimed historical operation.
7. **Active versus closed?** Active admission needs a reconciled opening and
   supported future calculation/custody capabilities. Closed history can be
   accepted as read-only evidence without operational debt.
8. **Admission needed?** Yes; partially implemented already. Keep it orthogonal to
   the five business states.
9. **Incomplete history?** Typed known/unknown/disputed source assertions and
   retained raw evidence; not arbitrary nullable operational aggregates.
10. **Identifiers?** Separate database key, local display number and namespace-scoped
    source identity. Preserve aliases and reserve live ranges explicitly.
11. **Provenance?** Permanent source snapshot/hash, row/key, mapping/rule versions,
    original assertions, actual importer/reviewer and append-only decisions.
12. **Calculated versus asserted?** Store both with basis/as-of; differences require
    explanation, not automatic replacement by today's engine.
13. **Lifecycle over-granularity?** No demonstrated unnecessary stored state.
    Complexity is concentrated in boundary coupling and duplicated representations.
14. **Essential complexity?** Debt recognition, obligations, tranches, custody,
    reversals, frozen evidence and tenant security.
15. **Simplify internally?** Consolidate identity/admission/export boundaries and
    capability reporting first; do not delete financial evidence entities.
16. **Tolerant input, strict operation?** Accept factual evidence separately; block
    only admission/operations whose prerequisites are unresolved.
17. **Re-import without lifecycle reconstruction?** Supported files rebuild and
    reconcile financial graphs today. An evidence archive should not replay them;
    operational restore still needs faithful materialization, not invented events.
18. **Best balance?** Existing Loans plus a small explicit historical-evidence and
    admission boundary, with stable semantic exchange profiles.
