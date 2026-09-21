---
status: active
owner: project
updated: 2026-09-12
tags: [flows, party, import, export]
---

# Import and export Party master data

Open Parties and choose **Import** or **Portable export**. These are separate from
the pre-existing generic data-tools and CSV/XLSX report exports.

## Keep reviewed customer records with matching names separate

In a validated customer-master batch, open **Keep reviewed customers with matching
names separate**. Enter the source customer IDs already visible in the preview,
one per line, and a reason for retaining separate source records. Review every
same-name peer in that batch; reviewing only one does not resolve the other row.
**Record decision and preview** records the decision and revalidates without
creating customers. Confirm the new preview and its warnings through the ordinary
commit button when ready.

This preserves display names and source-to-Party links. It does not merge records,
verify real-world identity, clear duplicate source IDs, or bypass phone/email/tax
matches. Changed source values or a changed set of matching destination names
require review again. Decisions apply to the current batch and cannot be saved as
reusable presets. Replacing the mapping removes them. See the
[decision](../adr/2026-09-12-reviewed-party-name-collisions.md).

## Import

1. Open `/w/<workspace-slug>/data-tools/party/`. Import requires `data.import` plus
   Party read permission in an ACTIVE Workspace. Browser billing rules still apply.
2. Upload a UTF-8 CSV or canonical JSONL file. Maximum: 5 MiB, 1,000 records,
   40 columns, 4,096 characters per encoded field. XLSX/ZIP/binary input is rejected.
3. For CSV, supply a stable source-system/register name. Map an external identifier
   column to `source.external_id` and the name column to `name`. Map the remaining
   supported summary fields or leave columns unimported. The screen exposes explicit
   type/status/credit-hold defaults and normalization choices. It does not import
   address text into a made-up Party field.
4. For JSONL, supply the source Workspace UUID from the export filename. Canonical
   field names and IDs are already present; choose **Validate canonical records**.
5. Inspect counts and paginated source/normalized rows. ERROR blocks all commits.
   WARNING requires acknowledgement; INFO explains normalization/defaults. Phone
   validation uses the existing Party convention (India default, E.164 output).
6. Choose **Confirm and commit import**. Confirmation is bound to that validation
   revision and its source/mapping/row digest. Revalidation invalidates an old form.
   Commit rechecks permissions, Workspace state, source identities and local edits.

Upload, validation and preview never create Parties or consume Party codes.
All new Parties in a batch commit in one transaction. Failure rolls back Parties,
codes, identity aliases and row results; validate/retry from the previous stable
batch. COMPLETED replay returns the existing result only after authorization.
Cancelled unfinished batches discard staged values and cannot commit.

The source key is `(Workspace, source system, external ID)`. Same accepted data is
an unchanged no-op. Changed source data, changed local records, repeated IDs/identity
details within the batch, or a possible existing Party match cause conflicts.
No automatic fuzzy match, merge, overwrite or name-based identity is performed.
Resolve conflicting identity outside the import; this first slice does not provide
an existing-Party binding editor.

New Parties receive normal local codes. Legacy business codes and source-created
timestamps remain source evidence; they do not replace local recording time or PKs.
Completed batch/row provenance preserves initiator, committer/time, filename/hash,
row number, raw and normalized values, transformations, source ID and resulting
portable Party identity. PostgreSQL guards prevent editing completed evidence.
This retained PII is accessible only through authorized Workspace import review.

## Export and reimport

Open `/w/<workspace-slug>/data-tools/export/party-master/`. Export requires the
existing Party read/export grants. Its exact route remains available through the
existing lifecycle recovery policy even without paid access. ARCHIVED owners may
export; platform suspension rules remain separate. Every download reauthorizes.

Choose **Download Party master JSONL**. Keep the UUID-bearing filename. The response
also includes profile, source namespace, partial-coverage and SHA-256 headers.
The schema link describes supported fields. No file is stored for later downloading;
there is no bearer URL to expire. JSON preserves formula-looking text as data and
does not execute it. Downloads disable caching and use attachment/nosniff headers.

