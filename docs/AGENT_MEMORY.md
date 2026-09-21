---
status: active
owner: project
updated: 2026-09-21
tags: [agents, context, architecture]
---

# Agent Memory

Stable project understanding only. Delivery evidence belongs in [Status](STATUS.md),
selected work in [the hardening plan](plans/project-hardening.md), and shelved ideas
in [Future work](plans/future-work.md). Prior notes, including superseded decisions,
are preserved in [the historical snapshot](archive/context/2026-09-09/AGENT_MEMORY.md).

## Product and tenant foundation

Rokkad is operational pawn-lending SaaS. Supported business apps are Party, Loans,
Rates and Notify v2. General-ledger accounting/DEA, Girvi, Contact, Product and legacy
Notify are retired. Do not restore their imports or product promises. Preserve
intentional legacy redirects, 410 responses, migrations and Party `contact.*`
permission aliases until separately reviewed.

Workspace (`orgs.Company`) is the SaaS tenant; licenses and series live inside it.
PostgreSQL shared-schema forced RLS isolates directly Workspace-owned business rows.
`workspace_context()` owns transaction-local RLS context. Request identity comes
from an explicit Workspace URL/domain; `request.workspace` is authoritative.
Profile Workspace is navigation preference only. Domain/path disagreement fails
closed for everyone. Do not require Clear Workspace to manage teams or accounts.

Membership is the ordinary user/Workspace relationship. `Company.owner_id` is
canonical ownership, mirrored by Owner Membership. Runtime role grants are
Workspace-local (`WorkspaceRole`/`WorkspaceRoleGrant`); global Role identities remain
templates. Defaults seed once, never overwrite local edits. Membership, action
permissions, lifecycle, billing, entitlements and RLS are separate checks. Read
[control-plane contracts](architecture/control-plane-contracts.md) before changes.

## Production migration boundary

Linode production at `4312573fa2dca9f8bea3abd1ab84aadb5bd1e1cd` is a historical
ancestor of `rls-mvp`, but runs the former `django-tenants` schema-per-Company
deployment. Treat JCL, JSK and Lakshmi Pawn Brokers as a read-only source-to-RLS
conversion, never an in-place database upgrade or old-database restore. The local
portability baseline and Loans import migrations are committed in `a3e0e2b8`, but
are not a deployed migration tool. Rehearsal results are not proof that Linode data
was imported. Follow [the production migration design](architecture/production-tenants-to-rls-migration.md): inventory a fresh custom dump, build exact per-schema adapters,
reconcile with owner gates, then cut over from a final frozen snapshot.

The legacy source remains live while discovery and rehearsal proceed. A discovery
archive is never an incremental-import base: rehearse in isolation, freeze legacy
writes for cutover, take one final complete archive, then build the production RLS
destination from that snapshot. The 2026-09-21 discovery inventory and its
future-dated JCL loan hold are recorded in
[the Linode discovery report](implementation/linode-production-discovery-20260921.md).

## Business rules to preserve

For the seven-loan jcl rehearsal, the owner confirmed on 2026-09-17 that all
calculated interest after the upfront first month remains unpaid. The earlier
jcl-13 zero-unpaid-interest simulation is not a balance-matching baseline. Preserve
its immutable origins and C07432's subsequent release; use an isolated corrected
rehearsal. The owner subsequently authorized the full eligible cohort in test
Workspace 10 using this interest premise, retaining the seven samples and holding
payment-history, inactive-borrower and validation failures. This is not a live
migration. Do not generalize the premise to the held payment-history cases.

Opening export v1 owns its row names, types and nullable values in
`loans/services/opening_contract.py`, independently of model metadata. Keep the
published row definition and old synthetic archives compatible; model refactors
must adapt writers/exporters without changing v1. Financial graph reconciliation
and admission remain separate. See the
[wire-contract decision](adr/2026-09-13-frozen-opening-wire-contract.md).

Portability validation categories are reporting metadata, not admission policy.
Opening document reconciliation never certifies operational readiness; its separate
readiness checks remain NOT_EVALUATED. History errors preserve original messages
and blocking behavior while reporting malformed data, missing evidence, historical
inconsistency or operational readiness. Historical-only acceptance uses the separate
closed-evidence archive; classification alone never authorizes financial admission.
See the [classification decision](adr/2026-09-13-portability-validation-classification.md).

`loan-closed-evidence/1` retains source-reported closed loans in immutable,
Workspace-owned HistoricalLoanEvidence, with separate LoanArchiveBatch staging.
Unknown borrower/payment/collateral facts and contradictory claims can be retained
after explicit owner review without creating PawnLoan, Party or financial/custody
rows. Identical document retries reuse a snapshot; changed evidence appends another.
Browse requires data.view; export additionally data.export. Acceptance reuses the
owner import/setup gate. See the
[archive decision](adr/2026-09-13-historical-closed-loan-archive.md).

The jcl source licence field was decorative and its validity dates were not
recorded, per the owner (2026-09-12). Preserve its source label separately from
verified destination licence evidence; do not invent validity dates or repeatedly
ask for dates the old system never stored. For C00121, custody at the April 9
rehearsal is confirmed and grace is three days. The dumped valuation is old, not
an approved current appraisal; its date/current value remain unknown. The current
opening path now represents these explicitly. Inactive legacy licence references
retain null validity and cannot authorize new lending; optional opening setup
evidence selects that mapping. V2 UNVERIFIED valuation claims create no appraisal
or current LTV. Full settlement can return all opening collateral without using
unknown values; native/partial-release valuation checks remain. Export/restore
preserve these claims and any later first appraisal. See the
[unknown-evidence decision](adr/2026-09-12-legacy-opening-unknown-evidence.md).

