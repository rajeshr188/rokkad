---
status: in-progress
owner: project
updated: 2026-10-08
tags: [loans, release, recovery, storage, operations]
related: [../plans/loan-origination-completion.md]
---

# LO-06 final candidate and recovery preparation

The owner accepted the series-driven New loan presentation as satisfactory for
now on 8 October and explicitly requested LO-06 release preparation. Production
rollout and D01623's production financial correction remain separate.

## Published candidate

Candidate **7a7bc8e6e8a2ad1539a1597173bbaeae508eac04** is committed and pushed.
Its [first full CI](https://github.com/rajeshr188/rokkad/actions/runs/37705798126)
failed one auction assertion among 2,138 Loans tests. The test used today's date
and assumed that adding one month to the sale always crosses the original loan
anniversary. On this run a 31 March sale plus a month clamps to 30 April, which
remains covered. The corrected deterministic fixture asserts zero through that
anniversary and the next INR 164 charge on 1 May, after the auction reversal and
interest repayment. Runtime calculation/posting code is unchanged. Focused tests
and new exact-candidate CI must pass before completion. All 38 focused auction and
shared-monthly-contract tests pass locally; full CI remains required. The clean local image is
`rokkad:loan-continuation-7a7bc8e6`, image ID
`sha256:c00ccd5d43210648f3869d951564ffe11d492fbbe92f9f4909a9ce985fa576ae`.
Committed source ZIP SHA-256:
`355d341acf073607673d8e6bed8cf82b7170c2698234aa53ebfbaa9d99ed57a1`.
This local artifact remains distinct from the clean server-built artifact:
`rokkad:loan-origination-7a7bc8e6-server`, image ID
`sha256:e8275c7c2413c905afa2a6ba453585ed59bdc7997b7fdf9559e1d9814de9a44e`.
Both use the same committed archive. Neither is deployed to production.

The corrected published candidate is **b172c7bbcfa5d309588bf0a9582858ce1cb6115e**;
[its full CI](https://github.com/rajeshr188/rokkad/actions/runs/37709841525)
passed the corrected interest test but failed one recovery fixture setup among
2,138 Loans tests. PostgreSQL's service log identifies autovacuum on
`loans_loanchangelog` waiting on the fixture transaction while that transaction
waits for its table lock. Per-test early locking was still after class-level role
grants. The five fixtures using that helper now acquire the same locks in
`setUpTestData`, before class catalogue/row writes. Production recovery locks and
autovacuum are unchanged; separate TransactionTestCase concurrency fixtures do
not acquire those class locks. All 60 checkpoint/auction tests and 65 other
affected origination/entry/bundle/concurrency tests pass (125 checks total).
A fresh published candidate and full CI remain required.
Its source ZIP SHA-256 is
`6c67802de1f4f87f5b6f47dc35fe5d1e23949c8f449966ae694f3b278ea8c6d0`.
Clean local image `rokkad:loan-continuation-b172c7bb`, ID
`sha256:a2e4c33f1ccd8870fc02a104eecabfceb8ce56de2feb0874aeeb83508ba1f87c`;
clean server image `rokkad:loan-origination-b172c7bb-server`, ID
`sha256:7edda077ba56e3de658e3a07583cd3ddcc402430dfd1a9b952b46dc7025cb1e9`.
Both artifacts match all 1,673 runtime source files and pass Python parse,
dependencies and restricted static collection. Local restricted startup,
owner refusal, schema and cohort reads pass, preserving all 202 tables in both
fictional recovery databases. The only changed runtime file is the auction test;
business code, contracts, migrations, templates and static assets match 7a7bc8e6.
Final-candidate server checks reuse the verified cold checkpoint rather than
recapturing identical source data. First-run recovery artifacts remain preserved;
final-candidate evidence uses the separate `lo06-final-` prefix.

At **06:28:42 IST**, the final server artifact passes restricted startup/schema,
all three Workspace inventories (6,739 supported active/closed calculations),
selected source/isolation checks and actual restored-file reading: all 350 issued
PDFs open and 27,616 photo/archive hashes match. All 202 tables still match the
sealed cold checkpoint, and all 199 sequence positions remain unchanged before/
after reads. Ephemeral media credentials are removed. Free space after the final
build is **12,535,508,992 bytes** (about 11.7 GiB). Provider delivery and public
listeners remain disabled; production readers/data are unchanged. Final guarded
timer-reader files are prepared under `lo06-final-`, not installed.

Restricted production-settings startup, owner-startup refusal, schema-drift and
retained-cohort reads pass on both existing fictional recovery databases. All
202 public tables remain unchanged. This does not prove fresh production or actual
media recovery. Documentation links, application boundaries, four boundary unit
checks and both shared-editor JavaScript checks pass. All **1,673 allowlisted
runtime files**, including contracts, match the local clean archive; Python parse,
dependency consistency and restricted static collection pass. The first hash
probe included operator scripts deliberately excluded by `.dockerignore`; the
corrected probe follows the runtime allowlist.

## Fresh read-only production discovery

At **05:34–05:36 IST, 8 October**, production remains at Loans
`0032_series_partial_interest` and portability `0017_loan_history_v2`.
Database size is **784,669,719 bytes**, staging size **702,135,319 bytes**,
WAL **603,979,776 bytes**, with no temporary files observed. Free host space is
approximately **1.85 GiB**.

The existing registry covers 14 installed FileFields plus document snapshots and
retained media admission receipts. Restricted repeatable-read/read-only references
and production-prefix listing find **30,293 distinct required objects,
942,099,334 bytes**, **zero missing references**. All production-prefix objects
are referenced. This does not verify body hashes or recoverability. No media body
was downloaded. Bucket-versioning discovery returns AccessDenied; it is unverified.

Exact keys remain in the approved mode-0700 server folder
`/home/rokkad/deploy/cutover-20260924/loan-continuation-20261006-b69df6ab`, file
`lo06-media-metadata.private.json`, SHA-256
`ae96ab6a6379ada7552ab4a04fceeb07afc72287f3328a02fca8db99986db6bb`.
No customer media, full dump or customer records are downloaded into local OneDrive.

## Capacity and backup finding

The hourly backup timer is active, but its service fails with exit code 1.
Its script requires more than **5 GiB free** before dumping; current space is
below the guard. The latest completed operational backup is **3 October,
11:00 UTC**, over four days old. No completed copy exists in the last 24 hours.
Keep the guard; remedy capacity rather than weaken it.

`backups/operational` contains **288 completed dumps, 17,447,834,330 bytes**.
A dry run retains the newest 24 completed hourly copies and the latest completed
copy from every older date: **31 retained**, **257 removable**,
**15,244,664,604 bytes** reclaimable (about 14.2 GiB). All separate release and
rehearsal checkpoints remain outside this proposal. Removal permanently loses
those older hourly restore points. The owner explicitly approved this scoped
cleanup on 8 October. All 31 retained copies passed SHA-256 and catalogue checks.
This does not mean that all 31 have each undergone a full cold restore.

The server-only proposal is `lo06-retention-plan.private.json`, SHA-256
`e0b1293d901d5649f716f54bfd38e2cabce930ab205820f8eb912a15999a8d12`.
At **05:41:41 IST**, a new consistent server-only source checkpoint was captured:
**88,598,984 bytes**, SHA-256
`089586839e7c7140a66e4d2a7f0bace0a0d68c1d784c9b54c61c027bdb020c68`.
The exact approved 257 dumps and their checksum sidecars were removed after
containment/manifest/retained-checksum validation. Free space rose to about
**15.96 GiB**. The existing backup service then completed at **05:41:58 IST**,
creating an 88,598,984-byte archive, SHA-256
`f9befcb0716714bbb87cb670586fe6b88595e848d336c73d8773f17e547ab416`.
Its catalogue and checksum pass. Free space after that service is
**17,047,748,608 bytes** (about 15.9 GiB). The 5 GiB guard is unchanged.
Live data, media objects and production image are unchanged. A one-time cleanup
does not establish ongoing retention or off-host recovery.

At **06:30 IST**, the next automatically scheduled hourly copy also completed
successfully (`20261008T010000Z`, 88,598,984 bytes). Its checksum/catalogue pass,
the timer remains active and the production web container remains running on its
original image. SHA-256:
`00f20e6e324a81a17145139841936a3b7103abd1f6a726386928f4fc24b51047`.
Free space after the final build and this backup is **12,446,515,200 bytes**
(about 11.6 GiB). At roughly 89 MB per hourly dump, unchanged retention can consume
the headroom above the 5 GiB guard in about three to four days, before other
growth. Daily capacity/success review is required until ongoing retention is
separately approved and installed; this rehearsal installs neither retention nor
failure alerting.

The fresh checkpoint restored exactly across all 186 original tables into the
previously approved private staging database. The earlier corrected stage is
preserved in a separate checkpoint. Role provisioning initially refused to create
the already existing runtime role. The corrected runner explicitly uses the
supported grant-only option without changing that role. At **05:49:12 IST**, owner
migrations through Loans 0063 and dependencies passed; all 183 original business
projections remained exact. Restricted startup, owner refusal, pending-migration
refusal and no schema drift pass. Free space after upgrade is 15,803,539,456 bytes.

## Reader discovery and rollout requirements

Storage inventory executes inside `rokkad-production-web-1`, so it follows that
container's artifact. Platform-mail dispatch, feedback and stale recovery instead
launch the fixed older `rokkad:onboarding-monitor-20260929-df4b82f62000` image and
invoke `manage.py` directly. The health watchdog is a separate host Python helper.
These are independent scheduled readers; a web-only image switch would leave
them behind. LO-07 must pin those scheduled readers to the same compatible
candidate and use the runtime startup/contract guard, with provider credentials
remaining server-only. Discovery did not change units or send notifications.

Actual media collection uses conditional R2 reads and SHA-256 capture in the
approved private folder. Its initial startup failed because a secret-free mounted
settings file was unreadable by the unprivileged app; no files were downloaded.
The scoped file permission was corrected. The initial six-request collector was
stopped and restarted with 24 bounded reads to shorten capture; partial scratch
copies are re-read, not treated as a completed checkpoint. No production object
is uploaded, rewritten or deleted. A subsequent SSH reset did not stop the
server-side capture/copy; its completed aggregate report was retrieved independently.

At **06:00:33 IST**, all **30,293 referenced files, 942,099,334 bytes** were captured
and independently copied into isolated restore storage with exact per-file SHA-256
matches. The migrated candidate registry covers 16 FileFields. All **350 issued
documents and 20 template assets** match their retained expected hashes. Required
object metadata remained unchanged before/after capture. Checkpoint manifest
SHA-256: `d855e904d2e9d9c8240d7292b37585e58a61e5c2f7e625ef315884fe62690be8`.
Versioning remains unverified; conditional ETag reads and frozen SHA-256 checkpoint
bytes are the demonstrated recovery mechanism, not a bucket-versioning claim.
Free space after both media copies is **13,727,592,448 bytes** (about 12.8 GiB).

Private candidate drop-ins/config are prepared for dispatch, feedback, stale
recovery and the health watchdog, all pinned to the server artifact and guarded
startup. The three underlying management-command entrypoints pass guarded help
checks on the isolated stage with providers disabled. No units/config are installed
in production and no notification was sent. The existing host watchdog helper
remains unchanged; its prepared command array includes the guarded candidate.

## Fresh cold recovery and source reads

At **06:08:23 IST**, the exact server candidate cold-restored **202 tables and
199 sequence positions** exactly. All **30,293 restored media hashes** remain
equal. Restricted readers opened all **350 issued PDFs**, verified their stored
hashes, and checked **27,616 photo/archive hashes** against retained records.
Representative actual collateral/historical images decode in each Workspace;
representative issued PDFs render in JCL/JSK. This is technical readability,
not human document acceptance. No customer contents leave the server.

Candidate cold checkpoint: **88,868,128 bytes**, SHA-256
`1294a3790acc05e1983a8356803114842b2332a3c1bca07c2e5610e9e17aaf50`.
Post-read table and sequence comparisons remain exact. No-context/cross-Workspace
ordinary reads return zero. Free space is **13,620,654,080 bytes** (about 12.7 GiB).

| Workspace | Active | Closed | Supported active/closed | Unadmitted archive identities |
| --- | ---: | ---: | ---: | ---: |
| JCL | 2,615 | 10 | 2,625 | 26,664 |
| JSK | 1,595 | 79 | 1,674 | 3,840 |
| Lakshmi | 2,440 | 0 | 2,440 | 8,711 |

All **6,739 ordinary active/closed loans** calculate under retained contracts:
348 native-event-fold/1 and 6,391 opening profile /2. No contract is adopted or
archive converted. Independent limits remain: 335 SYSTEM_RECORDED versus 6,404
UNCONFIRMED transaction coverage, 152 STALE versus 6,587 UNASSESSED risk freshness,
and all 6,739 valuations UNASSESSED. Calculation support does not authorize a
collection, certify books or prove current valuation readiness.

RA00500 remains active, recorded principal 60,000 and computed collection 61,200;
C07557 remains active at 8,170; 06716 remains closed at zero. D01623 remains the
source DRAFT at zero recorded debt, with the retained reversed native attempt:
its explicit production correction is still required. The earlier corrected staging
demonstration is preserved separately; this fresh source clone did not silently
apply that correction. The 39,215 unadmitted archive identities remain source evidence.
Archive counts complete in 1.656s (JCL), 0.538s (JSK) and 0.663s (Lakshmi).

## Remaining verification and rollout limits

1. Full exact-candidate CI must pass; resolve findings before freezing a new identity.
2. Database/media capture, owner upgrade, exact cold recovery, restricted reads,
   representative file decoding, source integrity and capacity checks pass as dated
   above. A rollout needs fresh checkpoints covering subsequent production activity.
3. Install the prepared compatible web/timer readers only through LO-07's concrete
   deployment review. No production reader or unit has changed in this rehearsal.
4. Record off-host recovery separately; same-host recovery does not prove host-loss
   resilience. Corrected-paper display/latest position and document/monitoring staff
   acceptance remain separate LO-05 gates.

Use the [recovery and retention runbook](../flows/loan-candidate-recovery-lo06.md).
The exact 21 bounded operator sources are preserved in `lo06-operator-sources/`
inside the same private server folder. Source manifest SHA-256:
`8fa32e17cd60a9fa62391d2cd9fa01b0eb53d47bfb072dffee48b53f300fe93d`.
The final ten verification/operator sources are separately preserved in
`lo06-final-operator-sources/`, manifest SHA-256
`91c7fb1acff857cc4217937699d3ba1a2063e3faed954c3f8d51a610009938d1`.
These harnesses are scoped to this approved disposable target; they are not permission
to reuse its destructive staging commands against another database.

Production data, media, migrations, routing and readers remain unchanged.
