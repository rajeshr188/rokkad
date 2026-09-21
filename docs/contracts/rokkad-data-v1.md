---
status: partially-implemented
owner: project
updated: 2026-09-12
tags: [contracts, portability, schema]
---

# Rokkad Data Format v1 — first contract proposal

Current Loans implementation includes bounded
[complete-history JSONL](loan-history-jsonl.md) and
[opening export/restore](loan-opening-export-v1.md), with separate admission
requirements and explicit partial coverage. Neither is a complete Workspace
archive or a general historical-facts importer. See the
[current Loans audit](../architecture/loans-portability-audit.md) for capabilities,
limitations and proposed changes awaiting owner review. Earlier increment notes
below describe their own checkpoints, not the current Loans implementation.


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





The Party master profile is implemented; the expanded financial/archive profiles
remain drafts. See the [architecture](../architecture/data-portability.md)
and [implementation plan](../plans/data-portability.md). Freeze a machine-readable
schema and conformance fixtures for each profile before its first implementation.
The initial executable profile is **party-master/1**; broader entities below are
design candidates requiring their own detailed evidence schemas before release.

## Implemented party-master/1 constraints

The frozen [machine schema](party-master-v1.schema.json) is also served at the
Party export screen's `?schema=1` URL. CSV and bare JSONL are accepted. XLSX, ZIP
packages, manifests, child collections, files, nonempty extensions, updates and
automatic merges are not implemented. Export headers and the screen explicitly
declare partial coverage. Source Workspace UUID appears in the JSONL filename
and `X-Rokkad-Source-Namespace`; supply it when uploading canonical JSONL.

The implemented profile uses typed Party identity bindings. Destination UUIDs are
new; source aliases preserve identity. CSV requires a mapped stable external ID;
JSONL uses its canonical UUID in a `rokkad:<source-workspace-uuid>` namespace.
`source_refs` are preserved provenance only, never trusted as extra identity
bindings. Existing same-Workspace export IDs can be recognized as unchanged.
Changed source data or changed destination Party fields are blocking conflicts.

Optional empty master strings normalize to null (and to the existing model's
blank string on commit). This deliberately narrows the general draft's empty/null
distinction to the current Party domain. All form-normalized changes appear in
preview. Source `recorded_at`/`source_recorded_at`, original business code and source
references remain in immutable committed row provenance. Local timestamps and
Party codes are generated locally. Export includes the original code on its source
reference when available. Nonempty Party metadata and photos are explicitly excluded,
not represented as restored empty child collections.

Source reference arrays have at most ten members. More history, files above 5 MiB,
more than 1,000 records, or fields above the parser limits are rejected rather than
truncated. An empty Workspace exports an empty file/count zero; it needs no import
(empty uploads are rejected). Native records that were created outside today's form
rules may require visible normalization or validation review when reimported.
The executable schema validates structure; the domain validator additionally enforces
Party formats and paired relation fields.

## Released partial Party bundle: party-bundle/1

This implemented ZIP contract is distinct from the broader proposed archive below.
It has exactly six `entities/party-{master,contact,address,identifier,role,relationship}.jsonl`
members, six matching `schema/party-<name>-v1.schema.json` members, `README.txt` and
`manifest.json`. The six existing business schemas are unchanged. All member names
are server-defined; the ZIP is built in memory without filesystem extraction.

Manifest fields are: `format="rokkad-data"`, `profile="party-bundle/1"`,
`source_namespace` (UUID), `scope="PARTIAL"`, `snapshot` containing
`consistency="workspace-row-locks"` and ISO timestamp `captured_at`, `entities`,
`import_order`, boolean `zip_import_supported`, `exclusions`, `limits` and `files`.
New exports set the capability true; previously exported false values remain accepted.
Each entity entry has `profile`, `path`, `schema`, integer `count` and `coverage`
(INCLUDED when nonempty, EMPTY otherwise). All six entries are required, in master,
contact, address, identifier, role, relationship order. `import_order` repeats their
paths in that order. Each file entry has `path`, exact `bytes` and lowercase hex
SHA-256 `sha256`; every member except the manifest itself is indexed. The complete
ZIP checksum is supplied outside the archive in the HTTP header and audit record.

