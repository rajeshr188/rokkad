---
status: accepted-direction
owner: loans
updated: 2026-10-16
tags: [architecture, loans, origination, monitoring, risk, review]
related: [post-origination-loan-monitoring.md, loan-origination-monitoring-review-20261016.md, monitoring-worker-lifecycle-and-scaling.md, ../plans/loan-boundary-simplification-20261016.md]
---

# Loans architecture: remaining gaps after consolidation

The owner subsequently accepts the recommendations and authorizes implementation
in the recommended order. Delivery is tracked in the
[hardening plan](../plans/loans-architecture-hardening-20261016.md). The review and
verification below retain the original analysis baseline.

The subsequent [implementation and isolated acceptance record](../implementation/loans-architecture-hardening-20261016.md)
tracks delivered local changes and remaining evidence gates. This report's gap
descriptions are the original baseline, not a claim that the prepared fixes are
already deployed.

## Scope and conclusion

The owner requested a fresh analysis of origination, monitoring policy, setup and
risk workflows. This report proposes work; it authorizes no implementation,
production amendment, data transfer, deployment or capacity programme.

Keep the current PawnLoan architecture. The main remaining drift is that some
admission/setup interfaces still describe compatibility evidence as current
monitoring configuration, while policy administration and operational follow-up
have not caught up with the stronger calculation boundaries. Another loan model,
generic workflow engine, ledger or monitoring service would add complexity.

The review uses current source, accepted decisions, tests and recorded release
evidence. The union of the combined release and latest default overlay contains
104 files; all current normalized file hashes match those manifests. The recorded
latest deployment is image `53f6dd38d64b`, over combined source `21391df87683`, with
default/UI overlay `b5ff247195f3` and Loans migration 0088. This is a local manifest
comparison, not a new inspection of the running server. See the
[combined release](../implementation/loan-boundary-release-20261016.md) and
[default amendment release](../implementation/calculated-monitoring-default-20261016.md).

The earlier review's LS-01 through LS-06 are delivered foundations, not remaining
recommendations. Its local-only delivery paragraphs are historical checkpoints;
the later release records above establish deployment. No production database was
queried for this follow-up. Recorded portfolio counts and quote ages can change.

## Preserve these boundaries

| Responsibility | Current authority | Rule to preserve |
|---|---|---|
| New advance | Approval/disbursal commands and frozen decision evidence | Validate permission, licence, applicable economics and lending evidence when making the decision. |
| Completed payout | Reviewed recorded admission | Record actual facts; retain genuine earlier approvals without inventing retrospective approval. |
| Opening/closed position | Versioned admission evidence and accepted checkpoint | Earlier unavailable history stays unavailable. |
| Agreement and servicing | Shared contract/continuation readers and canonical financial/custody commands | Entry source does not select different borrower arithmetic for equal supported contracts. |
| Correction | Shared fact/agreement review with supported compensation adapters | Preserve original events/documents and reconcile dependent money or custody. |
| Current monitoring | Effective monitoring policy, supported financial inputs and current eligible collateral evidence | Original approval is evidence, not today's monitoring instruction. |
| Recording confidence | Immutable transaction reviews and explicit future-capture choice | A correct calculation does not certify missing paper activity. |
| Operational response | Current projection, immutable transitions and authorized staff actions | Monitoring does not post money or independently send borrower messages. |

Shared [financial inputs](../../apps/tenant_apps/loans/selectors/financial_inputs.py),
[monitoring inputs](../../apps/tenant_apps/loans/selectors/monitoring_inputs.py),
[evidence disclosure](../../apps/tenant_apps/loans/selectors/evidence_quality.py) and
[aggregate eligibility](../../apps/tenant_apps/loans/selectors/assessment_evidence.py)
already implement much of this separation. Intraday evidence eligibility and
scheduled evidence deadlines are also implemented. Do not rebuild these features.

