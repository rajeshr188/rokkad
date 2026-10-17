---
status: deployed
owner: project
updated: 2026-10-17
tags: [loans, origination, closing, integration, release]
related: [origination-simplification-20261017.md, ../adr/2026-10-17-explicit-closing-mode-and-shared-contract-checks.md]
---

# Origination and closing integration: 17 October 2026

The owner authorized the explained integration, commit/push and verified release
sequence. This combines the independently tested origination simplification and
closing work on maintained main `ed585f334d3a610a0976b8488e52e2cffb21ea68`.
Source worktrees and unrelated dirty WhatsApp work are preserved. Their 43 and 29
changed/untracked files are retained in checksum-verified private snapshots.
No financial correction, policy amendment or messaging activation is authorized
by this application release. Leave JSK WH02306 unchanged.

Commit `4898c243` formats the 24 existing touched Python modules with verified AST
equivalence. The behavior commit is separate. Shared URL imports/routes, detail
actions and documentation retain both implementations; Windows line endings are
normalized only for the three-way comparison. Draft replacement remains a
preparation action; Close / release remains an active-loan transaction action.

Both parts reuse existing calculators, posting services and evidence profiles.
There are no schema migrations, new financial wire profiles or monitoring-policy
changes. Paper agreements retain the owner's confirmed full monthly rules.
Started-week direct financial correction remains explicitly unsupported; closing
uses its existing saved-rule calculator and does not claim new correction parity.

## Combined verification

Five added journey tests pass in 24.539 seconds. They correct borrower, collateral
description and original principal/rate through the supported reviewed services,
then close direct/paper agreements through single/multiple, current/completed
paths. Corrected ticket contents, retained original events, frozen rules, unchanged
monitoring policies, actual settlement dates, custody and duplicate submissions
are checked. A replaced preparation draft can be reviewed, paid and closed through
the shared UI while the cancelled original retains its number and zero postings.

The combined regression selection passes 481 tests in 599.014 seconds. All 18
origination browser page/viewport checks also pass. The first exact-source Linux
CI run identified a guided-onboarding test still expecting immediate setup save;
it now verifies that review writes nothing, retains guided navigation, and saves
only after acknowledgement with the signed review token. All 20 onboarding tests
pass locally. Its formatting-only baseline is separate in `1c383fcb`.
The same older assumption in the first-loan operator fixture is updated through
an explicit review and acknowledged confirmation; all 17 operator journey tests
pass. Its formatting-only baseline is separate in `e6f5127f`. All 12 closing
browser checks pass, including selection invalidation and both detail layouts.
All seven exact-source Linux CI jobs pass for `a14b5a7f0ca8ee753a57aac9ae5944a0c4d0e233`.
The fresh isolated boundary selection passes 366 tests in 297.244 seconds.
An earlier reused-database run lacked migration-seeded roles after prior transaction
fixtures flushed them; clean migration replay resolves that local setup failure.
The two follow-up formatting commits also pass explicit AST-equivalence checks.
Prior independent selections are overlapping evidence:
368 origination regression tests, 88 final origination checks, 106 closing checks,
18 origination and 12 closing desktop/mobile page checks. They are not added into
one unique test count.

## Production/release boundary

Read-only preflight verifies both live readers still use original-rate image
`sha256:00d351bd154c1f68d27d6c5d72302a6b2beb4352e830d8708979d7c62053de98`.
All 1,947 runtime paths match on each reader; six timers and public HTTPS pass.
Free space is 8.210 GiB at this check. Protected configuration hashes are retained
privately. The staged WhatsApp image is not the live predecessor and is excluded.

Prepare one immutable committed candidate, preserving current runtime settings,
subscription/grace configuration, media and scheduled readers. Require exact-source
CI, source/dependency integrity, restricted read-only candidate acceptance,
financial-position parity, separate static assets and compatible recovery before
the guarded switch. Use the already approved encrypted backup job before/after
promotion and preserve the predecessor for code rollback. Release acceptance must
not post a loan transaction or turn unknown collateral/history into healthy risk.

The following records the pre-switch acceptance gates, now completed.
The candidate has passed 24 restricted read-only screens across three Workspaces,
an empty migration plan, and 15 financial/release-quote comparisons covering three
saved-contract profiles within one exported PostgreSQL snapshot. Monitoring-policy
and grace evidence fingerprints also match. Separate static collection preserves
the live volume; encrypted application-only recovery verifies the exact image.
All gates bind to the final committed candidate and exact image below.
Private snapshots, logs and deployment helpers live in ignored
`.tmp/loan-workflow-release-20261017/` and the matching protected server directory.

## Verified production release

Application `a14b5a7f0ca8ee753a57aac9ae5944a0c4d0e233` is deployed as
`sha256:60868e8324cb16040e4ae7f0eabb5d6ddfd79c35bb465a03841edb2acbbeb73a` at 2026-10-17T11:11:52.914454+00:00.
The coordinated code/static switch took 62.939 seconds; no migration or
production financial correction ran. Exact 1,962-file manifests pass for web and
monitoring; four compatible scheduled readers and all six timers are verified.
Twenty-four restricted read-only screens across three Workspaces, public HTTPS,
three hashed JavaScript assets, unchanged protected configuration and error-free
startup pass. Risk remains V13, Loans 0092, portability 0031/package 4 and servicing
bundle 8. Monitoring policies, subscription/grace, media and WhatsApp activation
are preserved. The predecessor image/static volume remain available for code
rollback; the customer database is never restored by this release.

The existing encrypted R2 backup job passes before and after promotion, including
remote download and retention/recovery verification. Application-only encrypted
recovery verifies the exact candidate image with the local key; transient plaintext
is removed and the private key stays off-server. See the
[de-identified deployment proof](loan-workflow-release-20261017.deployment.json).
Source worktrees and unrelated dirty WhatsApp work remain intact. Maintained main
receives the verified source and this documentation; the dirty root checkout is
left untouched rather than rewriting its outstanding changes.
