---
status: completed-with-holds
owner: project
updated: 2026-09-21
tags: [migration, loans, rehearsal, portability]
---

# Three-Workspace loan admission rehearsal

This continues the [Party rehearsal](linode-party-rehearsal-20260921.md) and
[source review](linode-loan-review-20260921.md), using the same September 21 archive
and installation namespace. Destination is the isolated database
`rokkad_baseline_rehearsal_linode_20260921`, under `rokkad_runtime`, with
`django_project.settings.baseline_rehearsal`. Normal application Workspaces,
including `jcl-13`, and Linode production are separate.

## Results

| Workspace | Operational openings | Closed source evidence | Active holds | Principal INR | Interest INR |
| --- | ---: | ---: | ---: | ---: | ---: |
| JCL | 2,345 | 26,474 | 200 | 44,061,398 | 4,850,848 |
| JSK | 1,478 | 3,811 | 6 | 102,284,325 | 9,531,464 |
| Lakshmi | 2,431 | 8,658 | 4 | 52,228,200 | 7,935,171 |
| Total | 6,254 | 38,943 | 210 | 198,573,923 | 22,317,483 |

Every source loan ID is accounted for exactly once: operational opening, held
active record or closed source evidence. All imported opening fees are zero.
The held categories are 190 inactive borrowers, 14 payment-bearing cases and
eight source/collateral cases; two records overlap, giving 210 unique holds.
The owner's R09911 correction is retained as `opened_on: 2025-12-16` in closed
evidence (`closed_on: 2026-03-12`), with the raw source/correction ledger preserved.
It is not an operational active loan.

## Accepted rehearsal inputs

The owner confirmed shared interest/maturity rules, net item weight, branch
custody apart from flagged exceptions, and finally "no fees are unpaid,proceed".
The unflagged, payment-free cohort uses unchanged principal, first month paid
upfront, subsequent original-anniversary charges rounded once in aggregate to
whole rupees with HALF_EVEN, and zero unpaid fees. Preserve recorded tenure or
the confirmed three-month fallback. The rehearsal checkpoint is September 21;
production still requires a fresh frozen source and final balance acceptance.

Legacy licences retain exact source labels without inventing validity dates.
Series permit servicing and reserve migrated source number ranges. Original loan
numbers are preserved. The legacy product is retired and legacy licences do not
authorize new lending. Existing ancillary rehearsal policy defaults are explicit
in each frozen setup. No current appraisal is inferred from undated legacy values;
gross weights remain unknown and item net weights retain the owner's evidence.

## Preparation repairs

317 loans (13 JCL, seven JSK, 297 Lakshmi) had description line breaks or tabs
rejected by bounded text validation. The scoped Linode adapter normalizes these
runs to a space. Signed staging retains original source rows/hashes and explicit
before/after transformations; unrelated edits still fail source verification.

902 recent loans (381 JCL, 205 JSK, 316 Lakshmi) have zero additional interest
at the checkpoint. Preparation initially emitted an empty interest obligation.
The writer rejected it before admission. Remove that uncommitted empty row,
retain the positive principal obligation and all balances, and resume from
verified accepted fingerprints. The offline validator now reports the same
positivity requirement before database preview. Accepted records are immutable.

## Execution and checks

Opening admission uses ordinary source re-extraction, staging, signed preview
and per-loan commit in transactions of at most 20 loans. Each chunk checks a
completed-batch retry. Checkpoints are written after commit; persisted origins
are the resume authority. There is no direct financial model bulk insert.

Independent verification compares every frozen document and source record,
borrower, collateral, opening event, balance and remaining obligation. It checks
the next monthly interest boundary and raw SQL RLS under the restricted role.
Representative loan pages and exports are exercised. Full settlement and retry
are simulated on September 22, strictly after the opening checkpoint, and rolled
back together with release-number changes. No test settlements remain.
All 6,254 opening loans passed this reconciliation. Twenty-one representative
loans passed the page/export/full-release-and-retry rollback checks. Restarting
each completed opening importer verified all persisted document fingerprints and
performed no additional admissions.

Closed-loan admission uses the historical evidence service, preserving unknown
fields and contradictory source claims. It creates no active loans or certified
payments. Every stored archive document, review and digest is reconciled; sampled
exports and retries are verified. Operational table checksums must remain
unchanged before and after archive admission.
All 38,943 closed records passed reconciliation. Six representative archive
exports and a retry in each admission chunk passed. The archive kept unknown
principal/balance/payment fields and chronology findings; retention does not
certify settlement or reconstruct unavailable financial history.

The focused source-staging, owner-profile, opening-validation, obligations and
opening-import regression suite passed all 70 tests.
The two migration fixes and their regressions are committed in `7d8e131a`.

## Private evidence and remaining work

Private report: `outputs/linode-opening-rehearsal-20260921/review.html`, with
per-branch loan/month/next-increase tables, held rows, inputs, fingerprint
revisions, receipts and verification. All three opening and archive completion
markers were written only after their independent checks passed. The root
manifest hashes 791 evidence files, including local orchestration scripts;
all report links resolve. Customer evidence is ignored by Git. These fixed-source
local scripts are rehearsal orchestration, not a clean-build production release.

This does not clear the 210 active-loan holds, ten duplicate Party addresses or
retained Party preparation decisions. Opening servicing currently supports
full-settlement catch-up, full release and coupled reversal; ordinary partial
repayments and other financial actions remain guarded. Establish the actual
branch servicing requirements before calling the migration operationally ready.
Current lending setup, approved user access, media migration, a clean committed
release, final write freeze/fresh archive and final reconciliation remain
production prerequisites. The rehearsal owner has an unusable password; these
records are not automatically visible through the normal running app.