To move this subset to a clean Workspace, upload the JSONL there, enter its source
Workspace UUID, validate and commit. Relationships to Party children are outside
this profile; the file is **not a full Workspace or complete Party aggregate export**.
Roles, contact/address/KYC child rows, photos, other files, metadata and Loans are
explicitly excluded. Reimport regenerates destination IDs/codes and preserves
source identities/provenance. Empty exports require no reimport.

## Services and boundaries

Public services in `apps/tenant_apps/data_portability/services.py` require explicit
`workspace_id`, actor and a matching `workspace_context`. They do not infer profile
Workspace or establish a tenant from source data. Service/command callers must
open context themselves; no background queue is introduced. The web adapter uses
the existing Workspace middleware and CSRF protection.

Five models are protected by forced RLS and cross-Workspace relationship guards.
They are deliberately absent from the legacy generic model picker. Synchronous
staging stores parsed values in PostgreSQL; no application upload/artifact directory
is created. Request upload temporary files are closed by Django. Automatic provenance
retention/purge remains a future policy decision, not a completed deletion feature.

## Limits and next work

Legacy generic imports still write directly through model resources and legacy
exports remain model-based; they were left unchanged under the owner's latest
scope instruction. Do not use them as an alternative to staged Party portability.
Their allowlist/security review remains outstanding.

There is no update/merge resolver, XLSX parser, mapping-template library, background
worker, full archive, attachment transfer, loan migration or erasure. Raw malformed
files fail staging with a safe message. Unexpected infrastructure errors roll back;
they do not mark a partly written batch successful. Launch-scale throughput is
unmeasured; the bounded synchronous limits are not an SLA.

Contact methods and addresses were subsequently authorized; see the implemented
child profiles below.


## Contact methods and addresses (2026-09-12)

The same upload, mapping, preview, confirmation and export screens now select
`party-master/1`, `party-contact/1` or `party-address/1`. Each profile is a separate
bounded CSV/JSONL batch and a separate partial JSONL download. Import the Party
master first, then its children; there is no cross-file transaction or archive.
Use the namespace in each export filename when staging its canonical JSONL.

Both child profiles require `party_source_system` and `party_external_id`. For a
legacy CSV these are the exact source system and durable Party ID used in its
master import. For canonical files they are the exporting Workspace's `rokkad:`
namespace and Party public UUID. Local database IDs, names and phone numbers are
never parent selectors. Missing parents block commit; mappings cannot normalize
parent references. Child source IDs are independent for each profile.

Contact fields are `contact_type`, `label`, `value`, `is_primary`; addresses use
`address_type`, `line1`, `line2`, `area`, `city`, `state`, `postal_code`, `country`,
`is_default`. Existing Party forms normalize/validate phone, email and website
values and address requirements. Raw source strings (including postal leading
zeros), normalized values and issues remain reviewable. Explicit boolean defaults
and conversions are part of the mapping. The frozen schemas are
[contacts](../contracts/party-contact-v1.schema.json) and
[addresses](../contracts/party-address-v1.schema.json).

Child commits require `data.import`, Party read and Party edit permission in an
ACTIVE Workspace. Export uses the existing Party export/recovery boundary.
Creating children does not require Party-create permission. Source verification
must be explicit (`source_is_verified`); a true claim warns and needs acknowledgment,
remains provenance, and never grants local `is_verified`. Native verification and
source claims are distinct. No documents or evidence files are transferred.

Existing primary/default records of the same type are not demoted by imports;
conflicts require review outside the importer. Duplicate rows and duplicate
primary/default flags of the same type block the batch. Different primary phone
types are valid under native Party rules: their summary updates occur in source
row order, with before/after warnings when values differ. Canonical exports place
contacts matching the source Party summary last, preserving that summary during a
complete child round trip. Do not reorder exported records. If no primary contact matches the Party summary,
export stops explicitly until that inconsistency is resolved. Master and children
are separate snapshots: avoid editing them between the related exports/imports.

