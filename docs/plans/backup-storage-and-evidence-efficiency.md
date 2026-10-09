---
status: proposed
owner: operations
updated: 2026-10-10
tags: [backups, storage, positions, plan]
---

# Backup storage and source-evidence efficiency

The owner selects review and recommendations. The [measured review](../implementation/backup-storage-review-20261010.md)
is complete; implementation, destructive cleanup, external upload and retention
activation are not claimed or authorized merely by that review.

## Recommended order

| Slice | Outcome | Current state |
| --- | --- | --- |
| BS-01 | Read-only server, backup, source-duplication and protected-image inventory | Complete; 25 image candidates after protecting 89 images; private exact manifest retained |
| BS-02 | Scoped unused application-image cleanup and renewed capacity measurement | Proposed; recheck references and verified checkpoint, approve exact final manifest, remove only eligible IDs; no force, database, volume, media or checkpoint deletion |
| BS-03 | Encrypted private R2 database-backup upload with verified remote bytes | Proposed; choose private backup bucket, dedicated scoped credentials and externally recoverable decryption key; retain current local copies while proving upload |
| BS-04 | Restore downloaded/decrypted backup in isolation and activate retention | Proposed; preserve remote 24-hourly/30-daily set; proposed six recent local hourly copies only after owner selection and actual restore acceptance |
| BS-05 | Compact future closed-position source snapshots | Proposed; versioned stored profile, immutable source identity/FK/hash, financial facts and standalone export/restore; old posted bytes and profile semantics preserved |

BS-02 may obtain enough headroom without a paid server expansion, but nominal
Docker image sizes do not guarantee physical reclaimed bytes. Measure after
cleanup and separately assess unused build cache; never apply generic system or
volume pruning. If safe cleanup cannot sustain the 5 GiB cutoff and reasonable
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

Related: [FW-023](future-work.md#fw-023-database-backup-capacity-after-closed-position-conversion),
[position-import decision](../adr/2026-10-09-loan-position-import-without-earlier-history.md),
[constitution](../constitution.md),
[production release](../implementation/loan-position-import-release-20261010.md).