The AA example is supported: reserve the historical range through AA05000, issue
AA05001 onward, and admit missing older numbers without rewinding the live
counter. The existing
[integration case](../../apps/tenant_apps/loans/tests/test_origination_consolidation.py),
`test_actual_direct_and_interleaved_paper_backlog_share_AA_register`, covers direct
issuance interleaved with older paper admissions. Range reservation prevents
reuse; it does not certify that every old loan or receipt has been entered.

## R1: Paper admission still misidentifies its monitoring settings

**Priority: P1. Confirmed semantic and workflow gap; no observed monetary defect.**

[paper_entry_terms](../../apps/tenant_apps/loans/services/paper_entry_terms.py)
resolves today's **economic lending policy** to populate `monitoring_method`,
`monitoring_ltv` and a reason reading "Standing current monitoring policy".
Actual current monitoring instead resolves `LoanMonitoringPolicy` through
`resolve_monitoring_valuation_inputs`. These are different authorities.

A database-free characterization with synthetic objects gives paper defaults
`LATEST_APPRAISAL` while actual current monitoring selects
`CALCULATED_METAL_VALUE`. This is a valid configuration after the recent default
change. The discrepancy proves misleading semantics, not incorrect live risk
calculation. Also, a missing economic default can require staff to supply
monitoring-labelled fields while recording an otherwise supported completed fact.

The fields are not disposable: [recorded admission](../../apps/tenant_apps/loans/services/recorded_history.py)
requires them and freezes them in a `RECORDED_CONTRACT` policy snapshot. Existing
readers use that snapshot for saved-method compatibility and a saved reference
LTV. [Routine presentation](../../apps/tenant_apps/loans/web/routine_entry.py)
usually hides supplied values, so staff can be unaware of this distinction.

**Smallest useful correction:** show the effective current monitoring policy as
read-only context in paper/completed-payout entry. Rename retained per-loan values
as saved compatibility/reference evidence. Do not describe a saved reference LTV
as the current breach threshold or proof of historical approval. Remove duplicate
staff configuration where the existing policy already answers the current
question. First preserve old signed requests and portable profiles; a later
versioned admission shape can represent unavailable reference facts explicitly
rather than force an invented lending limit. Do not silently copy current risk
thresholds into historical agreement evidence.

**Acceptance:** economic and monitoring methods may deliberately differ; the form
explains both and the risk result follows the monitoring policy. Completed-fact
recording never acquires a fresh quote or retrospective approval requirement.

## R2: Monitoring policy lifecycle stops at append-only amendment

**Priority: P1 for policy administration. Confirmed supported-workflow gaps.**

The service only accepts the latest predecessor, and model/database guards require
an amendment's effective date to be on or after that predecessor's start.
Consequently, after v2 is scheduled for 1 November, an urgent v3 effective
16 October cannot supersede it. v1 already has a successor; a new unlinked policy
overlaps. A synthetic model validation confirms rejection of the earlier date.
There is no supported cancel/reschedule route to bridge this situation.

An open-ended licence override also cannot be retired back to Workspace
inheritance through the existing service: policies are immutable, amendments keep
the same scope and must remain open-ended, and resolution always prefers an
applicable licence policy. Copying the Workspace values into another licence
version duplicates configuration and will not inherit subsequent Workspace edits.
These are architectural limitations, not evidence that current production scopes
are affected. The last recorded policy inspection found no licence overrides.

Evidence: [policy service](../../apps/tenant_apps/loans/services/monitoring_policies.py),
[model](../../apps/tenant_apps/loans/models/monitoring.py),
[database amendment guard](../../apps/tenant_apps/loans/migrations/0007_monitoring_policy_amendments.py),
and [resolution](../../apps/tenant_apps/loans/selectors/monitoring_policy.py).

