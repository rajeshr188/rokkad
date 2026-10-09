---
status: deployed
owner: project
updated: 2026-10-09
tags: [loans, release, production, verification]
---

# Loan entry and servicing production release

The owner authorizes production rollout of the accepted loan changes on 9 October.
The switch completes at 15:53 IST with runtime commit `2b85a41f0a162717e4f8fea6707f8a5f528956a5` from
`work/loan-servicing-contract-ld01`. GitHub retains that source revision.

Web image: `rokkad:loan-release-20261009-e7d8f58bbc0e`.
Image ID: `sha256:ce84a5d1533ea7aebf963af40d856f1325394ac8440f8b35bcd260fbbc2da240`.
Static volume: `rokkad_production_static_20261009_e7d8f58bbc0e`.

This is a bounded 67-file derivative of the live monthly-choice image, preserving
the already-deployed billing flow and configuration. It carries the cumulative
loan/Party changes: customer repair services, unified current/completed closing,
paper tenure and two-step review, compact agreement/direct-entry presentation,
running-series availability and retained-register entry, atomic draft splitting
with one draft per collateral entry, and editable paper number/reference defaults.
Independent uncommitted billing development is excluded. Existing media storage,
private credentials, runtime environment and non-static mounts are preserved.

## Verification and switch

456 release regressions pass in a fresh disposable PostgreSQL database using
settings.test (365.838 seconds). Coverage includes origination, standing terms,
multi-item paper entry, numbering and races, grouped/batch splitting, series stop,
current/completed closing, bulk closure and concurrency, connected servicing
restoration, customer defaults/status, permissions and Workspace isolation.
Fifteen Node browser-interaction checks pass, plus JavaScript syntax,
1,056 curated documentation links and supported-app import checks across 1,095
tracked Python files. The initial aggregate test selection accidentally named a
nonexistent test module; the corrected complete 456-test command passes cleanly.
These are local release checks; no new GitHub Actions run is claimed.

Before the switch, the exact candidate passes restricted read-only production
checks for paper defaults, direct presentation, detail/closing and Loan health in
JCL, JSK and Lakshmi. RA00500, C07557, 06716, D01622 and D01623 retain their states,
collection balances and servicing profiles. Annual/monthly billing availability
and Subscription fingerprint are unchanged. Templates compile, collectstatic
succeeds and migration-drift checks show no new model migration.

Pause the previously active six timers and drain their services; stop web.
Capture a fresh server-only custom-format checkpoint and validate its checksum
and catalogue. Apply only Loans migration 0064 through settings.migration with
separately injected owner credentials. It updates two existing immutable batch
guard functions, allowing missing payer/collector only for exactly bound completed
settlement evidence. No table, backfill or customer financial posting is created.
All 198 original checked business-table row fingerprints match the checkpoint
after migration. Restricted guarded startup and post-migration read-only checks
pass before switching the canonical Compose web image and static volume.

Live checks pass for HTTPS login/public pages, actual loan screens, source hashes,
fingerprinted CSS/JavaScript content and an empty pending-migration plan. The app
runs as UID 10001 with rokkad_prod_runtime, without owner credentials. All six
timers resume; compatible independent mail readers retain their existing images.
No error/critical traceback appears in the new web log. The post-release backup
and bounded retention pass; free disk space is 9.73 GiB.

## Recovery evidence

Private server folder:
`/home/rokkad/deploy/cutover-20260924/loan-release-20261009/`.
It retains source/base manifests, exact candidate ID, candidate/live checks,
Compose before/candidate, release metadata before, a catalogued pre-release dump,
business-row fingerprints, maintenance and health reports. The checkpoint SHA-256
is `f93075b60da84be2b23df0316eea17b0adcd421c64f1b810e55b827343db234a`. Customer rows and media are not copied off-host.
Local ignored operator evidence: `.tmp/loan-release-20261009/`.

The previous live image and static volume remain available for image rollback.
Migration 0064 is additive for narrowly bound evidence and remains compatible with
the prior readers; retain it during image rollback. Do not reverse guards or
restore the checkpoint over subsequently entered customer transactions. Review
any later financial records before deciding recovery. Existing media and the
earlier verified LO-07 recovery evidence remain in their approved locations.
