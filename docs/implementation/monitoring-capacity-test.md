---
status: active
owner: loans
updated: 2026-09-12
tags: [monitoring, performance, rls, acceptance]
---

# Monitoring capacity test

The owner selected completion within one hour of an applicable metal-price change
for all affected active loans. This is an acceptance target, not an established
service guarantee. Further large-scale testing is **shelved at the owner's request**
until better representative hardware is available; see
[FW-004](../plans/future-work.md#fw-004-launch-scale-loan-monitoring-capacity).
See the [prior measurements](rates-appraisal-monitoring-review.md)
and [operator explanation](../flows/loan-health-monitoring.md).

## Reproducible workload

`scripts/benchmark_monitoring_load.py` creates only
`test_rokkad_monitoring_load` through the owner-backed Django test settings. It
refuses a populated dataset unless `--reset` explicitly clears that disposable
database or `--resume` validates and reuses its benchmark fixtures. It retains the test data after completion for diagnosis. Do not use
the synthetic copies for lifecycle/audit acceptance or customer operations.

```powershell
.\.venv314\Scripts\python.exe -X utf8 scripts/benchmark_monitoring_load.py --workspaces 2 --sizes 25 --seconds 60 --workers 2
.\.venv314\Scripts\python.exe -X utf8 scripts/benchmark_monitoring_load.py --reset --workspaces 100 --sizes 3000 10000 --seconds 3600 --workers 8
```

The second command explicitly replaces only the first command's disposable data.
Fixture expansion uses up to the configured worker count in separate owner-backed
processes; a temporary advisory lock serializes sequence reservations only.
Independent Workspace inserts remain concurrent. Fixture transactions commit at
most 1,000 active loans and their related history at a time to bound deferred
foreign-key-check memory; partially completed expansion can be resumed. `--resume` can reuse a fully prepared set of seed Workspaces after an
interruption during first-size expansion, without clearing completed copies.
Only one driver may hold the load-database advisory lock. An interrupted process
may leave its temporary role behind; first verify no test processes/connections
remain before removing that role's grants in this disposable database and retrying.
No production/development worker is enabled, and no business database is reset.
On Windows, the driver requests temporary idle-sleep prevention for its own
process and restores the previous execution state on exit; display sleep and
manual sleep remain under user control. A measurement gap above 120 seconds
invalidates continuous-load acceptance and stops further matrix phases.
The test temporarily creates a NOLOGIN/NOSUPERUSER/NOBYPASSRLS role with table DML
and sequence permissions in this test database, then removes its grants and role.
Application worker and foreground processes assume that restricted role; the owner
connection performs fixture setup and aggregate measurement only. Neither RLS nor
database triggers are disabled.

Each Workspace has distinct owner/membership, borrower, products, licenses, policies,
quotes and loan evidence. Five real command-created active profiles cover bullet,
periodic-interest, flexible and EMI contracts, 7-400-day ages, 1-4 gold/silver items,
and dated repayments/reversal history. One real fully released silver loan adds
20% closed history. Each Workspace has one synthetic borrower shared by its loan profiles; borrower
distribution is not a measured production mix. SQL copies preserve the mixed benchmark's read-relevant
relational/JSON linkage; historical audit fingerprints on copies are synthetic.
Only original command-created seed loans receive concurrent financial actions.

The matrix is 100 x 3,000 active (+60,000 closed), then 100 x 10,000 active
(+200,000 closed), in the same database. ANALYZE follows expansion. Each wave
publishes a new Workspace-local gold quote and verifies saved active assessments
are no longer current. Eight processes partition explicit Workspace lists and
call the actual per-loan-commit worker service, 50 candidates per turn with a
one-second busy pause and five-second idle pause. The harness retains each process
connection; it does not launch the management command or reproduce its default
300-second idle interval/connection cleanup. The one-hour timer starts before wave publication, so invalidation
time is included conservatively.

A separate process rotates through Workspaces, reading the portfolio and executing
a real INR 1 repayment followed by its reversal, then waiting five seconds.
This measures service/selector latency, not end-to-end browser HTTP latency. The
target foreground arrival cadence is sequential rather than an independent
constant arrival rate; achieved sample counts and percentiles must be reported.

Progress is measured every 30 seconds. These aggregate observer queries consume
database resources too; their overhead is part of this harness workload, not
free instrumentation. Completion is observed, not extrapolated.
Each Workspace must be observed to have successfully assessed every affected loan
using its new quote within the deadline. Quote identity and assessment timestamp
track this wave separately from a later payment or midnight rollover making the
latest projection stale. Latest-current counts are reported separately. Observation
resolution is 30 seconds, so a completion in the final unobserved interval cannot
be claimed as a pass; post-deadline observations never satisfy the gate. Worker/process
or foreground failures stop the phase early and fail the run. The driver verifies
closed-loan exclusion, cross-Workspace read denial, new-quote provenance and sampled
financial/risk results against independent canonical selectors after workers stop.
Shutdown and verification time are included in the final wall time; observation
times determine deadline completion. No duration extrapolation counts as a pass.

## Local environment

The application baseline is the locally uncommitted monitoring-capacity changes
on `rls-mvp` after published checkpoint `21a48aee`; the indexed-query candidate
described below is not part of either full-load phase.

Windows 11, Python 3.14.3, PostgreSQL 16.1, Intel Core i5-12500H
(16 logical CPUs) and 15.6 GiB physical RAM. PostgreSQL
shared_buffers is 128 MiB, work_mem 4 MiB, max_connections 100, and
max_parallel_workers_per_gather 2. These are the existing local settings; the
test does not tune the database server. Approximately 168 GiB of disk space was
available before expansion. This shared development machine is not resource-isolated or a specified production
server; unrelated development work may compete for resources. Neither a pass nor
a failure predicts other infrastructure unchanged.

## Driver verification

The final 2-Workspace/50-active smoke test completed with both Workspaces observed
current at 31.92 seconds; final verification finished at 33.624 seconds. There were
no errors, and ten refreshed-copy samples matched independent calculations. Six
portfolio reads and six repayment/reversal pairs ran concurrently. This verifies
the test driver, not launch capacity.

## Remaining acceptance dimensions

The single-wave matrix is only one launch gate. Sustained overlapping price bursts,
publication/invalidation races, forced worker interruption/restart, concurrent
release/origination, failed-evidence recovery, daily rollover, and production-like
infrastructure/HTTP foreground latency still need explicit acceptance. Earlier
focused correctness tests cover some of these paths at small scale; this workload
does not turn those into full-load evidence. Formal regulatory NPA classification
is a separate [future review](../plans/future-work.md#fw-003-formal-lender-specific-npa-classification).

## Interrupted first attempt (2026-09-11)

The 300,000-active/60,000-closed dataset occupied 6,736,601,615 bytes after
preparation. The first price wave started at 17:34:20 UTC; publication across 100
Workspaces took 52.798 seconds. At 1,700.57 seconds, 55,208 loans had been assessed,
with no reported errors. The next recorded progress arrived over three hours
later. The host/session interruption invalidates a continuous one-hour result.
Do not treat the old driver's 19,619-second phase wall time as an assessment
throughput measurement or a completed one-hour failure. The million-active phase
never started, and no benchmark client remained after environment recovery.

The interrupted segment collected 294 portfolio samples (p95 0.580 seconds) and
294 repayment/reversal pairs (p95 0.273 seconds). These are partial local service
measurements, not full-window or HTTP acceptance. The final old-date projection
count of zero after midnight reflects date freshness, not lost loan data.

## Continuous rerun (2026-09-12)

The retained dataset was tested with temporary idle-sleep prevention
and explicit measurement-gap detection. Each wave changes the numeric gold price
between 1,400 and 1,500, rather than repeating an unchanged price on retries.
The completed lower-size phase failed the one-hour target; the upper-size phase
was interrupted and is not valid continuous-load evidence.
Retain exact in-window and post-shutdown counts separately: commits or verification
after the deadline cannot be claimed as within-hour completion.

### 100 x 3,000: continuous result

The 2026-09-12 wave started at approximately 01:24:16 UTC. Price publication took
29.065 seconds, included in the deadline. The last in-window observation was
**121,869 / 300,000 (40.6%) at 3,589.09 seconds**. No Workspace finished all 3,000
loans within the observed deadline. After workers stopped, 122,400 were assessed;
that post-shutdown count must not be labelled within-hour completion. Final
verification finished at 3,677.519 seconds. The run was continuous, reported zero
errors, and failed the one-hour gate.

| Foreground operation | Samples | p50 seconds | p95 seconds | p99 seconds |
| --- | --- | --- | --- | --- |
| Portfolio service/selector read | 648 | 0.249 | 0.462 | 0.797 |
| Repayment plus reversal, combined | 648 | 0.184 | 0.275 | 0.644 |

Sampled canonical financial/risk results and new-quote provenance matched. Closed
loans received no projections, and scoped reads rejected other Workspace loans.
The retained dataset started this rerun with old-date projections; therefore its
price invalidation cost is not a benchmark of updating 300,000 already-current
same-day projections. This is a local baseline failure, not a proof that all other
server sizes/configurations fail. No production sizing claim follows from it.

### 100 x 10,000: interrupted result, retry required

All 100 Workspaces were prepared with 1,000,000 active and 200,000 closed loans.
The database occupied 26,783,511,011 bytes after ANALYZE. The wave began at
03:26:46 UTC on 2026-09-12; price publication took 110.238 seconds, included in
the deadline. The last normal observation recorded 2,044 new-wave assessments
at 209.78 seconds. A later measurement gap of 706.258 seconds triggered the
continuity guard, which stopped the phase. Temporary idle-sleep prevention did
not prevent this interruption; its exact external cause was not established.

The run reported `valid_continuous_run: false`. Its sole reported error was the
measurement gap. After workers stopped, 2,800 projections used the new quote;
final verification finished at 999.245 seconds. These numbers are not one-hour
throughput or an upper-size capacity failure. No Workspace completed its full
10,000-loan wave. Closed-loan exclusion and foreign-Workspace loan-read checks
passed across all 100 scopes; available refreshed financial/provenance samples
also matched. Scopes with no refreshed loans supplied no monetary sample.

Only 18 samples of each foreground operation were collected: portfolio p95 was
2.503 seconds; repayment plus reversal p95 was 0.278 seconds. These partial-run
latencies do not establish full-hour foreground performance. The driver exited,
removed its temporary role, and left no other clients connected to this test
database. The 26.8 GB fixture database remains available for diagnosis and retry.

Retry only the upper size after confirming the machine can run continuously for
at least the preparation time plus one hour; no fixture reset is needed:

```powershell
.\.venv314\Scripts\python.exe -X utf8 scripts/benchmark_monitoring_load.py --resume --workspaces 100 --sizes 10000 --seconds 3600 --workers 8
```

The lower-size local failure already warrants optimization. An uninterrupted
million-loan result remains outstanding; do not substitute linear extrapolation
or the interrupted sample for that acceptance run.

### Upper-size retry: stopped at owner request

The owner confirmed an uninterrupted window and an upper-size-only retry started
at 03:51 UTC on 2026-09-12. The retained database occupied 27,457,335,779 bytes
after ANALYZE. The timed wave began at 03:52:32 UTC; price publication took
143.780 seconds. The last observation was **19,185/1,000,000 at 940.65 seconds**
(15 minutes 41 seconds), with zero reported errors and no completed Workspace.
The owner then requested stopping and shelving the test until better hardware
is available. This is an intentionally cancelled partial run, not a one-hour
pass/fail or an extrapolated throughput result. It did not reach final monetary
verification or produce a completed phase summary. Test processes stopped;
absence of remaining database clients and temporary-role removal were verified.

The retained dataset started with a mixture of old/stale projections, so this
retry is not a clean invalidation-cost benchmark of one million already-current
same-day projections. The synthetic dataset is preserved. Further large-scale
runs require owner resumption under [FW-004](../plans/future-work.md#fw-004-launch-scale-loan-monitoring-capacity).

### Diagnostic findings before optimization

During the earlier partial run, restricted-role EXPLAIN ANALYZE confirmed that a
single-loan pending recheck still scanned the Workspace's 3,000 snapshot rows
(~7.2 ms execution in that sample); bounded candidate selection took ~29.2 ms.
These are observations, not proof that this is the sole bottleneck. Repeated
canonical event/tranche/schedule reads also remain targets for profiling and reuse.

A read-only query comparison during upper-size fixture preparation used one
Workspace with 10,000 active loans, under the same restricted role and scope.
Both query forms returned exactly the same ordered pending-loan IDs. For one
pending loan, the existing NOT IN subquery scanned 4,000 matching current
snapshots (4.891 ms execution, 1,487 shared-buffer hits and three reads); a
correlated NOT EXISTS lookup used the Workspace/loan unique index (0.084 ms,
12 shared-buffer hits and no reads). Planning was 0.593/0.375 ms respectively.
These are single, warm/local plan samples, not an end-to-end speedup or a new
capacity result. The candidate was not applied to the running baseline.

A separate instrumented refresh of the five original seed profiles, inside a
rolled-back transaction under restricted RLS during fixture preparation, issued
84, 66, 91, 122 and 96 statements respectively (459 total). This measures the
refresh function, not worker claim/context overhead or committed throughput.
Ninety statements came from repeated collateral-identity and tranche-repayment
reads, 31 from per-period event-date reads, and 30 from balance-event reads.
Schedule/obligation and monitoring-policy reads also repeat. Reuse should remain
inside a single loan/date/source-checked calculation; before/after source guards,
reversal semantics and row-lock boundaries must be preserved. Query counts alone
do not establish an end-to-end speedup. No diagnostic writes were committed.
A separate aggregate progress-query probe during partial fixture expansion took
11.203 seconds under concurrent fixture writes. Its matching count included copied
previous-wave projections and is not a new-wave assessment result. Observer
overhead must be considered when comparing this harness with production load.
