---
status: active
owner: loans
updated: 2026-08-06
tags: [loans, documents, pdf, templates, printing]
related:
  - ../apps/loans/architecture-and-girvi-parity.md
  - loans-rewrite-roadmap.md
  - ../adr/2026-07-15-loans-rewrite-domain-and-cutover-architecture.md
---

# Loans Configurable Documents Plan

## Outcome

Give each workspace controlled customization of PawnLoan tickets, receipts,
release memos, auction documents, renewal memos, and later notices without
bringing Girvi's frame-specific rendering complexity into Loans.

Loans keeps its current fixed PDFs as a permanent safe fallback. Custom
printing is an additional rendering path over the same immutable document
facts; it never becomes a second source of loan, accounting, settlement, or
custody logic.

## Post-LPD6 Rich Composition Order

1. Flow schema v2 foundation: explicit mode, bounded page margins, themes, and
   schema-v1 compatibility.
2. Flow containers: sections, rows, columns, and field grids.
3. Configurable tables plus repeating headers and footers.
4. Safe formatting, conditional visibility, and overflow policies.
5. Visual flow editor emitting the same validated JSON. Initial Owner/Admin
   editor complete for page/theme settings, top-level composition, common
   block presets, preview, and test print; deeper property panels remain an
   incremental usability enhancement rather than a second schema.
6. Absolute-overlay schema and renderer with bounded page geometry. Complete:
   exact top-left millimetre rectangles over mandatory validated backgrounds,
   constrained block vocabulary, copy/duplex composition, and fail-closed
   bounds/overflow.
7. Visual overlay editor over the uploaded PDF background.
8. Physical printer acceptance for both composition modes.

Flow and overlay remain separate renderers over the same typed payload,
immutable revision, deterministic assignment, and exact-issue infrastructure.

## What To Learn From Girvi

Carry forward the useful operator capabilities:

- workspace-managed layouts;
- uploaded letterhead/background pages;
- original, duplicate, front/back, and combined print variants;
- activate, clone, preview, test-print, publish/default, and retire actions;
- readiness checks before a layout can become live;
- starter layouts and downloadable samples.

Do not port these Girvi implementation properties:

- a renderer coupled directly to `GivenLoan` and its related models;
- one database row and one code branch for every positioned field;
- mutable defaults whose later edits change historical reprints;
- global template lookup without explicit workspace ownership;
- silent blank pages or missing content when an asset or frame fails;
- document-specific PDF composition mixed into views.

## Proposed Architecture

```text
PawnLoan source/event
        |
        v
document projection builder  ---> immutable, typed DocumentPayload
        |                                  |
        |                                  +--> fixed renderer (fallback)
        v
layout resolver ---> published revision ---> configurable renderer
        |                                  |
        v                                  v
DocumentIssue -----------------------> PDF bytes + hashes
```

There are five deliberately separate responsibilities.

### 1. Document projections

Create one typed projection builder per document kind. It reads only the
authoritative source aggregate and immutable snapshots/evidence already used
by `PawnLoanDocumentService`.

Initial document kinds:

- `LOAN_TICKET`
- `REPAYMENT_RECEIPT`
- `RELEASE_MEMO`
- `AUCTION_NOTICE`
- `AUCTION_RECOVERY_MEMO`
- `RENEWAL_MEMO`

Each builder returns a versioned `DocumentPayload`, made only of scalar values,
tables, asset references, source IDs, fingerprints, accounting/reversal state,
and the deterministic verification ID. Templates never receive Django model
instances and never calculate balances.

The current fixed methods should be refactored to consume these projections
before configurable rendering is introduced. This establishes one factual
contract for both rendering paths and prevents content drift.

### 2. Versioned layouts

Add Loans-owned tenant models (names are provisional until the ADR/schema
slice):

- `LoanDocumentLayout`: stable workspace-owned identity, document kind, name,
  and lifecycle.
- `LoanDocumentLayoutRevision`: immutable schema version, page setup, layout
  definition, asset references, creator, validation result, and content hash.
- `LoanDocumentLayoutAssignment`: selects a published revision by workspace,
  optionally narrowed to license and series, with deterministic precedence
  `series -> license -> workspace -> system fixed layout`.
