---
status: active
owner: project
updated: 2026-10-12
tags: [dashboard, performance, loans, production]
related:
  - dashboard-reliability.md
  - ../domain/pawn-loan-financial-read-models.md
  - ../adr/2026-10-06-loan-continuation-read-boundary.md
---

# Live JCL dashboard performance investigation

The verified fix was deployed on 12 October on top of MR-07. See the
[release evidence and live measurements](dashboard-performance-release-20261012.md).
The investigation and initial candidate results below retain their 10 October scope.

## Scope and safeguards

The reported slow dashboard is the live JCL Workspace at rokkad.com, whose slug
is jcl. The local review Workspace jcl-13 contains only six active and one closed
loan and cannot reproduce the live portfolio cost.

Measurements ran in the existing production web image
rokkad:compact-closed-bs05-74c3634f, through its restricted runtime database role.
Each diagnostic used an explicit PostgreSQL READ ONLY transaction, a 12-second
statement timeout, matching workspace_context and ordinary Workspace filters.
The runtime role was verified NOSUPERUSER/NOBYPASSRLS. No production session,
profile preference, financial record, migration or deployment was created.
SQL instrumentation retained shapes and timings without parameter/customer values.

The direct view measurement used RequestFactory and the existing canonical owner.
Its navigation preference was set only on the in-memory profile so the GET did not
attempt to persist that preference. The real access helper and template still ran.
This measures server view/template work, excluding middleware, HTTP transport,
browser assets and rendering. It is not an end-to-end browser or load test.

## Measured live portfolio

JCL contained 2,619 ACTIVE and 26,713 CLOSED PawnLoans and no Khata accounts.
Current queues reported eight due-today loans, 1,963 overdue loans and zero
draft/approved/review rows.

| Measurement | Time | SQL queries |
| --- | --- | --- |
| Business overview, including current-month activity | 2.546 s | 18 |
| Counter queues | 7.643 s | 3,296 |
| Both selectors, sequential first probe | 10.189 s | 3,314 |
| Full dashboard view and template, subsequent probe | 8.864 s | 3,360 |

Times include diagnostic SQL instrumentation. The two probes were separate;
warming and ordinary host variation mean their durations must not be added.
SQL execution consumed 2.631 seconds in the selector probe and 2.101 seconds
in the subsequent view probe. The remaining elapsed time includes row transfer,
JSON decoding, ORM materialization and Python calculations; it is not a pure CPU
measurement. The rendered view returned HTTP status 200 and 36,202 bytes.
The view probe executed only SELECT, SAVEPOINT and RELEASE SQL statements.

Within the first probe, saved-health aggregation took 0.103 seconds and one query.
Obligation selection/folding took 7.332 seconds and 3,295 queries. Inside that,
57 continuation calls consumed 6.024 seconds and 3,177 queries. These are nested
measurements and must not be summed.

## Confirmed repeated-read path

workspace_dashboard invokes get_business_overview and get_workspace_counter_work
before rendering. The latter loads all draft/approved/active loans and computes
all queues; Paginator is applied afterward to display 20 selected rows.

The schedule/obligation/allocated-payment reads are batched, but
_fold_obligation_state now adjusts supported monthly contracts through
_monthly_obligation_state and resolve_loan_continuation. Native monthly continuation
calls preview_pawn_loan_accruals. That preview loops periods and calls
get_pawn_loan_balance by loan ID at each period's basis date. The balance loader
refetches the loan/policy, all events and collateral each time, even when a loan
object was already available. Each itemized period also rereads effective
disbursal, principal tranche and advance-consumption evidence.

Production query shapes show 353 repetitions each of loan/policy, loan-event and
collateral reads and 592 effective-disbursal snapshot reads inside continuation.
The repeated work for 57 loans dominates the queue measurement. This explains why
the earlier five-query synthetic queue benchmark is not a guarantee for current
monthly continuation contracts. Closed loans are not folded into active balances
or queues, although customer and activity queries can reference historical loans.

The business overview adds another material cost by folding current event
evidence for all 2,619 active loans on every load. Its queries are already batched.
Saved health is a comparatively small part of this measurement; the dashboard
does not refresh risk assessments while rendering.

## Recommended smallest implementation

First retain the common canonical continuation calculation and load a loan's
dated event, policy, collateral, disbursal/tranche and accrual/advance evidence
once per selector call. Reuse that evidence for period-specific pure calculations
rather than invoking ORM loaders inside each period. Start with the native
monthly preview path responsible for the measured repeated reads, then batch
its inputs across the dashboard's supported monthly loans where useful.
Do not build a second dashboard interest formula.

