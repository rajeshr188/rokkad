---
status: complete
owner: project
updated: 2026-09-30
tags: [fw-015, storage, recovery, rehearsal]
---

# Rehearsal recovery packages — 30 September 2026

**Later checkpoint:** the owner subsequently approved retirement, completed after
fresh source/archive checks. Original rehearsal databases/media are now removed;
all verified recovery packages remain with no automatic expiry. See
[the retirement record](rehearsal-retirement-20260930.md). The sections below describe
the earlier recovery exercise and its limits.

The owner approved preparing private recovery packages and isolated restore tests
for the two obsolete rehearsal environments. The owner separately approved a
private R2 archive prefix and explicitly confirmed temporary staging of database
dumps, media and recovery configuration on the new Linode. Initial automatic review
blocked server-side media staging pending that explicit confirmation; capture began
only after approval. No source environment or media retirement is authorized by
this recovery exercise.

## Scope and method

| Scope | Source database | Matching historical application image |
| --- | --- | --- |
| Local baseline | `rokkad_baseline_rehearsal_linode_20260921` | `rokkad:a9f793fc` |
| Former hosted rehearsal | `rokkad_cutover_rehearsal` | `rokkad:rc-20260924-fd011920` |

The local database snapshot is streamed directly over SSH into private server
storage, without a local dump in OneDrive. Its exported PostgreSQL snapshot binds
the dump to all-table row counts/content fingerprints. Hosted capture checks
all-table fingerprints before and after pg_dump. No other source connections were
present at those checks; the former hosted web container remains stopped. This is
a capture-time observation, not a durable write freeze or deletion authorization.

Only the two exact rehearsal media prefixes are downloaded. Each object is fetched
with its listed ETag as a precondition; byte count and streamed SHA256 are checked
against the saved copy. Listings before and after each capture must match. Keys,
metadata and content hashes remain in private manifests. Production, preserved
legacy originals and attachment evidence reports are excluded from this capture.

Restores use new databases in `rokkad-recovery-db-20260930`, a dedicated PostgreSQL
16 container with **no network and no published ports**, and separate private data
storage. Original passwords are not restored. Fresh runtime roles have no superuser
or BYPASSRLS authority; the application drill gets SELECT-only access with read-only
transactions. The matching historical application images also run without network,
using synthetic configuration and disabled external communications/payments.

Every restored public table is compared by row count and sorted row-content MD5
fingerprint. MD5 here is a consistency comparison, not an archive security guarantee;
dump/archive/media integrity uses SHA256. Row JSON uses the source timezone for
equivalent timestamp formatting. Both application images must have no pending
migrations and return no business rows outside a Workspace context.

Each environment archive is read back in full; all member hashes are checked.
Media is reconstructed from the archive into a new directory using the original
relative keys, then every reconstructed file is hash-checked again. Historical app
checks resolve all FileFields, issued-ticket snapshots and immutable admission
receipt references against this restored media. No original R2 objects are needed
by the offline application drill.

## Verification checkpoints

| Check | Baseline | Hosted |
| --- | ---: | ---: |
| Restored public tables | 160 | 161 |
| Restored rows, all public tables | 295,602 | 275,390 |
| All table fingerprints match | Yes | Yes |
| Application workspaces | 4 | 3 |
| Parties / loans | 8,632 / 6,275 | 8,634 / 6,371 |
| Pending migrations in matching image | 0 | 0 |
| Media copied, archived and restored | 29,381 | 29,518 |
| Media bytes, all SHA256 checked | 831,444,125 | 834,049,140 |
| Historical/current media references resolved | 29,379 | 29,514 |
| Verified environment archive bytes | 872,913,844 | 874,503,471 |

Together the packages cover **58,899 media objects / 1,665,493,265 bytes**.
The shared image archive is 533,922,263 bytes; the support archive is 17,834,074
bytes. Total recovery artifacts before the small top-level manifest are
**2,299,173,652 bytes**. Package size includes databases, images, configuration and
recovery evidence, not just the original media.

## Recovery artifacts and limits

Private staging and evidence stay under
`/home/rokkad/deploy/cutover-20260924/rehearsal-recovery-20260930/`.
The verified off-server destination is
`rokkad-production-media/recovery/rehearsal-retirement/20260930/22c54576e1d9d1ad/`.
All **five objects / 2,299,177,212 bytes** passed full-byte SHA256 readback from R2.
The top-level manifest is `recovery-manifest.json`; its SHA256 begins with the
prefix identifier. Local `archive-upload-report.json` records each exact object key,
size, SHA256 and readback result. No public ACL or expiration rule was requested.

The artifacts are two database/media/configuration archives, one shared archive
containing both application images and PostgreSQL, a support archive with manifests,
historical baseline source and the offline recovery recipe, and a top-level manifest.
The upload procedure verifies each R2 object with a full streamed SHA256 readback.
Private runtime/signing configuration is included only within these approved private
packages. The current production environment used by the transfer helper is excluded.

After independent readback passed, the three temporary capture/upload/restore
containers and disposable restored database/media directories were removed.
The temporary copy of production transfer settings and the drill password were
also removed. Original rehearsal databases/media and the verified server packages
remain. Final checks confirmed the production image was unchanged, authenticated
HTTPS still required login and existing mail/storage timers remained active.
The server had 12,272,041,984 bytes free after disposing of the test copies.

This proves database/content recovery and historical application read compatibility;
it does not certify real Google sign-in, business writes, mail, payments or every UI
workflow in a restored environment. Original ACLs/ownership are preserved in dumps,
but the isolated test deliberately uses fresh roles/grants. An operational restart
needs a reviewed security/configuration plan.
The baseline source uses Windows `English_India.1252` collation with UTF8 encoding;
the Linux drill uses its default locale. All rows and constraints restored, but
exact locale-dependent sorting needs a matching native locale/Windows restore or
a separately reviewed collation migration. This limitation is also in the private
recovery recipe.

R2 provides a copy independent of the Linode, within the same R2 account/bucket as
the source media. It is not a second-provider or immutable backup. Moving files into
archives does not reduce total bucket storage; no automatic expiration is installed.

## Retirement remains separate

The precise candidate environments remain those in the
[retirement plan](../plans/recoverable-media-cleanup.md). Exclude the production
database/media prefix, preserved migration evidence, old legacy server and shared
PostgreSQL/proxy/Docker infrastructure. Before deletion, confirm that neither scope
has changed since capture, stop any remaining writers and approve an exact scope
and recovery retention period. No source files or databases are removed by this work.

No automatic archive expiry was configured and no retention deadline was approved.
Suggested next decision: approve retirement of the named rehearsal environments,
retaining these verified archives until a separately agreed review/expiry date.
Keep archive retrieval restricted: the packages contain personal data and secrets.
