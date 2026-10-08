---
status: active
owner: project
updated: 2026-10-08
tags: [loans, operations, recovery, release]
related: [../implementation/loan-release-preparation-lo06.md]
---

# Loan candidate recovery and retention runbook

This procedure concerns recovery preparation. It does not authorize restoring
over production, deploying a candidate, changing a loan or deleting retained copies.
Use the [dated LO-06 evidence](../implementation/loan-release-preparation-lo06.md)
for artifact identities and completed checks rather than older release notes.

## Daily operational check

Check `rokkad-production-backup.timer` and the last result of
`rokkad-production-backup.service`. An active timer does not mean backups succeed.
Inspect the private `backups/operational/latest.json`, its completed dump and
checksum. Compare its timestamp with the hourly schedule; investigate a missing
or overdue completed copy. A catalogue check confirms archive structure, not a
successful complete restore.

The existing service refuses to dump below 5 GiB free. Keep that guard and review
space before it fires. Include database/WAL growth, image builds, source and
migrated checkpoints, a disposable restored database, two media copies and normal
operations. Inspect memory/load and free inodes during rehearsals too. No global
Docker prune or removal of unrelated backups is part of this procedure.

## Retention

On 8 October the owner approved one exact cleanup of 257 operational hourly
copies, retaining the newest 24 completed hourly copies and the latest completed
copy from every older date. All separate deployment/rehearsal checkpoints were
preserved. The manifest and validation evidence remain in the approved private
server folder. This approval does not authorize arbitrary future deletions.

Until ongoing retention is approved and installed, review capacity and backup
success daily. Prepare a new bounded manifest when more space is needed. Validate
path containment, immutable names/checksums, the copies to retain and a fresh
checkpoint before a separately approved cleanup. Do not remove the only compatible
reader or the checkpoint needed for an existing correction/recovery demonstration.

An ongoing automated retention policy and backup-failure alerting remain follow-up
operational improvements. Do not claim that the one-time cleanup installs them.

## Consistent recovery checkpoint

1. Record source database, snapshot time, migration baseline and production image.
   Export a PostgreSQL repeatable-read/read-only snapshot and bind the custom dump
   to it. Keep the dump and SHA-256 in the approved server-only destination.
2. Restore into an approved private isolated target; preserve its previous
   diagnostic checkpoint before reuse. Assert that its name differs from production.
   Keep providers disabled, cache/files isolated, no public listener and no workers.
3. Compare original COPY row multisets for every table before migration. Use hashes
   of individual rows rather than sorting expanded customer JSON in PostgreSQL.
4. Provision the restricted role with explicit grant-only behavior if it already
   exists. Use owner-only migration settings for migrations; owner credentials must
   never enter a web/worker runtime. Confirm owner and pending-migration startup
   refusal, then compare the original non-metadata projections after upgrade.
5. Resolve every media reference in that fixed database, including retained document
   snapshots and admission receipts. Record exact object keys/metadata privately.
   Capture bytes conditionally against their ETags. When version identity is not
   available, say so; ETags alone are not content SHA-256 or bucket versioning proof.
   Fail if a required object disappears/changes during capture.
6. Store per-file SHA-256 and byte sizes. Check retained document/photo/archive
   hashes where available. Restore into separate isolated media storage and compare
   every file. Preserve issued bytes rather than regenerating receipts/tickets.
7. Cold-restore the migrated candidate checkpoint. Compare every table and sequence
   position, including `is_called`, and all media hashes. Open representative actual
   files with the candidate reader; distinguish technical decoding from human review.
8. Recheck restricted source/servicing/monitoring cohorts, no-context and cross-
   Workspace isolation, retained archive counts/performance and source-integrity
   fingerprints after reads. Record independent evidence limits truthfully.

## Reader compatibility and rollout

Use one pinned compatible image for web and independently launched timer readers.
The production mail timers currently use an older fixed image rather than the web
container; LO-06 prepares private candidate drop-ins/config, without installing them.
Every candidate reader must execute the runtime startup/contract guard before its
command. Keep credentials and private watchdog configuration on the server.

Production rollout remains LO-07. Its final checkpoint must account for transactions
entered since the rehearsal snapshot. An older image is not a safe rollback reader
for newly recorded contracts simply because the database schema can still load.
Use a verified compatible reader or an explicitly reviewed recovery procedure;
never restore an old checkpoint over subsequent live transactions.

## Off-host limitation

Database and captured media checkpoints in this rehearsal remain on the same host.
Successful cold recovery there does not prove recovery after that host is lost.
The live R2 media bucket alone is not a matching off-host database/media checkpoint.
Select and authorize a private encrypted off-host destination and run a separate
restore drill before claiming disaster recovery. No new off-host backup destination
or full customer-data export is authorized by this runbook.
