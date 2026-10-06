---
status: active
owner: project
updated: 2026-10-05
tags: [contracts, loans, portability]
---

# loan-servicing-bundle/1

LC-05 preserves the existing row inventory while validating new nested explicit
receipt/checkpoint and verified terminal-position profiles. A terminal loan carries
its sole zero checkpoint, original agreement and retained archive, with no invented
settlement or handover. See the [bounded evidence contracts](bounded-loan-evidence-lc05.md).

This named ZIP profile preserves an admitted loan's supported financial/custody
graph and source documents. It is separate from the published JSONL history and
opening profiles and from exact-identity Workspace recovery.

`manifest.json` contains exactly `profile`, `namespace`, `workspace_id`,
`root_loan_id`, `as_of`, `coverage`, `exclusions`, `tables`, `setup`, `positions`,
`files`, `documents`, and `sha256`. Coverage is
`SOURCE_FINANCIAL_AND_CUSTODY_GRAPH`. Exclusions are explicitly ordered:
Workspace configuration, Party master, funding, storage and outbound notification
jobs. Cached risk is recalculated locally. Earlier history before an opening's
cutover remains unavailable; export does not manufacture it.

The [frozen row inventory](loan-servicing-bundle-v1-rows.json) fixes names, scalar
types, nullability, source-local typed references and enums. Changing live Django
models cannot silently extend this wire. Every table is present, including empty
tables. Rows are ordered by source primary key and owned by the stated source
Workspace. Connected renewal and release-batch loans travel together. Hashes use
canonical `history_contract.dump` UTF-8; manifest hash excludes its own `sha256`.

Files are stored as `files/<sha256>`. Each manifest claim contains SHA-256, actual
byte size and unambiguous source storage names. Inventory and ZIP members match
exactly; paths, encryption, duplicates and decompression size are checked before
admission. Issued PDF claims include the frozen `ISSUE_FIELDS` source issue record,
original snapshot/hashes, issue actor/time and exact original bytes. They remain
source copies, including original numbering and Workspace identifiers. They are
not inserted as newly issued destination approvals/documents.

Bounds: 32 MiB compressed **and expanded**, 20 connected loans, 5,000 canonical
rows, 1,000 financial events per loan, 200 file entries and 200 issued copies.
Source document ancestry is bounded to eight transfers before admission and display. Larger or unsupported graphs
require exact Workspace recovery or a separately reviewed future profile.

Setup binds each source loan's exact Party identity, licence number/reference
basis and compatible product semantics. The operator selects an owned destination
borrower, licence revision, series and product for **each** connected loan. Genuine
native approvals require an evidenced original licence revision; a paper source
reference does not invent original approval validity. Retired compatible products
can supply servicing without authorizing a new lending decision. Frozen per-item
rates travel independently of old standing rate-policy FK IDs.

Admission validates source hashes, financial event envelopes, reversals, typed
ownership, operation/line arithmetic, original payouts and approvals, original
recorded agreements, recognition, schedule/exposure and collateral lineage.
Recorded book/future-capture completeness claims must match their source review
fingerprints and supported subsequent activity. A recomputed digest does not
authorize inconsistent money or an invented complete review.

Fresh local primary/public IDs and generated import numbers replace operational
source IDs. Number remapping is scoped by document kind; source IDs/numbers remain
immutable claims and searchable loan aliases. Neither live numbering counters nor
source user IDs are transplanted. Local evidence actors/times identify the import;
original actors, known timestamps, unknown values and issued documents remain in
`HistoricalLoanImport.references.portable`. Compensated earlier contracts are
validated at their original projection while inserting their immutable snapshots;
the current projection is restored before accepting the destination position.
All ordinary Python/SQL guards and forced RLS remain enabled.

Preview performs a complete admission in a rollback transaction, verifies deferred
guards, reconciles positions, and removes provisional file writes. Commit requires
the exact preview digest bound to source ZIP bytes, destination Workspace, actor
and mappings. Identical committed retry is idempotent; conflicting mappings,
changed source bundles and existing accepted financial origins are held.
This command cannot merge into or overwrite an already accepted loan.

The source future-capture choice remains a retained claim. Destination review is
paper/mixed; staff can later explicitly select Rokkad-only capture per loan. Export
does not export a Workspace's future-entry configuration or transplant queued
notices. Funding, storage, capitalization and unknown versions fail explicitly,
with no truncated apparently complete export. Published earlier exporters continue
to reject evidence they cannot retain, and older consumers reject this named ZIP.
