---
status: accepted
owner: project
updated: 2026-10-10
tags: [adr, portability, snapshot, pc-04]
---

# Bounded exchange reuses released domain files and receipts

The owner selects PC-04 in the [completion plan](../plans/data-portability-completion-20261010.md).
A private operator directory uses `rokkad-exchange/1`: a checksummed manifest and
ordinary published Party JSONL, connected servicing ZIP and closed-position
JSON/ZIP files. This is partial business exchange, not a database backup or the
fresh-Workspace package planned in PC-05. Configuration, Party binary files,
access grants and unsupported financial graphs are not claimed as covered.

The standalone command begins REPEATABLE READ before Workspace context or any
source SQL in that transaction. Existing serializers can bypass their export
row locks only after verifying that isolation level. Domain authorization and
all lossless-export/financial/media validation remain unchanged. Source queries,
including configuration and identity/provenance reads, share one MVCC snapshot;
new identities and audit receipts created by this transaction are visible to
its own later reads. The command does not lock the whole lending portfolio.
Concurrent source identity conflicts or database failures abort publication,
rather than mix snapshots. Existing browser exporters keep their row-lock path.
No import or financial writer bypasses a lock.

Files are written inside a private temporary directory and published only after
the database transaction commits. A failed export is cleaned up by the command.
A process failure can leave an unpublished temporary directory, which an operator
may remove after checking that the process has ended. A retained media file must
still match its frozen size/hash; an unavailable file aborts the export.
Checksums establish integrity, not authenticity or source-book acceptance.

Party master chunks precede all child profiles. A parent's children remain in
one file, preserving the existing primary-contact summary ordering. Relationships
resolve against the already imported full master cohort. Per-file limits remain
1,000 rows and 5 MiB. A connected renewal/release component travels once, intact,
under the existing twenty-loan, 5,000-row and 32 MiB expanded servicing bounds.
Closed-position files retain known facts and unknown earlier history. Financial
chunks never synthesize cash, release actions or links to fit a file.

Destination progress derives from existing protected ImportBatch and
LoanRestoreBatch receipts, scoped to Workspace, profile, source namespace/hash.
Staging requires the exact manifest digest and completion of prior Party chunks.
Disjoint financial chunks can be admitted independently once Party dependencies
finish; every stage does not reload the entire financial receipt history.
One chunk is staged per request; interruption reuses its existing pending/completed
batch. Cancellation permits fresh staging. Ordinary browser review still applies
explicit mappings and signed/current confirmation. Completed receipts describe
accepted admission, not a claim that the loan has had no subsequent servicing.
There is no new job framework, table, arbitrary JSON write or financial importer.

Re-exported closed positions can retain a legacy borrower reference while the
newly imported Party has a new canonical identity. The shared exact-parent
resolver recognizes `source_refs` only from immutable, completed native Party
master import rows when no authoritative SourceIdentity exists. Exactly one
accepted destination identity must match; ambiguity is held. Pending/CSV/foreign
rows cannot establish it. Explicit source bindings remain authoritative. This
creates no alias rows, does not change source evidence and never matches names.
Migration 0022 adds a partial JSONB GIN index on committed ImportRow canonical
evidence for this lookup at portfolio size.

Explicit envelope bounds are 200,000 rows per Party profile, 50,000 admitted
loans, 60,000 chunks, one million scanned source rows, 32 MiB manifest and 20 GiB
aggregate chunk bytes. They exceed audited population sizes without removing
the smaller domain file bounds. A file/group that cannot fit those existing
bounds is held; the exchange does not truncate it. Large exports still use
database/CPU/I/O resources and retain a long MVCC snapshot. Operators schedule
them, protect the output parent directory, and provide adequate disk headroom.
PC-05/06 remain responsible for package usability and wider graph coverage.