**Smallest useful correction:** define one supported lifecycle for effective
policy changes, including cancellation/replacement of a scheduled revision and
dated retirement of an override. Keep recorded evidence immutable and make
resolution deterministic. This needs a focused ADR and compatible database,
portable-profile and invalidation changes, not a bypass of overlap validation.
Retirement must expose a missing Workspace policy explicitly if none applies.

**Acceptance:** schedule, replace/cancel, urgent current amendment and return to
Workspace policy all have reviewed commands, actor/reason evidence, exact dated
resolution, concurrent-writer tests and recovery/restore coverage.

## R3: Policy setup lacks an impact review and end-to-end readiness view

**Priority: P1. Confirmed administration gap; evidence checks themselves work.**

[Economic setup](../../apps/tenant_apps/loans/web/economic_setup.py) posts a valid
monitoring form directly into policy creation. It has no affected-loan preview,
before/after scope summary or projected evidence blockers. A technically valid
lower-of policy can make many loans' coverage unknown when appraisals are absent.

The [setup selector](../../apps/tenant_apps/loans/selectors/setup.py) and
[monitoring readiness component](../../templates/components/setup/monitoring_readiness.html)
correctly distinguish lending from monitoring. However, the monitoring indicator
counts policy availability for currently issuable series; it does not establish
active-portfolio coverage, fresh required evidence, worker assignment or completed
assessments. An expired/legacy register with active loans is particularly different
from a register eligible for new advances. This is a missing operational view,
not a reason to make receipt entry depend on monitoring readiness.

The last release recorded Lakshmi's gold/silver quotes dated 2 October exceeding
the seven-day monitoring limit. That dated observation illustrates the gap:
selecting calculated value cannot supply the missing current prices. This review
has not rechecked those quotes.

**Smallest useful correction:** extend the existing setup/health screens with
effective policy by actual active-loan scope, required metals/appraisals, missing
or stale evidence counts, assigned worker/last progress and outstanding refreshes.
Before an amendment, show changed fields, Workspace/override exclusions, affected
count and estimated loss of usable coverage. Use existing source-bound review
patterns; exact classifications require calculation and may be bounded/deferred.
Recheck the policy and relevant evidence identity at commit. An advisory preview
must never promise complete portfolio simulation or silently create evidence.

**Acceptance:** staff can explain why a configured Workspace is not yet monitored
and what a proposed change affects. An approved missing-evidence policy remains
possible with an explicit explanation; financial servicing retains its own rules.

## R4: Wider origination support needs explicit capabilities, not more entry types

**Priority: P2. Known scope limitation and maintainability risk.**

The shared [servicing contract](../../apps/tenant_apps/loans/selectors/servicing_contract.py)
already exposes monthly-servicing capability. But
[completed payout admission](../../apps/tenant_apps/loans/services/completed_payouts.py)
supports a bounded simple/full-month agreement and limited deducted fees;
[financial correction](../../apps/tenant_apps/loans/services/agreement_corrections.py)
has additional native/recorded/checkpoint and connected-history guards. Product
availability by itself does not promise equivalent completed-recording or
correction support. Native linked renewals, funding/auction dependencies and some
opening histories still need connected reconciliation.

These restrictions protect real evidence and are not bugs to delete. The gap is
discovering the limitation late, and repeating profile checks as more workflows
are added. Source-specific replay remains necessary where evidence differs.

**Smallest useful correction:** document and test a compact matrix of agreement
semantics, financial history boundary, intended action and dependency state. Reuse
existing contract/dependency selectors to disclose supported actions and specific
blockers early. Keep command authorization, locks and final validation. Add a
missing adapter only for an actual selected business profile, starting with the
highest-frequency held case. Do not build a configurable capability framework or
force every legacy profile through one generic posting function.

**Acceptance:** equal supported direct/paper/opening cases agree on debt and risk;
legitimate differences in earlier history and capture confidence are disclosed.
Draft editing, approved return/reapproval, fact correction, financial restatement
and physical collateral changes remain distinct consequences behind familiar
agreement/history navigation.