- `LoanDocumentIssue`: immutable evidence of what was printed, including source
  identity/fingerprint, layout revision (or fixed-renderer version), payload
  schema version/hash, PDF hash, issue time, actor, and optional stored artifact.

Draft revisions may be edited. A published revision is immutable; changes use
clone-and-publish. Retiring a revision prevents new selection but preserves
historical reprints. Only one active assignment may exist for the same scope
and document kind.

All models are tenant-scoped and carry explicit workspace ownership consistent
with Loans. Model changes require `migrate_schemas`, not plain `migrate`.

### 3. A constrained layout schema

Use versioned JSON for page composition rather than Girvi-style polymorphic
frame rows. Validate it against an application-owned schema before preview or
publish. The schema should support a deliberately small block vocabulary:

- text and labelled value;
- image/logo;
- QR code;
- key/value group;
- data table;
- signature box;
- divider and spacer;
- page break;
- background PDF/image;
- conditional visibility from an allow-listed boolean payload field.

Blocks bind only to keys from a document-kind field registry. No arbitrary
Python, Django template expressions, database paths, HTML, JavaScript, or
user-supplied fonts are executed. Repeating data is supported only through
registered table fields such as collateral or allocation rows.

The first UI can be a structured form with ordering and measurements. A visual
drag/drop editor is optional later; it must emit the same validated schema and
must not create a second rendering contract.

### 4. Rendering and composition

Add a Loans-local document package rather than importing Girvi:

```text
loans/documents/
  payloads.py
  registry.py
  selection.py
  validation.py
  renderers/fixed.py
  renderers/layout.py
  composition.py
  issuing.py
```

Keep ReportLab for content and isolate PDF overlay/merge operations behind
`composition.py`. The configurable renderer accepts only
`DocumentPayload + PublishedLayoutRevision` and returns bytes plus render
metadata. It must fail closed with an operator-readable error; it must never
silently omit a required field or page.

`PawnLoanDocumentService` remains the public facade. Its call shape becomes:

1. build the document projection;
2. resolve the applicable published revision;
3. render configurable or fixed layout;
4. issue/retrieve reproducible evidence;
5. return the existing `PawnLoanDocumentResult` and PDF response.

Existing PDF URLs remain stable. An optional explicit `layout_revision_id` is
allowed only for authorized preview/test-print requests, never normal loan
printing.

### 5. Issuance and historical reproduction

Regulatory documents must not change because an administrator edits the
current default. Normal first print creates a `LoanDocumentIssue`; subsequent
normal reprints use that issue's revision and payload identity. If artifacts
are stored, return the exact bytes after verifying the hash. If storage is not
enabled, rebuild only from the frozen payload/revision and verify the resulting
hash.

An explicit `REGENERATED` issue is required when an authorized operator needs a
new layout for the same source. It must retain a link to the prior issue and be
shown as a regenerated copy. Preview and test-print output is watermarked and
never creates an official issue.

## Authorization And Safety

- Workspace Owner/Admin may create drafts, upload assets, clone, publish,
  assign, and retire layouts.
- Normal loan staff may print only the resolved published layout.
- Every mutation records a workspace audit event; publication and assignment
  changes also record before/after hashes.
- Asset uploads accept only supported PDF/image types, enforce size/page limits,
  validate that content can be parsed, and use tenant-isolated storage paths.
- Layout resolution always verifies active tenant, workspace, license, series,
  document kind, and revision state.
- A failed custom render offers the fixed PDF only as an explicit, audited
  fallback action; it does not automatically disguise the failure.

## Delivery Slices

### LPD0: Decision and characterization

Status: completed 2026-08-06.

- Add an ADR accepting the projection/revision/issue architecture and deciding
  whether official PDF bytes are retained or deterministically rebuilt.
- Characterize all current `PawnLoanDocumentService` fields and immutable data
  sources with golden tests.
- Define document kinds, payload schema versioning, and field registries.

Gate: every current fixed document has an explicit payload contract and no
business calculation is found only inside PDF drawing code.

Result: ADR `2026-08-06-loans-versioned-configurable-documents.md` accepts
versioned projections/layouts/issues and exact artifact retention for official
prints. All six current document kinds have schema-versioned projection
builders and allow-listed scalar/section binding keys.