Characterization must compare complete previews, obligation states, queue
membership and amounts before/after across native, recorded and opening profiles;
earlier reporting dates, maturity forecasts, anniversary/short-month boundaries,
principal reductions, advances, item rounding, reversed charges and termination
must retain their current meanings. Query-count regressions must include modern
monthly contracts with multiple periods and loans. Restricted-role foreign
Workspace isolation remains required.

After that optimization, remeasure a representative JCL-sized mixed portfolio
and the live read-only view. Assess business-overview event/materialization cost
separately if it remains significant. Deferring separately loaded dashboard
sections can improve initial display but does not remove this repeated work.
Any saved summary or cross-request cache would require explicit date, freshness,
mutation/reversal and Workspace invalidation rules; it is not the first remedy
established by these measurements.

The initial investigation changed documentation only. The following section
records the authorized local implementation; no deployment has been performed. Diagnostic scripts and parameter-free raw measurements
are local ignored artifacts under .tmp/dashboard-performance.

## Shared fix implemented locally (10 October)

The final implementation adds selectors/accrual_evidence.py and uses its
request-local evidence bundle in obligation_state.py, continuation.py,
pawn_interest.py, pawn_tranches.py and recorded_collections.py. The schedule query
also loads its source event and loan product with the frozen policy.
Only monthly-adjusted schedules receive the additional batched evidence reads.
Empty/non-monthly portfolios retain their existing batched path.

Native previews load one source bundle even when called outside the dashboard.
A financial writer still obtains that bundle fresh inside its normal operation;
there is no global/request-spanning cache. Recorded collection reads accept the
same internal bundle on the dashboard path, keeping ordinary callers compatible.
Effective disbursal, repayment/closing lines, charge history and advance-consumption
cutoffs retain their existing distinct predicates. Reporting knowledge and forecast
horizon remain separate. Both paths reuse the original balance, tranche and
interest algorithms; canonical errors and reviewed correction requirements remain.

The first candidate fixed native monthly reads but did not improve Lakshmi's
recorded anniversary loans. A separate restricted read-only Lakshmi profile
measured 79 continuation calls, 4,589 queries and 10.246 seconds within queues.
It included 930 repeated item-allocation queries. The final candidate also batches
recorded contracts and supplies those facts to the existing cumulative calculation.

| Workspace | Active loans | Existing queue queries | Final candidate queue queries |
| --- | --- | --- | --- |
| JCL | 2,619 | 3,296 | 13 |
| JSK | 1,592 | 600 | 13 |
| Lakshmi | 2,515 | 4,594 | 13 |

The full queue comparison hashes match before/after for each Workspace, covering
every loan ID, queue, date, amount and note, with one repeatable-read snapshot per
diagnostic. Candidate modules were loaded only into a separate Python process;
no production file or web process was replaced. SQL remained READ ONLY under the
restricted runtime role. No persistent test login or navigation update was created.

JCL's native-path candidate view/template took 3.932 seconds and 77 queries.
Its same-snapshot queue probe dropped from 13.138 seconds to 1.432 seconds.
The subsequent final multi-profile probe used 73 queries for JSK's view/template
and 72 for Lakshmi's. Lakshmi queues fell from 13.796 to 2.854 seconds, with a
3.144-second candidate view. JSK's candidate view took 5.504 seconds during that
probe; its earlier native candidate took 2.998 seconds. Its queue durations varied
from 0.801 to 2.322 seconds despite the same 13-query count. These single probes
include instrumentation and host-load variation and are not latency guarantees.
Business overview still folds all active events, and row materialization/memory
still grow with portfolio size. Browser/CDN/middleware time was not measured.

70 focused monthly, admission and dashboard checks pass for the final code,
including five new tests in test_dashboard_monthly_performance.py. Tests establish
13 queue queries for one and three modern loans over short and 14-period horizons,
zero-query reuse of loaded item/balance/preview evidence, 12 batch-state queries
across direct/paper/history/opening admissions, receipt/reversal historical parity,
unchanged legacy anniversary /1-/2 results and restricted-role foreign-row exclusion.
Recorded receipts that require reviewed correction still reject generic reversal.
Additional interest/settlement, business overview, health and ordinary obligation
checks pass. Supported-app boundaries and scoped diff formatting pass.

The local server on port 8000 was refreshed with the six runtime files, retaining
the Party picker, isolated review database, existing login accounts/cookies/media
and the rest of the committed-source snapshot. Restricted local request profiling
and authenticated actual HTTP return 200; the temporary diagnostic session is
deleted. The exact inactive local disposable regression database is removed.
The local portfolio is small and is not a production-scale benchmark.

The fix is implemented locally and verified on production data through read-only
candidate processes. It has not been deployed. No migration is required.