Child IDs and aliases are stable. Unchanged replay is a no-op; source edits, local
child edits, moves, deleted children and ambiguous matches conflict. Native child
deletions remain available and leave non-reusable identity tombstones. A child
moved to another Party by native merge is not automatically rebound; its export
fails explicitly pending an identity-resolution feature. Imported verification
claims remain available in exported provenance.

Identifiers were subsequently authorized and implemented below. Loans, roles, relationships, attachments, automatic merging,
full archives and erasure remain deferred.


## Identifiers without documents (2026-09-12)

`party-identifier/1` now uses the same profile selector, exact Party references,
staging, mapping, preview, explicit confirmation, atomic commit and JSONL export.
The [frozen identifier schema](../contracts/party-identifier-v1.schema.json) covers
`identifier_type`, full `value`, `masked_value`, and nullable ISO `expires_on`.
Treat these downloads as private: a masked value does not replace the full value.
Existing Party validation trims/uppercases the value and enforces one identifier
per Party/type. This slice adds no checksum, identity-verification or expiry policy.
It does not synchronize identifier values into Party PAN/GST summary fields,
matching native identifier saves. Empty expiry cells become null; other dates
must be YYYY-MM-DD. Supported types are the current Party form choices.

`source_is_verified` remains mandatory and `source_verified_at` is optional ISO
text with a timezone. A verification claim or timestamp warns and requires
acknowledgment. They survive in provenance/export but never set local
`is_verified` or `verified_at`. Existing native verification timestamps export
as source evidence. Metadata, internal hashes and binary documents are not import
fields. Identifiers with nonempty metadata cannot be exported by this profile;
the operation fails atomically rather than omitting it silently.

Duplicate types within a batch, missing parents and existing destination types
block creation. Stable child identities and source aliases provide unchanged
replay; local/source edits and deletions conflict. Native deletion retains a
tombstone. The existing permission, Workspace, RLS and no-cache rules apply.
Migration 0005 adds a typed identifier target to ChildIdentity and extends the
SQL relationship/result/tombstone guards; it adds no table. Reversing this schema
change is blocked once identifier identities exist, to preserve their evidence.

Party roles were subsequently authorized and implemented below.
Documents, relationships, Loans, full archives, metadata import and erasure remain
separate future work. No subsequent slice is started automatically.


## Party roles with explicit type mapping (2026-09-12)

Select `party-role/1` for CSV staging or canonical JSONL import/export. The
[frozen role schema](../contracts/party-role-v1.schema.json) contains the exact
Party source reference, `role_type_key`, `status`, nullable `segment`, and nullable
ISO `effective_from`/`effective_to`. This transfers Party business roles, never
Workspace membership, staff roles or authorization grants. Existing Party edit
permission is required; the pipeline does not create or seed role definitions.

Every source role key must be explicitly mapped to an existing active destination
PartyRoleType key. Matching key spelling is not automatic approval. For CSV,
first map source columns and validate; then choose a destination type for each
source role shown and validate again. Column selections are retained. JSONL shows
the role-type choices directly. Missing, inactive or other-Workspace definitions
block validation. Destination key/label and a definition snapshot are bound to the
preview, so changing a definition or mapping invalidates the old approval.

Native PartyRoleForm validation and date/status behavior remain unchanged. Only
one ACTIVE role per Party/mapped type is allowed; two source keys mapped to that
same type are checked together. Distinct inactive/ended history can be imported,
but identical history is flagged as a possible duplicate. No date-order or
historical reactivation policy is invented. Imports never end or overwrite existing
roles, and changed source, local rows, mappings or definitions require review.

Exports are bounded partial JSONL with role keys, not complete role-definition
archives. Create/configure destination definitions through existing administration
before importing. Nonempty role metadata blocks export rather than being silently
lost. Related exports are separate snapshots. Stable child identities, immutable
aliases/results, deleted-target tombstones and current authorization/RLS checks
apply. Migration 0006 adds a typed role target to ChildIdentity and extends SQL
parent/type/Workspace/result/tombstone guards, without adding a table. Reversal is
blocked once role identities exist.