Limits are 1,000 records and 5 MiB per entity profile; snapshot role types are also
bounded to 1,000. All-or-nothing export failure preserves the individual profiles'
lossless-export checks. Exclusions explicitly cover Loans, files/KYC, Party metadata,
role-type definitions, Workspace settings/access, mapping presets and other apps.
Namespace is lineage, not destination authority. ZIP validation/staging is supported;
explicit aggregate commit is now supported for wholly unfinished staged bundles,
through a signed dependency-aware preview. Extracted nonempty files also continue to use
the staged JSONL import flow. ZIP intake is bounded to 31 MiB compressed/expanded,
exactly 14 fixed members and 128 KiB per metadata member. It verifies all checksums,
byte sizes, counts and schemas, rejects unsafe/unknown members and requires child
references to resolve to bundled master IDs under the same namespace. See the
[staging contract](../adr/2026-09-12-party-bundle-staging.md).
See the [bundle ADR](../adr/2026-09-12-party-export-bundle.md) for the snapshot proof.

## Proposed full-archive encoding, package and capabilities

Use UTF-8 JSON for manifest/schema/configuration and JSON Lines (one JSON object
per line) for canonical entity collections. No database dump, Python object pickle,
Django serializer envelope or model-name lookup is part of this format.
CSV and XLSX map into these definitions. JSONL supports explicit nulls, nested
frozen evidence and stable typed relationships without inventing CSV JSON syntax.

```text
manifest.json
workspace.json
entities/parties.jsonl
entities/party_roles.jsonl          # later profile, not silently omitted if promised
entities/loans.jsonl                # later profile
entities/loan_events.jsonl          # later profile
files.jsonl                        # when binary coverage is supported
documents/<file-uuid>/<safe-name>   # authorized copied bytes, no storage URLs
schema/<profile>.schema.json
README.md
```

A package can contain multiple entity files or deterministic numbered chunks
declared in the manifest. A single Party import may also be a canonical JSONL or
mapped CSV upload with an explicit profile chosen by the operator. Bare files
are not complete Workspace packages.

Proposed manifest (values are illustrative; checksums must be computed on actual bytes):

```json
{
  "format": "rokkad-data",
  "version": "1.0",
  "profile": "party-master/1",
  "export_id": "9d8214ac-daa4-4bcb-a02b-63491d14331e",
  "source_workspace_id": "6162ee14-0d2a-4735-a1ba-beb3ba631bd8",
  "exported_at": "2026-09-11T10:00:00Z",
  "application_revision": "revision-of-exporting-build",
  "snapshot": {"consistency": "transaction", "captured_at": "2026-09-11T09:59:59Z"},
  "scope": {"kind": "PARTIAL", "entities": ["parties"]},
  "capabilities": {"importable": ["parties"], "archive_only": []},
  "entities": {"parties": {"count": 1, "schema": "party-master/1"}},
  "files": [{"path": "entities/parties.jsonl", "bytes": 842, "sha256": "computed-64-hex-digest"}],
  "attachments": {"coverage": "EXCLUDED", "count": 0},
  "exclusions": ["Party child collections", "Binary files", "Loans", "Workspace access grants"],
  "warnings": []
}
```

Manifest required: the fields shown, with real digest/size values for every member
except the manifest itself. Include schemas, README and workspace.json in its file
index. Package checksum lives outside the package/ExportJob. `scope.kind=FULL`
requires reviewed coverage of all applicable families from the architecture inventory;
an unknown/unmapped family or missing required attachment blocks FULL. `EMPTY`
coverage is different from `EXCLUDED`, `UNSUPPORTED` or `MISSING`. Filtered exports
identify the filter and always report PARTIAL. Manifest source Workspace is lineage,
never import destination authority.

`workspace.json` has required `id`, `name`, `timezone`, `default_currency`, and
optional display branding/reference fields explicitly allowed by the profile.
Timezone/currency describe the package interpretation (proposed Asia/Kolkata and
INR for this deployment), not a claim that Company currently stores those fields.
No owner login, access grant, subscription activation or domain registration is
restored from it. These values may be exported as separate archive-only metadata.

## Common values and identity

Bare canonical files require the source namespace to be explicitly supplied and
frozen on the batch; UUIDs alone must not be guessed to belong to a previous source.