For the jcl migration, the owner's latest instruction (2026-09-12) is to preserve
recorded maturity terms and use three calendar months from the original loan date
when maturity is missing. This supersedes the proposed no-fixed-date implementation.
C00121 therefore uses 2025-01-10 from its 2024-10-10 loan date. Retain the owner's
migration instruction separately from source facts; do not claim a newly supplied
date was historically recorded. Source tenure zero uses the explicit scoped owner
evidence reference; positive recorded tenure is preserved, invalid values held.
The chosen maturity participates in overdue reporting while interest keeps its
original billing anchor. See the [first-import plan](plans/first-legacy-import.md).

Loans opening v2 has an owner-authorized per-loan preview/commit command. It freezes
reviewed source/setup evidence and uses HistoricalLoanImport for shared identity
with complete history. Legacy identities include source schema; older raw-key
complete bindings remain recognized without edits. Preview rolls back all business
rows; exact-input retry never resets subsequent servicing. This is a domain
building block, not proof of source claims or production approval. Source adapter/
selection approval, missing due terms and an actual reconciled pilot remain activation gates.
See the [opening commit decision](adr/2026-09-12-authorized-opening-commit.md).
The jcl one-loan adapter now re-extracts the dump, verifies the selected source
facts and stages immutable evidence for owner browser approval. LoanHistoryBatch
has separate immutable complete-history/opening profiles; source_sha256 identifies
the inner Loans commit document and signed approval covers the complete source
wrapper plus preview. No real source activation follows automatically. The operator
prepares technical review inputs; users do not author JSON. See the
[staging decision](adr/2026-09-12-legacy-opening-staging.md).
Opening downloads use `loan-opening-export/1`, retaining the reviewed origin,
available source verification and supported servicing with earlier history declared
unavailable. A dedicated owner/operator restore now rebuilds the supported graph
through dated Loans calculations and reconciles it before commit. Public live
commands retain current-date behavior; no production clock patch or live-number
allocation is used for restore. New exports advertise restore support; old files
with the same format remain readable. Original actor/time/reference claims stay in
immutable `references.restore`; destination actors and IDs are newly bound.
An identical restore retry never resets later servicing; a different restore or an
existing ordinary opening conflicts under the shared financial-origin identity.
Complete-history upload stays separate. See the
[restore decision](adr/2026-09-12-opening-restore-reconciliation.md).

Loans owns lifecycle services and immutable disbursal, repayment, release, renewal,
auction, custody and document evidence. Correct completed work through explicit
compensating/reversal actions. Rates supplies reference values; Loans freezes used
values. Party owns borrower identity. Notify delivery never determines loan state.
See [the constitution](constitution.md) and [dependency policy](implementation/dependency-policy.md).

Authorization precedes mutation and idempotent replay. Public actor-less business
commands are denied; internal bootstrap/delivery helpers are not staff APIs.
Servicing requires explicit repay/release/accrue/capitalize grants; renewal composes
release+approve+disburse. Setup/funding administration uses workspace settings
permission. Export/document permissions are recorded in the
[action-permission review](implementation/action-permission-review.md).

`Company.loan_workflow` defaults to EXTENDED. Owners can choose SIMPLE for atomic
review/approval and disbursal while retaining both evidence records. Adding staff
never changes this mode. Use plain labels: Dashboard, New loan, Loans. "Counter"
is historical workflow shorthand, not mandatory product language. See
[workflow choice](flows/loan-workflow-choice.md) and [business setup](flows/business-setup.md).

Setup is resumable and stays accessible after completion. Select a sole usable
series/product only on unbound new forms; preserve submitted/explicit values and
fixed edit choices. Gold 2% monthly, silver 4% monthly and INR 10 document charge
are editable setup form defaults, not automatic persisted policies.

Multiple-loan release groups at most 20 current-date full releases atomically.
One payer funds settlement; each loan records its own verified collector. Signed
quotes expire after ten minutes. Reversals and original loan evidence remain
canonical. See [multiple-loan release](flows/multiple-loan-release.md).

Official document issues retain exact bytes and immutable published layout/assets.
Reprints retain the original issue; fixed-renderer recovery is explicitly authorized
and audited. See [layout/print guide](flows/loans-document-layout-operator-guide.md).
Physical phone/camera and printer acceptance remains deferred.

## Private media and cache

Party/KYC and collateral media use authorized Workspace routes; templates/widgets
must not expose business storage URLs. Reviewed private responses disable caching.
Draft-only photo deletion preserves shared renewal file lineage. Development raw
media permits only company logos and personal profile pictures; deployment bucket,
proxy/CDN privacy still needs acceptance. See [private media](implementation/private-media-access.md).

Rates has no request cache middleware or cache-writing signal. Loans reads its
Workspace facade from PostgreSQL. Redis is optional via CACHE_URL; local memory is
the default display cache. Borrower autocomplete uses signed tokens and rebuilds its
authorized queryset, without cache-stored widgets. See [cache configuration](implementation/cache-configuration.md).

## Billing and operations

Billing is global control-plane data linked to Workspace subscriptions; browser
billing actions require canonical owner/Membership or the existing platform override.
Frozen checkout/order/amount/currency evidence precedes verified captured-payment
activation. Paid access ends at end_date through the shared effective policy; reads
do not rewrite stored status. Old payment replay cannot restore expired access.

