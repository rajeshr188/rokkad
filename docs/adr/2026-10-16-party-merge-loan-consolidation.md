---
status: accepted
owner: project
updated: 2026-10-16
tags: [party, loans, identity, corrections]
---

# Consolidate loan borrower links when duplicate Parties merge

The owner confirms that a Party merge means two records represent the same person.
Every ordinary loan and Khata account must belong to the retained Party after a
merge, including drafts and closed agreements. Each agreement keeps its number,
terms, financial source events, custody and issued document bytes. This is identity
consolidation, not debt assignment, loan combination or a financial action.

Reuse the existing explicit Workspace and Party edit authorization. Lock both
Parties in primary-key order, transfer all current borrower links and archive the
duplicate in one transaction. Reject archived inputs for a new merge. Preserve
the source/target metadata, retained duplicate record and historical source aliases.
Names never determine the target.

Ordinary loans append the existing immutable BORROWER_CORRECTED evidence with an
explicit `party_merge: true` marker, original/retained Party snapshots and actor.
The database permits non-active correction logs only for a recorded same-Workspace
merge with equal before/after loan state. Closed-position loans permit a borrower-
only update backed by this log; all other closed-position fields stay frozen.
Existing correction-chain readers validate historical approval/opening identities.
A later approval can start after a prefix of same-person merges. Original financial
facts and historical documents are not rewritten.

Khata preserves every account field except its current borrower. Its existing
database guard allows this narrowly when the recorded duplicate mapping and a
per-account actor AuditLog agree. Merge AuditLogs cannot be updated or deleted.
No new table, financial event, schema ownership or RLS registry entry is needed.

Loans 0084 serializes new or changed borrower references with the merge's Party
locks. Its INSERT/borrower-change triggers take `FOR KEY SHARE` before checking
for retained merge metadata, preventing deferred foreign-key checks from admitting
a stale duplicate concurrently. Admission that commits first is included in the
merge; admission waiting behind a completed merge fails with a retained-customer
message. This applies to ordinary loans and Khata, including direct SQL. Existing
financial updates with an unchanged borrower and archive-only historical admission
retain their rules. Both race orderings require real PostgreSQL tests.

Historical incomplete merges have an explicit, permission-checked repair command.
It defaults to a rolled-back preview, follows only exact reciprocal retained merge
metadata, is idempotent, and refuses missing, foreign, cyclic or chained targets
needing review. Production repair details remain on the private server; public
results contain counts. It never infers identity from contact details or names.

Bounded cross-Workspace servicing exports explicitly refuse Party-merged loan
histories until a separately versioned merge-remapping contract exists. Exact
database/Workspace recovery preserves all original identities and merge evidence.
This follows the existing hold on automatically rewriting moved Party child
identities; never silently discard merge evidence during portable export.

Loans 0082 branches from deployed 0077; 0084 depends only on 0082. Separate local
0083/0085 no-ops join the pending agreement-correction branch and are excluded
from the scoped production candidates, along with unrelated correction work.
