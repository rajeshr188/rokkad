---
status: complete
owner: project
updated: 2026-09-30
tags: [fw-015, storage, recovery, rehearsal]
---

# Retirement of the two historical rehearsals

After the [recovery exercise](rehearsal-recovery-20260930.md), the owner instructed
the agent to proceed with retirement. Recovery archives are retained with no
automatic expiry; their eventual removal requires a separate decision.

## Exact scope

| Environment | Database | R2 source prefix | Objects | Bytes |
| --- | --- | --- | ---: | ---: |
| Local baseline | `rokkad_baseline_rehearsal_linode_20260921` | `media/application/rokkad_baseline_rehearsal_linode_20260921/` | 29,381 | 831,444,125 |
| Former hosted | `rokkad_cutover_rehearsal` | `media/application/production/hosted-rehearsal-20260923/` | 29,518 | 834,049,140 |

These are whole obsolete environments, not production orphan files. Most of their
media was referenced by their own databases. The six previously identified unused
rehearsal assets are included in these complete manifests.

## Pre-deletion checks

Stopped the two parent/child Python processes serving only the baseline rehearsal
on local port 8081. The separate billing rehearsal on port 8083 remains running.
The former hosted web and reviewed importer were already stopped; disabled their
restart policies before proceeding. Both database connection gates were closed
through separate maintenance connections, with no other source sessions present.
Existing read-only connections compared every public table against the archives:
160 baseline tables / 295,602 rows and 161 hosted tables / 275,390 rows match.

The first freeze attempt was rejected because PostgreSQL does not let a connection
disallow connections to its own database. The corrected separate-connection check
also disabled parallel read workers, which cannot connect to a frozen database.
No destructive step depended on a failed check.

All five independent R2 archives passed another full streamed SHA256 readback.
Both exact source listings matched their archived keys, sizes, ETags and modified
timestamps. Production's restricted runtime checked the full registered reference
set across workspaces, including historical references: 29,770 objects /
880,056,600 bytes, all 29,770 distinct references present, none resolving to either
retiring prefix. No production business writes were made by these checks.

## Execution and evidence

Completed on 30 September at approximately **01:25 IST**. Both R2 prefixes are
empty: **58,899 objects / 1,665,493,265 bytes** removed, with no batch errors.
All five recovery archives remain and their stored hashes/sizes were rechecked.
Both frozen databases were dropped after confirming no remaining connections.
Removed only `rokkad-hosted-rehearsal-web-1` and
`rokkad-reviewed-import-20260923`; the local 8081 server remains stopped.

Production before/after inventories match: **29,770 objects / 880,056,600 bytes**,
all references resolved. Production image remains
`rokkad:media-retention-20260930-b65c552f57c4`. HTTPS still requires sign-in;
shared PostgreSQL/proxy and all five existing mail/storage timers are active.
Removed both temporary retirement helper containers and their transfer env file.
No application release, production schema/business mutation or old-server change.

The one-off operation deletes only exact manifest keys in batches of 500. A private,
flushed audit records batch intent and each provider response; errors stop the
operation. It does not configure a general cleanup command or background purge.
The databases can be dropped only after media retirement passes, with their
connection gates still closed and no sessions; no forced database drop is used.

Private reports remain under
`/home/rokkad/deploy/cutover-20260924/rehearsal-recovery-20260930/`:
`baseline-retirement.json`, `hosted-retirement.json`, `retirement-preflight.json`,
`media-retirement-audit.jsonl`, `media-retirement-report.json` and
`retirement-final-check.json`.
No customer dumps, media or secret configuration are copied into the synced repo.

## Retained recovery and exclusions

Keep all five recovery objects, **2,299,177,212 bytes**, under private R2 prefix
`recovery/rehearsal-retirement/20260930/22c54576e1d9d1ad/` in
`rokkad-production-media`, plus the verified server-side recovery packages.
The archive includes databases, media, private configuration, historical images,
source and recovery instructions. The recovery report records restore-test limits,
including Windows/Linux collation differences and read-only application testing.
Same-account R2 storage is independent of the Linode, not immutable or a second
provider. No automatic expiry is installed.

Exclude the live production database/media, preserved legacy originals and
attachment reports, old legacy server, and unrelated billing rehearsal. Retain
the shared PostgreSQL container `rokkad-rehearsal-db-db-1`, production proxy
`rokkad-hosted-rehearsal-proxy-1`, Docker network and shared volumes. Their names
do not imply that they are disposable rehearsals.

Removing the two loose media sets reclaims **1,665,493,265 bytes** relative to the
post-archive bucket. Recovery storage remains **2.30 GB**; this is not a net 1.67 GB
bucket reduction compared with the state before recovery archives were created.