| Value | Contract |
| --- | --- |
| `id` | Required opaque UUID string; unique by source Workspace and entity type. Persist export identity separately from PK. |
| Reference | `{ "entity": "parties", "id": "uuid" }` within the package's source namespace. No numeric database PK or row-number reference. Required targets must be in the package or explicitly resolved to a reviewed existing destination alias. |
| String | Unicode, preserved exactly after declared normalization. Display name limit 255 for Party v1; field-specific limits checked before commit. No invisible trimming by serializers. |
| Null | JSON `null` means absent/unknown; required fields reject it. Omitted optional fields equal null for create; full exports emit them explicitly. `""` remains a distinct actual empty string where permitted. No sentinel date/zero for unknown. Updates are not patch semantics in v1. |
| Dates | `YYYY-MM-DD` local business date; never infer date from import time. |
| Instants | RFC 3339 string with explicit offset; exporters emit UTC `Z`. Date-only source facts stay dates and must not be invented as midnight timestamps. |
| Decimal | Base-10 JSON string without grouping/currency symbol/exponent; finite values only. Reject excess precision instead of silently rounding. Binary floats are forbidden for monetary/weight/rate fields. |
| Money | `{ "amount": "50000.00", "currency": "INR" }`; loan principal/allocation inputs support 2 fractional digits, operational evidence may need 4. Per-field schema defines scale (not globally 2). Archive Rates may contain USD; operational Loans import initially INR only. |
| Weights | Gram decimal strings to 4 fractional digits. Current operational collateral requires gross and net strictly positive and net no greater than gross. |
| Purity | `purity_percent`, strictly above 0 and at most 100 with 4 fractional digits. `91.6000` is 916 parts per thousand. Do not import 916 into the percentage field. |
| Interest | `monthly_interest_percent`, up to 6 fractional digits; `2.000000` means 2% per month, not the ratio 0.02. LTV fields separately use ratios (`0.7500` means 75%). |
| Boolean | JSON true/false. CSV adapter accepts only an explicitly selected spelling set. |
| Enum | Case-sensitive stable code from the profile. Reject unknown operational values; no translated display-label matching without an explicit adapter map. |
| Metadata | `extensions` namespaced JSON only with explicit schema/size limits. Does not control authorization, calculations or identity. No secrets or unrestricted ORM JSON pass-through. |
| Ordering | Entity export sorted by portable ID; event chronology has an explicit per-loan sequence. Never reconstruct chronology from imported PKs. |

Each exported record includes optional `source_refs` (source system, external ID,
legacy number/register reference), `recorded_at`, `source_recorded_at`,
`origin` (NATIVE/IMPORT/BACKFILL), and an archive actor reference when applicable.
Local import recorded time/actor are new facts; source times/actors remain provenance.
Current schema-derived times do not prove a historical source event happened then.
API origin may be added later when an API exists.

Destination import creates new local export UUID bindings and preserves source
UUID aliases. Repeated exports from the same Workspace keep identical IDs. Round
trip uses an explicit source/destination identity map; regenerated Party codes
and local recorded timestamps are allowed differences, not lost historical values.
Public collateral/storage UUIDs and QR links are separately described historical
identities; they are not reused as global unique destination PKs on a clone.

## Executable first profile: party-master/1

Customer is an application label for Party in relevant roles. Do not introduce a
Customer model or silently grant BORROWER/PORTAL_CUSTOMER roles from a file name.
This first profile deliberately covers the Party master only. It is useful for
legacy counterparty lists and proves the pipeline without Loans configuration.

