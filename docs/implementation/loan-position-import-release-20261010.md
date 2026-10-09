---
status: deployed
owner: loans
updated: 2026-10-10
tags: [loans, release, positions, production]
---

# Ordinary closed-position production rollout

The owner authorizes the coordinated rollout after [IP-05 acceptance](loan-position-import-ip05.md).
Compatible code and schema are live from 10 October 2026, 01:20:58 IST. Conversion
completes and reconciles in all three Workspaces. All 39,196 eligible retained
records are ordinary CLOSED loans; 19 contradictory claims remain held.

Runtime source: `e851f2613238fbc1e5b85701946defaf675a19a9`, pushed to
`work/loan-servicing-contract-ld01` on GitHub.
Image: `rokkad:closed-position-ip05-3829abaa8ac7`.
Image ID: `sha256:7b1a2aab8c04be1e74b7409a4e9e4d08e1d7bb8be59e629aa3c2a1b36d721436`.

The 36-file bounded derivative preserves the deployed billing image/configuration,
static volume, media mounts and runtime environment. Unrelated local billing
work is excluded. No static source changes require a new static volume.

## Checkpoint and compatible switch

Pause the six active operational timers, drain their services and stop web.
Capture a fresh server-only custom-format dump, validate its checksum/catalogue,
and fingerprint original business rows. Checkpoint SHA-256:
`9ba9201f592aa4d41b1c619ae54f8e1d69a1d51a37d0359cdf19bc29d8d78707`.
Customer rows and source graphs remain on the server.

Owner-only migrations 0065, 0066 and 0067 pass. All 198 checked original business
tables retain their row fingerprints. Generated source metadata and narrowly
scoped nullable closed-position terms do not rewrite financial facts. Migration
0067 aligns the new guard with the India business day and retains future-date
rejection. Runtime startup, original paper/direct/detail/closure/Loan health,
billing checks and empty pending-migration checks pass before and after switch.
Web remains UID 10001 with the restricted runtime role and no owner credentials.
HTTPS checks pass and all six timers resume. Existing configuration/file hashes
and non-static mounts remain identical. The maintenance switch creates no
financial events or ordinary admissions.

## Reviewed conversion

Run fresh production review through the existing admission/batch services, using
current authority, exact source/Party/register mappings and number checks. Compare
every retained source hash with the frozen inventory. The exact 190-record JCL
identity/hash attestation is used only for its approved recovery cohort; no
standing missing-release inference is added. Source semantics remain zero debt
and returned collateral, with unavailable earlier financial history.

Verified eligible/held counts: JCL 26,649/15; JSK 3,836/4; Lakshmi 8,711/0.
All 39,196 admissions complete, including the exact 190-record JCL recovery cohort.
Original loan/event/provenance/source/sequence fingerprints and retained source
hashes remain unchanged in every Workspace. Each loan has exactly one zero
MIGRATION_OPENING and one origin; no other events were added to these loans.

Each chunk has at most 100 records, commits independently and saves progress.
Successful chunks remain immutable and retries skip matching origins. Two jobs
at a time have CPU/memory limits; web stays online during conversion.

An accepted position adds only an ordinary CLOSED loan, one zero opening
checkpoint and immutable origin/audit evidence. No earlier payout, receipt,
approval, accrual or physical return transaction is fabricated. Preserve all
source snapshots/photos and existing original dates. Hold contradictory dates
rather than silently changing or discarding them.

## Recovery and final acceptance

Private server evidence:
`/home/rokkad/deploy/cutover-20260924/loan-position-release-20261010/`.
It contains checkpoint/checksum/catalogue, manifests, configuration hashes,
pre/post switch checks, signed reviews, progress and conversion verification.
Ignored local operator helpers are in `.tmp/loan-position-release-20261010/`.

Before admission begins, image rollback can retain the additive schema because
all original loans remain compatible. After admission, keep a reader that supports
nullable closed-position details. Never switch back to an incompatible reader,
delete successful admissions or restore the old checkpoint over later customer
transactions. Stop failed chunks and re-review unchanged sources before resuming.

