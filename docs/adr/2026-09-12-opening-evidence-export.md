---
status: accepted
owner: project
updated: 2026-09-12
tags: [loans, portability, evidence]
---

# Export opening evidence without claiming complete history

Follow-up: the [restore decision](2026-09-12-opening-restore-reconciliation.md)
now supplies the dedicated rebuild/reconciliation path. The evidence-only boundary
below records the original export slice; the file's coverage remains partial.

An imported opening has reviewed debt at cutover, without the original payment
history. Its supported later actions include full release, interest concession and
coupled release reversal. `loan-history/1` cannot express these facts truthfully.

Add the bounded `loan-opening-export/1` evidence download. It preserves the exact
accepted opening command, original source identity, available source-verification
records, financial events and their supporting Loans records. Record amounts and
unposted collection estimates are separate. Earlier history is explicitly
unavailable. Do not invent disbursal, receipts, gross weights or item-level accrual
allocations for the agreed aggregate interest calculation.

The existing owner download route chooses the correct profile after Workspace and
export authorization. Export locks the Workspace, loan and collateral, checks the
frozen opening bindings and supported continuation, and records a data-export audit.
No new table, migration, financial posting or bulk operation is needed.

This slice provides an evidence export, not cross-Workspace restoration. References
in frozen payloads remain source-database-local. The manifest explicitly declares
`restore_supported: false`; the complete-history importer rejects it with a clear
message. This does not satisfy the eventual opening-and-servicing round-trip
requirement. A bounded restore contract must map the financial/custody/schedule
graph, preserve original source identity and prove that retry cannot duplicate
debt. Do not implement restoration by invoking live release commands with a changed
clock or by replaying only the opening and discarding subsequent servicing.

The [file contract](../contracts/loan-opening-export-v1.md) describes this boundary.
Real pilot review, missing due terms and cutover approval remain outstanding; no
source loan is activated by exporting or by this decision.
