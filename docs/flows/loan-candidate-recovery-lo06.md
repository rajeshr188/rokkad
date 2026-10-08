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

On 8 October the owner separately approved the recommended recurring retention.
It is now installed as a post-success step of the existing backup service; the
[LO-07 execution record](../implementation/loan-production-release-lo07.md) gives
its exact source, tests and first successful run. Review backup success/freshness
and capacity; external failure alerting is not installed. Do not remove the only
compatible reader or a protected correction/recovery checkpoint.

### Ongoing policy (approved and installed on 8 October)

The 8 October follow-up recommends keeping the newest 24 completed hourly
database copies plus the newest completed copy for each of the last 30 UTC
calendar dates. Retain the union, so a copy serving both purposes is stored once.
At the current 88,598,984-byte dump size, the upper bound of 54 copies is about
4.8 GB (4.5 GiB), excluding protected release/rehearsal checkpoints and growth.
This bounds operational storage without lowering the existing 5 GiB free-space
guard. The backup is a full compressed PostgreSQL custom-format dump each hour;
it is not an incremental copy and does not copy R2 media each hour.

Run expiry only after a new copy passes checksum/catalogue validation, using the
same operational backup lock. Restrict candidates to completed dump/checksum
pairs in `backups/operational`; validate containment and retained copies before
removal. Keep `latest.json` pointing at a retained successful copy. Skip expiry
and surface a failure if validation fails. Separate deployment/rehearsal
checkpoints remain protected and require their own review. Recurring deletion is
covered by the separate 8 October approval, not the earlier 257-copy cleanup.

Check freshness against the hourly schedule and capacity before the guard is
reached. Service failures remain visible in systemd; retention reports flag space
below 8 GiB. No real notification recipient or outbound delivery is configured.
Nine tests cover retention selection, overlap, protected paths, failed validation
and repeat execution on Windows/Linux. Installation is an operator change
independent of the verified application candidate.

For host-loss recovery, separately select a private encrypted off-host destination
for daily database copies (30 days), monthly copies (12 months) and recoverable
media checkpoints. A separate private R2 backup destination is an option, not a
currently configured backup. Long-term copies must have verified recovery coverage
before local expiry is relied upon for that coverage. Avoid copying the entire
media collection every hour; retain matching manifests and required bytes through
a separately designed media backup procedure and periodic restore drills.

### Verified storage placement

At 08:18 IST on 8 October, a read-only production probe confirms the default
backend is `helpers.cloudflare.storages.MediaFileStorage`, with prefix
`media/application/production/linode-rls`. The LO-06 inventory contains 30,293
required media objects totalling 942,099,334 bytes. The two Linode media folders
are isolated checkpoint/restore copies, not the live production store. The live
database retains file references and relevant hashes; its hourly dump alone does
not contain the media bytes. Bucket versioning remains unverified (AccessDenied).

At the same check, the latest hourly database copy (07:30 IST) passes checksum
and catalogue validation, the timer is active and its service result is success.
There are 34 completed copies and about 10.5 GiB free. The operator script uses
`pg_dump -Fc` and has no expiry or off-host-copy command. Production remains on
the prior image; neither recurring expiry nor deployment is performed by these
checks.

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
