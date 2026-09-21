---
status: active
owner: project
updated: 2026-09-12
tags: [plans, portability, migration]
---

# Incremental data portability delivery plan

## Actual source priorities (2026-09-12)

Latest source bridge checkpoint: one reviewed jcl opening can now be verified
against a fresh read-only dump extraction, staged by the operator and approved by
the owner in the browser. Existing staging gains an immutable opening profile;
complete-history routes stay separate. No real loan was staged or imported.
Opening evidence download is now implemented as `loan-opening-export/1` with
pre-cutover coverage explicitly unavailable. It retains supported later servicing,
and a dedicated operator restore now rebuilds and reconciles that graph before
confirmed commit. New exports advertise restore support. The next MVP step is a
concrete one-loan pilot review and rehearsal. The actual pilot still needs approved balances/due
terms and source/destination/cutover decisions. See the
[operator flow](../flows/legacy-opening-import.md).

Latest commit checkpoint: the Loans-owned v2 opening command now provides a full
rolled-back preview, confirmed atomic commit and shared complete-history/opening
identity. Synthetic imports pass release, reversal, replay and rollback checks.
No real source loan is activated. The next slice connects reviewed source selection
and destination approval to this command; due-term decisions and truthful opening
export remain required before the actual pilot. See the
[commit decision](../adr/2026-09-12-authorized-opening-commit.md).

Latest mapping checkpoint: v2 opening evidence preserves unknown gross weight and
explicit Bronze, with native origination still strict. The source adapter emits
v2 for `jcl-owner/2`; no candidate becomes approved merely by changing its format.
The 2,448-candidate offline recheck retains all holds for missing financial/setup
facts. Opening commit/source binding, truthful export and actual cutover/destination
review remain pending; see the [first-import plan](first-legacy-import.md).

This clarification supersedes earlier "no further feature slice" and "prepare a
real canonical file" next-step recommendations. The implemented Party and complete
Loans history profiles remain valid, but do not yet satisfy the owner's actual
initial migration sources:

1. First: the previous Django/schema-per-tenant production application's PostgreSQL
   dump, supplied as `rokkaddb_prod_full_2026-04-10.dump`.
2. Second: simple customer, licence, series, loan and release Excel registers.
   Loans reference customer IDs; series reference licence IDs; releases may contain
   only the loan reference and release date.

Users should not have to author JSONL or manufacture missing source evidence.
Source adapters translate those inputs into the shared identity, mapping, staging,
preview, explicit commit and provenance pipeline. Party and Loans retain domain
validation and writes. The offline dump preview described below implements source
preparation only; dump/Excel financial import and incomplete-history contracts are
not yet implemented.

The owner supplied legacy source commit `c9fb81bc70adafa1d942721d642bfb2b38953f41`
on `tenants_workspace`. The [source review](../implementation/legacy-dump-source-review.md)
now records optional release payments, differing interest calculation paths,
source/dump schema differences, relationship checks and per-loan review cohorts.
It found 6,107 unreleased loans, of which 6,103 have separate items. The bounded
read-only source adapter/preview is now implemented and exercised against the
owner-selected `jcl` tenant. See [operator guide](../flows/legacy-dump-preview.md)
and [decision](../adr/2026-09-12-offline-legacy-dump-preview.md). The owner selected
preservation of existing billing dates/rules and proposed skipping incomplete
collateral. The [opening-position contract draft](../contracts/loan-opening-position-mvp.md)
now specifies the financial requirements. An opt-in preview proposal marks whole
loan exclusions and preserves every source row; actual selection acceptance and
opening financial implementation remain pending. Obtaining code and implementing
source preview are no longer pending prerequisites. No loan is certified
import-ready by this review.

