---
status: completed-rehearsal
owner: project
updated: 2026-09-21
tags: [migration, portability, rehearsal, evidence]
---

# Linode rehearsal: owner decisions completed

Continues the [opening admission checkpoint](linode-opening-rehearsal-20260921.md)
using the same immutable discovery archive and isolated database
`rokkad_baseline_rehearsal_linode_20260921`. Linode production, the normal application
database and `jcl-13` are separate. Runtime remained `rokkad_runtime` with neither
superuser nor bypass-RLS privileges. No production cutover was performed.

| Workspace | Operational loans | Closed evidence | Unused/cancelled | Loan holds | Principal INR | Interest INR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| JCL | 2,355 | 26,664 | 0 | 0 | 44,133,788 | 4,881,277 |
| JSK | 1,483 | 3,811 | 1 | 0 | 102,922,595 | 9,753,622 |
| Lakshmi | 2,435 | 8,658 | 0 | 0 | 52,791,200 | 7,979,951 |
| Total | 6,273 | 39,133 | 1 | 0 | 199,847,583 | 22,614,850 |

Balances are as of September 21, 2026, with zero unpaid fees and the previously
confirmed monthly-interest, upfront-first-month, net-weight and maturity rules.
All 45,407 source loan IDs are accounted for exactly once. The ten held JSK
addresses are admitted as distinct, preserving text and defaults. Party totals:
8,630 masters, 3,496 contact methods and 6,722 addresses, or 18,848 prepared records.

## Decisions applied

- Inactive customers mean all their loans were released and nothing remains due.
  Retain 190 JCL entries as owner-reported closed with unknown release dates and
  full raw graphs. No operational balances or settlement events are created.
- Exclude payments on the 14 source payment-bearing loans from calculations, retaining
  their rows and hashes. One overlaps the closed cohort; 13 remain outstanding with
  branch custody. The question incorrectly said 12 and two overlaps; the actual
  sets contain one payment overlap and one separate collateral overlap. The owner's
  answer and this count correction are retained explicitly.
- Keep ten matching JSK addresses separate. The generic batch-bound review path
  records exact source/parent/destination state, warnings, reason and approval.
- Correct JSK 03986, 05267 and WH01799, and Lakshmi C08257, C08612 and D00251 to 100%
  purity. No release records exist for these six; all are imported as outstanding
  with held collateral. `/2` profiles retain original values and hashes. Earlier
  profiles and already accepted openings were not changed.
- Retain zero-principal JSK WH01223 as unused/cancelled. It has no collateral or
  release rows and creates no loan or invented closure.

## Validation and evidence

All 6,273 opening documents, signed source evidence, collateral, balances, schedules,
remaining obligations and next monthly interest boundaries reconciled. All 39,133
closed documents and review findings exactly match their prepared evidence. The
entire source loan population partitions into operational, historical and excluded
sets without overlap. Existing source-review and opening-checkpoint manifests remain
unchanged. Closed/address admissions were checked against unchanged operational
table hashes. Repeated admission returned existing accepted results.

All 19 additional operational loans passed detail-page rendering, truthful opening
export and next-day full-release/retry checks under rollback. No release, payment,
new appraisal or historical disbursal was retained by these checks; native numbering
was unchanged. Restricted-role cross-Workspace and missing-context reads passed.
The focused 119-test suite passed, covering children, name reviews, opening staging,
source profiles, owner rules and presets. Subsequent command/browser-evidence checks
passed the 20-test opening module. `git diff --check` passed.

Private report: `outputs/linode-owner-decisions-20260921/review.html`. The manifest
covers 71 local files, including original owner answers, the payment-count correction,
prepared inputs, admission receipts, address verification, six purity corrections,
the cancelled source graph, all opening reconciliations, 19 exports and execution
scripts. `verification.json` contains combined totals; per-Workspace
`final-verification.json` contains full reconciliation results. Do not commit private
source/customer evidence. The prior sealed checkpoint remains a historical result.

## What remains

Make a separate local rehearsal application/login available for branch workflow
acceptance; the main app cannot display this database's records. Full settlement
with interest catch-up and coupled reversal is supported; ordinary partial repayment
remains guarded. Retained Party preparation decisions, required servicing, current
lending setup, access, media and clean-build readiness still need production
acceptance. Legacy continues receiving new data: freeze writes and take a fresh
complete archive for the final target, re-extract/review new or changed source
facts, rerun reconciliation and then switch over. This rehearsal dump is not a
delta-import base or a production-ready snapshot.