Refunds and final review decisions are immutable. Full refunds await owner decisions;
ending access is restricted to the latest current started term. Known stale payments
can be closed after verified full return without granting old terms. No refund
issuance or guessed orphan-contract restoration. See [billing flow](flows/subscription-checkout.md).

Web/workers use restricted DB credentials. Migrate only with
`python manage.py migrate --settings django_project.settings.migration`.
Tests use `--settings django_project.settings.test`; adversarial RLS DML must run
under a restricted role. New Workspace-owned tables require direct non-null
ownership, forced RLS, registry coverage and isolation tests. Container/CI runtime
startup checks role/RLS and pending migrations; it never migrates. See
[container/CI guide](implementation/container-and-ci.md) and
[testing guide](implementation/testing-and-migrations.md).

Loans operator seed/integrity/notice commands require `--workspace-id` and own their
context. Seeding/dispatch require ACTIVE; read-only integrity supports recovery.
See [operator commands](implementation/loans-operator-commands.md).

## Owner constraints and current direction

The owner requested a deep Loans/portability audit with documentation only and
explicit review before implementation. The [audit](architecture/loans-portability-audit.md)
distinguishes current operational invariants, source historical assertions and
portable contracts. It recommends separate historical acceptance and operational
admission, preserving existing Loans states/financial/RLS guards. Its target and
follow-up plan are proposals, not accepted implementation decisions. The audit
flagged the generic financial model importer as an integrity/action-authorization
exposure. The owner subsequently authorized slice 0A (2026-09-13): all Loans
models are denied by the generic import form, request handler and resource factory;
generic import requires current data.view/data.import/workspace.settings.manage
grants, matching Workspace context and ACTIVE lifecycle. Export behavior remains
separate. See the [containment decision](adr/2026-09-13-generic-loans-import-containment.md).
Historical acceptance and later admission architecture remain proposed.

The earlier dump was for testing. The owner supplied the current dump on
2026-09-12 at `C:\Users\rajes\backup_20260912_224652.sql` (custom PostgreSQL format,
SHA-256 `e33f78f3fb96e8c23a029f9b933492e02e2a2af7b27e0cf20686b178fe91a27f`).
Use the same installation namespace and jcl source identities across snapshots.
The new source has 2,463 unreleased loans and records C00121 released on 2025-01-21;
do not overwrite the earlier active pilot or invent a settlement. Five unfinished
old-source Party batches were cancelled with their artifacts preserved. Old balance
assumptions, candidate lists and number floors are superseded by the new comparison,
not by inferred financial approval. The owner authorized a fresh isolated rehearsal:
Workspace 10, `test-jcl-current-20260912`, created through the normal Workspace
creation service. This is not a selected live destination or approved cutover.
Its active-cohort preparation now has 1,093 source-linked Parties, 755 contacts,
1,104 addresses and 2,463 unapproved loan proposals, with no financial loans.
Two conflicting source default-address flags were retained in provenance while
leaving the destination default unset. See the private preparation report and Status.
The owner explicitly kept all 11 payment-bearing unreleased loans on hold until
checked. Their full-principal payments marked with release do not establish a
missing release's date or custody. Do not ask about the old 2024
freshness gap again. See the [first-import plan](plans/first-legacy-import.md).

The owner authorised the complete jcl preview, then active-batch preparation in
test Workspace 9. Preparation now includes saved legacy licence/series setup,
forward-only historical number reservations, five Party review batches and 2,446
loan proposals. Financial cohort commit remains unapproved. The ordinary Party
importer flags duplicate names even for distinct source IDs (769 old staged rows).
The new batch-specific reviewed-name command preserves source records and borrower
links without renaming or merging. It binds canonical source values, exact existing
name-match IDs and a reason to the ordinary preview/commit digest; stronger identity
conflicts remain blocked. It is not proof of distinct physical people and is not a
reusable preset. See the [decision](adr/2026-09-12-reviewed-party-name-collisions.md).
The owner also wants familiar series numbering to continue for new lending.
Reserved counters include all source loans, even released/held/skipped records;
imports preserve their own readable numbers without consuming new ones. C now
has prefix C/width 5/next 123. Legacy-reference series still cannot originate loans;
verified licence/active product and coordinated successor ranges are separate
pending setup. Do not claim numbering reservation activates lending or reassign
historical licence evidence. See the [first-import plan](plans/first-legacy-import.md).

The preview retains the incomplete-collateral exclusion rule without inventing an
age cutoff. Missing optional related-person names can be left unset in conversion
proposals while retaining raw labels; unfamiliar relationship meanings remain
held. Source IDs, original readable numbers and the existing C00121 binding must
survive future cohort processing. Cohort confirmations must not be inferred from
the single-pilot balance/custody answer.

The owner accepted C00121 as recognisable and approved the proposed monitoring
thresholds for the isolated test Workspace only (2026-09-12). Do not ask again.
Current-rate valuation at import is the owner's proposed next improvement; retain
historical source values separately and distinguish metal estimates from reviewed
appraisals. The confirmed test gold buying and selling quote is INR 15,500/g for 24K/100%.
The current appraisal service supports explicitly labelled RATE_BASED reviews
with a checked quote ID, price freshness and exact weight/purity calculation.
C00121 now has that current appraisal without rewriting its imported evidence.
See [rate-based appraisal](adr/2026-09-12-rate-based-collateral-appraisal.md).