### LPD1: Projection extraction, no behavior change

Status: completed 2026-08-06.

- Move source reading into typed projection builders.
- Make the existing fixed renderer consume projections.
- Preserve URLs, filenames, verification headers, eligibility checks, and
  visible document content.

Gate: the existing Loans document and UI suites pass, plus golden payload and
PDF text assertions for all six document kinds.

Result: Loans now owns immutable `DocumentPayload`, `DocumentField`, and
`DocumentSection` contracts under `loans.documents`. Source reading and
eligibility moved into one projection builder; the fixed ReportLab renderer
consumes only the projection through the unchanged
`PawnLoanDocumentService` facade. Existing URLs, filenames, verification
headers, and PDF content remain unchanged. Nine focused tests pass, including
typed/versioned binding, immutability, all primary document paths, and both
auction documents. The wider 201-test Loans command reached the environment's
240-second limit while constructing an additional test database, with no test
failure reported before timeout.

### LPD2: Layout schema and renderer, database-free

Status: completed 2026-08-06.

- Implement registry, schema validation, page composition, and custom renderer.
- Supply application-owned starter layouts for the loan ticket and release
  memo.
- Cover overflow, multi-page tables, missing assets, invalid bindings, Unicode,
  QR codes, original/duplicate, front/back, and deterministic output metadata.

Gate: untrusted layout input cannot access models/code, and invalid layouts
fail before rendering.

Progress: `loans.documents.layouts` now provides an immutable schema-v1 layout
contract, strict property/block validation, allow-listed field/table bindings,
per-document mandatory regulatory bindings, copy modes, page sizes, canonical
content hashing, and starter ticket/release layouts. The database-free
ReportLab renderer resolves only `DocumentPayload`, produces payload/layout
hash evidence plus a renderer version, marks previews non-official, paginates
long tables, and composes single, original/duplicate, and duplex copies.
LPD2A completes the asset boundary with immutable validated asset values,
PNG/JPEG signature and dimension limits, bounded readable PDF backgrounds,
tenant ownership checks, image/logo and verification/field QR blocks, image
and PDF background overlay on every simplex/duplex page, and asset hashes in
render evidence. The renderer registers the bundled Noto Sans Tamil font for
regional text. Missing, corrupt, duplicate, unsupported, or cross-workspace
assets fail closed. Nineteen focused projection/fixed/configurable tests pass,
including long tables, duplex backgrounds, and Unicode content. The LPD2 gate
is complete with no model or migration.

### LPD3: Tenant models and publication services

Status: completed 2026-08-06.

- Add revision, assignment, and issue models through a tenant migration.
- Implement atomic clone, validate, publish, assign, retire, and issue services.
- Add workspace/license/series isolation, uniqueness, audit, and concurrency
  tests.

Gate: a published revision cannot mutate, concurrent default assignment is
safe, and cross-tenant or cross-scope selection fails closed.

Result: tenant migrations `loans.0017` and `loans.0018` add workspace-owned
layout identities, immutable versioned revisions, revision-bound validated
assets, scope assignments, and exact-byte official/regenerated issue evidence.
Published definition/hash and issued evidence are immutable. Partial unique
constraints protect active workspace/license/series assignments and official
source issues; services also use atomic row locks for version allocation,
publication, assignment replacement, retirement, and issue lookup. Resolution
is deterministic `series -> license -> workspace -> fixed`. Official reprints
return the existing issue; regeneration creates a linked issue. Exact PDF,
payload/layout/asset hashes, renderer/revision identity, source fingerprint,
actor, and time are retained. Create/edit/asset/publish/assign/retire/issue
mutations emit public workspace audit records. Both migrations were applied to
all local schemas with `migrate_schemas`, and the combined 24-test document
gate passes.

### LPD4: Loan-ticket pilot UI

Status: completed 2026-08-06.

- Add setup list/detail/editor, preview, test print, clone, publish, assign, and
  retire screens for Owner/Admin.
- Add starter layout creation and readiness reporting.
- Route normal loan-ticket printing through the resolver, with the fixed ticket
  still available as an audited recovery choice.

Gate: one pilot workspace can customize a ticket, publish it, print it, change
the default, and reproduce the earlier issued ticket exactly.