Final acceptance requires exact ordinary/event/origin counts, held claims,
existing loan/event/source/provenance/sequence preservation or explicit
reconciliation of legitimate concurrent staff actions, readable ordinary/source
pages, native workflow checks, healthy timers and a completed post-conversion
backup with retained capacity.

## Final production acceptance

All three restricted conversion jobs exit successfully. Read-only repeatable-read
checks reconcile the exact ordinary/event/origin/pending counts and returned
custody with explicitly unavailable earlier history. Ordinary details, retained
source details, number search, open-first lists and Workspace isolation pass.
Original native paper/direct/closure/Loan health screens and sampled loan balances
match the paused baseline. Subscription fingerprints, deployed source files,
configuration and media remain unchanged. HTTPS pages and all six operational
timers are healthy; post-switch web logs contain no checked error/traceback lines.
The native comparison retains the original five Workspace/number samples. One
additional newly admitted sample with a matching number in another Workspace is
separately verified as a zero-debt closed-position profile.

Final backup acceptance completes at 10 October 2026, 02:42:37 IST. The fresh
post-conversion archive has a verified checksum and catalogue. SHA-256:
`9815d9e0603f295de24f3ab6cf5fcb2ab170d46e542a3777a80b1ff67383ebfc`.
Backup size is 164370606 bytes. Retention applies the existing
latest-24-hourly/30-UTC-daily policy and protects separate release checkpoints.
Free disk is 7.58 GiB, above the 5 GiB backup cutoff.
This server-only database copy is not off-server disaster recovery; existing media
storage/recovery arrangements are preserved.

Capacity follow-up: the verified archive is now about 157 MiB. The current 34
completed operational copies occupy 2.8 GiB. A conservative full
24-hourly/30-daily footprint of 53 copies at this measured size is
8.11 GiB, projecting only 2.27 GiB free with other usage fixed.
At least 2.73 GiB additional capacity is needed to preserve the 5 GiB cutoff,
before future business growth. The current backup passes; this projection is not
an assertion that ongoing capacity is solved. Preserve the approved retention,
media and release checkpoints. Arrange capacity expansion or separately reviewed
cleanup; do not silently weaken retention. Track
[FW-023](../plans/future-work.md#fw-023-database-backup-capacity-after-closed-position-conversion).

Use the ordinary Loans list for these closed loans. Retained source documents and
photos remain linked supporting evidence. The 19 held records require date
correction review; this rollout does not rewrite their claims. Search corrections
are deployed, but broad searches may still take several seconds. Unrelated local
billing work stays outside the deployed runtime and these scoped commits.

## Read-only backup-size follow-up

The default deployed media backend is helpers.cloudflare.storages.MediaFileStorage
(S3-compatible R2 media). The hourly command uses pg_dump -Fc for the entire
production database; it does not copy image files or only the latest changes.
Production database disk size is 1,317,362,711 bytes, about 1.23 GiB. The measured
157 MiB backup is compressed and cannot be equated to physical table/index size.

Restricted repeatable-read aggregate inspection of all three Workspaces finds:

| Data | Rows | Uncompressed JSON text bytes |
| --- | ---: | ---: |
| Original retained sources | 39,215 | 306,774,422 |
| New closed origin documents | 39,196 | 352,502,647 |
| New closed opening payloads | 39,196 | 365,672,503 |

Each of the latter two sets contains 306,617,412 bytes of embedded retained source
JSON, about 585 MiB additional uncompressed source copies in total. The current
closed-position admission deep-copies the full input, including retained_evidence,
into both financial-origin and opening snapshots while preserving the original
archive. That duplication contributes to the backup growth; it is not photo-file
storage. Logical JSON lengths include serialization whitespace and are not exact
compressed backup contributions. Source-copy measurements remain aggregate-only;
private customer rows stay on the server.

Consider compact future financial snapshots referencing one immutable source by
identity/hash, with versioned readers/guards and complete export/restore support.
Do not silently strip evidence from existing immutable payloads. Also review
separately protected off-server database backups with tested restore and approved
retention, keeping recent copies locally. R2 media storage alone does not provide
database backup protection. Inspect other server disk usage before purchasing
capacity or deleting artifacts. This is diagnostic/recommendation work only: no
runtime code, financial records, source snapshots or retention settings change.
Operator helpers and aggregate proof remain in the private release evidence folder.