| Field | Required/input default | Current model mapping and constraints |
| --- | --- | --- |
| id | Required for canonical package; mapped legacy rows need a durable source identity before commit | ExchangeIdentity/SourceIdentity; never Party.pk |
| business_code | Optional | Party.party_code exported; imported as source legacy code. New local code generated by existing allocator. |
| name | Required, nonempty, <=255 | Party.display_name |
| legal_name | Optional | Party.legal_name |
| kind | Required | Party.party_type: INDIVIDUAL, ORGANIZATION, BANK, GOVERNMENT, INTERNAL_WORKSPACE, OTHER. Source mapping may explicitly default INDIVIDUAL with INFO. |
| status | Required | ACTIVE, INACTIVE, BLOCKED, ARCHIVED. Imported status must not bypass ordinary Party restrictions. |
| relation_kind | Optional | SON_OF, DAUGHTER_OF, CARE_OF, PARENT_OF, FATHER_OF, WIFE_OF, HUSBAND_OF, OTHER |
| relation_name | Optional, paired with relation_kind | Party.relation_name; reject an unpaired relation |
| primary_phone | Optional text | Party.primary_phone; shared current E.164 normalization with explicitly chosen source region. Preserve source string in provenance. |
| primary_email | Optional | Party.primary_email; existing validation |
| tax_pan | Optional | Party.tax_pan, uppercase/trim via explicit normalization; <=16 |
| gstin | Optional | Party.gstin, uppercase/trim via explicit normalization; <=24 |
| risk_label | Optional | Party.risk_level, <=32; existing free text, not a new standardized scoring enum |
| credit_hold | Required, mapping may explicitly default false | Party.credit_hold |
| extensions | Optional object | Reviewed Party metadata keys only. Unsupported metadata must be reported in coverage, not silently serialized. |
| source_refs, source_recorded_at | Optional | Provenance, not identity matching by name |
| recorded_at | Export field | Actual Party.created_at source timestamp; destination records actual import time |
| photo_ref | Optional archive reference, unsupported for initial import | Party.profile_photo; Party-only export marks binary exclusion. It is not a downloadable raw storage URL. |

An initial master export of a Party with child contacts/KYC/roles is explicitly
partial; it must not imply those collections were empty. Source `is_verified`,
portal grants, account IDs, and role changes are outside this profile.

Example canonical record (UUIDs illustrative):

```json
{
  "id": "147970db-f587-43d4-8311-9919fc4e4195",
  "business_code": "C-0042",
  "name": "Asha Devi",
  "legal_name": null,
  "kind": "INDIVIDUAL",
  "status": "ACTIVE",
  "relation_kind": null,
  "relation_name": null,
  "primary_phone": null,
  "primary_email": null,
  "tax_pan": null,
  "gstin": null,
  "risk_label": null,
  "credit_hold": false,
  "extensions": {},
  "source_refs": [{"system": "paper-register-1", "external_id": "page-12-line-3", "legacy_number": "C-0042"}],
  "source_recorded_at": null,
  "recorded_at": "2026-09-11T09:30:00Z",
  "origin": "BACKFILL",
  "photo_ref": null
}
```

CSV mapping example separates column selection from transformation:

```json
{
  "mapping_version": 1,
  "entity": "parties",
  "columns": {"Customer No": "source.external_id", "Party": "name", "Ph No": "primary_phone"},
  "defaults": {"kind": "INDIVIDUAL", "status": "ACTIVE", "credit_hold": false},
  "normalization": [{"field": "primary_phone", "rule": "phone_e164", "version": 1, "region": "IN"}],
  "source_system": "register-export-1"
}
```

Defaults and transformations are shown in preview and bound to approval.
`12/8/25` requires explicit date order and century interpretation; an adapter must
not guess. `22KT` is not exactly synonymous with assayed 916 purity. Mapping it to
91.6000 requires a selected source convention and a warning; an exact karat-derived
fraction has different precision. `50,000/-` conversion requires a declared INR
currency/grouping/suffix rule, preserving the original. IDs and phone numbers
remain strings so leading zeroes are retained.

## Expanded entity field proposal

For each collection below `id` and relevant source/provenance envelope apply.
Fields marked `?` are nullable/optional. Others are required in the proposed
entity representation, with operational eligibility checked separately. This is
the initial domain field map; do not enable generic JSON import for these entities
until nested evidence, enum values and invariants have executable schemas.

