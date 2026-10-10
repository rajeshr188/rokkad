---
status: accepted
owner: loans
updated: 2026-10-10
tags: [loans, evidence, storage, portability]
---

# Compact future closed-position evidence

The owner authorizes BS-05 in the [storage plan](../plans/backup-storage-and-evidence-efficiency.md).
Current admission embeds the retained source document in both immutable financial
snapshots, in addition to HistoricalLoanEvidence. This duplicates source claims
without establishing any additional financial history.

## Decision

New admissions use loan-closed-position-admission/2 and
loan-closed-position-evidence/2. Keep the small accepted position, original known
terms, unavailable-history declaration, destination mapping and exact archive
ID/hash/snapshot identities in both ordinary financial snapshots. Their nested
position has retained_evidence=null; it is not a standalone export. The existing
protected archive FK retains the source document once. Loans without a retained
document keep an explicit null archive, as before.

Read the immutable stored origin/event first, then resolve and verify the exact
Workspace-owned source and frozen snapshot hashes. Check each source identity and
known fact against the accepted position. Missing, changed or conflicting evidence
fails closed. Hydration is an in-memory read only; it never mutates posted JSON.

Standalone exports remain loan-closed-position/1 and its existing media bundle:
include the full verified source document and exact media bytes. Fresh-Workspace
imports allocate new local identities and compact evidence. No new public import
format, table, lifecycle or operational capability is introduced.

Preserve version-1 readers, guards and stored bytes. Exact retries of existing
version-1 admissions continue to compare version-1 evidence; never rewrite them
or silently upgrade a reviewed batch. Changed approvals require a fresh review.
New database guards enforce version pairing, source binding and the same sole
zero checkpoint and immutable loan constraints. Existing forced RLS, authority,
numbering and the exact one-time 190-record JCL attestation remain unchanged.

## Consequences and verification

This prevents two full source copies in future admissions. It does not shrink
the roughly 585 MiB already duplicated in posted records. Backups still retain
all source and financial evidence; deployment requires the new owner-only guard
migration and compatible readers. Rollback must preserve those readers/guards
after a version-2 admission; do not reverse onto unsupported persisted evidence.

Test both versions, old retries and batches, source tamper/rebinding/missing
evidence, immutable original facts, restricted-role writes and cross-Workspace
hiding, unchanged numbering, standalone JSON/media export and fresh-Workspace
restore. Native/direct/paper/active financial contracts remain unchanged.