The next recommendation at the role checkpoint was Party relationships with
explicit references to both Parties, implemented below. Files, role-definition transfer, metadata import, Loans, full archives
and erasure remain deferred. No next slice is started automatically.


## Party relationships with both Party references (2026-09-12)

Choose **Party relationships** (`party-relationship/1`) for directional links.
Import both Party masters before validating relationships. CSV requires a durable
relationship source ID, `party_source_system` / `party_external_id` for the **from**
Party, and `to_party_source_system` / `to_party_external_id` for the **to** Party.
Use exact master-import source aliases or the namespace/public UUID from a master
export. Names, local database IDs and fuzzy matches never resolve endpoints.
References cannot be normalized. Map `relationship_type`, `notes` (optional), and
an explicit `is_active` boolean; CSV uses reviewed literal `true` / `false`
normalization. Canonical JSONL uses these exact fields without column mapping.
The [frozen schema](../contracts/party-relationship-v1.schema.json) lists all eight
native relationship types. This link profile is separate from the Party master's
free-text relation name/label.

Preview resolves both endpoints and retains their binding in the approval digest.
Commit requires the existing import and Party edit permissions, locks both Parties
in ID order and existing outgoing relationships, then revalidates and commits the
whole batch atomically. Native PartyRelationshipForm validation and a shared Party
save helper preserve self-link rejection and uniqueness of from/to/type, including
inactive links. Reversed links and different relationship types remain distinct;
no reciprocal relationship is invented. Existing links are never silently bound
to a new source ID or overwritten. Changed source facts, edited local links, moved
endpoints and deleted links require explicit resolution outside this import.

Each child identity retains both Party identities. Migration 0007 adds a typed
relationship target and immutable related-parent reference to ChildIdentity; no
new table or Party model change is needed. SQL guards enforce both endpoints,
profile and Workspace. Native deletion leaves an unbindable tombstone with its
source aliases and completed provenance. Export also rejects an endpoint moved
after the first export, even when no import alias exists.

Export Party master before relationships and retain the namespace filenames.
Relationship JSONL includes stable relationship UUIDs, both portable Party
references, type, notes, active state and source/timestamp provenance. Restoring
the master into a clean Workspace first allows exact relationship restoration and
safe replay. Each profile remains a separate bounded partial export (1,000 rows,
5 MiB, existing cell/row limits); oversized notes fail rather than truncate. Export
and import related profiles without intervening edits. There is no cross-file
snapshot/transaction, merge-identity repair, binary KYC, staff-grant or Loans import.

The next recommendation at the relationship checkpoint was reusable, versioned
CSV mapping presets, implemented below.


## Reusable CSV mapping presets (2026-09-12)

After validating a CSV batch with no errors, inspect **Current mapping** and the
row preview. **Save this reviewed mapping as a preset** retains the exact columns,
defaults, normalization rules and any explicit role-type map. Supply a name of up
to 80 characters. A completed CSV batch can also provide its reviewed mapping.
The submitted approval must still match the batch; an unvalidated/error/cancelled
batch or JSONL batch cannot create a preset.

A name belongs to one profile and source-system family within the Workspace.
Reusing that name with changed configuration or headers appends the next version;
saving its latest exact configuration again reuses that version. Existing versions
cannot be edited or deleted. Presets retain no uploaded rows, but defaults can
contain customer-specific values: inspect them before reuse. There is a limit of
1,000 retained versions per Workspace and 256 KiB per mapping configuration.

For another CSV upload, select **Saved mapping version** and **Apply and preview**.
Only versions matching the selected profile, exact source-system name and all CSV
header names are listed. Column order may differ; changed/missing/extra header names
require explicit manual mapping and a new version. The source system remains the
operator's upload choice; no preset changes source identity or guesses matches.