| Collection | Current concepts/models | Proposed fields |
| --- | --- | --- |
| party_role_types | PartyRoleType | key, label, description?, active; imported role definitions never become Workspace authorization roles |
| party_roles | PartyRole | party_ref, role_type_ref, status ACTIVE/INACTIVE/ENDED, segment?, effective_from?, effective_to?, extensions? |
| party_contacts | PartyContactMethod | party_ref, type PHONE/MOBILE/WHATSAPP/EMAIL/WEBSITE/OTHER, label?, value, primary, source_verified?; no imported proof of verification |
| party_addresses | PartyAddress | party_ref, type REGISTERED/BILLING/SHIPPING/HOME/WORK/KYC/OTHER, line1, line2?, area?, city, state?, postal_code?, country, default, source_verified? |
| party_identifiers | PartyIdentifier | party_ref, type PAN/AADHAAR/GSTIN/CIN/UDYAM/PASSPORT/DRIVING_LICENSE/OTHER, value, expires_on?, source_verification?; internal search hashes are implementation details |
| party_relationships | PartyRelationship | from_party_ref, to_party_ref, relationship_type, notes?, active; exact type dictionary frozen before release |
| party_documents | PartyDocument | party_ref, identifier_ref?, type KYC/TAX/CONTRACT/LICENSE/OTHER, title, file_ref?, expires_on?, source_verification? |
| licences | LoanLicense | name, number, authority?, issued_on, expires_on, active, notes? |
| licence_revisions | LoanLicenseRevision | licence_ref, revision, kind, name, number, authority?, issued_on, expires_on, notes?, file_ref?, source_actor? |
| series | LoanSeries | licence_ref, code, name, active |
| numbering | LoanNumberSequence | series_ref, document_kind PAWN_LOAN/PAWN_LOAN_RELEASE, prefix, width, next_number, maximum_number, active; exported checkpoint only, never automatically applied |
| products | LoanProduct | code, name, active |
| product_versions | LoanProductVersion | product_ref, version, status DRAFT/ACTIVE/RETIRED, available_from?, available_until?, repayment_structure, amortisation_method, payment_frequency, minimum_tenor_months, maximum_tenor_months, operational_grace_days, extra_payment_rule, calculation_contract_version |
| economic_policies | PawnLoanEconomicPolicy | licence_ref?, effective_from, effective_until?, active, valuation_method, maximum_ltv_ratio, advance_interest_periods, interest_method, partial_month_method, cutoff_days, lower_fraction, capitalization_interval_periods, rounding_method, currency_quantum |
| metal_interest_policies | PawnMetalInterestRatePolicy | licence_ref?, metal, monthly_interest_percent, effective_from, effective_until?, active |
| fee_policies | PawnLoanFeePolicy | licence_ref?, code, name, calculation_type, value, deducted_at_disbursal, effective_from, effective_until?, active |
| loans | PawnLoan | licence_ref, licence_revision_ref?, series_ref, borrower_ref, product_version_ref, business_number, state, principal, monthly_interest_percent, loan_date, tenure_months |
| loan_items | PawnCollateralItem | loan_ref, description, metal GOLD/SILVER/OTHER, gross_weight_g, net_weight_g, purity_percent, allocated_principal?, monthly_interest_percent?, interest_policy_ref?, draft_appraised_value?, custody_state, storage_location_ref?, renewed_from_ref?, physical_source_uuid? |
| loan_policy_snapshots | LoanPolicySnapshot | loan_ref, policy_version, complete frozen calculation/valuation/rounding fields (same meanings as policies); never resolve from current defaults |
| approvals | PawnLoanApprovalSnapshot | loan_ref, version, approved_at, source_actor?, terms_evidence, source_fingerprint; map embedded entity references and verify canonical evidence |
| disbursals | PawnLoanDisbursalSnapshot | loan_ref, approval_ref, policy_snapshot_ref, event_ref, gross_principal, monthly_interest, advance_interest_periods, advance_interest, deducted_fees, net_disbursed, tranche_evidence, fee_evidence |
| loan_events | PawnLoanEvent | loan_ref, sequence, kind, effective_date, recorded_at, reversal_of_ref?, values, typed_evidence, source_actor?; values contain explicitly signed/typed financial effects per released event schema |
| interest_accruals | PawnLoanInterestAccrual | loan_ref, event_ref, period_number, period_start, period_end, period_fraction, calculation_base, unrounded_interest, recognized_interest, finalized_at, source_actor? |
| accrual_lines | PawnLoanInterestAccrualLine | accrual_ref, item_ref, principal_base, monthly_interest_percent, period_fraction, unrounded_interest, calculated_interest, advance_interest_applied, recognized_interest |
| principal_allocations | repayment/closing/opening line models | event_ref, item_ref, predecessor_item_ref?, operation REPAYMENT/CLOSING/OPENING, order, monthly_interest_percent, balance_before?, principal_applied?, principal_settled?, principal_opened?, balance_after?; conditional required fields by operation |
| schedules | RepaymentScheduleVersion | loan_ref, source_event_ref, version, contract_version, disbursed_on, maturity_date, principal, contractual_interest, rounding_adjustment, supersedes_ref? |
| obligations | RepaymentObligation | loan_ref, schedule_ref, sequence, due_date, principal_due, interest_due, opening_principal, closing_principal |
| schedule_changes | RepaymentScheduleChange | loan_ref, schedule_ref, source_event_ref, kind, effective_date, reason?, reversal_of_ref? |
| obligation_allocations | ObligationAllocation | loan_ref, event_ref, obligation_ref, component, amount, allocation_order, reversal_of_ref? |
| releases | PawnLoanRelease | loan_ref, business_number, effective_date, full_release, settlement_amount, principal_amount, interest_amount, fee_amount, event_ref, catch_up_accrual_ref?, valuation_evidence |
| release_items | PawnLoanReleaseItem | release_ref, item_ref, valuation_evidence, returned_at |
| release_batches | PawnReleaseBatch/Line | effective_date, total_amount, paid_by, payment_reference?, lines[{release_ref, borrower_name, collector_name, collector_is_borrower, relationship?, authorization_note?}] |
| release_reversals | PawnLoanReleaseReversal | release_ref, event_ref, catch_up_reversal_ref?, reason, recorded_at, source_actor? |
| auctions | PawnLoanAuction/items | loan_ref, business_number, attempt_number, state, notice_date, scheduled_date, started_at?, completed_at?, cancelled_at?, cancellation_reason?, buyer_name?, buyer_reference?, recovery_amount?, principal_amount?, interest_amount?, fee_amount?, event_ref?, catch_up_accrual_ref?, items[{item_ref,snapshot,disposed_at?}] |
| renewals | PawnLoanRenewal | source_loan_ref, successor_loan_ref, business_number, mode, renewal_date, source_principal_amount, source_capitalized_principal_amount, interest_settled, fees_settled, principal_paid, top_up_amount, successor_principal_amount, successor_capitalized_principal_amount, successor_advance_interest, successor_deducted_fees, settlement_event_ref, opening_event_ref, catch_up_accrual_ref?, valuation_evidence |
| auction_reversals / renewal_reversals | matching reversal models | source_action_ref, reversal_event_refs by role, catch_up_reversal_ref?, reason, recorded_at, source_actor? |
| custody_events | PawnCollateralCustodyEvent | item_ref, source_action_ref, from_state, to_state, effective_date, recorded_at, source_actor? |
| storage_locations / movements | PawnStorageLocation/StorageMovement | location: parent_ref?, level, code, name, capacity?, active, source_public_uuid?; movement: item_ref, from_ref?, to_ref?, kind, reason?, workflow_source, source_reference?, moved_at, source_actor? |
| appraisals | CollateralAppraisal | item_ref, version, effective_at, appraised_value, status, method, evidence_reference, review_notes?, valuation_context, supersedes_ref?, recorded_at, source_actor? |
| rate_sources / quotes | RateSource/Rate | source: name, location?, tax_included; quote: source_ref, metal GOLD/SILVER/BRONZE (mapped from title-case storage), currency INR/USD, purity_code 24k/22k/18k/14k/10k, buying_per_gram, selling_per_gram, effective_at, recorded_at, supersedes_ref?, withdrawal, reason?, source_snapshot |

