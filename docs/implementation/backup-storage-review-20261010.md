---
status: reviewed
owner: operations
updated: 2026-10-10
tags: [backups, storage, evidence, review]
---

# Backup, server storage and source-evidence review

The owner requests review and recommendations after the verified closed-position
production rollout. All inspection is read-only. No images, databases, source
records or backups are deleted; no uploads, runtime changes or retention changes
are made. Unrelated local billing work stays outside this review.

## Findings

The production database is about 1.23 GiB on disk, and its compressed full backup
is about 157 MiB. R2 photo files are separate. Every hourly pg_dump -Fc copy
contains the whole database, not only the most recent changes. Current local
operational copies occupy about 2.80 GiB. The conservative full-retention
projection remains 8.11 GiB for up to 53 copies at the measured backup size.

Server inspection at 21:37 UTC on 9 October (03:07 IST on 10 October) finds:

| Measurement | Size/count | Interpretation |
| --- | ---: | --- |
| Root filesystem | 78.16 GiB total; 66.57 GiB used; 7.60 GiB available | Available space excludes filesystem-reserved capacity |
| Containerd image/build storage | 39.49 GiB | Largest inspected disk category |
| Docker volume/data directory | 8.01 GiB | Includes database storage; do not sum it again with database rows below |
| Deployment directory | 13.43 GiB | Includes operational backups, protected checkpoints and other release artifacts |
| All databases in inspected PostgreSQL instance | 7.27 GiB | Production plus templates and non-production databases |
| Production database | 1.23 GiB | Included in PostgreSQL total |
| Other databases | 6.05 GiB | Includes 14 non-production databases plus system/template databases |
| PostgreSQL WAL directory | 0.33 GiB | WAL is not the main disk consumer |
| System logs | 1.85 GiB | Separate from database backups |

These measurements overlap where noted. Production data and backups are not the
whole explanation for server utilization. Expansion is therefore not the only
potential way to obtain the projected 2.73 GiB of additional free capacity.

## Reviewed image candidates

Docker reports 117 images and 18.18 GB potentially reclaimable across all unused
images. That broad figure includes images worth retaining for recovery, and
must not be treated as permission to prune them all.

The first metadata review checks 106 release/rehearsal files and all container
image references. An expanded review checks 33,589 small script/configuration
files with no oversized configuration files left uninspected, plus 20 local
service/scheduler/Docker configuration files. It protects 89
images referenced by containers, retained release/rehearsal records, scripts or
configuration. Infrastructure and untagged images are excluded from this proposal.

The remaining 25 tagged Rokkad application images are candidates only. Their
nominal image-size sum is 19.05 GiB; their image-unique bytes sum is 3.14 GiB.
Shared layers and build-cache references affect actual disk recovery. Neither
number is a promise of freed space. See Docker's
[disk-usage definitions](https://docs.docker.com/reference/cli/docker/system/df/).

Private reviewed manifest SHA-256:
`7b82e8a4e003ea9e61335cec10171ef59d2afd2ef5175a693c0845b495dfdc20`.
Exact IDs/tags, protected references and aggregate reports remain in the private
server release-evidence directory. No customer data is exported for this review.

Before any removal, recheck all running/stopped containers, retained metadata,
scripts and service/configuration references,
latest verified backup, live image and image identities. A newly referenced
candidate must be removed from the proposal. Use exact reviewed IDs, without
force or volume pruning. Reassess unused build-cache references separately and
measure actual free space afterward. No database/rehearsal cleanup is included.

## Source snapshot duplication

The [prior size inspection](loan-position-import-release-20261010.md#read-only-backup-size-follow-up)
finds about 293 MiB uncompressed retained source JSON and two additional copies
of about 292 MiB each in the 39,196 new closed origin/opening records.

The current closed-position admission stores the full input, including
retained_evidence, in both HistoricalLoanImport.document and the opening event.
The reader and SQL guards expect those accepted bytes and their hashes. This
preserves a self-contained origin but duplicates the source graph unnecessarily
for future admissions. A source reference can preserve the same provenance if
identity, ownership, immutability and hash checks remain enforced.

Recommend a versioned compact stored admission/evidence profile for future
closed-position imports: retain small accepted financial facts in the ordinary
records, and reference one immutable source by FK, identity, snapshot IDs and
hash. Assemble standalone export evidence at the portability boundary. Keep
published wire profiles and existing readers compatible or explicitly version
the changed format. No generic blob framework or new financial lifecycle is
needed. Existing 190-record recovery scope and 19 held claims stay unchanged.

This does not immediately shrink the current production backup: the existing
immutable origin/event bytes remain. Do not strip retained_evidence, change
historical signatures, exclude required tables from backups or weaken existing
guards. Any separate optimization of existing storage needs its own preservation
decision and verified restoration; it is outside the recommended first steps.

## Off-server database recovery

Recommend a private database-backup bucket separate from application media, with
dedicated bucket-scoped credentials and client-side encryption. Keep the private
decryption key recoverable outside the host. Cloudflare documents
[bucket-scoped credentials](https://developers.cloudflare.com/r2/api/tokens/) and
[R2 encryption](https://developers.cloudflare.com/r2/reference/data-security/).
R2 media credentials and paths do not automatically become backup credentials.

Preserve the approved latest-24-hourly/30-UTC-daily recovery set remotely. Propose
keeping six recent verified hourly copies locally, about 0.92 GiB at today's size,
only after off-server restore acceptance and selection of that local policy.
Current retention remains unchanged during review. A failed upload or remote
verification must keep local copies and report failure; it must not expire the
last usable recovery copy.

Use the existing full dump/checksum/catalogue operator rather than adding an
incremental-backup framework at this database size. Verify uploaded bytes through
download/checksum; do not treat an object ETag as a SHA-256 guarantee. Restore a
downloaded/decrypted copy to an isolated database before activation. Verify
original/native/closed counts and hashes, restricted runtime startup, RLS,
balances, ordinary/source readers, configuration/image compatibility and media
references. Disable outbound billing/messages in the isolated environment.

The recovery package also needs the compatible runtime image/source manifest and
secure configuration/bootstrap instructions. Treat deployment checkpoints
separately from ordinary expiring hourly/daily objects. Do not enable a broad
bucket lifecycle that also deletes media or release checkpoints. R2 supports
[lifecycle rules](https://developers.cloudflare.com/r2/buckets/object-lifecycles/),
but expiry must match verified completed recovery copies and the selected policy.

The proposed R2 upload/encryption/restore path has not been implemented or tested.
No off-server disaster-recovery acceptance is claimed.

Follow the [ordered plan](../plans/backup-storage-and-evidence-efficiency.md).
Private aggregate proofs and operator helpers remain under
`/home/rokkad/deploy/cutover-20260924/loan-position-release-20261010/`.