Applying copies the complete mapping, links the selected version and increments
preview revision. It does not create Party records or approve a commit. Review the
new issues and normalized values, then use the existing separate confirmation to
commit. New rows, missing parent references, duplicates and current role definitions
are revalidated normally. For roles, inactive/missing destination types and new
unmapped source keys block the preview; repair the explicit mapping before saving
another version. Source verification claims retain their existing provenance-only
meaning.

**Revalidate current mapping** reruns the exact configuration, including any
per-field rules or defaults not represented by the basic form. **Map columns and
validate (replace current mapping)** replaces it with the explicitly submitted
form configuration and clears preset association. The current mapping is displayed
for every batch; selected name/version remain visible after completion. Creating
another preset version never changes mappings, previews or approvals in other
batches. Reapplying any version requires a new approval. Cancelling clears staged
row values under the existing rules and retains the immutable preset version.

Save/list/apply require existing Party read plus data.import permissions, matching
Workspace context and ACTIVE lifecycle. Party create/edit permissions are still
checked separately at commit. PostgreSQL forced RLS and immutable-version/batch
reference guards enforce storage isolation and provenance. Migration 0008 adds
MappingPresetVersion and ImportBatch.mapping_preset; no Party model or canonical
business schema changes. See the [decision](../adr/2026-09-12-csv-mapping-presets.md).
Presets are local configuration and are not included in canonical Party exports.
Preset transfer/deletion, JSONL presets, XLSX, aggregate archives and Loans remain
outside that increment. The next recommendation at the preset checkpoint was
bounded XLSX input for the implemented Party profiles, delivered below.


## XLSX input (2026-09-12)

Choose any of the six Party profiles and upload `.xlsx`, CSV or canonical JSONL.
XLSX uses the same stable source-system name, explicit column mapping, normalization,
preview and separate commit approval as CSV. Import Party masters before dependent
children. Exports remain canonical JSONL; this slice does not create Excel outputs.

Prepare exactly one visible worksheet, with unique nonempty text headers in row 1.
Use at most 40 columns and 1,001 physical rows including the header (at most 1,000
data rows). Blank rows are skipped; source row numbers still refer to worksheet
positions. The upload limit remains 5 MiB and each field retains the existing
4,096-character encoded-cell limit. Oversized data fails; it is never truncated.

Text cells preserve their exact strings, including leading zeros and literal text
beginning with `=`. Real boolean cells become `true`/`false` for the existing explicit
boolean normalization. Finite General-format numeric cells with at most 15
significant digits become exact decimal text based on stored XML, without using a
rounded floating-point value as the imported fact. Excel has already lost any
precision discarded before saving; this importer cannot recover it.

Store identifiers needing leading zeros or long numbers as **text**. Store dates
as ISO text (`YYYY-MM-DD`); timestamps use the timezone-bearing text already
required by the profile. Native Excel date cells and custom numeric formats (such
as `000000`, currency or percentage display) are rejected rather than interpreted.
Changing a display format alone cannot recover previously lost zeros or precision.

Use a plain data worksheet. Formulas are rejected even if they have cached results;
only literal values are imported. Macros, `.xls`/`.xlsm`, encrypted files, multiple
or hidden sheets, hidden/zero-height rows or columns, merged cells, hyperlinks,
filters, defined names, conditional formatting, comments/attachments and unsupported
embedded features are outside this adapter. Nondefault whole-row/column styles
are rejected to avoid silently ignoring inherited numeric formatting. Copy the
required data into a plain values-only workbook when necessary.

The package preflight allows at most 128 ZIP entries, 16 MiB expanded overall,
8 MiB per part and a 100:1 expansion ratio per part. XML depth is limited to 64 and
element count to 200,000 per part; DTD/entities/external references are forbidden.
Unsafe paths, duplicate/case-colliding or symbolic-link entries fail. Nothing is
extracted. Actual row/cell coordinates are checked independently of dimension hints,
so a false small dimension cannot conceal extra records. Malformed input creates
no staged batch or Party record.