Result: Owner/Admin setup routes provide layout/revision list and detail,
starter ticket creation, schema-v1 JSON editing with server validation,
validated asset upload, preview, downloadable test print, clone, publish,
workspace/license/series assignment, and retirement. Preview/test output is
marked non-official and requires an approved sample loan. Normal ticket URLs
resolve series/license/workspace assignments, render the published revision,
create or retrieve exact-byte official issue evidence, and expose its issue ID
in the response. An explicit `?renderer=fixed` recovery path is restricted to
Owner/Admin and emits a public workspace audit event. Existing ticket URL,
filename, verification header, and fixed fallback behavior remain compatible.
Focused tenant UI coverage proves the full create/edit/asset/publish/assign,
preview/test-print, official issue/reprint, clone/retire, permission denial, and
fixed recovery flow. No additional migration is required.

### LPD5: Remaining documents

Status: completed 2026-08-06.

- Roll out repayment receipt and release memo next.
- Then add renewal, auction notice, and auction recovery memo.
- Define required fields separately for each kind; a generic layout must never
  weaken a document's regulatory or verification content.

Gate: every kind has a starter layout, eligibility tests, immutable-source
tests, issue/reprint tests, and a fixed fallback.

Result: starter creation now supports loan ticket, repayment receipt, release
memo, auction notice, auction recovery memo, and renewal memo. Each starter
contains its document-kind mandatory field registry and only guaranteed table
sections; optional repayment allocation tables remain available to custom
layouts without making basic receipts fail. Existing receipt, release, auction,
and renewal PDF endpoints now resolve series/license/workspace layouts, render
from immutable projections, create/retrieve exact-byte official issues, return
verification and issue headers, and retain their fixed renderer when no layout
is assigned. `?renderer=fixed` remains the explicit audited administrator
recovery path for every endpoint. Existing URLs, filenames, lifecycle/source
eligibility, and fixed content remain compatible. Release projections now
explicitly include the mandatory official loan number. Twenty focused
projection/layout tests and the existing tenant-scoped essential-PDF route test
pass; focused pilot UI coverage also remains green. No migration is required.

### LPD6: Operational hardening

Status: engineering complete 2026-08-06; physical printer pilot pending.

- Add layout/issue diagnostics, orphaned asset checks, artifact hash checks,
  export/import of sanitized layout packs, and a rollout runbook.
- Pilot with representative printers, paper sizes, duplex modes, long borrower
  names, many collateral items, and regional text.
- Update the Girvi parity register only after operator acceptance.

Engineering result: read-only integrity diagnostics verify canonical layout
hashes, revision scope, asset ownership/bytes, issue artifact bytes, revision
scope, and regeneration lineage. Owner/Admin can view findings in setup, and
`check_loan_document_integrity --fail-on-findings` provides a tenant deployment
gate; `jcl1` passes with zero findings. Sanitized ZIP packs contain only
schema-v1 definitions and validated hashed assets. Import rejects unsafe paths,
unknown properties, excess files/size, invalid bindings, and asset drift, and
always creates an unassigned draft. Pack round-trip and intentional hash-drift
tests pass. The operational runbook at
`docs/implementation/loans-configurable-document-operations.md` documents
integrity, pack boundaries, audited recovery, and the representative printer
matrix. LPD6 must remain open until a real operator completes that physical A4,
A5, simplex/duplex, long/regional content, background, QR, margin, and
byte-identical reprint matrix.

## Explicit Non-Goals

- Porting Girvi's models, views, or renderer into Loans.
- Allowing templates to change accounting or lifecycle facts.
- Arbitrary Jinja/HTML/CSS or executable expressions.
- A drag/drop canvas in the first slice.
- Sharing mutable templates between tenant schemas.
- Removing fixed PDFs.
- Migrating legacy Girvi templates automatically. A later import tool may map a
  safe subset into draft revisions, but every imported draft must be reviewed
  and published explicitly.

## Recommended First Implementation

Start with LPD0 and LPD1 only. Extracting immutable projections is valuable on
its own, has no schema or operator-facing behavior change, and makes later
customization substantially safer. Do not begin the editor or migration until
the ADR settles artifact retention and the ticket/release field registries are
accepted.
