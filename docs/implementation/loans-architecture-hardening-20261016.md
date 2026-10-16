---
status: locally-verified
owner: loans
updated: 2026-10-16
tags: [loans, architecture, monitoring, verification]
related: [../plans/loans-architecture-hardening-20261016.md, represented-position-coverage-20261016.md]
---

# Loans architecture hardening: implementation and acceptance

The owner accepts the [architecture follow-up](../architecture/loans-architecture-followup-20261016.md)
and its recommended order. The implementation keeps one loan, immutable original
agreements/events and the existing canonical financial, correction and monitoring
services. This record describes a local candidate, not a production release.

## Delivered scope

- **LA-01:** paper/completed-payout entry distinguishes saved valuation/reference
  evidence from the effective current monitoring policy. Retained admission shapes
  and unknown original approval evidence are not silently reinterpreted. Existing
  overdue collection triggers and configured risk classification are characterized
  and explained separately.
- **LA-02:** immutable APPLY/RETIRE versions support licence-override fallback,
  explicit replacement of a future schedule and cancellation back to today's
  applicable settings. Resolution uses the highest applicable version. Workspace
  locking, predecessor/date/scope guards and immutable rows remain authoritative.
  Setup/package profile 4 preserves lifecycle meaning; older profiles reject
  unrepresentable evidence instead of losing it.
- **LA-03:** setup previews bind actor, scope, proposed settings, lineage, source
  identities, business day and evidence deadlines. Explicit confirmation rechecks
  them. Read-only impact includes affected scopes, exclusions, changed values,
  displaced/preceding schedules and at most 25 collateral observations under
  today's evidence. It does not simulate debt or future risk. Setup, onboarding and
  Loan health expose active-portfolio readiness, including stopped/legacy scopes.
- **LA-04:** existing completed-payout/correction prerequisites disclose unsupported
  paths early. Existing signed batch review adds future-capture choice and explicit
  imported-cohort selection of at most 50 active loans, exceptions, cursor and
  deliberate confirmation. Commands recheck individual sources and retries avoid
  duplicate reviews. These are optional book assurances under the concurrently
  approved represented-position treatment; supported positions do not require them.
- **LA-05:** open alerts have complete counts and 25-row pagination, prioritized
  critical then older work. Existing evidence supports measured-risk,
  valuation-repair, transaction-check and assessment work views. No additional
  persisted incident taxonomy or automatic borrower communication is introduced.
- **LA-06:** `monitoring_status --workspace-id <id>` and shared readiness expose
  configuration, assessment progress and coverage without financial writes.
  Assignment configuration is not liveness; oldest pending assessment is not an
  exact invalidation timestamp. Existing claims and transactional invalidation
  remain. Scheduling, reuse and worker-pool changes are still evidence-gated.

## Combined migrations and compatibility

The separate owner-approved [represented-position coverage change](represented-position-coverage-20261016.md)
is preserved in this candidate. Snapshot V13 supersedes this slice's initial V12.
It keeps represented financial position separate from optional book assurance.

The migration graph includes Loans `0089_monitoring_policy_lifecycle`, independent
`0090_recorded_position_notice` and `0090_transaction_review_history_boundary`,
joined by empty `0091_merge_position_and_review_boundary`; data_portability uses
`0030_monitoring_lifecycle_profile`. The review guard starts at an accepted opening
checkpoint, falling back to original loan date for native history. It permits
checking a closed zero checkpoint with unknown original date while refusing a
claim before the checkpoint. Neither 0090 branch overwrites the other's function
or edits retained evidence.

Compatible web, continuous-worker and scheduled readers must be released together.
Downgrade cannot discard retained lifecycle/package or new position-bound notice
evidence. Ordinary monetary calculations, posting authority and tenant ownership
are unchanged. Unsupported financial agreement profiles remain held; no missing
historical reference LTV, appraisal, receipt or source attestation is invented.

## Isolated acceptance source

The owner requests keeping the other session active and verifying a separate
snapshot. The frozen local candidate is
`.tmp/loans-architecture-hardening-20261016/snapshot/`, with 2,978 files. Its sorted
path/SHA-256 manifest digest is
`0e76bb669232f99b55ab2f21954fe16acb03c6a6823c94a4af5af37b25c8530b`.
No source file changed during the copy. The manifest and logs remain in the parent
task directory. The copy excludes the environment file, virtualenv, Git database,
uploads and private backups; two cached public Bootstrap assets support isolated
browser checks. Test credentials are loaded in-process from the existing local
environment without copying or logging them.