Saved mappings now work across CSV and XLSX when Workspace, profile, exact source
system and header names match. Header order may differ. Save/apply/revalidate and
version rules remain unchanged, with a fresh preview and approval before commit.
The same normalized source identity/facts replay safely across CSV and XLSX;
changed facts still conflict. JSONL retains its own canonical field names and does
not use presets. Migration 0009 extends the existing SQL batch-preset guard to XLSX;
there are no new tables, dependencies, Party models or business schema versions.
See the [decision](../adr/2026-09-12-bounded-xlsx-input.md).

Preset deletion/transfer, multi-sheet selection, workbook export, full archives,
binary KYC and Loans transfer remain deferred. The subsequent bundle export is
implemented below.

## Download the six-profile Party bundle

Open Export Party data and choose **Download Party ZIP bundle**. The existing
export/read permissions, CSRF checks and recovery access apply. The ZIP contains
all six JSONL files, their schemas, a README and `manifest.json`. The manifest gives
the source namespace, snapshot time, import order, exclusions, counts, sizes and
SHA-256 checksums. Zero-record profiles have empty files and explicit EMPTY coverage.
The whole package is PARTIAL, not a full Workspace backup. Treat all files as
private customer data.

Each profile supports 1,000 records and 5 MiB, at most 30 MiB of entity data in total;
the snapshot also supports at most 1,000 role types. Busy data produces a retry
message. Any unsupported/lossy profile or overflow stops the entire export without
truncation. The short snapshot transaction locks existing Party data and can delay
new Workspace-owned records until the download is prepared. Other Workspaces remain
independent. See the [snapshot decision](../adr/2026-09-12-party-export-bundle.md).

ZIP upload is supported as described below. Alternatively, extract the archive,
retain the manifest, and upload each nonempty JSONL file in manifest order, master first. Use source_namespace
as the JSONL source system. Select the intended destination Workspace yourself;
the manifest never grants access or selects it. Review and commit each profile;
map Party role types explicitly in that Workspace. Existing source-identity replay
and conflict checks remain in force. The six commits are separate transactions.

## Stage a Party ZIP bundle for review

In the destination Workspace, open Import Party data and use **Stage ZIP for review**.
Upload an exported Party ZIP of at most 31 MiB. Normal import permissions, ACTIVE
lifecycle and commercial access are required. The source namespace in the ZIP never
selects or grants access to the destination. Treat the bundle as private customer data.

The application checks all 14 members, manifest, checksums, exact schemas, record
counts and master/child references before staging anything. Nonempty profiles are
staged together or all rolled back; invalid package/capacity errors leave no partial
set of batches. Existing domain errors appear in the individual previews. At most
20 unfinished batches may exist, so a six-nonempty-profile bundle needs six slots.
Empty profiles are shown explicitly and create no batch. No Party data is committed.

The results page lists all profiles in order. Review and commit Party master first.
Open the child previews and choose **Validate canonical records** again after master
commit. Map Party roles to active role types in this destination before validation.
Review warnings and explicitly commit each READY profile. Cancellation, approval
expiry/staleness, identity replay and conflict checks use the existing batch rules.
For a wholly unfinished bundle, use the combined workflow below instead. Neither
workflow rolls back profiles that were previously committed separately.

Refreshing the results page is safe. Its signed Workspace-specific receipt expires
after one day; the batches remain available under Recent imports. Uploading the ZIP
again creates new previews, while later commit-time identity checks prevent duplicate
Party records. Uploaded README/schema instructions are never executed or rendered.
See the [staging decision](../adr/2026-09-12-party-bundle-staging.md).

## Review and commit the whole bundle

On the staging results page, choose **Review and commit whole bundle**. All nonempty
profiles must still be unfinished. Select the destination Party role types and click
**Generate combined preview**. The application evaluates master before children in
a transaction that is rolled back, so no Party data or approval changes from this
preview are retained. The page shows normalized values, new/existing dispositions,
role mappings and issues. Review each expandable row. Profiles after a failed
dependency are not evaluated and no commit approval is offered until errors clear.

