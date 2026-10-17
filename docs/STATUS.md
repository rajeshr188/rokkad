---
status: active
owner: project
updated: 2026-10-17
tags: [status, architecture]
---

# Status

Current delivery and open work only. The full prior chronology, including old
release gates, test counts, migration/import approvals and source/customer-specific
limits, is preserved in the [17 October context snapshot](archive/context/2026-10-17/INDEX.md).
See [memory](AGENT_MEMORY.md) for durable rules and [completed work](plans/completed.md)
for delivery history.

## Production baseline

The original-rate correction release is verified in production as application
`b0d572940dd2ed3f33f8e860d6a1a3ba6202e1b2`, image
`sha256:00d351bd154c1f68d27d6c5d72302a6b2beb4352e830d8708979d7c62053de98`.
Runtime V13, Loans 0092, `data_portability` 0031/package 4 and servicing bundle 8
are the compatible boundary. The image includes reviewed dependency/tooling
updates, including Django 6.1.2. All seven exact-source CI jobs pass, including
2,717 Loans tests. See the [release record](implementation/jsk-wh-original-rate-release-20261017.md)
and [de-identified proof](implementation/jsk-wh-original-rate-release-20261017.deployment.json).

The owner-authorized correction covers all 826 active JSK WH loans carrying wrong
2%: 824 imports and two unserviced native agreements. All are corrected to original
1.1%, retaining confirmed first-month-upfront coverage and saved document charges.
The live query confirms no active WH agreement/item remains at 2%; all 826 risk
assessments are current without changing monitoring policy. Principal, borrowers,
numbers and collateral facts stay intact; original source/evidence is preserved.
The app reopens after a 495.49-second coordinated write pause. No new cash or
messages are recorded. Broader payment-history claims are not inferred.

The isolated 222-table/1,160,810-row copy passes full correction, unchanged retry,
72 preservation groups and bounded risk catch-up. Exact encrypted application
recovery, 14 pre-correction balance samples, 1,947 runtime files per web/worker,
four compatible scheduled readers, six timers, restricted runtime, twelve counter
screens across three Workspaces, and encrypted pre/post backup recovery/retention
checks pass. Prior counter-release evidence remains preserved in its
[record](implementation/counter-release-20261016.md). Failed `a68dbcb0` was never deployed.
The disposable server copy and two plaintext dumps are removed after verified
recovery; encrypted recovery points and release evidence remain retained.

Canonical integration/default is `main`, advanced by the owner's reviewed
[fast-forward transition](implementation/canonical-main-20261017.md).
The old integration ref remains at the verified application checkpoint; other
branches, dirty worktrees, upstream settings and protection are preserved.

## Completed: Python dependency and tooling review

The owner also raised the need for a consistent agent/development process.
The [proposed workflow](implementation/development-workflow.md) now covers scoped
task branches/worktrees, change-specific checks, PR/CI integration, immutable
release candidates, hotfix reconciliation and separate data-repair authority.
It remains a reviewable draft; no GitHub protection, merge policy or future
production/data authority is activated. Main alignment is separately authorized.
The owner confirmed the source
session is finished and authorized independent review/integration. The frozen
24-file snapshot passes pin/tool/document checks, seven guard tests and all 18
shell/credential tests. Exact-revision Linux CI and the authorized release now pass.

The [17 October audit](implementation/python-dependency-audit-20261017.md) inventories
84 installed packages and separates 41 direct runtime requirements from 65 resolved
runtime distributions. Requirements/lock now include Django 6.1.2, cryptography
50.0.2, PyJWT 2.15.1 and refreshed certificate/timezone data. Twelve unused/retired
local packages are removed from `.venv314`; dynamic app/backend/export dependencies are retained.
Pinned uv/Black/Ruff/pip-audit tooling has a separate development lock and a CI
quality job. Ruff found an active Notify credential lookup using an undefined
legacy connection; it now uses canonical Workspace context, with fail-closed tests.
Clean-install, pin/version, Django system and runtime advisory checks passed
(65 packages, no known advisories). The focused run passed 353 of 355 tests; two
pre-existing session-less rendering fixtures also failed on Django 6.1.1, were
corrected, and all 18 shell/credential rerun tests passed. Seven boundary/hygiene
tests passed. The 96-package local runtime/dev/browser environment passes pip,
pin, Ruff and changed-file Black checks. The later authorized release includes
this reviewed work, with full Linux CI, image integrity and production acceptance.

## Repository hygiene (FW-024)

The owner authorized execution on 17 October, emphasizing document preservation.
[Execution record](implementation/repository-hygiene-20261017.md) records snapshots,
reference moves, reproducible fixtures/static collection, documentation compaction,
local retention and CI alignment. Core cleanup is committed/pushed as `d4a5d5ed`.
The owner then selected [individual retention and pruning](implementation/repository-retention-20261017.md):
verified Git recovery, eight merged local branches, two clean worktrees and
recoverable duplicate build copies. Dirty/unmerged work and customer/recovery
evidence stay preserved. No loan behavior, schema or production deployment changes
are part of cleanup. Exact revision `693031a7` passes all six CI groups, including
2,695 Loans tests. FW-024 is [completed](plans/completed.md#fw-024-repository-hygiene-and-reviewed-retention-2026-10-17);
routine retention remains separate work. The reviewed canonical-main transition
is now complete without branch pruning or history rewriting.

## Open business and acceptance work

- **Monitoring capacity:** normal bounded catch-up is deployed. Scheduling and
  scale optimization remain measurement-gated [FW-004](plans/future-work.md#fw-004-launch-scale-loan-monitoring-capacity).
  No one-hour launch-scale claim; large local runs remain paused by the owner.
  Current assessments do not certify missing prices, appraisals, books or custody.
- **WhatsApp:** PW-01 through PW-05 implementation/evidence is retained; live
  sender/provider acceptance remains separate. Production sending stays disabled
  at the last verified release. See [PW-05 gates](implementation/platform-whatsapp-pilot-pw05.md).
- **Billing:** existing purchased terms and grace are preserved. Live checkout and
  recurring-provider acceptance remain governed by their
  [rollout gates](plans/subscription-monetization-rollout.md), not local test success.
- **Source/physical acceptance:** broader portability, real-book/history completeness,
  print/hardware, source-specific unsupported corrections and live pilots retain
  the limits in their implementation records. Deployed code is not blanket
  acceptance of every source graph. See [future work](plans/future-work.md).