The owner clarified that the legacy dump is a one-time migration source, not a
reason to turn portability into a separate loan product. Finish the recognisable,
operational C00121 pilot before bulk conversion or additional portability features.
Readable destination numbers can be explicitly proposed in opening setup; source
identity remains separate. Opening pages must offer supported collection commands
and explain missing evidence without suggesting unsupported native servicing.
See [pilot readiness](adr/2026-09-12-opening-pilot-operational-readiness.md).


The owner requested a first-class customer data portability architecture, with
analysis/planning first and no automatic later-phase implementation. The
[proposal](architecture/data-portability.md), [contract draft](contracts/rokkad-data-v1.md)
and [plan](plans/data-portability.md) distinguish exchange schema from persistence,
historical Loans evidence from today's operations, and partial exports from full
archives. The owner subsequently authorized the Party master slice: bounded
CSV/JSONL staging, mapping, preview, atomic create/no-op commit and partial canonical
export now live in data_portability. Five directly scoped models retain identities,
source aliases and immutable completed-row provenance; JSON issues remain on rows.
Shared Party creation keeps current forms/number allocation. Missing context and
actor permissions fail closed. See the [operator guide](flows/party-master-portability.md).
Generic data-tools remain unchanged under the owner's narrowed instruction and
must not be reused as the new pipeline; their security/allowlist review remains open.
The owner then authorized contact methods and addresses: separate child profiles
reuse staging/preview/commit/export, require exact parent source references and
Party edit permission, and retain child aliases plus deletion tombstones. Native
primary/default rules and summary synchronization remain in Party services.
Source verification claims remain provenance and do not set local verification.
The owner subsequently authorized identifiers without documents: party-identifier/1
reuses child staging/identity with native per-type uniqueness, masked values and
expiry dates. Source verification/timestamps stay provenance; metadata-bearing
identifier export fails explicitly. No local verification or Party tax-summary
updates are inferred. Party roles were subsequently authorized: party-role/1 requires
explicit source-key to active destination-type mapping for CSV/JSONL, binds the
selected definition to preview approval, and preserves native role uniqueness and
history. It does not create Party role definitions or staff permissions.
Party relationships were subsequently authorized: party-relationship/1 resolves
both explicit master references, binds and locks both endpoints, and preserves
native directional uniqueness/self-link rules. Typed identities retain both Party
identities and deletion tombstones; moved endpoints fail replay/export.
Reusable CSV mapping presets were subsequently authorized: immutable Workspace
versions copy exact mapping/default/rule configuration into matching profile/source/
header batches, then generate a fresh preview. Saving changed configurations appends
versions; earlier versions and batch approvals remain independent. Source identity,
role-type validation and commit authorization remain unchanged. Preset defaults are
private configuration, potentially containing customer data; no cross-Workspace
preset transfer or deletion is implemented. See the [preset decision](adr/2026-09-12-csv-mapping-presets.md).
Bounded XLSX input was subsequently authorized and now reuses the same pipeline
for all six Party profiles. It accepts one visible plain-values worksheet, validates
ZIP/XML limits and actual cell coordinates, and rejects formulas, external links,
hidden data and ambiguous Excel formats. Dates/precision-sensitive identifiers use
text. CSV/XLSX share source identity and matching preset semantics; canonical JSONL
schemas stay unchanged. See the [XLSX decision](adr/2026-09-12-bounded-xlsx-input.md).
The bounded six-profile `party-bundle/1` ZIP export is implemented with a manifest,
checksums and frozen schemas from one lock-stabilized snapshot. Company and bounded
Party/type/child row locks protect consistency; busy sources fail with a retry
message. This remains PARTIAL, excluding Loans and complete Workspace archives.
See the [bundle decision](adr/2026-09-12-party-export-bundle.md). ZIP validation and
atomic staging into ordinary per-profile previews are now implemented, with strict
member/schema/hash/count/reference checks and no automatic business writes. A
Workspace-bound signed receipt lists previews; master must be committed before
child revalidation and explicit role-type mapping. See the
[staging decision](adr/2026-09-12-party-bundle-staging.md). Combined dependency-aware
review and atomic commit are now implemented: existing commands run in a rolled-back
savepoint for preview, then confirmation repeats and compares the approved plan.
Only database effects/on_commit callbacks are safe in this simulated command path;
no external inline side effects may be added. Signed operator/Workspace approval
expires in one hour; immutable completed summaries retain the aggregate hash for
permission-checked replay. See the [atomic decision](adr/2026-09-12-atomic-party-bundle-commit.md).
Persistent bundle history is now implemented in ImportBundle: immutable direct
Workspace ownership and six typed nullable batch references, forced RLS and SQL
membership guards. Migration 0010 recovers older groups only from verified staging
audit evidence. Stable saved pages generate fresh membership-checked receipts;
one-hour approval expiry and operator/Workspace binding remain unchanged. Progress
is derived from batch states. See the [history decision](adr/2026-09-12-persistent-party-bundle-history.md).
Saved bundle cancellation now requires explicit confirmation and current import
access, locks the Workspace and member batches, and atomically cancels only current
READY/NEEDS_MAPPING members. Completed evidence and immutable history remain;
cancelled staged raw/canonical values and issues are cleared, while mappings and
source/audit metadata remain. No-op replay still requires access. See the
[cancellation decision](adr/2026-09-12-party-bundle-cancellation.md).
The optional history progress filter is shelved as
[FW-006](plans/future-work.md#fw-006-party-bundle-history-progress-filter).
The owner authorized the bounded Loans contract review, now recorded in the
[contract](contracts/loan-history-mvp.md) and [decision](adr/2026-09-12-loans-complete-history-mvp.md).
Selected scope is flexible partial-payment complete history with ACTIVE or full-release
CLOSED outcomes. Current-date commands cannot serve as historical replay APIs.
The missing evidence guards found during review are addressed by Loans migration
0008 across fifteen append-only tables. UPDATE/DELETE (including actor clearing)
are denied; INSERT verifies owned references and direct/parent-derived loan scope.
Mutable loan/collateral state is unchanged. See the
[guard decision](adr/2026-09-12-loans-history-evidence-guards.md).
Historical setup preparation is now available from Loans setup and Party imports.
It is an owner-authorized read-only check of original licence/date, compatible
product terms and deterministic historical number candidates. No mapping is saved,
no number is reserved and no financial import occurs. See the
[preparation flow](flows/loans-import-preparation.md). Canonical JSONL now supplies the complete-history
staging/reconciliation, explicit atomic command and export path. See the
[wire contract](contracts/loan-history-jsonl.md), [operator flow](flows/loans-history-import.md)
and [decision](adr/2026-09-12-loans-canonical-history-import.md). Loans owns immutable
source provenance and historical financial/custody writes; portability owns batches
and signed confirmation. Both new tables have direct Workspace ownership and forced
RLS. One complete loan per file supports simple-interest flexible active and fully
released history. Preview rolls back business rows; confirmed commit rechecks all
scoped mappings and native calculations. Current-date live commands are not replayed.
Loans direction includes both active and historical loans: lifecycle state is
separate from evidence completeness. Complete-history active loans do not require
an opening-position import; missing-history cutover semantics remain separately
undelivered. See the [Loans clarification](plans/data-portability.md#loans-scope-clarification-2026-09-12).
Party portability MVP feature scope is closed. History filtering is optional and
deferred. See the scope boundary
in [the delivery plan](plans/data-portability.md#mvp-scope-closeout-2026-09-12).
The owner clarified the actual initial source priorities: migrate the previous
schema-per-tenant Django production dump first, then simple customer/licence/series/
loan/release Excel registers. These need source adapters, not user-authored JSONL.
Complete history, active opening positions and limited-evidence released records
are distinct capabilities; the latter two are not implemented. The owner supplied
`tenants_workspace` commit `c9fb81bc70adafa1d942721d642bfb2b38953f41`; its read-only
review confirms optional release payments and differing calculation paths, while
its model state differs from the dump. Source loan `interest` is monthly money in
the inspected calculation path, whereas item `interestrate` is a percentage.
Preserve stored evidence and reconcile before choosing opening balances; do not
execute legacy save methods or recreate retired apps. A bounded offline
`preview_legacy_dump` command is now implemented in data_portability and exercised
against owner-selected `jcl`. It reads no destination database, uses pg_restore only
for listing/text extraction, requires an explicit source schema and stable source
namespace, and produces ignored local HTML/JSON/JSONL review artifacts. These are
not canonical import packages or accepted source bindings. All records remain not
import-ready; missing-evidence contracts and explicit destination mapping precede
financial writes. See [preview guide](flows/legacy-dump-preview.md),
[source review](implementation/legacy-dump-source-review.md) and
[actual source priorities](plans/data-portability.md#actual-source-priorities-2026-09-12).
No automatic
later-phase implementation is authorized. Opening-position Loans has a design
contract but no executable import; physical erasure remains undesigned at executable
contract level. No accounting restoration or retention period is authorized.

The owner selected preserving existing billing dates/agreed interest rules for
retained active loans. Do not reset periods or silently adopt the current interest
basis. The [opening contract draft](contracts/loan-opening-position-mvp.md) requires
approved cutover balances, remaining due obligations and original-period carry;
financial implementation remains pending. The owner tentatively suggested skipping
incomplete collateral. The preview's opt-in proposal preserves whole source graphs,
has no age cutoff and grants no import/deletion authority. It does not classify
missing payments, non-Gold/Silver metal mappings or missing photos as incomplete
collateral by themselves. Final source selection remains part of financial review.

`loan-opening-review/1` now provides offline Loans-owned document reconciliation,
fed by `preview_legacy_dump --prepare-openings` and rechecked by
`validate_loan_openings`. The source adapter leaves unknown balances/weights/due
terms/continuation empty. Passing document arithmetic never authenticates source
claims, resolves destination authorization or permits import; `import_ready` stays
false. See [review contract](contracts/loan-opening-review-v1.md). The internal
`loan-opening-evidence/1` envelope now freezes reconciled review and item mappings
on a `MIGRATION_OPENING` event. Balance/tranche readers support cutover amounts,
keep them separate from new lending and reject earlier historical queries.
The existing immutable, forced-RLS event table permits only one opening per loan;
readers reject mixed origins. This is a read foundation, not source authentication
or an importer. Generic financial posting and native accrual remain blocked for
opening loans; dedicated full release and its coupled reversal are now supported.
The explicit
[v2 checkpoint](contracts/loan-opening-review-v2.md) now supports inclusive original
anniversary collection previews for unchanged item principal. It subtracts the
reviewed cumulative baseline through cutover, not merely opening unpaid interest,
so covered amounts and aggregate rounding are preserved. Exposure uses this rule
instead of native daily projection. Owner-authorized remaining-obligation persistence
uses existing immutable schedule/obligation tables with original dates and strict
retry comparison; the delinquency selector reads reviewed grace. Full release posts
only the additional collection interest in the same transaction as the receipt,
concession, original-schedule termination and custody return. Reversal restores
all of them together. Projection and item-principal reads respect closed intervals
and later reversal. Cash interest beyond the original schedule is explicit in the
release payload, without invented due dates. Partial repayments, native monthly
accrual/capitalization, renewals and auctions remain unsupported for this origin.
Actual source approval, legacy evidence gaps, opening commit, truthful export and
cutover remain pending. See the [servicing decision](adr/2026-09-12-opening-full-release-servicing.md).
Users should not author JSON records.

The offline dump preview also supports an explicit comparison date/timezone and
representative source reconciliation JSON. The [worksheet](implementation/legacy-reconciliation-worksheet.md)
compares inspected legacy expressions without adopting either as an agreed rule.
Released payment examples are controls outside active migration. The generated Excel
worksheet captures owner review only; it is not an opening upload/approval contract.

The owner's saved worksheet answers specify monthly loan-date anniversaries
(January 10 to February 10), no separate receipts/waivers elsewhere, and release
meaning paid and closed. Preserve that closure attestation without inventing missing
payment amounts or complete historical events. The owner subsequently clarified
that a 10,000 loan at 2% issued Jan 10 has 200 interest plus 10 document charge
collected at disbursal, and Jan 20 release collects only 10,000 principal. Preserve
that already-paid first-month coverage and fee; missing payment rows do not mean
no upfront collections. For the same loan released Feb 20, the owner specified
10,200 collected at release: principal plus 200 additional interest, with the
upfront interest/fee already paid. The owner confirmed Feb 11 is the first release
date requiring 10,200: first-month coverage includes Feb 10; the full additional
200 is payable from Feb 11. Preserve that boundary without charging on Feb 10 or
waiting until the next completed month. For a Jan 31, 2026 loan, the owner confirmed
the first additional monthly charge starts March 1, so upfront coverage includes
Feb 28; the owner confirmed April 1 is the first release date requiring 10,400.
Use original-date monthly anniversaries, clamped to month-end when necessary and
restored afterward: do not permanently carry February 28 forward. Collection
increases the day after the inclusive anniversary. The offline validator's period
descriptor alone does not implement this servicing timing. Do not infer
batch-wide amounts or refunds. The owner corrected the initial 9,890 cash answer
to 9,790: the 200 upfront interest and 10 document charge are deducted from the
10,000 loan in this example. Net cash is 9,790 and principal remains 10,000.
The correction is owner-supplied, not a source-data repair. Rounding responses were
148 for the paired 148.20/148.50 question, 149 for 148.80, and 150 for 149.50.
Interpreting the first answer as covering both, these match nearest-whole-rupee
HALF_EVEN, consistent with the old Decimal round(). Preserve these cases; do not
infer per-item/per-period aggregation or fractional-payment rules from those
examples alone. The owner subsequently clarified that they may collect 300 or
290 and accept a 50-rupee shortfall as interest lost; exact fractional rounding
should not block preparation. Use a deterministic rehearsal baseline (sum item
monthly charges, multiply by additional months, HALF_EVEN-round once), distinct
from actual negotiated collections. This is not an automatic 50-rupee tolerance
or principal waiver. Missing receipts/losses remain unknown, including for closed
legacy loans. Single-loan full release now supports explicit interest concessions:
cash plus concession equals total due, principal/capitalized principal/fees stay
fully collectible, and positive concessions require a reason plus existing
Workspace administration and release permissions. Immutable release event values
carry interest paid and interest conceded separately; ordinary reversal restores
both and replay checks all submitted details. The form, release detail and memo
show the concession. No additional table or migration; `loan-history/1` explicitly
rejects concession histories. Batch release, partial repayment and renewal have
no concession extension. Operational migration import and remaining legacy mapping remain pending;
see the [first-import plan](plans/first-legacy-import.md) and
[collection decision](adr/2026-09-12-legacy-collection-estimates-and-concessions.md).
Bronze is a distinct supported Loans metal; no silent OTHER mapping is approved. The owner corrected the initial weight answer: legacy item weight is
NET weight excluding stones/non-metal parts. This supersedes the earlier gross
interpretation. Do not deduct stones again or equate net weight with pure-metal
weight; source purity is separate. Gross weight remains unknown and must not be
invented by copying net weight. The explicit `jcl-owner/1` offline profile now maps
source weight to candidate net weight with the owner evidence reference, restricted
to namespace `6ca968d6-2647-4dbb-8e39-24f0c1a12ed6` and tenant `jcl`; generic
preparation still leaves both weights unknown. Loans owns the pure
`original-anniversary-upfront-inclusive/1` collection calculator. It supports
unchanged principal and whole-rupee monthly charges; version 1 retains its
fractional hold. Explicit `jcl-owner/2` uses calculation version 2 for aggregate
rounding, preserving unrounded values and separate unknown collection/loss fields.
The April 9 rehearsal now yields 2,447 collection illustrations and one source-error
hold among 2,448 active candidates. The earlier 1,700 results remain unchanged.
These are not accounting accruals, certified opening balances or
servicing activation. Opening review v2 and the destination model now retain all
2,470 gross weights as unknown, with required net/purity/evidence; seven Bronze
items map explicitly. Native draft forms and approval still require gross weight
(`blank=False`); known weights retain their SQL positivity/order checks. Explicit
`jcl-owner/2` emits v2 review candidates, leaving financial/destination approval
pending. See the [collateral decision](adr/2026-09-12-legacy-collateral-evidence.md).
Brief "ok" answers
do not supply missing maturity/grace or corrected R07743 balances. Explain technical
terms and obtain remaining rules through concrete business examples. See the
[recorded responses](implementation/legacy-reconciliation-worksheet.md#owner-responses-received-2026-09-12).

The owner approved the bilingual Rokkad / रोक्कड़ logo with forest teal, gold,
and ivory. Shared product branding lives in `components/brand.html` and
`static/images/brand/`; preserve Workspace and issued-document identities.
See [branding](implementation/branding.md).

Development data is experimental; do not infer permission to alter production.
Public env examples contain placeholders only; never print or commit secrets.
The owner confirmed the historical OAuth credential was rotated/deleted; sanitization
was published with the access/media checkpoint. Historical Git cleanup is separate.

FW-001 optional owner-configurable license scope remains shelved pending fresh
review and explicit approval. Do not infer assigned-license or creator-only access.
FW-002 Razorpay setup/test-mode acceptance is shelved because setup has not started.
Do not request provider keys or run provider setup during other work. Acceptance is
still required before real paid onboarding. Neither item resumes from "proceed" on
unrelated cleanup.

R08/R09/R10 cleanup is complete: current docs are separated from history, tour
choices use current product names and preserve old saved answers, and six unused
schema-tenancy settings are removed. The tracked-source AST import guard replaces
the DEA facade guard; migrations/archives and intentional compatibility remain.
R13 removed four unused packages (Viewflow, Slick Reporting, activity-stream and
extensions) and 14 unreachable legacy templates; compatibility routes remain.
See [reachability evidence](implementation/dependency-template-cleanup.md).
Dashboard payment queues explicitly warn when schedule-review loans are excluded.
The unused exported monetary summary reports unavailable totals as None with a
count/completeness flag and requires matching Workspace context.
The business dashboard now uses a separate overview selector: customer/active-loan
counts, current recorded principal/interest, and period-filtered ordinary issues,
new-loan net cash and separate renewal counts. It reuses the canonical event fold
with batched reads, without monitoring refresh. Invalid evidence makes whole money
totals unavailable. Period controls affect activity only; customer/portfolio cards
remain current. See [dashboard definitions](flows/business-dashboard.md).
Dashboard schedule reads are batched per Workspace/date and share the canonical
termination predicate and obligation fold; no persistent cache.
All 136 canonical Loans routes use named workspace_loans adapters. Templates,
redirects, HTMX targets, checklist and borrower-history links explicitly carry the
Workspace. Old mapped-domain routes and named aliases remain available. The old
Loans dispatcher name is only a URL-building compatibility fallback that rejects
unknown paths; it never dispatches views or rewrites responses. New collateral and
storage labels encode scoped QR URLs; old mapped-domain scan links remain valid.
See [routing migration](implementation/loans-workspace-routing.md).
The two Loans setup-link failures were incomplete fixtures: readiness correctly
checks numbering before economics and borrowers. Fixtures now cover each stage.
The Loans views portion of R12 is complete: views.py is a compatibility import
file; feature handlers live in web/. Shared preview assets and loan read helpers
have small dedicated modules. Preserve decorated public imports and scoped routes;
feature modules must not import views.py. Test mocks patch the owning module.
See [module map](implementation/loans-view-organization.md). No business rules changed.
The orgs views portion of R12 is also complete: views.py contains compatibility
imports; account/preferences, slug adapters, workspace settings, role editing,
team/invitations, lifecycle and navigation have dedicated web modules. Shared
access helpers retain the existing policy. All retirement aliases remain; two
unrouted/uncalled backup view classes were removed. See the
[orgs module map](implementation/orgs-view-organization.md). Feature modules must
not import the facade. Model/form/renewal-service review remains separate; avoid
splits solely for size, speculative abstractions and blanket package upgrades.
Document layout, overlay, asset and print-profile forms now live in
loans/web/document_forms.py. loans/forms.py retains their public class imports;
document handlers use the owning module. Preserve fields, validation and scoped
assignment querysets when organizing other form families.
License creation, renewal and series setup forms live in loans/web/license_forms.py;
forms.py preserves their public imports and license_setup.py uses the owning module.
Economic, fee and monitoring setup forms live in loans/web/economic_forms.py;
forms.py preserves their public imports and economic_setup.py uses the owning module.
Form organization preserves policy scope choices, Workspace filtering and starter
defaults; calculations and persistence remain in existing services.
The eight funding forms live in loans/web/funding_forms.py; forms.py preserves
their public imports and funding read/action handlers use the owning module.
Keep eligible collateral, lender selection, confirmation words and request keys
unchanged during organization work; funding services still own lifecycle changes.
The five storage/physical-verification forms live in loans/web/custody_forms.py;
forms.py preserves their public imports and custody handlers use the owning module.
Preserve Workspace/location filtering and resolution inputs. Intake and lifecycle
forms and their shared formsets remain together pending a concrete need to move them.
Rates/appraisal review now drives the next increments. Lending setup shows actual
usable quotes; a source alone is not quote readiness. New/edit loan price preflight
uses the selected series/policy/date/metals and preserves the current form/files
when missing quotes require a Rates detour. Gold-only and appraisal-only loans
must not require unrelated quotes. Commands retain final validation. Quote ages
are displayed. The owner selected same-day quotes at new-loan approval on
2026-09-12, for methods that consume Rates. Approval/disbursal enforcement and
frozen quote provenance are implemented locally. The first version uses today's
loan/disbursal dates as the recommended implementation assumption; historical
entry has no separately confirmed owner contract. Appraisal-only dates stay
unchanged. Changed/stale or missing legacy market evidence requires reapproval;
completed replay preserves evidence after authorization. See the
[decision](adr/2026-09-12-origination-quote-freshness.md) and
[origination review](implementation/origination-rate-freshness-review.md).
Do not silently change approved economics or reuse monitoring-age limits. Complete
monitoring and worker capacity are described below; see
[review](implementation/rates-appraisal-monitoring-review.md).
Rates quotes are immutable evidence: operator effective time is distinct from entry
time, corrections/withdrawals append actor/reason-linked records, and referenced
sources cannot be deleted. Source snapshots preserve recorded metadata. Use the
authorized Rates commands, not model updates or admin edits. Loans selects the
latest applicable INR pure-metal buying price per gram across sources with explicit
effective/recorded/ID ordering; `24k` remains the compatible pure-metal key, labelled
Pure metal for gold and silver. Historical lookups use current corrected knowledge;
completed loan evidence remains frozen. See [quote decision](adr/2026-09-11-rate-quote-evidence.md).
Current collateral monitoring enforces the effective monitoring policy's quote and
appraisal age limits, inclusively by local calendar date (zero means same-day).
Only evidence required by the frozen valuation method blocks coverage; stale or
missing required evidence is unknown. Active held collateral can receive a new
current-time appraisal through the authorized reassessment service, requiring
data.view/data.edit/loan.approve, method/reference/reason and the reviewed version.
It appends immutable evidence with quote context and marks its risk snapshot stale
within the transaction. Original loan/draft evidence stays unchanged; history is
readable with data.view. See [reassessment](flows/collateral-reassessment.md).

Loan health starts from all active Workspace loans, including unassessed ones.
Only today's successful V3 projection is current; reads derive outdated status.
V3 copies canonical projected interest, recorded total due and integrity findings
into existing assessment provenance for dashboard financial-health totals. Old
contracts need one ordinary bounded refresh, without a schema migration. Financial
and collateral coverage completeness are checked separately; unknown coverage can
coexist with usable financial evidence. Per-loan shortfalls are summed without
offsetting surplus on other loans. See the
[dashboard evidence decision](adr/2026-09-12-dashboard-assessment-financial-evidence.md).
Unknown collateral coverage is separate from assessment freshness and payment
performance. Missing current monetary assessments make whole-portfolio totals
unavailable. Source invalidation stays inside its RLS transaction; existing ERROR
projections remain errors (and retry candidates) until a successful refresh.
Monitoring policies amend through immutable, actor/reason-linked successors;
old values/end dates remain unchanged, same-scope precedence uses effective date
then version. Amendments cannot be backdated; original loan terms stay frozen.
The existing reassessment command supports explicit-Workspace bounded repeated
passes, oldest attempts first, under the restricted runtime role and ACTIVE
lifecycle. Optional Compose wiring does not itself start a worker. See
[loan health](flows/loan-health-monitoring.md) and
[monitoring decision](adr/2026-09-11-complete-loan-monitoring.md).

Launch sizing supplied by the owner: 30-100 loans processed per organization/day,
3,000-10,000 active loans per organization, and at least 100 organizations. The
worker is not capacity-validated for this
300,000-1,000,000-active-loan baseline. Correctness tests are not load acceptance.
Prioritize the [capacity review](implementation/rates-appraisal-monitoring-review.md#launch-capacity-requirements-and-review-2026-09-11)
before production claims or simply increasing batch sizes. Closed-loan monitoring
cleanup is implemented; realistic multi-Workspace load acceptance remains open.
The owner shelved further large-scale monitoring tests until better representative
hardware is available (FW-004). Do not automatically restart long local runs.
The one-hour target remains unproven; preserve measured findings for resumption.
See [the shelved work](plans/future-work.md#fw-004-launch-scale-loan-monitoring-capacity).

Closed loans keep their financial and monitoring evidence, but leave live health
calculations, source invalidation, active alert lists and background assessment.
Refresh rechecks state under the loan lock, including its error path. Reversing a
release to ACTIVE invalidates the saved assessment and resumes normal selection.

The monitoring command owns per-loan transactions through `risk_jobs`; it must not
run inside a caller's transaction/context. Candidate selection is bounded and
advisory; each loan is rechecked/locked through calculation and commit. Explicit
Workspace IDs receive round-robin turns. Successful rounds use a short busy pause;
empty/error-only rounds use the longer repeat interval. No Redis/queue or tenant
enumeration is introduced. See [worker turns](adr/2026-09-11-monitoring-worker-turns.md).

Single-schedule obligation reads now prefetch date-filtered allocations in two
queries and use the existing fold. Keep reversal effective-date filtering and
integrity findings unchanged. Mixed benchmarks are synthetic evidence, not a
production distribution or launch SLA.

Owner-selected monitoring launch acceptance target: all affected active loans
receive an updated health assessment within one hour of a metal-price change.
This is a target to load-test, not an established SLA. Closed loans are excluded;
individual authorized refresh remains available. Full-platform capacity remains
unproven until the 100-Workspace workload meets this target alongside servicing.

Health reassessment follows source changes and daily date rollover; worker polling
is not an hourly recalculation requirement for already-current loans. Operational
performance uses oldest unpaid contractual obligation DPD, with default Watch >=1
and Substandard >=90, independently of collateral coverage. This is not a formal
regulatory NPA engine; lender-specific classification/cure/reporting review is
captured as FW-003, unscheduled and not authorized by the capacity task. See
[the explanation](flows/loan-health-monitoring.md#payment-performance-and-the-npa-distinction).