The [opening review validator](../contracts/loan-opening-review-v1.md) is now
implemented and connected to dump preparation (`--prepare-openings`). It generates
2,448 retained `jcl` active candidates, preserves all 54,713 source rows and explicitly
reports missing financial/setup/continuation evidence. All candidates still need
review; one retains a source error. Revalidation is offline and never import-ready.
The [representative source reconciliation worksheet](../implementation/legacy-reconciliation-worksheet.md)
is now prepared: nine retained active examples plus one released payment control.
Initial [owner answers](../implementation/legacy-reconciliation-worksheet.md#owner-responses-received-2026-09-12)
confirm loan-date monthly anniversaries, no separately held receipts/waivers and
release meaning paid/closed; Bronze needs distinct support. At that checkpoint,
partial-month and month-end rules, weights, concrete due terms and cutover balances
were unresolved; subsequent clarifications and implementation follow below.
The owner subsequently confirmed first-month interest and document charge collected
at disbursal, with principal-only release within that first month; preserve paid
coverage without recharging or inventing historical events. For the same 10,000
loan at 2% dated Jan 10, Feb 20 release collects 10,200; the owner confirmed Feb 11
as the first date requiring that additional 200, with Feb 10 still covered upfront.
For a Jan 31, 2026 loan, first additional interest starts March 1; coverage includes
Feb 28; the owner confirmed April 1 as the first release date requiring 10,400.
Preserve original anniversaries after short-month clamping, with collection increases
the day after each inclusive boundary. Net cash is confirmed at 9,790 for the
10,000 example after deducting 200 interest and 10 document charge. The owner
corrected the weight answer: source weight is net, excluding stones/non-metal parts,
superseding the earlier gross interpretation. Gross remains unknown. Rounding
examples match nearest-whole-rupee HALF_EVEN. The bounded named collection
calculator, acceptance tests and source-specific net-weight preparation are now
implemented through explicit owner profiles. After the owner clarified negotiated
collections and accepted interest loss, `--owner-profile jcl-owner/2` now sums
monthly item charges, multiplies by additional months and HALF_EVEN-rounds the
total once for rehearsal. Version 1 retains its previous fractional holds.
The April 9 rehearsal now produces 2,447 collection illustrations and one
source-error hold; all 2,470 retained item weights map to net, with gross unknown.
72 focused database-prohibited tests pass. Actual collection/loss amounts remain
unknown; no balances, terms or continuation evidence are filled from illustrations.
Fractional rounding is no longer an open owner question for preparation. Next:
complete the pilot opening-balance/evidence basis and servicing integration.
Single-loan full-release concessions are now implemented with separate immutable
cash/loss evidence, authorization, reversal and replay checks. Other concession
workflows remain outside this slice. The [first-import plan](first-legacy-import.md)
lists the fixed remaining import requirements and separates an active pilot from
the limited-evidence released cohort.
The [collection decision](../adr/2026-09-12-legacy-collection-estimates-and-concessions.md)
records the boundary; actual import remains pending.
The next implemented foundation adds immutable `MIGRATION_OPENING` evidence and
cutover-aware balance/tranche readers, separate from lending/collection totals.
It is tested using synthetic fixtures; ordinary posting and native interest remain
blocked for opening loans. Original-period continuation, remaining obligations,
servicing, authenticated commit and adapter rehearsal are still required. No dump
loan has been activated by this foundation. See the
[opening contract](../contracts/loan-opening-position-mvp.md) for the exact boundary.
No optional history-filter work is reintroduced.

The following bounded increment now adds the explicit
[v2 collection checkpoint](../contracts/loan-opening-review-v2.md), cumulative
post-cutover collection projection in exposure and owner-authorized persistence of
reviewed remaining obligations. Original due dates and reviewed grace survive the
cutover. Posting and repayment/release/reversal integration remain required; no
source candidate was automatically upgraded, filled or activated. The
[continuation decision](../adr/2026-09-12-opening-collection-continuation.md) records
this implementation boundary and the unchanged first-import scope.

Dedicated opening full-release servicing is now implemented: the existing release
workflow posts the reviewed-rule collection catch-up, settles cash/concession and
returns collateral in one transaction. Coupled reversal restores interest, receipt,
schedule and custody. Native monthly accrual and partial-principal servicing remain
unsupported for this origin. See the [servicing decision](../adr/2026-09-12-opening-full-release-servicing.md).
The next fixed-scope work is legacy evidence mapping and authorized opening commit/
adapter rehearsal; truthful export and approved destination/source/cutover evidence
remain activation gates. No production source loan has been imported.

### Initial offline dump inspection

Read-only `pg_restore` list/schema/data extraction to ignored local scratch files
was parsed as text. No SQL was executed and no database was restored or changed.
The custom archive was produced with PostgreSQL 15.7. Selected COPY records contain:

| Source table | Rows |
| --- | ---: |
| `contact_customer` | 6,924 |
| `girvi_license` | 4 |
| `girvi_series` | 10 |
| `girvi_loan` | 22,987 |
| `girvi_loanitem` | 12,408 |
| `girvi_loanpayment` | 1,010 |
| `girvi_release` | 16,880 |

These are archive-wide source counts, not reconciled destination totals. Of the
loans, 12,329 have separate item rows, 1,009 have payment rows and 16,880 have release
rows. There are 15,876 released loans without linked rows in the selected payment
table. Item/payment/release references to loans had no orphans in this limited
check. Customer, setup, financial and source-tenant reconciliation remain pending.

Missing item rows do not prove missing collateral: loans also carry inline item
description, weight and value fields. Release rows contain dates and references
but no settlement amount. Missing payment rows do not prove zero repayments or
unpaid balances. The matching legacy application's release/payment/calculation code
and any other relevant evidence must explain these representations. The source
licence table also lacks a direct match for the current licence number/date-range
contract. Do not guess those mappings or import retired apps into the runtime.

### Bounded next delivery

Produce a source mapping and reconciliation report for one explicitly selected
legacy tenant before implementing financial writes. The supplied source revision
has been reviewed; resolve its observed schema/calculation differences, map source
schemas to destination Workspaces and preserve stable
source namespace/schema/table/primary-key identity across successive snapshots.
Map customers and their child records, licence -> series, loans -> items/payments/
releases. Account for every source row and every unsupported relationship.

Classify loans by evidence, separately from ACTIVE/CLOSED lifecycle state:

- Complete, supported histories can use the existing `loan-history/1` contract.
- Active loans without complete history need a separately designed opening-position
  contract: approved cutover balances, interest paid-through/accrual basis, remaining
  obligations, collateral and subsequent servicing rules. Original loan amount
  alone is insufficient. Do not assume missing payments mean no payments occurred.
- Released loans with only limited evidence need a separately reviewed legacy
  historical-record representation, preserving known facts and coverage limitations
  without manufacturing settlement events or claiming complete financial history.
- Ambiguous or unsupported rows retain explicit blocked reasons until resolved.

The next report must identify which of those contracts the real data requires;
new executable semantics need an ADR and domain tests before implementation.
Plan bounded, resumable processing for the actual volume: current single-loan JSONL
and bounded Party uploads are not a delivered whole-dump batch runner. Define pilot
acceptance with reconciled source counts/balances, original-number lookup, repeated
import safety, Workspace isolation and native servicing of restored active loans.

After the dump pilot, implement the Excel adapter against the same agreed contracts.
A customer row can generate Party master/contact/address records; inline loan
collateral can be mapped without requiring a separate user-authored item sheet.
Weight meaning, interest rate unit, identifiers and release semantics must be
explicit; no synthetic payment sheets are required or invented.

The April snapshot is rehearsal input while the old application remains live.
Production cutover needs a fresh consistent snapshot and an agreed write handover
or separately designed delta procedure; immutable replay is not automatic sync.
Media bytes require a separate source when only paths occur in the dump. Credentials,
sessions and access grants are not business migration defaults. Optional history
filters, generic vendor frameworks, full archives and erasure remain deferred.

Bounded XLSX input is implemented for all six Party profiles, using the existing
staging/mapping/preview/approved commit and canonical JSONL export pipeline. One
visible values-only worksheet is accepted; text is preserved and ambiguous Excel
formats, formulas, hidden data, external links and unsupported package parts fail
before staging. Existing presets can be reused across CSV/XLSX when profile, source
system and header names match. Migration 0009 extends only the SQL preset-link guard.
See the [XLSX decision](../adr/2026-09-12-bounded-xlsx-input.md) and
[operator flow](../flows/party-master-portability.md#xlsx-input-2026-09-12).
The bounded `party-bundle/1` ZIP export is now implemented: all six profiles,
manifest, checksums, schemas and README from one lock-stabilized snapshot. See the
[bundle decision](../adr/2026-09-12-party-export-bundle.md). It remains a partial
Party export. ZIP validation/staging is now implemented into existing per-profile
previews; see the [staging decision](../adr/2026-09-12-party-bundle-staging.md).
Dependency-aware combined previews and explicit atomic Party bundle commit are
now implemented; see the [atomic commit decision](../adr/2026-09-12-atomic-party-bundle-commit.md).
Persistent Workspace-owned bundle history is now implemented, with stable review
URLs and fresh approvals after receipt expiry. See the
[history decision](../adr/2026-09-12-persistent-party-bundle-history.md).
Confirmed cancellation of all currently unfinished profiles in a saved bundle is
now implemented atomically, preserving completed evidence and history. See the
[cancellation decision](../adr/2026-09-12-party-bundle-cancellation.md).
Party portability MVP feature scope is closed. History filtering is optional and
deferred; no further portability feature slice is queued. See the scope boundary
in [the delivery plan](data-portability.md#mvp-scope-closeout-2026-09-12).

Reusable, versioned CSV mapping presets are implemented for all six Party profiles.
An immutable Workspace version captures mapped columns, defaults, normalization and
explicit role-type mappings. Applying one requires matching profile/source/header
names, copies its configuration and produces a fresh preview. New versions cannot
change existing approvals. Migration 0008 adds one forced-RLS configuration table
and a nullable batch reference; the released business exchange schemas are unchanged.
See the [preset decision](../adr/2026-09-12-csv-mapping-presets.md) and
[operator flow](../flows/party-master-portability.md#reusable-csv-mapping-presets-2026-09-12).
The next recommendation at that checkpoint was bounded XLSX input for these
Party profiles (subsequently implemented). Loans and full archives remain deferred.

`party-relationship/1` now reuses the staged CSV/JSONL pipeline, with exact
portable references to both Parties, native directional uniqueness and self-link
rejection. Approval binds both resolved endpoints; commit locks and revalidates
them. Migration 0007 extends ChildIdentity with a typed relationship target and
immutable related-parent reference, with SQL guards and deletion tombstones.
See the [relationship flow](../flows/party-master-portability.md#party-relationships-with-both-party-references-2026-09-12)
and [schema](../contracts/party-relationship-v1.schema.json). The next recommendation at that checkpoint was reusable, versioned CSV mapping
presets for the implemented Party profiles (subsequently implemented). These remain separate partial exports, not a complete archive.

`party-role/1` is now implemented through the shared pipeline. Explicit source-key
to active destination-type mapping is mandatory for CSV and JSONL; no Party role
definitions or staff permissions are created. Preview approval includes the mapped
definition snapshot. Native active-role uniqueness, historical row behavior and
Party validation are preserved. Migration 0006 extends the typed child target and
SQL guards without a new table. See the [role flow](../flows/party-master-portability.md#party-roles-with-explicit-type-mapping-2026-09-12)
and [schema](../contracts/party-role-v1.schema.json). The recommendation at that checkpoint was
Party relationships with explicit references to both Parties.


The identifier slice is now implemented as `party-identifier/1`, reusing the child
pipeline and typed identity model (migration 0005; no new table). It preserves
native value normalization, per-Party/type uniqueness, masked values and expiry
dates. Source verification/timestamps remain provenance only. Nonempty identifier
metadata blocks export; binary documents and internal hashes are excluded.
See the [identifier flow](../flows/party-master-portability.md#identifiers-without-documents-2026-09-12)
and [frozen schema](../contracts/party-identifier-v1.schema.json). The next
recommendation at that checkpoint was Party roles with explicit role-type mapping. No Loans or
financial migration is included.


The owner subsequently authorized the contact-method/address slice. The shared
pipeline now supports separate `party-contact/1` and `party-address/1` CSV/JSONL
profiles, with exact portable Party references, typed child identities and source
aliases, immutable result links, and explicit source-only verification claims.
Two additional Workspace-owned tables and a child-result link extend the existing
five-model staging design. Native child deletion leaves an identity tombstone;
merge/move alias resolution remains deferred. See the
[implemented child flow](../flows/party-master-portability.md#contact-methods-and-addresses-2026-09-12)
for permissions, primary/default conflicts, summary ordering and schema links.
Earlier master-only scope descriptions below record the first increment. The next
recommendation at that checkpoint was Party identifiers without binary documents; no Loans or
financial migration is authorized by this increment.





The [audit/architecture](../architecture/data-portability.md),
[ADR proposal](../adr/2026-09-11-customer-data-portability.md), and
[contract draft](../contracts/rokkad-data-v1.md) are the completed analysis slice.
The owner subsequently authorized and the implementation now covers the bounded
Party master slice described in the [operator guide](../flows/party-master-portability.md).
Future phases remain unimplemented and require their own selected work. Existing
monitoring capacity work and shelved FW-001/FW-002/FW-003 retain their own scope.

## MVP scope closeout (2026-09-12)

The owner requested a finite stopping point and no drift beyond MVP. The original
Party master end-to-end slice and the subsequently authorized six-profile Party
extensions are implemented locally. **Zero required portability feature slices
remain.** The final closeout fixes the import page's malformed browser title and
explains empty bundle history, then verifies the existing bundle journey.

The delivered scope is bounded staging, mapping/normalization, validation and
explicit approved commit; canonical export and RLS-safe round trips; six Party
profiles, CSV/XLSX/JSONL, reusable local presets, ZIP staging/atomic commit, saved
history and cancellation. Existing size limits and explicit conflict handling
remain. No further feature slice is selected automatically.

History filtering is tracked as [FW-006](future-work.md#fw-006-party-bundle-history-progress-filter).
Preset transfer/deletion, background processing, binary KYC,
Loans/configuration transfer, full Workspace archives and physical erasure are
post-MVP proposals. M3 onward below is a future roadmap, not an MVP checklist.
The generic legacy data-tools review remains a separate known open item under the
owner's earlier instruction to leave those paths unchanged. This closeout does
not certify those routes or the whole SaaS as release-ready. Publication,
deployment and production acceptance have not been performed by this slice.

## Implemented first slice

**Party master import/export end to end:** bounded CSV/canonical JSONL input,
explicit mapping, versioned normalization, staged validation and preview,
confirmation bound to validation revision, authorized atomic creation/no-op replay,
portable identity/provenance, canonical Party export and restricted-RLS round trip.

This shares existing Party creation/validation through a small domain service.
The follow-up owner instruction explicitly permits leaving generic paths alone;
they remain unchanged and are not the new pipeline. Their closure/allowlist review
is outstanding, not counted as delivered.
It excludes child entities, XLSX, Loans, historical financial states, opening
positions, binary uploads, full-Workspace export and deletion. One Party master
profile proves both directions without needing licence/series setup or pretending
that a Party listing is a full archive.

## M0 — Audit and architecture (this task)

- Scope: trace current code, document gaps, propose identities/contracts, migration,
  export, security, retention and phased delivery.
- Files: four new documents linked above and here; additive Status/Agent Memory
  entries. Preserve existing uncommitted work.
- Prerequisite: required repository context and source/service/test inspection.
- Acceptance: explicit answers to all twenty architecture questions and deliverables
  A–N; one next slice, with future policy decisions labelled.
- Validation: local documentation links, whitespace and source-reference checks;
  no database tests needed for documentation-only changes.
- Rollback/risks: remove only this task's additions if withdrawn. Proposals must
  not be mistaken for implemented guarantees or accepted legal policies.
- Non-goals: application changes, migrations, provider actions, imports or erasure.

## M1 — Party master vertical slice

Implemented within the owner's narrowed authorization: five scoped models,
CSV/JSONL services, bounded issues/provenance on staging rows, shared Party create
service, explicit Workspace screens and partial JSONL export. No ZIP/ExportJob,
XLSX, Party children or generic-tool rewrite. See Status for exact verification.
The original acceptance checklist below remains the design baseline; artifact TTL
tests do not apply to synchronous exports with no persisted download URL. Completed
source evidence is retained, with retention execution deferred. Concurrent first
export and repeated same-batch commit are explicitly tested.

- Scope: party-master/1 executable schema and fixtures; CSV/JSONL adapters; batch,
  row, issue, identity/alias and immutable result persistence; mapped dry run;
  atomic <=1,000-row Party create/unchanged commit; private canonical export and
  checksum; current source metadata retained, generated destination Party codes.
- Files/apps: new `apps/tenant_apps/data_portability` app with small models/services;
  Party `forms.py`, `views.py`, new shared validators/create service and merge alias
  handling; tenancy registry/RLS migrations/tests; settings app registration;
  explicit Workspace URLs/templates; generic `utils/importing` routes; narrow
  existing permission/recovery integrations, docs/contracts and tests.
- Prerequisites: freeze profile/limits and changed-input-conflict policy; implement
  an explicit allowlist. Replace generic import with the staged Party path and deny
  unsupported models. Preserve route names where useful, but not unsafe write
  semantics. Generic export must no longer expose arbitrary fields/secret models;
  retain only explicitly reviewed legacy reports and label their partial coverage.
- Acceptance: upload/preview causes zero domain writes; exact approval is required;
  new Parties use the existing domain rules; any commit error rolls back all rows;
  reupload has no duplicate/counter effects; changed source/local edit conflicts;
  repeated exports preserve IDs; clean-Workspace import/export matches supported
  facts through an identity map. Renamed local roles continue to work by grants.
- Tests: restricted role missing/cross-Workspace DML and relationships; API/direct
  service/worker denial; forged workspace/actor/PK; post-preview membership removal;
  two concurrent same-source commits; sequence rollback; normalization ambiguity;
  byte/row/cell limits and malicious formula text; source/header mutation invalidates
  approval; duplicate/changed/source-less identities; private download expiry and
  wrong owner; native/imported stable export ID race; generic route cannot mutate
  loan or Notify models; no credentials in any remaining export; round trip.
- Rollback/risks: disable new writes/routes and preserve committed Party/provenance
  records; never reverse migrations destructively after successful imports. Profile
  is partial; do not silently discard child collections or unsupported fields.
- Non-goals: updates/automatic merge, Party children, XLSX, background scale engine,
  operational history, licence/series, attachments, erasure, global adapter registry.

## M2 — Complete Party aggregate and reusable file mapping

**Delivered increment:** Party contact methods and addresses, through the same
preview/commit/export pipeline and shared native validation/save rules.
**Delivered follow-up:** Party identifiers without binary documents.
**Delivered follow-up:** Party roles with explicit role-type mapping.
**Delivered follow-up:** Party relationships with explicit references to both Parties.
**Delivered follow-up:** Reusable, versioned CSV mapping presets.
**Delivered follow-up:** Bounded XLSX input and CSV/XLSX preset reuse.
**Delivered follow-up:** Bounded six-profile Party ZIP export with manifest and
one consistent snapshot.
**Delivered follow-up:** Validate and atomically stage Party ZIP files into existing
per-profile previews; commits remain explicit and separate.
**Delivered follow-up:** Dependency-aware combined previews and one explicitly
approved atomic Party bundle commit, including role-type mapping and safe replay.
**Delivered follow-up:** Persistent bundle history, verified legacy-group recovery
and stable review URLs that survive receipt expiry.
**Delivered follow-up:** Confirmed atomic cancellation of currently unfinished
bundle profiles, preserving completed evidence and history.
**MVP feature scope closed:** No further portability feature slice is queued.
History filtering is optional and deferred under the owner's MVP constraint.
Full Workspace archives and Loans transfer remain separate.
Aggregate transactions beyond the six Party profiles, background processing and
binary KYC files remain separate future work.

- Scope: roles, contact methods, addresses, identifiers, relationships and export;
  shared contact summary synchronization; saved Workspace template versions;
  bounded XLSX parser and background staging when measured limits require it.
- Files/apps: Party shared commands/validators/merge, portability profiles/parsers/
  templates/worker, tests and operator flow documentation.
- Prerequisites: M1; define verification provenance and relationship enum dictionary;
  XLSX limits/formula/external-link policy; no portal account grant restoration.
- Acceptance: whole Party aggregate commits atomically; conflicts resolved explicitly;
  child IDs stable; role types resolve by Workspace key; common Excel variants map
  deterministically; no formula evaluation or implicit source verification.
- Tests: contact primary/default constraints, duplicate KYC review, cross-party/
  Workspace relations, merge aliases, XLSX ZIP bomb/cell limit/macro/link fixtures,
  worker crash/resume/context cleanup, aggregate export/reimport equivalence.
- Rollback/risks: stop batches between units; retain successful aggregates and mapping
  versions. Repeated mapping versions must not reinterpret old approved batches.
- Non-goals: historical lending, automatic fuzzy merge, binary ingestion, portal grants.

## Selected Loans contract review (2026-09-12)

Completed the first bounded Loans contract review; see the
[contract](../contracts/loan-history-mvp.md) and
[decision](../adr/2026-09-12-loans-complete-history-mvp.md). The selected structure
is FLEXIBLE_PARTIAL_PAYMENT, covering complete active histories and full-release
closed histories. No opening balances or unsupported event graphs are inferred.

The review found missing local SQL immutability triggers on six core evidence
tables. The follow-up now protects fifteen append-only evidence tables through
migration 0008; see the [guard decision](../adr/2026-09-12-loans-history-evidence-guards.md).
The subsequent [setup preparation](../flows/loans-import-preparation.md) is now
implemented as a read-only owner workflow with historical licence/product checks
and number candidates. It creates no reservations, mappings or financial records.
**Next implementation:** complete-history staging/reconciliation and the historical
command with persistent provenance, locked number checks and canonical export.
The review, guards and preparation page were prerequisites. The subsequent
[canonical JSONL delivery](../flows/loans-history-import.md) implements bounded
staging, reconciliation, explicit atomic import and export for active and fully
released flexible loans. No history filter or vendor adapter is required for this MVP.

## Loans scope clarification (2026-09-12)

The owner wants both active and historical Loans considered; these are not mutually
exclusive import modes. Loan lifecycle state (active or closed) and source evidence
coverage (complete history or an incomplete cutover position) are separate axes.
An active loan can have complete history and use the M4 historical profile. An
opening-position import is needed only when required earlier evidence is missing;
it is not the default way to import active loans.

The existing roadmap already supports complete active history and an evidenced
full release in a bounded M4 profile, then wider histories in M5. M3 supplies setup
and numbering prerequisites. M6 separately defines incomplete-history openings.
Party portability supplies the borrower/import foundation, but no executable Loans
import contract or historical command is delivered by it. The next Loans work can
start from this existing plan; validate the narrow product/event profile and its
current model/SQL invariants before financial writes. Do not impose an active-only
product requirement or treat all historical event graphs as one MVP increment.

## M3 — Lending configuration and numbering cutover

- Scope: licence/revisions, series, products/versions, calculation/interest/fee
  configuration; matching exports; number namespace/preservation preview and explicit
  cutover. Party remains an independent predecessor rather than a licence child.
- Files/apps: Loans setup services/models if narrowly needed, portability setup
  profiles, number service/tests, configuration documentation.
- Prerequisites: M1 identity model; versioned historical configuration semantics;
  exact financial decimal/enum schemas; no automatically activated imported setup.
- Acceptance: expired historical licence evidence preserved without implying current
  issuance; every reference Workspace-checked; live counter never decreases; invalid
  bounds/collisions block; existing native origination still behaves identically.
- Tests: A/392 backfill with A/1042 live, future-number overlap, repeated cutover,
  concurrent native allocation, sequence exhaustion, licence revision immutability,
  product/policy scope/effective dates and round trip.
- Rollback/risks: deactivate unused imported setup if necessary; no reclaiming issued
  numbers, mutating old revisions or deleting referenced configuration.
- Non-goals: operational financial migration, automatic series merge, schema redesign.

## M4 — One supported complete loan-history profile

- Scope: select one existing repayment structure with supplied complete source
  evidence; new Loans-owned historical command for loan+collateral+frozen terms+
  disbursal+contract+ordered event/allocations, matching export and read reconciliation.
  Start with a narrow active history, then an evidenced full release within this
  same released profile when it is correct; do not release bare state assignment.
- Files/apps: Loans historical service, shared domain validators, source/evidence
  schema/guard migrations only if demonstrated necessary; selectors characterization
  tests; portability graph resolver and profile serializers.
- Prerequisites: M3, accepted historical semantics ADR; identify mandatory evidence
  and event schema; characterize all touched PostgreSQL guards. No rule-bypass flag.
- Acceptance: every imported financial/custody amount is traceable; original dates
  and source actors distinguish import time; balance, schedule/DPD, interest and
  exposure agree at source dates and cutover; no current-time replay, number allocation,
  external notification or fabricated document issuance. Missing facts block activation.
- Tests: dependency ordering, missing/other-Workspace references, impossible state,
  release-before-loan, negative/overprecision numbers, double cash effect, same-date
  event ordering, accrual/repayment/release/reversal histories, immutable SQL denial,
  transaction rollback, native workflow regressions and domain-equivalent round trip.
- Rollback/risks: stop import; successful immutable evidence is corrected by explicit
  reviewed compensation, not deletion. Release data cannot be committed separately
  from required custody and schedule changes.
- Non-goals: incomplete-history activation, opening balances, arbitrary historical
  status support, renewal/auction/funding restoration, all product structures.

## M5 — Wider history and progressive backfill

- Scope: additional product structures, renewal/auction/reversal graphs, funding and
  custody history, supported closed-loan backfill alongside live entry; chunked
  aggregate units with durable partial-success ledger. Extend export concurrently.
- Files/apps: Loans owning services/guards, portability dependency resolver/worker,
  history profiles, source evidence UI and batch status.
- Prerequisites: M4; graph unit bounds and explicit partial-progress consent; preserve
  source actor/chronology and shared collateral/file lineage. No two live identities.
- Acceptance: independent live servicing proceeds; native number counters and closed
  history remain correct; completed units survive crashes; no duplicate notice jobs;
  retry only pending units; oversized connected graphs reject cleanly.
- Tests: renewal successor and reversal, auction disposal, funding pledges/returns,
  batch payer/collector evidence, concurrency with live release and borrower edits,
  partial commit crash/cancel/retry, closed loans excluded from live monitoring.
- Rollback/risks: stop future units; preserve imported immutable graphs. Shared events
  cannot be split solely to hit an arbitrary row-count target.
- Non-goals: guessing missing history or replacing an opening basis with old payments.

## M6 — Opening-position contract and servicing

- Scope: separately reviewed Loans opening evidence and cutover semantics, remaining
  obligations/original due dates, tranche split, interest basis, reconciliation and
  documentary pre-cutover backfill.
- Files/apps: Loans vocabulary, model/event schema, guards, balance/interest/obligation/
  exposure/report/reversal services and tests; portability opening profile and docs.
- Prerequisites: accepted Loans ADR with actual examples of source cutover data and
  known missing history; M4 reconciliation framework. An aggregate balance is insufficient.
- Acceptance: no false cash disbursal, principal/capitalized-interest distinction,
  unchanged DPD basis, no double accrual or double-counted history; pre-cutover reads
  accurately report incomplete coverage. Post-cutover servicing reconciles exactly.
- Tests: cutoff boundary inclusive/exclusive dates, source principal vs capitalized
  amounts, future instalments, accrued/unrecognized interest, post-cutover repayment,
  reversal and release; later history cannot add a second opening or overwrite events.
- Rollback/risks: highest financial semantic risk; disable new opening imports while
  preserving existing opened loans. No production use before accounting-free Loans
  invariants and representative source cases pass.
- Non-goals: general-ledger entries or automatic replacement of opening evidence.

## M7 — Complete Workspace archive and binary portability

- Scope: complete reviewed export inventory for Party/Loans/Rates/Notify plus scoped
  control-plane business metadata; attachment paths/hashes and exact issued bytes;
  repeatable-read worker snapshot, consistency/completeness checks, private expiring
  downloads; human XLSX views from canonical projections. Binary import only after
  private file controls and domain lineage validation are implemented.
- Files/apps: portability exporters/file handling/profile schemas; domain read
  projections; Orgs/billing scoped selectors; tenancy registry completeness tests;
  document/media permission routes; deployment storage/runbooks.
- Prerequisites: identity coverage, schema-aware translation of embedded IDs, full
  secret exclusion map; consistent DB/file capture design and performance budgets.
- Acceptance: every applicable entity has documented coverage or policy exclusion;
  FULL never means an incomplete subset; all required referenced bytes and records
  present; non-importable security/delivery history marked archive-only; repeated
  exports stable; expired subscription/archived owner recovery works as designed.
- Tests: wrong-Workspace IDs in nested JSON, credentials excluded, removed owner/
  member on download, concurrent updates/deletes and new-ID creation, missing/tampered
  files, ZIP traversal/collision/bombs, formula injection, stable hashes, memory/time,
  shared renewal media, exact document byte round trip for supported restoration.
- Rollback/risks: revoke failed exports and purge temp artifacts; preserve user data.
  Long snapshots can affect DB vacuum/servicing; reject/defer rather than lie about
  completeness. Imported notification history must never dispatch.
- Non-goals: restoring login grants/provider credentials/entitlements, unattended deletion.

## M8 — Controlled offboarding and retention execution

- Scope: Orgs owner closure request, final-export state/acknowledgement, retention/
  legal-hold decisions, platform scheduling, cancellation and audited purge ledger;
  file/database/control-plane disposition and backup restore suppression.
- Files/apps: Orgs lifecycle/offboarding services and records, subscriptions explicit
  retention selectors, domain-specific erasure inventory, reviewed DB erasure routine
  if needed, storage worker and operational runbooks.
- Prerequisites: M7 full archive; policy/legal retention decisions supplied and approved;
  separate privileged-erasure ADR and access review. Unknown policy means no purge.
- Acceptance: current four-state graph preserved; owner cannot clear platform hold;
  cancellation and execution serialize; data from other Workspaces/global accounts
  survives; retained categories/backup expiry accurately reported; incomplete erasure
  retries safely and cannot be misreported as permanent deletion.
- Tests: legal hold, retained billing/audit refs, owner transfer, cancelled closure,
  concurrent export/restore/erase, crash after DB before file purge, shared file
  detection, denied runtime SQL privileges, restored backups respect tombstones,
  unknown registry model blocks erasure, complete disposition verification.
- Rollback/risks: irreversible once execution begins. Preview exact category counts/
  retention and export evidence before authorization; no rollback promise after
  permanent purge. Cancellation available only before the recorded execution boundary.
- Non-goals: hardcoded legal periods, refunds/provider setup, a general superuser bypass.

## Test execution and evidence rules

Use disposable PostgreSQL test databases with
`--settings django_project.settings.test`; owner-only migrations use
`--settings django_project.settings.migration`. Adversarial SQL must execute as
NOSUPERUSER/NOBYPASSRLS, not merely run under a test owner that hides policy defects.
Use the repository's WorkspaceTestCase and existing RLS/concurrency patterns.

Run focused contract/parser/service/route tests plus affected Party/Loans/lifecycle
regressions. New app/migrations require registry/runtime role checks and migration
upgrade rehearsal. Test outcomes are committed evidence; a design matrix or test
name is not proof that a future feature passes. Round-trip expected results should
be independently specified source facts, not snapshots copied from the serializer.

## Documentation delivery map

- Architecture, import pipeline, provenance, historical semantics, security and
  offboarding: current architecture document; split into focused guides only when
  implementation makes the file unwieldy or requires distinct ownership.
- Format/versioning: current contract plus executable schemas/fixtures in M1.
- Operator guides: `docs/flows/importing-legacy-data.md` and
  `docs/flows/exporting-workspace-data.md` in M1/M2, with actual UI/command paths,
  limits, failure recovery and no implied full-export coverage.
- Historical/opening/erasure decisions: new ADRs at M4/M6/M8 before domain changes.
- Deployment/temp-file cleanup/storage retention: `docs/implementation/` guides
  when those workers are implemented, not fictional executable runbooks now.
- Status tracks delivery/tests; Agent Memory records only established direction
  and stable constraints. This plan does not replace monitoring capacity acceptance.

## Canonical Loans delivery (2026-09-12)

M4 now has a local end-to-end `loan-history/1` implementation; see the
[wire contract](../contracts/loan-history-jsonl.md) for executable bounds and exclusions.
The first source is canonical JSONL, one complete loan per file. Native and imported
active/closed histories are exercised through export, preview and commit. New
structures, archive coverage and vendor adapters remain future work. The next
operator step is preparing a representative real source file and reviewing its
preview, not adding another usability feature. Production migration/import is a
separate operational action.
