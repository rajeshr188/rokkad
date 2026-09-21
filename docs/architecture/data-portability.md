---
status: proposed
owner: project
updated: 2026-09-13
tags: [architecture, portability, audit, migration, rls]
---

# Data portability: repository audit and proposed architecture

For the current Loans-specific architecture, implemented boundaries and gaps, use
the [2026-09-12 Loans audit](loans-portability-audit.md). Owner-authorized slices are
tracked in the [follow-up plan](../plans/loans-portability-audit-followup.md). Earlier increment descriptions
below retain delivery history and must not be read as a current capability list.

Current source priorities are the owner's legacy schema-per-tenant production dump,
then simple linked Excel registers. See the [source review and next delivery](../plans/data-portability.md#actual-source-priorities-2026-09-12),
which supersedes earlier next-step recommendations below. The
[offline legacy source preview](../flows/legacy-dump-preview.md) is implemented;
one-loan legacy opening source verification, staging and browser approval are now
implemented alongside the Loans-owned v2 opening command. See the
[opening flow](../flows/legacy-opening-import.md). Missing business facts and the actual pilot remain pending.
A bounded [opening export and dedicated restore](../contracts/loan-opening-export-v1.md)
now rebuilds and reconciles supported opening/servicing records with explicit
destination mappings; source-local keys never become destination foreign keys.
The existing complete-history contract stays strict.

The bounded [closed-loan evidence archive](../contracts/loan-closed-evidence-v1.md)
is implemented locally with immutable Workspace-owned retention, owner-reviewed
staging and separate browse/export routes. Missing or contradictory source claims
can be retained without creating an operational loan, borrower or debt. Existing
financial admission stays strict. Its two additive migrations are prepared and
tested in disposable databases; no real-source import follows automatically.

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
in [the delivery plan](../plans/data-portability.md#mvp-scope-closeout-2026-09-12).

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





The original audit below uses the working tree on 2026-09-11, including local
monitoring capacity changes after `21a48aee`. A bounded Party implementation now
exists; the rest of this architecture remains proposed. Current delivery evidence
is in [Status](../STATUS.md).

## Implemented Party boundary

`apps/tenant_apps/data_portability` implements CSV/canonical JSONL staging,
column mapping, explicit normalizers, existing Party form validation, paginated
preview, revision/digest-bound confirmation, atomic commit and synchronous JSONL
export. Limits are 1,000 rows, 5 MiB, 40 columns and 4,096 characters per encoded
field. Export is explicitly a partial Party master representation. Shared Party
creation is in `party/services/creation.py`; existing UI creation calls the same
service. No Party model or financial behavior is replaced.

Implementation choices narrowing the proposal:

- Five directly owned models: ImportBatch, ImportRow, WorkspaceNamespace,
  PartyIdentity and SourceIdentity. Typed Party FKs replace the proposed generic
  entity reference. Issues are bounded JSON on each row; completed rows also
  provide immutable provenance/results. No extra ImportIssue/ImportRecord table
  or generic mapping framework is needed yet.
- Upload and parsing are synchronous and atomic, publishing NEEDS_MAPPING only
  when all rows have staged. Validation is atomic, publishing READY or
  NEEDS_MAPPING; no durable UPLOADED/VALIDATING intermediate states. Commit publishes
  COMPLETED only with all results. Failure rolls back to the previous stable state;
  CANCELLED discards raw/canonical values for unfinished rows.
- Source hash/name/type/size and exact parsed values are retained in PostgreSQL
  under RLS. No persistent uploaded binary or export artifact exists, and no
  application temporary-file or stale-download-URL cleanup is required. Django
  closes its request upload files. Completed row provenance is retained;
  automatic retention/purge policy is not introduced by this slice.
- A single materialized Party query captures master fields. A bounded Workspace
  row lock serializes import/identity allocation; native Party edits continue to
  use their established behavior. Commit rechecks source aliases/local digests
  and locks existing replay targets. This is not full-Workspace snapshot support.
- Export is a bare JSONL file; the filename and response header carry the persisted
  source Workspace UUID. Schema is downloadable separately. There is no ZIP,
  manifest, attachment support or ExportJob. Export creates only identity/audit
  evidence, never business mutations. Download is an authorized POST with no-store.
- Current Party forms normalize whitespace, phones (existing IN default), tax
  codes and relation names. Those changes are explicit preview INFO entries, in
  addition to selected mapping normalizers. Blank optional strings normalize to
  null; the executable profile documents that distinction from the broader draft.
- An archived merge source keeps its own Party identity and source aliases;
  reimport detects its changed local fields and conflicts. No automatic alias
  retargeting or merge was introduced.
- The latest owner instruction explicitly allowed legacy tools to remain.
  Generic immediate model imports/exports and existing human Party reports are
  unchanged. The new infrastructure is included in the RLS registry but excluded
  from the legacy business model picker. Generic model export still needs a
  separate allowlist/security review; the new route makes no guarantee about it.
- The exact `workspace_portability:export` route is billing-exempt and lives under
  the existing lifecycle export-recovery prefix. Import is ACTIVE-only. Neither
  operation adds a new paid entitlement; the existing browser billing gate still
  applies to import. Service calls enforce actor/actions/context/lifecycle; an
  operator's commercial policy is separate from their RLS identity.

See the [operator guide](../flows/party-master-portability.md) and
[released Party schema](../contracts/party-master-v1.schema.json).

The recommendation is one orchestration app, explicit domain import services,
and a versioned exchange contract independent of Django serialization. Establish
Party import and export together before attempting financial migration. The
[ADR](../adr/2026-09-11-customer-data-portability.md),
[contract draft](../contracts/rokkad-data-v1.md), and
[milestone plan](../plans/data-portability.md) complete this proposal.

## Current-state audit and gaps

Paths below are relative to the repository. `loans/` and `party/` in explanatory
text mean their existing `apps/tenant_apps/` directories.

| Area | Evidence inspected | Finding and consequence |
| --- | --- | --- |
| Workspace identity | [context](../../apps/tenancy/context.py), [ownership base](../../apps/tenancy/models.py), [control-plane contracts](control-plane-contracts.md) | Explicit Workspace identity; transaction-local PostgreSQL context with same-ID nesting, conflict rejection, constraint settlement, and cleanup. Profile is navigation only. New services must receive Workspace explicitly. |
| RLS | [registry](../../apps/tenancy/registry.py), [RLS migrations helper](../../apps/tenancy/rls.py), Party/Loans `tests/test_rls.py` | Four business apps plus selected role tables registered. Policies use both USING and WITH CHECK with forced RLS. New app registration and migrations are mandatory; the base model alone is insufficient. |
| Authorization | [WorkspaceAccess](../../apps/orgs/access.py), `orgs/permissions.py`, domain `services/action_access.py` | Stored local role grants and canonical owner coexist with lifecycle/entitlement checks. `data.import`, `data.export`, and normalized `data.export.bulk` already exist. No second role system is needed. |
| Existing generic data tools | [views](../../apps/tenant_apps/utils/importing/views.py), [forms](../../apps/tenant_apps/utils/importing/forms.py), `orgs/web/slug_routes.py`, `django_project/shared_urlpatterns.py` | Reachable Workspace routes enumerate every registered business model, resolve model resources or construct a factory, and call `import_data(..., raise_errors=True)` on upload. No staged confirmation. Authorization compares Owner/Admin/Administrator names. RLS still applies; this is a domain/permission/contract gap, not evidence of a demonstrated cross-tenant exploit. |
| Existing exports | [PartyResource](../../apps/tenant_apps/party/resources.py), [report renderers](../../apps/tenant_apps/loans/services/report_exports.py), Party views | PartyResource uses internal `id` as import identity and flattens roles into labels. Loans CSV/XLSX/PDF reports are useful summaries, not reconstructable archives. Generic export uses unrestricted model fields unless a resource exists; credentials in Notify models make a deliberate allowlist essential. |
| Party | [models](../../apps/tenant_apps/party/models/party.py), `models/{role,contact,address,document,relationship,portal}.py`, [forms](../../apps/tenant_apps/party/forms.py), [views](../../apps/tenant_apps/party/views.py) | Party is identity; borrower/customer/lender are roles. Contacts, addresses, KYC, documents, relationships and portal access are separate. Creation currently saves through views/forms; no reusable aggregate creation command. Phone normalization and relation-pair validation are in forms. Contact summary synchronization is in views. |
| Party numbering | `party/models/party.py::generate_party_code` | Workspace/key sequence is locked; allocation skips existing codes. Codes are unique per Workspace. Blank code triggers allocation in save. Import preview must never save merely to validate. |
| Lending setup | [core models](../../apps/tenant_apps/loans/models/core.py), `models/{products,regulatory}.py`, [setup service](../../apps/tenant_apps/loans/services/license_series.py) | Licence, immutable licence revisions, series, document-kind sequences, product/version, economic/metal-rate/fee policies are distinct. Party has no licence dependency. |
| Loan intake | [draft service](../../apps/tenant_apps/loans/services/pawn_drafts.py), `web/pawn_intake.py`, `forms.py`, `tests/test_pawn_draft_service.py` | Draft creation validates active borrower, series/licence, product availability/tenor and collateral economics, then consumes the loan number at draft creation. This is unsuitable for simply loading historical numbers. |
| Lifecycle | [disbursal](../../apps/tenant_apps/loans/services/pawn_disbursal.py), [repayment](../../apps/tenant_apps/loans/services/pawn_repayment.py), [release](../../apps/tenant_apps/loans/services/pawn_release.py), `pawn_lifecycle.py`, `pawn_reversal.py` | Approval freezes evidence; disbursal establishes events, policy and repayment schedule. Repayment uses today's allocation and schedule effects. Full release uses today's date, catch-up interest, number allocation, termination and custody evidence. Partial release explicitly is not the supported workflow. |
| Financial authority | [event recording](../../apps/tenant_apps/loans/services/event_recording.py), `selectors/{balances,obligation_state,exposure}.py`, `services/obligations.py` | Balances fold events; contractual dues/DPD fold schedules and allocations. A standalone loan principal or payment row does not establish a serviceable balance. Event hashing alone is not an external import identity. |
| Immutability | Loans `models/core.py`, `db_guards/`, migrations, `tests/test_accounting_retirement_boundaries.py` | Application and PostgreSQL guards protect completed evidence, reversals and cross-record relationships. Migration must satisfy guards, never disable them. `record_loan_event` is an internal persistence primitive, not a publicly authorized import endpoint. |
| Accounting | [retirement ADR](../adr/2026-08-16-retire-accounting.md), [constitution](../constitution.md), Loans event service/integrations/selectors and retirement tests | No live ledger, journals, vouchers, accounting periods or external accounting outbox. Operational events remain canonical. Do not revive DEA, Girvi or accounting to implement migration. |
| Attachments | [private-media guide](../implementation/private-media-access.md), Party download views, Loans `models/{media,documents,regulatory}.py` | Local FileSystemStorage is the documented current default. Private authorized routes; filenames/storage keys are not external identities. Issued documents retain exact bytes, hashes, layout/asset versions and reprint lineage. Renewed collateral may share files. |
| Rates/monitoring | `rates/models.py`, Loans `models/{appraisals,monitoring,risk}.py`, [worker](../../apps/tenant_apps/loans/services/risk_jobs.py) | Quotes/appraisals preserve corrections and effective/recorded time. Risk projections are derived and may be stale. Existing bounded explicit-Workspace worker pattern is reusable; it is not a generic portability job runner. |
| Audit | [AuditLog](../../apps/orgs/audit.py), `LoanChangeLog`, loan/quote/custody/document evidence | AuditLog is a global control-plane model with a company link, not automatically protected by business RLS. Batch provenance needs direct Workspace ownership and atomic evidence beyond a general audit message. |
| Offboarding | [lifecycle policy](../../apps/orgs/lifecycle.py), `orgs/services/control_plane.py`, `orgs/models.py`, middleware and lifecycle tests | ACTIVE, SUSPENDED, ARCHIVED, DELETION_PENDING already exist. Owner/platform archive; platform alone schedules erasure. Ordinary Company.delete is disabled. Archive export has an explicit recovery path; physical erasure/retention is not implemented. |

The current financial-read-model guide retains some pre-retirement accounting
phrasing. Current code and the accepted retirement ADR govern; that wording must
not be read as a functioning posting integration.

### Scope inventory for a genuinely complete export

The initial Party subset must be labelled partial. A future full export requires
an explicit reviewed mapping for every registered model, plus selected global
Workspace-owned control-plane data. A registry test must fail when a newly added
model lacks an export/exclusion decision. Registry coverage is an inventory check,
not permission to serialize all columns.

| Family | Domain evidence to preserve | Exclusions or reconstruction policy |
| --- | --- | --- |
| Workspace/control plane | Company display/configuration, licence-independent preferences, Membership roster, WorkspaceRole/Grant definitions, relevant AuditLog, invitation history, subscription/order/payment/refund/customer-facing billing evidence | No passwords, login/session tokens, invitation secrets, provider secrets, global users' other Workspaces or platform-only audit detail. Imported roster never grants access. Plans are referenced commercial descriptions, not imported entitlements. |
| Party | Party, PartyRoleType/Role, ContactMethod, Address, Identifier, Document, Relationship, photo | PortalAccess is historical access metadata, never recreated as a login grant. Sequence state is informational. |
| Setup | LoanLicense/Revision, LoanSeries/NumberSequence, LoanProduct/Version, economic/metal-interest/fee policies, monitoring and communication policies | Preserve version/effective-date semantics. Do not auto-activate copied configurations or reset live counters. |
| Loan source and evidence | PawnLoan, collateral, LoanPolicySnapshot, Approval/DisbursalSnapshot, PawnLoanEvent, accrual/header lines, repayment/closing/opening allocation lines, LoanChangeLog | Explicit domain projections; internal keys in frozen JSON require schema-aware translation, not blind pass-through. |
| Servicing | Release/ReleaseItem/Reversal, release batch/lines, Auction/items/reversal, Renewal/reversal, all source and successor links | A payment is an event plus allocations, not an existing Payment model. Closure cause is separate from CLOSED state. |
| Contract | RepaymentScheduleVersion, Obligation, ScheduleChange, ObligationAllocation | Preserve due dates, termination, reversal, supersession and calculation version; do not recompute old contracts from today's product defaults. |
| Custody/funding | StorageLocation, StorageMovement, CustodyEvent, physical verification session/expectation/observation/resolution; FundingLoan, draft terms/collateral, cancellation, frozen terms, events, pledge/return items and reversals | Operational state must reconcile with evidence. QR/label issue history is evidence; destination URLs are rebuilt only for newly issued labels. Funding sequences informational. |
| Rates/monitoring | RateSource, Rate revisions/withdrawals, CollateralAppraisal, LoanMonitoringPolicy, LoanRiskEvent/Alert/Snapshot | Snapshots are labelled derived/as-of/status, never authoritative imported balances. Rebuild active projections without replaying alerts. |
| Communications | PawnLoanNotice, LoanOperationalNotice, consent/policy; Notify EventType/Policy/Recipient/Template/Batch/Event/Job/Artifact/AttemptLog/WebhookReceipt and integration public configuration | Export redacted, documented business projections. WhatsApp integration ciphertext and webhook/auth secrets are excluded. Import never requeues jobs, sends notices or treats imported consent as verified authorization. |
| Documents | Layout/revision/assignment, assets, print profile/revision/assignment, issued artifact and prior-issue chain, collateral photos/label issues, licence supporting files, notification artifacts | Preserve original bytes and hashes. Missing bytes explicitly make attachment coverage incomplete. Never render a replacement and call it original. |
| Portability itself | Stable identity aliases, source lineage, committed import result, normalized change summaries, export history | Raw uploads/temp previews expire separately. Include the package's own provenance without recursively embedding previous export ZIPs. |

## Boundaries and module design

Use one new app when work begins, with a small conventional layout:

```text
apps/tenant_apps/data_portability/
    models.py                 # initially small, no package tree for each noun
    access.py
    contracts/v1.py            # explicit field definitions and serializers
    mapping.py                # declarative source-column mapping
    normalization.py          # named, versioned transformations
    parsers.py                # bounded CSV first; XLSX later
    services/imports.py
    services/exports.py
    selectors.py
    management/commands/process_portability.py   # when background work is needed
    tests/
```

This is a likely file map, not a directory scaffold to create now. Domain-owned
commands live in Party/Loans; portability must not duplicate their balance,
custody, interest or lifecycle rules. Orgs owns offboarding orchestration. Future
adapters are simple functions producing canonical records and source locations.
No adapter receives ORM classes or writes business models. No new framework or
queue dependency is required.

### Minimum persistence design

All new business-side rows have direct non-null Workspace ownership and forced RLS.

| Proposed model | Essential fields and constraints |
| --- | --- |
| ImportBatch | UUID, actor, source_system, mode, contract version, state, immutable mapping/normalization snapshot, source storage key/hash/name/size, manifest, validation revision/hash, approval hash/actor/time, counters, bounded failure summary, timestamps. One source file per MVP batch; a later ZIP manifest can describe several members without immediately adding ImportSource. |
| ImportRow | batch, stable row ordinal/source sheet, entity type, raw JSON, canonical JSON, canonical digest, source identity, state, resolved binding, result. Unique `(workspace,batch,sheet,row,entity)`; JSON payload capped. DB ownership/FK checks must reject a row linked to another Workspace's batch. |
| ImportIssue | batch, optional row, field, code, ERROR/WARNING/INFO, safe message, transformation/reference details, validation revision. Separate rows support paging/counts; old revisions are audit history, not current blockers. |
| ExchangeIdentity | opaque export UUID, entity type, allowlisted internal reference, timestamps; unique `(workspace,entity_type,internal_reference)` and `(workspace,entity_type,export_uuid)`. No caller-supplied content-type/model lookup. Resolver validates target existence and Workspace. Tombstones preserve merged/deleted identity history. |
| SourceIdentity | source_system, entity_type, external_id, ExchangeIdentity FK, accepted canonical digest, last batch/result; unique `(workspace,source_system,entity_type,external_id)`. Multiple source aliases may identify the same record only by reviewed resolution. |
| ImportRecord | row/source reference, ExchangeIdentity, operation, actor/time, accepted digest, relevant reviewed values, validation/rule versions and outcome. Append-only successful provenance; written with domain mutation. It survives raw-source cleanup. |
| ExportJob | requester, scope/profile, contract, state, snapshot time, counts, package key/hash/size, expiry, error, timestamps. Introduce alongside the first downloadable artifact if downloads persist beyond the request. |

ImportResult is a return value/summary of row outcomes, not another table.
ImportTemplate is deferred: initially freeze mapping inside ImportBatch. When
repeated mappings are needed, add Workspace-owned immutable template versions
keyed by source system, header signature, contract and normalization versions.
Globally shipped adapters are reviewed source code, not customer-editable global
templates or executable scripts.

Cross-Workspace FK safety needs explicit enforcement: RLS filters row visibility
but ordinary FKs do not themselves require matching workspace_id. Use the
repository's constraint-trigger patterns (or scoped unique keys/FKs where suitable)
for batch/row/binding relationships, and restricted-role adversarial tests.
An allowlisted polymorphic internal reference is validated by the resolver; its
integrity must be checked on every resolution and merge, not assumed from JSON.

## Import pipeline and operating workflow

```mermaid
flowchart LR
    U[Private upload] --> S[Raw staging]
    S --> M[Explicit field mapping]
    M --> N[Versioned normalization]
    N --> V[Validation and reference resolution]
    V --> P[Preview and frozen approval]
    P --> C[Authorized domain commit]
    C --> E[Provenance and exportable identities]
```

1. Authenticate, resolve explicit Workspace, authorize import and entity access,
   check lifecycle/entitlements, enforce quotas, then create a private batch.
   Archive-provided workspace_id is source metadata, never the destination.
2. Detect encoding/headers/sheets within strict budgets. Stage raw values with
   source positions. Upload modifies no domain rows. Never evaluate formulas.
3. User chooses entities and references, maps source columns to canonical paths,
   and selects normalization rules. Preserve original values. Ambiguous mappings
   require review; header guessing is only a suggestion.
4. Normalize with pure deterministic functions: trim, configured locale decimal,
   explicit date format, phone region, documented enum/purity conversion. No eval,
   Python expressions, arbitrary SQL, network fetches, or user regex engines.
5. Validate format, field/domain rules, dependency graph, identity conflicts,
   dates, numbers, ownership, duplicate candidates, and operation capabilities.
   Preview does not invoke write services inside a rollback transaction: sequence
   allocation, files, and downstream work make that an unsafe dry-run technique.
6. Freeze source/mapping/rule/contract hashes, candidate results, reference
   bindings and their versions. Show counts by new/unchanged/conflict/error,
   warning acknowledgements and normalized changes. Approval is a POST against
   this exact validation revision. Any edit invalidates readiness/approval.
7. Commit reauthorizes the actor, checks Workspace availability and locks the
   batch. Revalidate mutable references and unique keys inside the transaction.
   A preview is not a reservation. Stale validation returns to review.
8. Invoke an entity allowlisted domain command with typed canonical input. Write
   domain rows, identities, provenance and row result in one atomic unit. No
   notification dispatch. Report actual committed counts, never merely parsed rows.

Recommended batch states: `UPLOADED -> NEEDS_MAPPING -> VALIDATING -> READY ->
COMMITTING -> COMPLETED`. Validation errors return to NEEDS_MAPPING with issues;
unsupported records cannot reach READY. FAILED records infrastructure failure and
the last safe checkpoint. CANCELLED applies before commit or between later units.
COMPLETED carries warning counts; no separate warning state is necessary. A retry
of FAILED explicitly resumes validation/commit from persisted evidence, not from
an untrusted client-reported row offset.

Row issues use `{severity, code, field, source_position, message, rule_version,
before, after}`. Raw PII is visible only on authorized detailed review; audit logs
and progress notifications contain counts/codes/opaque IDs. Example codes:
`REFERENCE_NOT_FOUND`, `AMBIGUOUS_DATE`, `SOURCE_ID_CONFLICT`,
`INVALID_STATE_EVIDENCE`, `NORMALIZED_PHONE`. An implausibly old but valid date can
warn; release before origination is an error. Warnings never weaken invariants.

### Transactions, failure recovery and scale

MVP: at most 1,000 Party master rows per batch, proposed 5 MiB decoded input limit,
all rows valid before approval, one atomic commit. These are initial conservative
limits to measure, not capacity claims. No silent skipping of bad rows. A rollback
must leave no imported Party, consumed transactional Party sequence increment,
identity or success marker. Record the failure afterward in a fresh scoped
transaction. Unchanged repeats are successful no-ops with provenance.

Larger jobs: bounded parsing into relational row envelopes with capped JSON,
batched reference lookups, paginated issues, explicit-Workspace worker turns.
No whole workbook/list of domain objects in memory. Bulk insert is appropriate
for staging/issues after validation; business `bulk_create` requires a specific
review because it bypasses save/validation/sequence behavior.

For larger domain imports, the commit unit becomes one independent aggregate:
Party and children, or a complete loan history and collateral/contract evidence.
Renewal-linked loans and shared releases/funding dependencies may require one
larger connected unit; reject oversized/cyclic unsupported graphs rather than
split invariants. Configuration/master dependencies commit first only under a
previewed partial-progress policy. Expose PARTIALLY_COMMITTED then, with an exact
unit ledger. Never advertise whole-file atomicity across committed chunks.

Use durable unit identity plus atomic result writes. Crash before commit rolls
back the unit; crash after commit discovers its result and does not duplicate it.
Bounded row locks serialize competing commits. If work moves outside a transaction,
add an expiring claim with attempt token; stale workers must fail the token check
before publishing. Cancellation cannot delete successful evidence: stop future
units and use normal reviewed compensating actions if correction is necessary.

Track parsed/validated/committed/unchanged/failed counts, durations, bytes, query
counts, memory, oldest pending work and retries. Limit concurrent jobs per Workspace
and globally; do not let imports starve servicing or the existing monitoring
one-hour acceptance target. No launch capacity claim until mixed multi-Workspace
load testing includes foreground servicing. A restricted management command with
explicit Workspace/actor is sufficient before a general distributed queue.

## Domain dependency and reuse analysis

The dependency order is a graph, not the proposed single chain:

```text
Workspace -> Party/roles/contact/address (independent of lending setup)
Workspace -> licence -> licence revision and series -> document sequences
Workspace -> product -> product version
Workspace/licence -> economic, metal-interest, fee policies
Party + series/licence/revision + product version + frozen terms
  -> loan + collateral/tranches + historical approval/disbursal evidence
  -> schedules/obligations + chronological events/accruals/allocations
  -> release/auction/renewal + custody/termination/reversal evidence
Storage hierarchy -> current placement and movement history
Lender Party + existing collateral -> funding graph
```

Rates are a dependency only when the frozen valuation method needs them. Never
require silver quotes for a gold-only loan or replace a historical appraisal with
today's rate. Resolve external references through the batch staging index and
Workspace identity bindings; do not depend on workbook sheet order. Deterministic
same-date event order must be retained explicitly, not inferred from new PK order.

| Existing component | Reuse decision |
| --- | --- |
| workspace_context, WorkspaceAccess, domain action checks | Reuse at every public service/worker boundary; they are not supplied by source files. |
| PartyForm phone, relation and identifier validation; Party model constraints | Extract narrowly into shared Party validation/create service, preserve interactive behavior through characterization tests. Do not implement a parallel importer-only identity domain. |
| Party merge service | Only for explicit reviewed duplicate resolution, never automatic name/phone matching. Extend merge to preserve portable aliases before allowing merges of imported identities. |
| create_license/create_series/configure_sequence | Suitable for authorized current setup with their actual signatures, validation and audit; historical revisions/expiry and imported counter handling require separate reviewed semantics. |
| Loans pure domain calculations, schema validators, canonical selectors | Reuse to validate/reconcile when the source contract matches; do not recalculate historical contractual facts using today's defaults. |
| record_loan_event | Potential internal reuse beneath a Loans historical command after exact event/payload/date/reversal checks. Its key hashes payload and embeds loan PK/kind; it does not independently authorize actor or validate complete financial meaning. New portable identity/digest must include effective date and relations. |
| create_pawn_draft/approve/disburse | Do not replay for history: draft consumes number, approval freezes current review, disbursal requires approval and creates current source/schedule evidence. Disbursal accepts an effective date, but that alone does not make it a history importer. |
| repayment/full release/reversal | Do not replay for history: repayment/release/reversal use current date; allocate against current balance, alter schedules/custody, and release consumes a number. |
| renewal/auction/funding operations | Do not call wholesale for historical graph restoration; settlement/opening, successor numbering, custody and immutable event side effects require dedicated historical evidence validation. |
| notices/document issuance/risk dispatch | Never invoke as historical side effects. Import issued bytes as historical artifacts after validation; refresh derived active monitoring separately without generating old alerts or resending jobs. |

## Identity, duplicates, provenance and numbering

Internal PK, operational business number, source/legacy reference and portable UUID
are four different concepts. Native records acquire a persisted ExchangeIdentity
on first canonical export (or at creation once that is adopted). Concurrent exports
use uniqueness and retry to choose one stable UUID. A Workspace has a portable
namespace UUID independent of its numeric Company PK and mutable presentation name.

Package references use `(source_workspace_uuid, entity_type, export_uuid)` and a
destination resolver remaps them. Imported IDs are preserved as source aliases;
destination export identities may preserve the UUID within its namespace or be
new with explicit lineage. Choose **new destination UUIDs with preserved source
aliases** for v1, so an import into an existing Workspace cannot collide with a
native object. Round-trip equivalence follows the alias bijection, not UUID equality.

External legacy identity is `(destination Workspace, source_system, entity_type,
external_id)`. A canonical digest includes meaningful fields and relationships,
not upload time or source row position. Same identity+same digest: no-op. Changed
digest: conflict requiring review, not an implicit overwrite. Same identity with
different records in one file: error. Existing local edits also block source
overwrite; compare current canonical projection to the accepted baseline.

Without reliable external IDs, use `(file hash,sheet,row)` only to identify an
exact upload retry. It cannot establish identity across a reordered/edited sheet.
Require a user-confirmed durable source key or an assigned downloadable mapping
before commit. Names, shared phones, PAN and old numbers are duplicate candidates,
not automatic identity authorities. If matching is ambiguous, block. For loan
legacy numbers include source register/licence/series/year when that is their
real uniqueness scope. A backfill paper register/page/line can supply the source ID.

Append-only ImportRecord provenance retains source hash/name/reference, source
row, source system/ID, canonical/rule/template version, actor/time, accepted digest
and material transformations. Raw uploads expire under a documented technical
cleanup policy; provenance retention follows the business record and later retention
policy. Existing created_at means actual local recording time; original source
creation/effective dates are separately preserved, not backdated via auto_now_add.
Historical staff names remain source actor references, never invented User accounts.
NATIVE/IMPORT/BACKFILL describe provenance; future API origin is reserved, not an
implemented endpoint. Detect later edits by comparing a fresh canonical digest;
complete edit history requires explicit domain change auditing, not an assertion
that every current Party edit is already audited.

### Number policy

Loans allocate a locked series/document-kind counter and never reclaim a committed
number. `PawnLoan.loan_number` is unique across the Workspace, not merely a series;
release numbers also have their own model constraints. A/1042 cannot be reset by
backfilling A/392. `configure_sequence` is setup, not a migration reset hook.

Default legacy migration uses a separate reviewed historical business-number
namespace (for example `H-<source-code>-<legacy-number>`, subject to field length
and uniqueness) and retains the exact old number in SourceIdentity/provenance.
It does not call live loan/release allocators or mark historical series issuable.
If an owner requires the exact legacy number in the operational number field,
allow only an explicit preservation mode: lock the relevant sequence/configuration,
check every number conflict, and reject overlap with future generated numbers.
Before enabling issuance on a migrated series, perform a separate audited cutover
that advances the counter monotonically beyond reserved/imported numbers. Never
silently skip, reuse, rewind or derive `next_number` from an arbitrary row.

Party MVP assigns a normal generated local Party code and retains the old code as
a legacy alias. This intentionally consumes one new local Party number per new
identity, never on preview or retry. Native export/reimport preserves the source
code in the contract but does not overwrite destination codes. Funding numbers,
collateral/storage public UUIDs and label URLs need the same distinction later.

## Historical migration, opening positions and backfill

Full history is operationally eligible only when a supported source supplies the
complete evidence needed by Loans. Preserve business dates, ordered event effects,
frozen terms, tranche balances, contractual obligations, allocation/reversal links,
custody and closure cause. Validate principal/interest/fees independently, then
compare canonical selectors at every event date and at cutover. ACTIVE needs a
valid remaining schedule and held collateral; CLOSED needs reconciled settlement,
termination and disposal/return/renewal evidence. DRAFT and APPROVED need their
appropriate evidence; a bare status string is never enough.

`Released` may map to `CLOSED` plus a release closure cause only when release evidence
exists. Stored states are DRAFT, APPROVED, ACTIVE, CANCELLED, CLOSED; overdue and
part-paid are derived conditions. A missing historical approval, item valuation,
allocation or required licence evidence is not fixed by pretending staff approved
it today. Keep the source staged/archival with a clear unsupported-evidence issue.
Any audited reconstruction policy needs a separate Loans ADR and guard/test review.

Opening position is **not currently supported**. Existing selectors recognize
specific event kinds and scheduled obligations; inserting principal/interest totals
or disguising them as a disbursal would misstate cash movement and DPD. Before this
mode, design a Loans-owned immutable opening-position source event at a cutover
date, distinguishing original principal from capitalized interest principal,
unpaid recognized interest, fees, unrecognized interest basis, remaining schedule
and original due dates, tranche allocations and custody. Preserve rate/rounding
contract and source evidence. Amend balance, interest, schedule, reversal, exposure,
report and PostgreSQL guards together; decide if pre-cutover reads are unavailable
or explicitly partial. Do not infer them from the opening total.

Progressive backfill uses the same staging/preview/identity services with origin
BACKFILL and paper references. Historical closed records can be added independently
once supported; historical active loans need either full history or the approved
opening-position mechanism. Never create a second active representation of an
already migrated loan. Pre-cutover history added after an opening position initially
remains documentary evidence excluded from financial folds. Replacing the opening
basis with full history requires a locked, reconciled, explicit compensation/
supersession design, preserving post-cutover actions. It is not an MVP update path.

Live operation and backfill can coexist because identities, namespaces and effective
dates differ, and commits lock/recheck only the reviewed aggregate. Do not use a
Workspace-wide maintenance transaction for routine backfill. New intake never waits
for a customer's entire paper archive to be entered.

### Accounting impact, explicitly

| Mode | Current accounting impact | Loans requirement |
| --- | --- | --- |
| Full history | No journal/voucher/posting or accounting-period operation exists to run. | Preserve immutable operational events and exact historical financial/custody effects; do not manufacture cash transactions. |
| Opening position | No general-ledger opening entry is appropriate. | A new reviewed Loans opening evidence contract is required; unsupported today. |
| Progressive backfill | No ledger replay or double posting. | Deduplicate against imported/native/opening identities; exclude documentary pre-cutover evidence from live balances until separately reconciled. |

Future accounting-system adapters may translate canonical records externally;
they do not authorize reintroducing retired accounting dependencies in Rokkad.

## Export design

`request_export(workspace_id, actor, scope, profile)` accepts explicit scopes, not
arbitrary querysets or model names. Resolve authoritative domain data in matching
RLS context; select control-plane metadata only through explicit company filters
and allowlisted projections. Materialize package content before an HTTP streaming
response leaves middleware scope. Subsequent download reads only the sealed file
after fresh authorization.

For bounded Party exports, assemble one consistent snapshot in a transaction and
publish after commit. For future full exports, define a worker-owned read-only
repeatable-read snapshot before the first data query; `workspace_context` remains
the sole context setter. Bootstrap missing portable identities in a preceding
authorized transaction, then verify snapshot coverage and retry if concurrent new
records lack identities. Record the actual snapshot time. Independently chunked
READ COMMITTED queries are not a coherent full export. A long snapshot has vacuum
and capacity costs: cap duration/size and later use a reviewed consistent snapshot
strategy or a brief customer-coordinated freeze, never silently inconsistent files.

The DB snapshot does not freeze file storage. Read and hash referenced bytes into
private staging, retain them until package sealing, detect missing/changed content,
and fail complete mode if any required bytes are unavailable. Immutable issued
artifacts should match their stored hash. Mutable photos require copy/hash checks
and retry or an explicitly incomplete result. Generate package hashes and counts,
validate every relationship, then atomically publish the sealed file. Failed
packages never become downloadable as successful exports.

MVP manifest includes format/version, profile/supported entities, source Workspace
UUID, export ID/time/application revision, snapshot semantics, entity counts,
file sizes/SHA-256, schema versions, attachment coverage, exclusions and warnings.
Do not hash the manifest into itself; record the final ZIP hash on ExportJob and
optionally provide a separate checksum. Hashes detect corruption, not authenticity.
Signing/key distribution is later hardening, not an implied guarantee.

Human XLSX sheets and CSV tables come from the same explicit projections. XLSX
keeps identifiers and untrusted text as text cells, no formulas/macros. CSV intended
for spreadsheet opening escapes formula-like text and declares a reversible escape
convention. Canonical JSONL preserves exact strings and is the lossless authority;
do not silently sanitize it and break hashes or identities.

## Authorization, isolation and offboarding

| Action | Recommended policy using current mechanisms |
| --- | --- |
| Create/upload/map/validate/inspect batch | `data.import` plus the entity read permission; explicit Membership or existing audited platform override. No role-name check. |
| Commit Party master | Above plus Party create permission using existing `contact.create` / `data.create` compatibility policy; domain service rechecks before replay. Subsequent mutable updates require edit, but MVP rejects changed-source updates. |
| Commit configuration | `data.import` and `workspace.settings.manage`; no automatic local role-template overwrites. |
| Historical financial commit | Owner plus import/settings permissions initially (or audited platform override), and domain action permissions for the supported evidence. Define a specific action through the existing catalog if delegated historical migration is introduced. |
| Entity export | Existing entity export/read policy; Party uses `contact.export` / `data.export`. |
| Full Workspace export/download | Canonical owner with Membership or audited platform override; `data.export` and `data.export.bulk`. Default no delegated admin full-PII access. Delegation later must be an explicit existing-catalog grant/policy decision, never role label. |
| Request/cancel closure | Canonical owner with Membership or platform override through Orgs; preserve existing transition restrictions. |
| Schedule/permanently erase | Current scheduling remains platform-only. Physical erasure requires a separately approved, auditable retention workflow. |

Recheck roles/membership/owner/lifecycle at commit, worker unit start and download.
Permissions are separate from billing; authorized recovery export must remain
available after paid access ends. Test the actual explicit route through both
middleware layers; adding a URL alone does not establish a recovery exception.
For SUSPENDED preserve the platform restriction on resumption; no importer may
change it. ARCHIVED/DELETION_PENDING exports use the existing owner recovery boundary.

### Fail-closed argument and proof obligations

No source field can select the destination Workspace, actor, model, internal PK,
role or storage path. Service validates actor/Workspace, then opens or verifies
matching `workspace_context`. New rows carry that Workspace directly. Scoped
queries and forced RLS prevent other-Workspace reads/writes; relationship guards
prevent mixed ownership. Global control-plane data uses explicit company filtering.
Workers accept explicit Workspace IDs and never enumerate tenants implicitly.
Artifacts and source files resolve from authorized batch/job rows, not paths from
requests. Missing context or permission is an error before replay or side effects.

This establishes a design argument, not an implemented security proof. Restricted
SQL, HTTP, worker/crash, file and control-plane tests listed in the plan must prove
each boundary before release, including platform actors and guessed valid IDs.

### Controlled offboarding

Keep export job state separate from the four Workspace lifecycle states. An
owner may export while ACTIVE, archive through the existing audited service,
request a fresh final export once writes have stopped, then request closure.
Store export completion/checksum and acknowledgement (or explicit decline where
policy permits) on a future Orgs offboarding request. Export requested does not
mean export delivered, and acknowledgement does not prove the customer has a backup.

Platform scheduling uses ARCHIVED -> DELETION_PENDING under the existing transition
service. A technical retention plan identifies each data category and action:
DELETE, ANONYMIZE, RETAIN_UNTIL, LEGAL_HOLD, with authority/reason/review date.
Unknown policy blocks erasure. No legal duration is selected in this design.
Cancel back to ARCHIVED before execution; atomically lock the request/Workspace
against cancellation and erasure races. A resumed Workspace needs fresh final
export and retention review before another erasure attempt.

Purge business rows/files by an explicit inventory and dependency plan. PROTECT
FKs and immutable database guards intentionally prevent a casual cascade; future
erasure may require a tightly scoped, owner-maintained DB routine with narrowly
granted execution. Its exact privileges, hold checks and immutable-evidence
exception need a separate ADR and adversarial tests. Ordinary import/export and
web roles never acquire BYPASSRLS or a generic trigger-disable switch.

Customer identities/loans/docs follow the approved category policy. Memberships,
invitations and Workspace roles are removed only at the correct final step;
global user accounts and memberships elsewhere survive. Financial operational
evidence and audit/billing metadata may require retention; do not anonymize them
in place if that violates immutable evidence. Restricted retained storage or a
Workspace tombstone may be required before physical Company deletion. Subscription
settlement/provider retention is separate from lifecycle; no automatic refund.

Remove original files, generated artifacts, imports, exports and temporary copies
through a retryable purge ledger; shared renewal lineage must be checked before
deleting bytes. Revoke future export access on purge start. Backups have separately
documented expiry and restore suppression/tombstones so a restore cannot resurrect
erased data. Distinguish live erasure complete from retained records/backups pending;
issue an accurate disposition receipt. No permanent-deletion claim until database,
storage, replicas/caches and recovery procedures meet the approved policy.

## Security controls and deferred hardening

MVP controls: file signature/extension allowlist, byte/row/column/cell limits,
strict encoding/date/decimal parsing, reject NaN/infinity and overprecision,
escaped HTML previews, CSRF on every mutation, per-Workspace private storage,
random server filenames, paginated PII access, no-store downloads, attachment and
nosniff headers, fresh download authorization and short artifact TTL. No arbitrary
URL fetch or client-selected storage key. Hash and validate uploads before approval.

CSV parser must preserve leading-zero identifiers and explicitly select delimiter/
locale. Formula-looking text is data, never executed. XLSX addition must reject
macros, external links/formula cells for import, oversized dimensions/shared strings,
unexpected members and excessive decompressed totals/ratios; enforce limits while
reading, not merely from ZIP headers. Do not trust cached formula results.
ZIP packages reject absolute/drive/UNC paths, `..`, symlinks, duplicate or
case-colliding members and undeclared members. Never extract to caller paths.
Validate allowed relative file paths and hashes before use.

Restrict temporary directory access and clean failed/expired uploads on a bounded
schedule, retaining required provenance. Native storage paths do not include a
complete authorization policy. Encrypt transport and use private encrypted storage
where deployed; current local storage does not establish production encryption
or bucket/CDN privacy. Those remain deployment acceptance items.

Later hardening: malware scanning before serving binaries, stronger isolated file
parser resource limits, organization quotas and measured fair scheduling, revocable
storage delivery integration, signed manifests if needed, and audited erasure/
retention tooling. Binary attachment ingestion stays off until its controls exist;
calling scanning later does not justify enabling unreviewed binary ingestion now.

## Explicit answers to the twenty architecture questions

1. **v1 contents:** versioned envelope, Party master profile first; concrete expanded
   loan/evidence/configuration entities and coverage boundaries in the contract draft.
2. **Entity/model map:** inventory above and field map in the contract; customer is
   Party plus roles, payment is PawnLoanEvent plus allocations, release is separate evidence.
3. **Safe service reuse:** context/access, shared Party validation/create seam,
   current setup commands, pure domain calculations and canonical read selectors.
4. **Unsafe historical replay:** draft/approval/disbursal/repayment/release/renewal/
   reversal/auction/funding workflows wholesale; notification and document issuance.
5. **Provenance:** directly scoped ImportRecord, source aliases and frozen batch
   configuration, not many migration columns on every business model.
6. **Legacy numbers:** exact source alias plus separate historical namespace by default;
   exact operational preservation requires explicit conflict-free cutover.
7. **Idempotency:** unique scoped source identity, accepted canonical digest and
   atomically committed result; changed input conflicts instead of overwriting.
8. **Mappings:** immutable batch JSON snapshot first, Workspace template versions later.
9. **Normalization:** allowlisted pure versioned transformations with before/after evidence.
10. **Issues:** relational row/field/source-position issues with code, severity and revision.
11. **Staging:** private raw file plus relational rows/identity/results with capped JSON values.
12. **Transactions:** bounded whole Party batch initially; explicitly declared aggregate units later.
13. **Partial failure:** committed unit ledger and replay checks; no blind rollback of successful history.
14. **Historical states:** Loans-owned complete evidence establishment and reconciliation;
    unsupported/incomplete states remain staged, not activated by status assignment.
15. **Accounting:** retired in all three modes; opening-position Loans semantics still need design.
16. **Stable exports:** persisted opaque UUID binding per native entity and Workspace namespace;
    destination identities retain source aliases on import.
17. **Attachments:** file index with relative package paths, relationships, hashes and exact bytes.
18. **Deletion:** existing lifecycle plus separate export/offboarding/retention records;
    no ordinary cascade or unreviewed legal assumptions.
19. **MVP:** Party master CSV + canonical JSONL import, staging/preview/commit/export and
    isolation/idempotency/round-trip tests. Loans, XLSX, binaries and erasure follow.
20. **Required refactors:** close generic model write-through, extract shared Party command/
    validators, preserve identity through merge, register RLS and explicit serializers.
    Historical Loans and offboarding need targeted later contracts/guard work; no broad model split.
