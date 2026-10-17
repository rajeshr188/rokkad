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

The counter/monitoring release is verified in production as application
`1889e48820eeb042f35bfb523276b29e264340cd`, image
`sha256:450699d7a6084949ca754990260220db8b6963e7eeb3204e9ae1d9213e269967`.
Release evidence is committed at `ebf2dd6e`; integration is
`work/loan-servicing-contract-ld01`. Runtime V13, Loans 0091 and
`data_portability` 0030/package 4 are the verified compatible boundary.

All six CI groups passed, including 2,695 Loans tests. Isolated production-copy
rehearsal, exact encrypted application recovery, 14 sampled balances and 1,539
runtime-file parity passed. Compatible web/worker/scheduled readers moved together;
six timers, restricted runtime, twelve read-only screens across three Workspaces,
encrypted pre/post backups and actual R2 recovery/retention checks verified.
Disposable server copies and plaintext dumps were removed; recovery points retained.
See the [release record](implementation/counter-release-20261016.md) and
[deployment proof](implementation/counter-release-20261016.deployment.json).
The failed `a68dbcb0` candidate was never deployed; older V11/local-only claims in
historical notes are superseded by this release.

## Current work: Python dependency and tooling audit

The owner also raised the need for a consistent agent/development process.
The [proposed workflow](implementation/development-workflow.md) now covers scoped
task branches/worktrees, change-specific checks, PR/CI integration, immutable
release candidates, hotfix reconciliation and separate data-repair authority.
It is a reviewable draft; no default-branch, GitHub protection, merge policy or
production-authorization changes have been applied. The owner confirmed the source
session is finished and authorized independent review/integration. The frozen
24-file snapshot passes pin/tool/document checks, seven guard tests and all 18
shell/credential tests; exact-revision Linux CI/release remain separate gates.

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
pin, Ruff and changed-file Black checks. Full Linux CI/image/release acceptance
remains separate. No production deployment is part of this audit.

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
routine retention and a reviewed canonical-main transition remain separate work.

## Open business and acceptance work

- **JSK WH original terms:** owner confirms paper agreements at 1.1% monthly,
  first-month interest paid upfront, inherited 2% migration error and no later
  transactions on the intended 685 imported active loans. Use this confirmed basis;
  request further records only for specific missing or contradictory payment facts.
  The explicitly approved fresh read-only check matches the exact 685 nonzero-
  interest imports and unchanged source hashes. All retain a sole opening,
  entirely unpaid additional interest, first-month-paid coverage and no connected
  custody/funding/renewal/auction activity. All 685 pure recalculations succeed.
  The owner supersedes the initial 685-only scope and requests correcting all
  active WH loans carrying wrong 2%: 824 imports and two unserviced native policy-1
  records, 826 total. All 824 import recalculations pass. For WH02145/WH02146 the
  owner confirms the original 1.1% advance/proceeds basis, retaining saved fees.
  [Aggregate checkpoint support](implementation/aggregate-checkpoint-corrections-20261017.md)
  extends the existing signed correction/form for aggregate and unserviced legacy
  native evidence, and adds guarded Loans 0092,
  portability 0031 and servicing bundle 8. The final 49-case correction selection
  passes, including native/aggregate exact and portable recovery. Earlier
  overlapping 100 servicing and 213 portability selections also pass. The owner
  requests actual all-active correction; exact-source release/rehearsal precedes apply.
  Private proposal flags do not restrict live loans or collections. No financial
  correction or deployment is applied. See the updated
  [correction plan](plans/jsk-wh-original-rate-correction-20261017.md).
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