## R5: Reuse batch review for a controlled migration capture transition

**Priority: P2. Confirmed workflow limitation.**

An existing [batch review service](../../apps/tenant_apps/loans/services/batch_transaction_reviews.py)
supports one to fifty explicitly selected loans, signed per-loan reviews and atomic
confirmation. Its [web form](../../apps/tenant_apps/loans/web/paper_backlog.py)
deliberately removes `future_capture`. The individual review supports a complete
through-today check followed by a future Rokkad-only choice. Thus "bulk is not
implemented" in recent notes means the proposed migration-scale capture transition;
ordinary small-batch paper/mixed confirmation already exists.

**Smallest useful correction:** extend that reviewed boundary when selected,
using explicit Workspace/licence/series/source-cohort identity rather than only
pasted numbers. Preview each accepted checkpoint, source binding and exception;
record a separate immutable review/capture choice per eligible loan. Preserve
bounded processing, successful retry semantics and source-change rejection. A
cohort attestation needs real source/cutover evidence, not automatic confirmation
because the balances calculate or monitoring has refreshed.

**Acceptance:** a supported migration cohort can move to future Rokkad-only capture
without thousands of individual clicks or invented pre-checkpoint receipts;
changed, unsupported and ambiguous loans remain explicit exceptions.

## R6: Turn monitoring findings into clearer operational work

**Priority: P2. Confirmed rule/interface differences; business semantics need a decision.**

The current evidence selector already distinguishes measured risk, missing
evidence and freshness. Preserve it. The remaining
[Loan health endpoint](../../apps/tenant_apps/loans/web/operations.py) exposes only
status/severity filters and takes the newest 100 open alerts without alert
pagination or a complete alert count. With more than 100 newer alerts, an older
unresolved critical case can fall outside that list. Current portfolio size alone
does not prove that this has happened.

`VALUATION_UNKNOWN` is HIGH advisory priority, but
[alert projection](../../apps/tenant_apps/loans/services/risk_alerts.py) does not
create a distinct evidence work item for it. A successful CURRENT assessment with
unknown coverage is not an assessment failure. Repeated refresh cannot repair
missing prices, appraisal or physical facts.

There is also a policy distinction to resolve: the
[classifier](../../apps/tenant_apps/loans/domain/risk.py) uses configurable DPD
watch/substandard thresholds, while
[transition buckets](../../apps/tenant_apps/loans/domain/risk_transitions.py) use
fixed 1/30/60/90 boundaries and alert eligibility treats any positive DPD as
delinquency. A synthetic watch threshold of seven days with DPD one yields LOW /
STANDARD classification but qualifies for a delinquency alert. The default
one-day watch masks this difference. Earlier overdue work may be intentional;
the settings must state whether they govern classification, collection attention
or both. Do not silently suppress legitimate overdue work to align labels.

**Smallest useful correction:** paginate/count existing alerts; offer actionable
views for measured breaches, evidence repair, transaction checks and overdue
refreshes using existing flags/provenance. Link to the actual repair action.
Clarify classification versus alert trigger semantics and test non-default DPD
thresholds, including changes while an alert is open. A new stored incident type
is unnecessary merely to filter existing evidence problems.

**Acceptance:** no unresolved alert is hidden by a fixed display cap; staff can
separate missing evidence from actual breach and understand policy effects.
Unknown/failed evidence must continue to preserve an earlier known breach until
current evidence demonstrates clearance. Borrower messages retain separate
review, authorization and dispatch-currentness checks.

## R7: Worker correctness is stronger than its capacity and onboarding guarantees

**Priority: P1 before material growth; current saturation is not established.**

