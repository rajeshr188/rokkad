---
status: completed
owner: project
updated: 2026-10-16
tags: [loans, release, monitoring, corrections]
related: [loan-boundary-simplification-20261016.md, ../implementation/loan-boundary-release-20261016.md]
---

# Combined Loans coordinated release

The owner authorizes release preparation, explicitly choosing a combined candidate
containing the previously committed collateral/agreement corrections and LS-01
through LS-06. After preparation completes, the owner separately authorizes the
production switch by replying "proceed". Preserve the deployed
Party-merge consolidation/guard, existing Workspace authority, runtime restrictions,
business data, media, configuration and unrelated WhatsApp setup notes.

| Gate | Status |
|---|---|
| Freeze source and enumerate exact scope | Complete: 99 runtime files, source `21391df87683` |
| Read-only live baseline / roles / timers / capacity | Complete: both readers match all expected base hashes; V9; six timers; HTTPS; 10.556 GiB free at check |
| Frozen-source local regression and layouts | Complete: 566-case run plus passing 56-case follow-up for the two executions of one corrected clock fixture; 14 desktop/phone states |
| Source consistency / migration graph / V11 | Complete locally; ten pending steps simulated from live migration metadata |
| Stage source and build isolated server image | Complete after explicit owner approval; exact image `82b9e9065ad9`, all 99 files verified |
| Isolated production-copy migration and preservation rehearsal | Complete: 222-table/1,099,616-row restore; ten migrations; original business projections preserved; 30 refreshes, zero errors |
| Exact encrypted image recovery and candidate static collection | Complete: local-key recovery/load verified; new static volume and manifest pass, old static unchanged |
| Prepare coordinated reader/configuration changes without installing | Complete: web/worker/static plus four scheduled readers validate; protected configuration unchanged; nothing installed |
| Disposable rehearsal cleanup / final live checks | Complete: exact database/dump/settings removed; unchanged live readers, V9, HTTPS, six timers and 10.515 GiB free |
| Coordinated production switch and follow-up backup | Complete after separate owner authorization: ten migrations, compatible readers/static, HTTPS/roles/timers and pre/post encrypted backups pass; no loan/policy correction performed |

## Scope and coordination

The source manifest pins the existing live image, source parent, every changed
runtime file's expected baseline/candidate hashes, and the outgoing source-only
archive. It excludes credentials, runtime settings, customer data and uncommitted
WhatsApp setup notes. The immutable local source snapshot is tested independently
of the moving working tree. See the
[release record](../implementation/loan-boundary-release-20261016.md) and
[manifest](../implementation/loan-boundary-release-20261016.manifest.json).

Loans 0078-0081 and portability 0028/0029 enable the already-reviewed correction
evidence/readers. Loans 0086 fixes the policy parent lock; 0083/0085/0087 only join
branches. Existing Party migrations 0082/0084 are already deployed and must not
be removed, renumbered or replayed as a new repair. No existing agreement is
corrected simply by preparing or applying these migrations.

Web, continuous monitoring, three scheduled mail command readers and the health
reader must use compatible application source. Candidate static assets require
a separate collected volume because this combined scope includes changed loan
section JavaScript. Leave the old static volume intact. Preserve current resource
limits, explicit worker Workspace IDs, subscriptions/grace, policy choices and
disabled WhatsApp activation.

## Recovery boundary

Migration 0079 adds non-null `agreement_revision` with an application default but
no database default. Old writers omit it. Therefore the old image is not a safe
write rollback even before a corrected agreement exists. Stop/drain all affected
readers before the migration/write transition; do not briefly resume old writers.
New V6/V7 portable evidence and corrected agreements/checkpoints also require
compatible readers. Retain an exact recovered compatible candidate and forward-fix
if necessary with writes stopped. A database restore must never overwrite later
legitimate transactions as an automatic rollback.

V9 saved assessments become noncurrent under V11. Initial dashboard coverage may
be incomplete until the ordinary bounded worker refreshes the backlog. This is
derived-state catch-up, not financial data loss. Missing evidence remains missing;
do not change monitoring policy or fabricate appraisals to clear the queue.

## Completed server preparation

1. Stage the pinned source artifact into the private release directory and build
   a separate image from the exact live base. Verify all 99 image files offline.
   Do not restart or reconfigure production services.
2. Restore a current checksum-verified production dump into the disposable server
   database `rokkad_ls_release_rehearsal_20261016`. Customer data and diagnostics stay there;
   return aggregate proofs only. Disable provider delivery/payment activation in
   rehearsal, use restricted readers and owner-only migrations, and cap resources.
3. Assert the exact ten-step migration set, preserved original table projections,
   new revision-one column values, schema/model consistency, and retained original
   document rows. Exercise direct, paper, imported/opening and closed readers,
   correction replay/retry inside rollback. Reuse the unchanged deployed Party
   merge acceptance and frozen-source Party/portable round-trip regressions;
   no new Party merge or customer-package import is performed on the server.
4. Refresh a bounded V11 sample, permitting only derived monitoring/transition
   changes. Recheck unchanged financial sources and failed/unknown non-cure.
5. Collect and verify candidate static assets independently. Preserve the exact
   candidate image encrypted in the established private backup destination;
   independently recover it with the protected local key without exposing it.
6. Prepare compose/scheduled-reader changes, protected-configuration checks,
   fresh pre-switch backup requirements and post-switch checks. Do not install or
   run a switch as part of preparation. Remove only exact disposable rehearsal
   artifacts once their proofs are retained.

The initial staging attempt was rejected by automatic approval review because
release preparation was not considered explicit authorization for private source
transfer and server-side writes. After an explanation, the owner replies "ok
proceed", explicitly authorizing that preparation/rehearsal scope. New execution
passes approval review. That approval covers preparation; the subsequent "proceed"
after completed preparation separately authorizes the production deployment.

All preparation gates now pass; see the
[acceptance record](../implementation/loan-boundary-release-20261016.acceptance.json).
The coordinated production deployment now passes, including fresh encrypted
pre/post backups and a separately verified stopped-writer release checkpoint.
See the [deployment proof](../implementation/loan-boundary-release-20261016.deployment.json). The prepared candidate does not cure
missing valuation evidence: all thirty selected monitoring results remain honest
about unavailable coverage. Do not change policies merely to clear that status.

The exact candidate is live on web, monitoring and four scheduled readers.
All 99 source hashes verify on both live readers; V11, zero pending migrations,
restricted roles, 23 read-only screen checks and all six timers pass. Fourteen
paused balances match before/after migration; monitoring progresses in all three
Workspaces with zero observed errors. Redundant plaintext checkpoint/temp runtime
environment are removed after verified recovery; 10.506 GiB remains free.
No application-source change, Git commit or push accompanies this deployment.
