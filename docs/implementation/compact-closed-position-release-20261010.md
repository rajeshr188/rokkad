---
status: complete-live
owner: operations
updated: 2026-10-10
tags: [loans, storage, evidence, backups, release, bs05]
---

# BS-05 production release — 10 October 2026

BS-05 is live. Future closed-position admissions store compact version-2 financial
snapshots and reference the protected source archive. Existing posted version-1
records and their source copies remain unchanged. This reduces future duplication;
it does not reclaim the approximately 585 MiB already duplicated in posted records.
See the [implementation](compact-closed-position-evidence-bs05.md),
[decision](../adr/2026-10-10-compact-closed-position-evidence.md) and
[backup plan](../plans/backup-storage-and-evidence-efficiency.md).

## Exact release scope

Production switched at 06:33:52 UTC / 12:03:52 IST. The image is
rokkad:compact-closed-bs05-74c3634f, with immutable ID
sha256:7a81f9956bfe068029735375313480d96116a7b95b5b5e936fabd3af1fb65b49.
The seven runtime files come from commit
74c3634fbc86269db5adb115c063c58938bbcea2 on work/loan-servicing-contract-ld01.
They overlay the verified live IP-05 image; unrelated local onboarding, billing
and setup work is excluded. Every original file was checked against its expected
base hash and every candidate/live file against the committed hash.

Owner-only migration 0068 replaces three guard functions, without rewriting
business rows or introducing tables. It was applied online with a five-second
lock timeout and a sixty-second statement timeout. Existing version-1 readers
and writers remain compatible during the switch. Production web authority stays
restricted; the release posts no loan, payment, payout or accounting transaction.

Environment names and values, command, mounts, production settings, runtime
environment file and backup credential configuration match the prior deployment.
HTTPS login, pricing, FAQ and refund pages pass. All six timers are active again.

## Rehearsal and independent image recovery

An isolated production-backup restore reproduces all 202 tables and 879,465 rows.
All 201 business-table row fingerprints remain identical after migration 0068;
only migration bookkeeping changes. Restricted startup, schema consistency,
ordinary closed-loan pages, retained-source links, number search, direct/paper
entry, native detail/closure and loan-health readers pass in all three Workspaces.
Six native loan samples retain the same balance fingerprint on production.
Foreign-Workspace DML affects zero rows in a rolled-back isolated transaction;
live checks are read-only. Outbound messaging and payments are disabled in rehearsal.

The 39,196 previously admitted closed positions remain: JCL 26,649, JSK 3,836 and
Lakshmi 8,711. The 19 unadmitted records remain held: JCL 15 and JSK four. No
archive conversion, source rewrite, numbering change or expansion of the exact
190-record JCL exception occurs.

The exact candidate image was encrypted to the existing public age recipient,
preserved in the private R2 release prefix outside ordinary expiry, downloaded,
checked, decrypted locally and loaded into Docker with its exact image ID verified.
The encrypted image is 227,770,663 bytes; its SHA-256 is
6c35175f99a7999e728154108e8bec3089244133240def8a127045a723fe9b75.
The private recovery key never reaches the server. The slow Windows streaming
pipe was replaced by secure file transfer of the recovered application image,
using an account/SYSTEM-only local temporary directory and private server staging.
This stages no plaintext database/configuration backup; the application image
uses external production secrets and media. Temporary recovered image files are
removed on both sides.

The rehearsal database rokkad_bs05_rehearsal_20261010, its copied dump, generated
static files, temporary environment files and ciphertext staging are removed.
The original hourly backup, encrypted R2 image and private aggregate proofs remain.

## Rollout corrections and interruption

The isolated page check initially lacked its static manifest. Collectstatic in
the isolated mount resolves it without a production change. Private log export
was rejected by automatic approval review; an allowlisted error-category/boolean
diagnostic identified the issue without exporting log text or customer records.

The first live image attempt stopped at an operator check that compared environment
lists by order. The prior image was restored, compatible migration 0068 retained
and all timers resumed. The corrected comparison proves identical names/values,
zero changed keys and the same command; only list order differs. The successful
retry took 14.38 seconds for container replacement, with approximately 11.84 seconds
of sampled HTTP failures. This is an observed estimate, not a guaranteed bound;
the initial attempt and recovery caused additional brief restarts.

After any compact admission exists, old-reader rollback is prohibited. Preserve
compatible readers and schema support; never rewind the database over later
transactions. No compact admission was made by the release operator.

## Backup completion and capacity

Before switching, production-20261010T062227Z.dump completed with encrypted R2
publication and verified remote bytes. After deployment,
production-20261010T063417Z.dump completed the full ordered service path under the
renewed exact-image recovery acceptance. Its dump SHA-256 is
ae53cc643c64efb4f08c239188a5c1eb7b99a6fa09304e59c6faf171b9bdf704.
The completion includes download verification and guarded remote/local retention.

At the final check, HTTPS is 200, all six timers are active, protected configuration
and all seven runtime files match, and free space is 9.155 GiB. Retention reports
12 completed remote copies retained, 38 local copies retained, one covered local
copy expired and all 32 uncovered older local points protected. Release images,
separate checkpoints, media and orphan objects remain outside ordinary expiry.
The existing remote 24-hourly/30-UTC-daily and local-six-plus-uncovered policy is
unchanged. Capacity monitoring remains necessary as data grows.

BS-01 through BS-05 are complete. A later migration of existing posted source
payloads, older-checkpoint retirement or managed PostgreSQL move remains separate
work requiring its own scope; none is needed to finish this release.
