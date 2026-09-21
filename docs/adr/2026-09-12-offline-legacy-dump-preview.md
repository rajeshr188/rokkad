---
status: accepted
owner: project
updated: 2026-09-12
tags: [portability, legacy, preview]
---

# Offline source preview before legacy financial migration

The owner authorized a read-only legacy dump preview after the
[source review](../implementation/legacy-dump-source-review.md), and selected `jcl`
for the first pilot. The old schema does not supply the current complete-history
contract, and some source calculations disagree. Do not create synthetic events
merely to route these records through `loan-history/1`.

Implement the source adapter in the existing data_portability app, exposed first
as an offline management command. It reads an operator-supplied PostgreSQL custom
archive and emits source mapping/reconciliation artifacts. It does not read current
Workspace data, resolve memberships, stage database rows, reserve identities, bind
a destination or execute a business command. This source preparation therefore
does not grant or bypass destination Workspace access. Future staging/commit must
use the existing actor, Workspace, lifecycle and RLS boundaries.

Use a bounded pg_restore subprocess solely for archive listing and selected-table
text extraction, with no database argument or SQL execution. Freeze an input copy,
limit bytes/rows/time, decode supported COPY escapes, check exact observed columns,
and reject cross-schema output or ambiguous primary keys. The adapter intentionally
supports the inspected legacy shape; it is not an arbitrary SQL import service.

Reuse stable source-system/external-ID conventions and issue fields. A required
source namespace identifies the legacy installation across snapshots; each schema
and table/key remains distinct. Candidate UUIDs and record hashes are proposals,
not accepted bindings. Existing strict profiles stay unchanged. No new database
tables, migrations, queue, web upload or generic adapter registry are introduced.

Write HTML, summary JSON and per-record JSONL to a new local directory only. The
directory is ignored by Git and includes a final completion marker. Escape source
text in HTML and include no scripts or external assets. Artifacts contain private
source values and are explicitly not canonical import packages. Optional source
payment absence is a coverage warning; invalid fields and reconciliation findings
are review errors. Every record remains not import-ready even if it has no errors.

Opening-position and limited-evidence released-record contracts remain separate
next decisions. Production handover, media, setup writes and financial imports are
outside this authorized preview slice. See the [operator guide](../flows/legacy-dump-preview.md).

The owner subsequently suggested skipping loans with incomplete collateral.
An opt-in `incomplete-collateral/1` proposal now annotates whole source loan graphs,
preserves every row and reports membership/counts/stored principal. It has no age
cutoff and does not turn that tentative preference into approved financial selection.
The owner selected preserving existing billing dates/rules; see the
[opening contract draft](../contracts/loan-opening-position-mvp.md).

The subsequent `jcl-owner/1` opt-in applies the recorded owner net-weight
attestation only to the identified source namespace and tenant. It calls a pure
Loans-owned named collection calculator for offline illustrations, leaving source
facts, opening financial evidence and runtime servicing unchanged. Fractional
aggregation remains held. This extends the same preparation boundary without a
generic rule registry or formula engine; see the
[implementation](../implementation/legacy-reconciliation-worksheet.md#implemented-owner-rule-preparation-2026-09-12).