`payments` is a convenience filtered view of `loan_events.kind=REPAYMENT` with
principal/interest/fee and obligation allocations; it must not create duplicate
canonical events. RELEASE_RECEIPT is separately tied to a release. Event kinds:
DISBURSAL, REPAYMENT, INTEREST_ACCRUAL, INTEREST_CAPITALIZATION, RELEASE_RECEIPT,
AUCTION_RECOVERY, RENEWAL_SETTLEMENT, RENEWAL_OPENING, REVERSAL. There is currently
no OPENING_POSITION kind; that proposed future type cannot be imported in v1.

Loan state codes: DRAFT, APPROVED, ACTIVE, CANCELLED, CLOSED. Custody codes:
IN_VAULT, WITH_CUSTOMER, WITH_FUNDING_LENDER, AUCTION_DISPOSED, RENEWAL_TRANSFERRED,
RENEWAL_REVERSED. Repayment structure codes: SINGLE_PAYMENT_BULLET,
PERIODIC_INTEREST_BULLET, FLEXIBLE_PARTIAL_PAYMENT, INSTALLMENT, LEGACY_UNSPECIFIED.
The last can describe existing history; it does not authorize pretending an unknown
legacy repayment contract is serviceable. Amortisation: NONE/EMI/EQUAL_PRINCIPAL;
frequency: AT_MATURITY/MONTHLY/FLEXIBLE; extra-payment rule: NOT_APPLICABLE,
REDUCE_PRINCIPAL, KEEP_PAYMENT_SHORTEN_TENURE.

