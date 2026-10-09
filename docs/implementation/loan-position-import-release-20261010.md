---
status: deployed-conversion-in-progress
owner: loans
updated: 2026-10-10
tags: [loans, release, positions, production]
---

# Ordinary closed-position production rollout

The owner authorizes the coordinated rollout after [IP-05 acceptance](loan-position-import-ip05.md).
Compatible code and schema are live from 10 October 2026, 01:20:58 IST. Conversion
is running; do not describe all retained records as converted until reconciliation
passes for each Workspace.

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

Expected eligible/held counts: JCL 26,649/15; JSK 3,836/4; Lakshmi 8,711/0.
JSK completes 3,836 admissions with 4 held claims; original loan/event/provenance/
source/sequence fingerprints remain unchanged. JCL and Lakshmi continue.

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