A ready preview offers **Confirm and commit whole bundle** with an explicit review
acknowledgement. The approval belongs to this operator/Workspace and expires in one
hour. Confirmation repeats validation and checks that the staged inputs and evaluated
results still match. It saves all profiles together or rolls back everything; changed
role definitions, conflicts or stale input require a fresh preview. Repeating the
same approved confirmation returns the same completed results without duplicates,
provided current permissions still allow the operation.

Do not commit/cancel/revalidate individual profiles between combined preview and
confirmation. If part of the bundle was already committed separately, continue with
individual profiles; combined commit cannot reverse those earlier results. Preview
uses short-lived database writes/locks that are rolled back and may consume internal
surrogate ID sequence values; no simulated local Party code is promised. This remains
a synchronous bounded Party operation, excluding Loans and external effects.

Receipt-only links expire after one day. Saved bundles can now be reopened through
Bundle history below; existing approvals still expire after one hour. See the
[atomic commit decision](../adr/2026-09-12-atomic-party-bundle-commit.md).

## Reopen a saved bundle

Open Import Party data and find **Bundle history**. The list shows the stage date,
source Workspace namespace and current progress, with 20 attempts per page. Open an
entry to return to its saved review page, even after the original receipt expires.
No ZIP re-upload is needed. Empty bundles are listed explicitly; repeated uploads
remain separate attempts. The page is private to the destination Workspace and
requires current import access, ACTIVE lifecycle and commercial access.

Choose destination role types and generate a fresh combined preview. Reopening does
not renew an old approval: every combined approval still expires after one hour and
belongs to its original operator/Workspace. A saved page cannot accept an approval
for another bundle. Completed/cancelled profiles remain visible. Partly finished
bundles must continue through individual profiles; no completed result is reversed.

Migration 0010 recovers older groups only when their retained staging audit evidence
matches all referenced batches. If evidence is missing or inconsistent, individual
batches stay in Recent imports without an invented group. Bundle history cannot be
edited or deleted in this slice. See the
[history decision](../adr/2026-09-12-persistent-party-bundle-history.md).

## Cancel unfinished bundle profiles (2026-09-12)

Bundle history is empty until a ZIP bundle is staged or an older verified bundle
is recovered. Individual CSV, XLSX and JSONL imports appear in Recent imports;
they do not create bundle history.

Open a saved bundle with unfinished profiles. In **Cancel unfinished profiles**,
read the retained-data notice, tick the confirmation and choose **Cancel all
unfinished profiles**. The action applies to profiles still unfinished when it
runs. It cancels them together and frees their unfinished import slots. If another
operator has completed a profile meanwhile, that completed import is preserved.
A failure rolls back the whole cancellation. Repeating a successful cancellation
makes no additional changes and still requires current import access.

Cancelled profiles lose staged raw values, canonical values, issues and approval
digests. Bundle history, completed imports, mappings (including potentially private
defaults), headers, source identifiers, checksums and audit metadata remain. This
is not complete customer-data erasure. Existing combined approvals cannot commit
a cancelled group; cancelled profiles cannot be resumed. Upload again if needed.
The cancellation button disappears when no unfinished profiles remain.

Party portability MVP feature scope is closed. History filtering is optional and
deferred; no further portability feature slice is queued. See the scope boundary
in [the delivery plan](../plans/data-portability.md#mvp-scope-closeout-2026-09-12).

## Keep reviewed matching addresses separate

In an unfinished, validated address batch, open **Keep reviewed matching addresses
separate**. Enter the exact source address IDs shown in the review and a reason
confirming they represent distinct records. **Record decision and preview** creates
a new preview without writing addresses. Review its warnings and use the ordinary
import confirmation. Address text stays unchanged; duplicate source IDs, default
conflicts and unrelated errors still block. A changed source row, parent or matching
destination address set requires review again. Decisions apply only to this batch
and cannot be saved as reusable presets.
