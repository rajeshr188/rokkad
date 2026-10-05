---
status: accepted
owner: project
updated: 2026-10-05
tags: [adr, loans, portability, provenance]
---

# Portable servicing evidence retains source identity separately

LD-07 is authorized by the owner. Existing history and opening wires retain their
meaning and frozen readers. Wider Loans graphs use a named, bounded ZIP contract,
`loan-servicing-bundle/1`, with an explicit row inventory, source-local relationships,
financial/custody positions, supporting media and exact issued PDF bytes.

Cross-Workspace admission creates fresh local identities and requires explicit
Party, original licence, series and compatible servicing-product mapping. It is a
Loans command under runtime RLS and ordinary database guards. It neither disables
guards nor uses native recovery's owner credentials. Preview rolls back financial
records and provisional media. Commit binds the exact source bytes and mappings.
Existing accepted source origins cannot be overwritten or augmented by this command.

Original rows, actors, known timestamps, review choices and files remain immutable
source evidence inside HistoricalLoanImport. Local recording actors/times describe
the import, not an invented past action. Historical approval labels use original
claims rather than a newly created snapshot's approved_at. Source-issued documents
remain source copies; they are not reissued as local approval attestations.

Source future-capture choices are retained as claims. Destination capture remains
paper/mixed until its staff explicitly review the loan and choose otherwise.
Monitoring is recalculated locally; cached source risk and queued notifications
are not transplanted. Original agreement prices remain source evidence, not new
destination Rates rows.

The financial command validates event/operation/line arithmetic and ownership,
then reconciles canonical readers, schedules and custody before acceptance. Source
checksums detect alteration but do not establish financial consistency or prove
that the underlying real-world facts are true. Connected renewal and release-batch
members travel together. Unsupported funding/storage/capitalization graphs are
held explicitly rather than truncated. Exact Workspace recovery remains a separate
same-identity operation with actual schema and guard fingerprints.
