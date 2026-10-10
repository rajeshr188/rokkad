---
status: active
owner: operations
updated: 2026-10-10
tags: [backups, storage, positions, plan]
---

# Backup storage and source-evidence efficiency

The owner selects review and recommendations, then authorizes proceeding with
BS-02 and then the BS-03/04 recovery recommendation. The [measured review](../implementation/backup-storage-review-20261010.md)
and [scoped image cleanup](../implementation/backup-image-cleanup-20261010.md)
are complete. One real encrypted backup and its compatible runtime image are
uploaded/downloaded/decrypted/restored successfully. Owner recovery-copy custody
is confirmed; ordered hourly R2 publication and conservative retention are active.
The owner subsequently authorizes BS-05: compact future financial snapshots,
with existing posted source copies preserved.

## Recommended order

| Slice | Outcome | Current state |
| --- | --- | --- |
| BS-01 | Read-only server, backup, source-duplication and protected-image inventory | Complete; 25 image candidates after protecting 89 images; private exact manifest retained |
| BS-02 | Scoped unused application-image cleanup and renewed capacity measurement | Complete; 25 removed, 89 protected, 2.553 GiB net recovered; backup and live checks pass; no force, cache, database, volume, media or checkpoint deletion |
| BS-03 | Encrypted private R2 database-backup upload with verified remote bytes | Complete/live; private bucket/root-only scoped token, real ciphertext download/hash and compatible independent release image recovery; hourly publication passes |
| BS-04 | Restore downloaded/decrypted backup in isolation and activate retention | Complete/live: 202 tables/879,350 rows, restricted startup/native/RLS and exact image recovery pass; owner confirms both key copies; ordered remote 24-hourly/30-daily and local six-plus-uncovered retention active |
| BS-05 | Compact future closed-position source snapshots | Complete/live; local regressions plus isolated 202-table/879,465-row restore and 201 unchanged business tables pass; scoped migration/readers deployed, exact image independently recovered, recovery acceptance renewed and new-image R2 backup/retention verified; posted version-1 bytes preserved |

BS-02 available space is 10.127 GiB; full retention at current backup sizes
projects 4.817 GiB, below the cutoff before growth. Headroom is improved
but not fully resolved. After the recovery test and removal of its exact generated
database/files, free space is 9.375 GiB; after the complete new hourly cycle it is
9.141 GiB. Retention acceptance preserves all 35 local points initially, including
32 without independent remote coverage. New hourly growth is bounded while these
older points stay protected. No generic cache
pruning is authorized. See the [recovery acceptance](../implementation/encrypted-backup-recovery-20261010.md)
and separate [managed PostgreSQL review](../implementation/managed-postgresql-feasibility-20261010.md).

Nominal Docker image sizes do not guarantee physical reclaimed bytes. Separately
assess unused build cache before any further cleanup; never apply generic system
or volume pruning. If safe cleanup cannot sustain the 5 GiB cutoff and reasonable
growth headroom, arrange additional capacity. Existing operational backups pass.

BS-03/BS-04 solve host-loss recovery and long local-retention growth. Application
R2 photos are not a database backup. Use the existing full compressed dump path,
without a new workspace-facing backup feature, generic storage layer or PITR
system. The backups contain all Workspaces; keep the bucket/operator credentials
outside web/media credentials and Workspace inventory/billing surfaces.

Suggested upload order: complete dump, validate catalogue/checksum, encrypt,
upload unique artifact and recovery metadata, verify remote bytes, publish remote
completion, then consider expiry. On failure, retain local recovery and alert
operators. No partial upload counts as a completed restore point. Keep media and
release checkpoints outside ordinary hourly/daily expiry.

Actual acceptance restores a downloaded/decrypted archive into an isolated
database using owner-only schema setup, then runs web/read/isolation checks under
the restricted role. Validate all eligible closed positions and 19 held sources,
existing native loans/balances, source hashes and media references. Outbound
messages and payments remain disabled in the restore environment. Package the
compatible runtime/image manifest and securely recoverable configuration; do not
store the private decryption key next to encrypted archives or on the host alone.

BS-05 is a financial-evidence storage optimization, not a new loan product or
workflow. Reuse existing admission/auth/source/numbering services. Keep small
financial agreement snapshots in ordinary origin/opening evidence and reference
the source once. Retain old readers and database guards for existing profiles;
add versioned guards and portability tests for the new representation. Required
tests include source tampering/rebinding refusal, forced RLS, immutable financial
facts, unchanged duplicate/number checks, missing-source recovery, old/new export
and fresh-Workspace restore. Any architecture change gets its own ADR before
implementation. Do not extend the exact 190-record JCL recovery exception.

Compact future admissions do not remove the current 585 MiB of repeated source
text from already-posted records. Their existing snapshots remain intact. A
separate rewrite of those records is not part of this plan.

BS-05 follows the [accepted compact-evidence decision](../adr/2026-10-10-compact-closed-position-evidence.md)
and [implementation record](../implementation/compact-closed-position-evidence-bs05.md).
Migration 0068 and compatible readers are now live through the
[scoped production release](../implementation/compact-closed-position-release-20261010.md).
Production loan/source/servicing/monitoring checks pass across all three Workspaces;
39,196 existing closed positions and 19 held sources remain unchanged. Exact-image
recovery acceptance is renewed, all six timers and the new-image backup/retention
cycle pass, and final free space is 9.155 GiB. The temporary rehearsal database and
recovered-image staging are removed. No production admission is posted by the release.

Related: [FW-023](future-work.md#fw-023-database-backup-capacity-after-closed-position-conversion),
[position-import decision](../adr/2026-10-09-loan-position-import-without-earlier-history.md),
[constitution](../constitution.md),
[production release](../implementation/loan-position-import-release-20261010.md).