The [worker](../../apps/tenant_apps/loans/services/risk_jobs.py) has fair bounded
Workspace turns, per-loan commits, competing-worker claims and final source/time
checks. [Currentness](../../apps/tenant_apps/loans/selectors/risk_portfolio.py)
expires all continuing active loans each local day.
[Pending selection](../../apps/tenant_apps/loans/services/risk_snapshots.py) finds
non-current loans rather than using an indexed per-loan due schedule. Errors have
no separate retry deadline. Older `updated_at` ordering helps rotation; this review
does not claim proven starvation. Broad rate/policy invalidation remains coupled
to source transactions, including repeated stale-row updates.

The command requires explicit Workspace assignments. A newly configured customer
is not automatically included in the current production assignment list. Recorded
configuration covers JCL, JSK and Lakshmi with ten-loan turns, five-second busy and
300-second idle pauses. This is a deployment/operational integration gap to address
before onboarding more customers, not permission to enumerate or process arbitrary
tenants. Commercial/lifecycle restrictions remain authoritative.

**Smallest useful correction:** follow the already captured
[FW-004](../plans/future-work.md#fw-004-launch-scale-loan-monitoring-capacity)
order: measure oldest-due age, progress, errors, throughput and servicing latency;
add indexed dirty/due and bounded retry scheduling; safely reuse exact
source-dependent components; then size a small fair assigned worker pool. Add a
reconciliation/health check that identifies active portfolios lacking an assigned
reader or acceptable refresh progress. Preserve atomic invalidation and existing
claims until equivalent race guarantees are proven. Do not make a permanent
process per Workspace the default architecture.

**Acceptance:** measured freshness and servicing targets on representative history,
safe midnight/evidence deadlines, failed-loan retry, late source changes, policy
fan-out and restricted-RLS concurrency. No capacity benchmark or worker change was
started for this review. See the [worker reference](monitoring-worker-lifecycle-and-scaling.md)
for existing measurements and the shelved larger programme.

## Recommended delivery order and gates

1. **Correct the remaining meanings:** R1 admission labels/default authority and
   R6 classification/alert contract characterization. Preserve saved financial
   evidence, old requests and published exchange meanings.
2. **Complete policy administration:** R2 lifecycle decision, followed by R3
   source-bound impact review and active-portfolio readiness. These belong to one
   coherent policy workflow, not another settings screen.
3. **Simplify staff work:** R5 controlled capture transition and R6 paginated,
   actionable views; R4 early capability/blocker disclosure. Extend existing
   reviews and selectors rather than add parallel workflows.
4. **Harden growth:** R7 measurement and assignment visibility first; implement
   scheduling/reuse/pool changes only with the FW-004 correctness and capacity
   gates. This is not authorization to resume the shelved load programme.
5. **Broaden agreements only from demand:** choose one genuinely needed unsupported
   origination/correction profile, prove cross-origin financial/risk parity and
   portable recovery, then repeat. Do not announce universal profile support.

Across all slices, assert unchanged original events, approved snapshots and issued
document bytes; supported before/after monetary parity; precise missing-evidence
states; date/race handling; retry safety; tenant isolation; compatible web/worker/
scheduled readers; and export/restore fidelity. Use immutable compensation only
when staff actually correct financial facts. Readiness or monitoring refactors
must not become financial corrections.

## Verification and release traceability

This review compared 104 manifest hashes, ran three database-free synthetic
characterizations (R1 method mismatch, R2 earlier-date amendment rejection, R6
non-default DPD semantics), and ran the existing alert/transition unit modules:
**11 tests passed**. These checks use source/in-memory inputs and are not evidence
of a new live incident or a full financial, database or concurrency regression run.
Local documentation links and whitespace are also checked.

The checkout already has substantial deployed but uncommitted work. Before a
future implementation/release, reconcile the accepted source manifests with a
reviewed Git commit and release identity. Preserve other sessions' changes.
Several earlier documents retain pre-deployment checkpoints; always link the
latest release status prominently instead of treating an old "production
unchanged" paragraph as today's state. No runtime source, production policy,
financial record, rate, review, notification or worker configuration changes as
part of this analysis.