Acceptance uses primary `test_rokkad_architecture_snapshot_20261016`, separate from
the earlier hardening database and the other session's database. Historical
rehearsals create their own disposable `test_migration_rehearsal_*` databases and
remove them afterward. Runtime modules and
resources import from the frozen directory using the existing Python virtualenv.
Final documentation updates in the shared checkout are separate from that frozen
runtime acceptance identity.

## Verification

Frozen acceptance executes **238 passing cases across two selections**. The first
command reports 214 cases in 378.831 seconds: 212 executed cases pass, while two
incorrect module labels produce loader errors. Correcting the command labels to
`test_risk_transitions` and `apps.onboarding.test_business_journey` executes all
26 omitted cases successfully in 2.593 seconds. No application/source change is
needed between these runs. The initial command is not presented as a clean
214-case run; the earlier broad selection is not repeated after successful cases.
The 238 figure counts executed cases, not a claim about unique underlying scenarios.

Coverage includes lifecycle/retirement/schedule cancellation, same-date replacement,
source-bound preview/confirmation and intraday evidence expiry, early capability
disclosure, bounded cohort selection/cursor/exceptions/retry, raw checkpoint-date
guard, alert pagination, evidence and represented-position treatment, setup,
onboarding, whole-business package/4 recovery, restricted-role integrity and worker
claims/invalidation. Populated historical default and lifecycle upgrade/reversal
rehearsals pass inside the frozen selection.

Earlier overlapping selections pass 212 cases and then 52 combined cases; these
are not added to frozen acceptance. Follow-up catches and fixes an opening
checkpoint date guard and mobile wrapping of long imported identifiers.

Browser checks cover 20 desktop/phone states (1365 and 390 pixels): policy impact,
cancellation, cohort review, completed-payout facts/review, and five monitoring
evidence views. Fictional responses and cached assets intercept browser network
requests; checks reject horizontal overflow and script errors. Representative
screenshots are inspected.

System checks and `makemigrations --check --dry-run` pass. The applied graph has one
Loans leaf, `0091_merge_position_and_review_boundary`, and no pending migrations.
Read-back verifies lifecycle, position-notice and checkpoint-review guard functions
coexist. All 1,435 frozen Python files parse; import boundaries pass for 1,247
non-migration files. Current documentation links and whitespace pass. Every frozen
manifest hash remains unchanged, and final shared-source comparison finds no
runtime additions, removals or changes; final documentation updates are the only
differences. Logs, guard read-back and comparison JSON remain in the task folder.

## Bounded measurement and remaining gates

The earlier local 212-case run observes a single-item worker median of 139.593 ms
per pass, 126.786 ms claim-to-return, maximum 217.217 ms and 120 queries per sample
over five samples. A synthetic 2,500-row policy invalidation has median 3,888.757 ms
(repeated stale median 3,912.836 ms, maximum 3,985.038 ms); 100-row cases observe
176.014 ms current and 385.190 ms stale. These are local synthetic observations,
not production sizing or a representative servicing-latency guarantee. Existing
same-loan blocking and unrelated/competing-worker behavior remain characterized.

The [FW-004 gates](../plans/future-work.md#fw-004-launch-scale-loan-monitoring-capacity)
still precede indexed due/retry scheduling, source-dependent reuse and worker-pool
sizing. The shelved large capacity programme is not resumed. A genuinely required
new financial origination/correction profile needs its own concrete business case,
parity proof and portable recovery; generic profile expansion is not part of this
release.

At the local acceptance checkpoint, no production access, policy/data amendment,
posting, external message, worker configuration change, commit, push or deployment
is performed. The owner subsequently requests committing the completed changes
and retaining the remaining scheduling findings/actions in FW-004. That local Git
consolidation does not select a push, deployment or worker optimization. Staged
whitespace checks remove one extra blank line at EOF from
`test_monitoring_operations.py`; all other staged runtime content matches the
frozen acceptance source after Git line-ending normalization. That formatting-only
cleanup changes no executed statement or test behavior.