### Remaining full-archive extensions

These are required for FULL coverage where present; the first milestone neither
imports them nor promises their final nested schema. Each is a bounded later
profile, not a generic dictionary of model fields.

| Profile family | Explicit field groups needed |
| --- | --- |
| funding | Lender ref; funding number/state; draft terms/collateral; immutable principal/rate/dates/LTV/quantum terms; cancellation reason/actor; events with sequence/kind/operation/effective date/principal/interest/fees/reversal; pledge/return and reversal source refs, item values, dates and frozen valuation/return evidence. |
| physical verification | Session scope/status/start/completion actors/times; expected item/location/custody/loan description; observation classification/location/notes; resolution outcome/reason/value/compensation/reference. |
| monitoring | Policy scope/version/effective dates/supersedes/amendment reason; compliance profile, maturity/grace/DPD/LTV thresholds, age limits, eligible custody and severity mapping. Snapshot amounts/status/as-of/calculation provenance; transition event old/new values and trigger identity; alert status/resolution refs. Derived snapshots remain archive-only on import. |
| communication | Party consent source and opt-out evidence; communication policy; notice recipient/channel/schedule/source refs/payload snapshot; templates/render versions/locales; job/event/batch history and delivery attempts; artifacts and provider receipt business status. Exclude credentials and bearer identifiers. No replay of delivery. |
| document configuration/issues | Layout and print-profile identities/revisions/state/definitions/hashes, assignments to licence/series, assets; issue type/source ref/fingerprint/layout/profile/render and payload versions/hashes/file ref/prior-issue ref/issued-at/source actor. Translate source_id and embedded refs explicitly. |
| media | Parent entity ref, file ref, original filename/MIME/size/SHA-256/captured-at/source actor, workflow source/inherited-from; label issue source QR text retained as evidence, no destination URL authority. |
| audit/control plane | Workspace configuration allowlist, roster role definitions and grants as non-executable history, permitted audit actions/actors/timestamps/reasons, subscription/payment/refund references/amounts/currency/status/dates. No global account graph or provider secrets. |

## Files and binary references

`files.jsonl` entries: required `id`, `path`, `size_bytes`, `sha256`, `media_type`,
`owner_ref`, `purpose`; optional `original_filename`, `source_captured_at`,
`inherited_from_ref`. Paths are forward-slash relative package paths with safe
generated components. Structured records refer to file UUIDs. Multiple records
can reference the same copied bytes with explicit lineage; a file's authorization
does not derive from its filename. Preserve issued-document exact byte checksums.

Missing files have explicit unresolved references and issues; do not substitute
empty files or silently call the package complete. No storage URL, local absolute
path, expiring download token or live provider credential appears in the contract.
An export lists required exclusions; secure source files are not fetched from URLs
embedded in uploaded data.

## Versioning and compatibility

Freeze 1.0 when Party conformance fixtures and machine schemas pass. New profiles
declare their own versions. Additive optional fields can be a minor contract
revision only when older consumers can safely ignore them. Required fields,
changed units/null interpretation/identity, new operational enum semantics or
changed financial effects require a new major/profile version and explicit adapter.
Do not silently interpret a newer financial event with older code.

Importer rejects unsupported mandatory entities/profile versions before commit,
reports archive-only records separately, and never silently imports just the rows
it recognizes from a supposedly full history. Readers may preserve unknown
namespaced extensions for archival if explicitly allowed; those never affect
operational validation. Ship old conformance fixtures and documented upgrade
adapters; internal model migrations do not automatically change the exchange version.

Round-trip guarantees are per released capability: preserve domain facts,
relationships, exact decimal/date values, correction order and supported file bytes
through the source/destination identity map. Do not promise identical internal PKs,
local recorded timestamps, generated destination business codes, security grants,
provider IDs, signed URLs, or freshly calculated monitoring projections.
