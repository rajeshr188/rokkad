---
status: active
owner: project
updated: 2026-10-17
tags: [status, architecture]
---

# Status

## In progress: authorized origination and numbering release

The owner requested commit, push and production release of the reviewed local
origination/setup/numbering and navigation/search changes. Formatting-only
baselines remain separate from behavior. Exact-source CI, migration/recovery
rehearsal, the existing approved encrypted backup job and a coordinated reader
switch are release gates. See the
[release record](implementation/origination-numbering-release-20261017.md).
Unrelated source work and production customer agreements remain preserved.
The first full Linux Loans run completed 2,813 tests with one stale error
assertion; the parent-identity guard correctly rejects the forbidden move earlier.
The assertion is being reconciled and full CI repeated before promotion.

## Local implementation: approval numbering and remaining origination simplification

The owner approved the explained delayed-numbering design and remaining review
recommendations. Local verification covers draft scope edits, approval/payout
atomicity, concurrent numbering, printing, historical reservations, recovery and
closing. Existing issued numbers remain unchanged. The broad initial snapshot
ran 2,806 tests with failures; all 45 distinct failing cases pass together on
final-code reruns. Final print/document checks pass 38 tests plus 12 page checks,
and number-allocation/concurrency checks pass 17 tests. See the
[implementation and verification record](implementation/approval-numbering-20261017.md)
for the separate runs and coordinated migration/recovery release boundary.
The owner clarified that drafts must not print loan tickets or draft PDF previews.
Approval enables ticket printing with the permanent number; reopening disables it
until reapproval. The preview route/action has been removed locally.
See the [numbering decision](adr/2026-10-17-loan-number-at-approval.md).
No production deployment or customer-record change has occurred.

An interactive local review is running on `http://127.0.0.1:8127/` in Workspace
`local-origination-review`, with a fictional unnumbered draft and approved
`AA05001` example. It uses an isolated copy of the fictional test database,
matching migrations, the restricted runtime role, local media/cache and in-memory
email. The banner identifies fictional data; the lending-terms and New loan
screens were opened through ordinary authentication. Review helper/PID/logs live
under ignored `.tmp/local-origination-review/`; no production data was copied.

Current delivery and open work only. The full prior chronology, including old
release gates, test counts, migration/import approvals and source/customer-specific
limits, is preserved in the [17 October context snapshot](archive/context/2026-10-17/INDEX.md).
See [memory](AGENT_MEMORY.md) for durable rules and [completed work](plans/completed.md)
for delivery history.

## Local implementation: business lending terms and entry preference separation

The owner requested comparison of automatic numbering with agreement/policy setup.
The [complexity review](implementation/origination-complexity-review-20261017.md)
finds implicit policy composition and operational entry preference coupled to
financial revisions to be the primary simplification opportunities. Permanent
number allocation before final review is a separate draft-recovery tradeoff;
automatic counters and historical range reservations remain necessary. Product
versions, frozen agreements and current monitoring have distinct responsibilities.
The owner approved the order. Local implementation presents the effective
business lending terms and scoped narrow rate/tenure/upfront-interest actions,
with an independent RLS-owned entry preference rather than financial revisions.
It adds Loans 0093 and setup/package profile 5 (`data_portability` 0032), preserving
old profiles and exact native recovery. See the
[implementation](implementation/business-lending-terms-20261017.md).
Validation passes: 173 combined tests, including concurrent/restricted-role checks,
native recovery, setup/package round trips, onboarding and 30 desktop/mobile page
checks. A separate 31-test run verifies repayment compatibility and the final UI.
Quality, migration-drift, documentation/archive, boundaries and hygiene checks pass.
The work is local and uncommitted; no production deployment or setup change has occurred.

The owner confirms official numbers are used only after payout confirmation.
The [numbering proposal](implementation/loan-numbering-stage-proposal-20261017.md)
was subsequently approved. Its local implementation and verification are tracked
in the [approval numbering checkpoint](implementation/approval-numbering-20261017.md)
and the in-progress section above; production still uses the released boundary.

## Local implementation: release navigation and searchable selectors

The owner reported Releases, Completed closures and Release batches in production.
The [navigation review](implementation/closing-navigation-review-20261017.md)
confirms all three on the deployed image across three Workspaces. Completed
closures opens a help guide; Release batches is batch-only despite its general
Closure history heading, so standalone current releases are absent from that view.
The local correction uses one Releases destination with the shared closing action,
All releases, secondary Grouped submissions and contextual Help with closing.
Standalone releases remain in the complete per-loan history; grouped history does
not pretend to include them. Legacy routes, records and receipts remain available.

Closing has a searchable multi-loan selector for active loans with outstanding
collateral, matching loan number, borrower name, Party code or primary phone.
Party relationship add/edit now uses the existing stateless Party search pattern,
with a source/Workspace-bound token, edit permission, pagination and selected-only
rendering. Relationship status eligibility, self/duplicate validation and loan
servicing rules are preserved. An open-dropdown width overflow found by browser
interaction checks is fixed in the shared Select2 CSS rule.

Validation passes: 121 Party/relationship/isolation/closing/release-batch regression
tests in 143 seconds, including two browser tests covering 38 desktop/mobile page
checks. Typed loan/Party search, multi-selection/removal, mode-change review
invalidation, relationship editing, active navigation and open-dropdown overflow
checks pass. Ruff, changed-file Black, documentation/archive checks, app boundaries,
repository hygiene and diff whitespace pass. See the linked review for artifacts.
The changes remain local and uncommitted; no production deployment, schema or
customer-data change is part of this checkpoint. Independent worktrees and root
WhatsApp edits remain untouched.

## Production baseline: origination and closing

The combined loan workflow is deployed from `a14b5a7f0ca8ee753a57aac9ae5944a0c4d0e233`, image
`sha256:60868e8324cb16040e4ae7f0eabb5d6ddfd79c35bb465a03841edb2acbbeb73a`. All seven exact-source CI jobs pass;
481 combined local regression tests, 366 fresh boundary tests and 30 browser
page/viewport checks pass. The release adds reviewed origination/setup changes,
safe unposted wrong-register/product recovery and one explicit one/many closing
flow, including the prominent active-loan Close / release action.

No schema, saved agreement, monitoring-policy, subscription/grace or messaging
activation change is part of deployment. Risk V13, Loans 0092, portability
0031/package 4 and servicing bundle 8 remain compatible. Both readers match all
1,962 runtime files; four scheduled readers, six timers, three-Workspace read-only
screen acceptance, 15 shared-snapshot financial/policy/grace comparisons, separate
static assets, exact encrypted application recovery and encrypted pre/post R2
backup download/retention checks pass. See the
[release record](implementation/loan-workflow-release-20261017.md) and
[de-identified proof](implementation/loan-workflow-release-20261017.deployment.json).

Maintained remote main includes the verified source. Independent source worktrees
and unrelated root WhatsApp changes remain preserved. The dirty root checkout is
not reset or overwritten. JSK WH02306 remains unchanged.

The following two sections retain the independent source-worktree checkpoints;
the combined release status above is authoritative for integration.

## Independent origination checkpoint (before integration)

The owner approved the [review](implementation/loan-origination-friction-review-20261017.md)
and its recommended order. The isolated `work/origination-simplification-20261017`
implements shared rule/provenance review and changed-term explanation, reviewed
configuration/rate amendments, contextual correction guidance and unposted mistaken
register/product replacement. The owner confirms all paper agreements use full
monthly interest; existing monthly correction parity is retained and other direct
rules' capability limits are disclosed. See the
[implementation/capability matrix](implementation/origination-simplification-20261017.md)
and [plan](plans/origination-simplification-20261017.md).
Local verification passes: 368 regression tests, 88 final focused tests including
concurrent confirmation/restricted-role DML/recovery, and 18 offline desktop/mobile
page checks. Ruff, changed-file Black/AST formatting review and documentation/
archive/boundary/hygiene checks pass. This is uncommitted local implementation;
integration and release remain pending. Closing and WhatsApp work remain separate.
No production setup, customer correction, deployment or outbound action is performed.

## Independent closing checkpoint (before integration)

Local implementation in isolated `work/unified-closing-20261017` adds a prominent
active-loan Close / release action and one shared one/many-loan selection with an
explicit current/completed mode. Completed recording requires the actual date;
ordinary date-aware settlement supports saved started-week agreements without
converting their terms to monthly rules. Existing posting, custody, concessions,
atomic batches and legacy issued forms are retained.
See the [decision](adr/2026-10-17-explicit-closing-mode-and-shared-contract-checks.md).
No production transactions or deployment are part of this local implementation;
the owner explicitly requested leaving WH02306 unchanged.

Changed-file quality gates require Black formatting of the touched Python files.
For Python review, `.tmp/closing-behavior.patch` compares the change against the formatted
baseline; `.tmp/closing-formatting-only.patch` isolates baseline formatting, whose
AST equivalence was checked. Keep these changes separate when committing.

Validation passes in the isolated local `.test` database: 105 closing, completed
batch, servicing eligibility, concessions and opening-release regression tests,
plus the connected mixed completed-batch servicing-bundle round trip. This includes
50 real fictional loans completed atomically. Offline Chromium checks pass for
six screens at 1440px and 390px, including both detail layouts, Select2 setup,
selection/mode invalidation and no page overflow or JavaScript exceptions.
Ruff, Black on nine changed Python files, app boundaries, repository hygiene,
diff whitespace, 2,665 documentation links across 767 files and all 22 preserved
document originals pass. The work remains uncommitted and has not been deployed.

## Previous baseline: original-rate correction

The previous original-rate correction release was verified as application
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
