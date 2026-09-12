---
status: active
owner: loans
updated: 2026-09-12
tags: [rates, appraisal, onboarding, monitoring]
---

# Rates, appraisal and collateral coverage review

The subsequent [origination freshness review](origination-rate-freshness-review.md)
records the owner's same-day-at-approval choice, confirmed quote-provenance gaps
and proposed delayed-disbursal/backdated-entry behavior. Enforcement is the next
increment; monitoring age limits have not been applied to origination.

Reviewed against published application checkpoint `fdb5e97f`, following a new-loan
failure when no metal valuation rate existed. The review examined code paths;
it did not verify the owner's database records. Implemented changes are recorded
separately below.
The baseline findings below describe the reviewed checkpoint. The owner approved
the recommended order; delivery progress is tracked here and in Status.

## Delivery progress

Increment 1 is implemented locally: shared quote readiness in lending setup and
general setup metrics, a permission-checked GET preflight for the actual series,
loan date and metals, actionable row/field errors, and another-tab Rates guidance.
The HTMX preflight keeps inputs/photos in place on a missing-price result and
preserves manual appraisals. Loan commands remain authoritative. Gold-only and
appraisal-only flows do not require unrelated quotes. The new route follows the
existing Workspace adapter pattern; no schema or runtime role changes are needed.

Origination quote ages are displayed; monitoring-age rules are separate. JavaScript-disabled and concurrent-change
fallbacks use normal server validation and may require photo reselection. The
client guard has package-free Node event-contract tests; these do not replace
physical device acceptance.

Increment 2 is implemented locally: explicit per-gram/pure-metal entry, positive
price validation, effective versus recorded time, deterministic source selection,
actor/source evidence, append-only corrections and withdrawals, and protected
source history. PostgreSQL guards quote immutability and relationship scope.
Selection, setup/suggestion dates and risk invalidation/fingerprints consume the
new evidence model. See the [decision](../adr/2026-09-11-rate-quote-evidence.md)
and [operator guide](../flows/metal-rate-entry.md). Migration and regression
validation passed.

Increment 3 is implemented locally: method-aware monitoring freshness, explicit
unknown coverage, evidence dates/ages, and current-time reassessment of held active
collateral. Approved appraisal versions preserve reviewer, method/reference/reason
and observed quote context; PostgreSQL protects history. Saved risk results are
invalidated in the appraisal transaction and at migration rollout. See the
[decision](../adr/2026-09-11-collateral-freshness-and-reappraisal.md) and
[operator guide](../flows/collateral-reassessment.md). Validation passed: 558 broad
tests (190.570 seconds), then 53 final focused checks (29.606 seconds), including
concurrent reviewers, read-only permissions, restricted SQL guards, original/as-of
preservation, and migration preservation/invalidation. Loans migration 0006 is
applied to local `rokkad_shared_dev`; runtime, drift and documentation checks pass.
Increment 4 is implemented locally: all-active portfolio coverage, date-based stale
detection, explicit unknown coverage and unavailable incomplete totals, bounded
repeating refresh and transaction-local invalidation. Monitoring amendments append
actor/reason-linked successors without rewriting previous periods. See the
[decision](../adr/2026-09-11-complete-loan-monitoring.md) and
[guide](../flows/loan-health-monitoring.md). All 576 broad checks passed, followed by 83 final checks and 24 display checks.
Loans 0007 is applied to local `rokkad_shared_dev`; runtime, migration and docs
checks pass. Optional worker configuration has not been started locally or deployed. Origination-age requirements need their own policy contract
and matching setup/preflight/command validation; this increment applies existing
monitoring age fields to monitoring, not to origination or release commands.

Validation: 137 focused Loans/onboarding/routes/Rates access and RLS tests passed
in a fresh disposable database (67.068 seconds); four Node preflight interaction
tests passed. Runtime, migration-drift and import-boundary checks also pass.
Increment 1 required no schema or development-data changes. Increment 2 adds
Rates migration 0003; both increments are local and uncommitted.

Increment 2 validation: 563 broad regression tests passed (192.195 seconds), then
31 final focused tests passed (12.767 seconds). Coverage includes real upgrade
preservation of invalid legacy data, concurrent correction exclusion, service
authorization, and raw DML under a restricted role. Rates 0003 is applied to local
`rokkad_shared_dev`; runtime/database, pending-migration, import, documentation and
whitespace checks pass. This is development validation, not production acceptance.

## Existing responsibilities

- Rates owns Workspace reference quotes and their sources. Loans consumes the
  Rates facade under Workspace context. Redis is not required for these reads.
- Loans owns lending interest/fee policies, collateral valuation, appraisal
  evidence, financial exposure, loan-to-value (LTV) and monitoring.
- A metal buying price in Rates is different from a loan's monthly interest rate.
- Preserve the organization/RLS boundary and existing action permissions. This
  review does not reopen deferred license-scoped staff access or Razorpay setup.

## Confirmed behavior and gaps

| Area | Current behavior | Gap |
| --- | --- | --- |
| Setup readiness | `loans/selectors/setup.py` checks license, series, calculation/interest policies and product. `build_business_setup` reuses it. | No usable metal quote check. The separate onboarding Rates task sums Rate and RateSource counts, so a source alone can mark it complete. |
| Error | `domain/collateral_economics.py` requires both calculated value and appraisal for the default lower-of method. | The message repeats both requirements even if only one is absent; unlike allocation errors it lacks row/field metadata. |
| Quote selection | `rates/facade.py` selects the latest matching metal, INR, `24k` quote on/before the requested date; Loans uses its buying rate as price per gram of pure metal. | No source preference or age cutoff; neither a 22k-only quote nor a different currency qualifies. Silver uses the same confusing `24k` purity vocabulary. |
| Rate entry | Manual CRUD; timestamp is creation time. Quote model has no unit field. Source tax flag is stored. | UI does not clearly establish pure-metal/per-gram basis; no operator effective date, tax normalization or preferred source. Browser min=0 is not a positive-price server contract. |
| Quote history | Quotes and sources can be edited/deleted; deleting a source cascades its quotes. | Historical reference evidence needs auditable correction/retirement. Source fingerprint uses counts/max ID/timestamp, not quote contents, leaving an in-place-edit race to address. |
| Suggestion | HTMX calculates buying rate × net grams × purity/100, preserving manual values and rejecting late responses. | The fallback suggests entering appraisal manually even when the lower-of policy still requires a rate. Suggested amount is not an independent physical assessment. |
| Approved appraisal | Approval creates immutable versioned `CollateralAppraisal` evidence from the draft value, dated to loan date with method ORIGINATION_APPROVAL and actor reference. | No dedicated active-loan reassessment service/UI was found. Model fields for method, evidence, notes and supersession exist but are not an end-to-end operator workflow. |
| Current valuation | Latest approved appraisal as of date, current matching quote, frozen loan valuation method; in-vault and funding-lender custody are eligible. | Lower-of remains capped by the older appraisal on rising markets. The configured rate/appraisal freshness fields are not consumed by this path. |
| Risk | Live loan detail assessment, persisted portfolio snapshots, DPD/maturity/LTV flags, transition events and alerts exist. | Portfolio is snapshot-based; loans with no snapshot do not appear in its query/count. It needs explicit unassessed/stale-date coverage. |
| Refresh | Source saves mark snapshots stale; UI refreshes one or up to 50 due assessments; a reassessment management command exists. | No automatic recurring refresh wiring was found. Rate deletion has no corresponding stale signal; elapsed time alone also requires reassessment. |

RateSource's `tax_included` and monitoring policy freshness fields currently being
stored does not mean those settings are enforced in valuation. Similarly, the
loan valuation selector hardcodes eligible custody states rather than applying
the monitoring policy's stored eligible-state configuration. Follow-up changes
must define which policy owns each decision instead of adding more inert fields.

## Coverage and repayment performance

Keep payment performance and collateral coverage separate. A loan can be current
on payments while its collateral value falls below its exposure, or overdue while
fully covered. Use “Collateral shortfall” or “Under-covered” for the first issue;
do not infer a formal regulatory NPA classification from it.

Existing `domain/ltv.py` already calculates:

```text
LTV = exposure / eligible collateral value
policy headroom = eligible collateral value × allowed LTV − exposure
full shortfall = max(exposure − eligible collateral value, 0)
```

For example, exposure of INR 60,000 and value of INR 50,000 means 120% LTV and an
INR 10,000 coverage shortfall. At 80% allowed LTV, policy headroom is -INR 20,000.
These are different measures. A policy breach can happen before full shortfall.

`selectors/exposure.py` uses maturity payoff for bullet/flexible LTV and total
economic exposure for amortizing LTV. Contractually due now, overdue, recorded
balance and projected interest are separate. Show the chosen denominator and
date rather than labelling every figure “due”. The snapshot's exposure column
stores total economic exposure, which need not equal its bullet-LTV numerator.

Whole-loan coverage can be authoritative using the existing exposure selector.
Per-item coverage should use outstanding tranche allocations and a documented
treatment of interest/fees. Original allocated principal is not necessarily the
item's current debt. Do not divide total debt equally or label collateral itself
non-performing. Missing/stale valuation evidence must be “Unknown”, never safe.

## Recommended increments

1. **Setup and actionable errors.** Add a shared, policy-aware quote-readiness
   check used by business setup and new-loan guidance. A source alone is not ready.
   Show each supported metal's usable/missing/stale quote, price basis and date.
   Validate the actual selected series, loan date and collateral metals; do not
   block a gold-only loan solely for missing silver or force market quotes for an
   appraisal-only policy. Preserve entered fields/photos when providing a Rates
   detour. Identify the missing input on its collateral row and link to the fix.
2. **Reliable quote evidence.** Explicit INR per gram and pure-metal basis; proper
   silver purity labels; positive-price validation, effective versus recorded time,
   source selection and auditable corrections. Keep manual entry; feeds/imports
   are optional later work. Do not invent default market prices.
3. **Valuation freshness and appraisal workflow.** Enforce meaningful age policy,
   distinguish current metal value from staff assessment and policy-selected value,
   retain suggestion provenance, and add permission-checked reassessment with
   reason/method/evidence and immutable supersession. Preserve origination records.
4. **Visible loan health and complete monitoring.** Show coverage value, exposure
   basis, shortfall/headroom, LTV, overdue/DPD, rate/appraisal dates and completeness.
   Make unassessed loans visible, apply time-based staleness, handle rate corrections
   and deletion, and schedule bounded reassessment through existing mechanisms.
   Review derived per-item exposure before displaying authoritative item shortfalls.

Validate missing/incorrect currency or purity quotes, dates, method-specific
requirements, mixed metals, manual appraisal preservation, stale inputs, price
corrections, unassessed loans, per-item/aggregate consistency and RLS isolation.
No automatic auction, financial posting or borrower communication follows merely
from detecting risk. Existing service authorization and workflow rules remain.

All four delivery increments are now implemented locally. Complete validation
and review the Loan health / amendment screens before publishing the checkpoint.
Origination quote-age policy and derived per-item exposure remain separate design
items; do not imply that monitoring limits govern those workflows.

## Launch capacity requirements and review (2026-09-11)

The owner subsequently specified 30-100 loans processed per organization per day,
3,000-10,000 active loans per organization, and at least 100 organizations at launch.
Treat this as a minimum planning range of 300,000-1,000,000 active loans plus loan,
collateral, repayment and evidence history, not a tested capacity claim.

Closed loans are excluded from the active portfolio, batch selection, rebuild and
normal single-loan refresh eligibility. Existing evidence remains stored. Source
invalidation signals still touch some closed-loan snapshots, and the separate open
alert query does not filter ACTIVE loans: these are follow-up cleanup items, not
scheduled closed-loan reassessment. Also, pawn_reads currently calls live
valuation/risk selectors when opening a CLOSED loan detail page. Stop routine
current-health calculations there while retaining settlement/balance/history reads.
Add explicit closure-versus-refresh and reactivation coverage; retain closure history and legitimate reversal behavior.

The delivered worker is a bounded correctness foundation, not launch-scale
acceptance. One configured process handles one Workspace, 50 candidates per pass,
then waits 300 seconds after computation. That is at most roughly 600 assessments
per hour at steady state, ignoring computation/retries. A full 3,000-loan sweep is
roughly 5 hours and 10,000 roughly 16?17 hours at this cadence. Date rollover makes
all previous-day projections outdated; an applicable price/policy change can also
create a portfolio-sized backlog. Daily intake volume does not bound this work.
No 100-Workspace/million-active-loan load test has been performed.

Source review found repeated calculations within each assessment: exposure is
read directly and through both collateral valuation calls, while delinquency and
collateral valuation are each invoked directly and again by risk assessment.
Rate/appraisal/policy queries recur across items/loans. Loan locks currently span
an entire selected batch and its transaction; simply raising batch size can
increase foreground repayment/release waits. Snapshot filtering, fingerprints,
synchronous rate invalidation and alert readiness queries need measured plans.

Recommended next work, pending implementation:

1. Establish freshness and foreground-latency acceptance targets, then benchmark
   representative 3,000/10,000-active-loan Workspaces under the restricted role.
   Include realistic collateral, repayment/reversal and historical closed records,
   concurrent origination/repayment/release, and a full metal-price-change backlog.
2. Reuse authoritative read results within an assessment and batch common evidence
   reads; preserve amount, reversal, policy and fingerprint parity. Measure query
   counts, elapsed time, lock waits, memory and database utilization before/after.
3. Drain due work without a fixed five-minute sleep between nonempty batches,
   subject to backpressure; use short transactions and a bounded shared worker
   pool that fairly rotates explicit Workspace jobs. Design durable claims/retry
   and source-change handling before changing lock boundaries. Do not require
   manually maintaining 100 dedicated worker processes or add Redis by assumption.
4. Prioritize individual loan changes, coalesce repeated market-price invalidation,
   schedule daily date-sensitive work, and retain reconciliation. Any version-based
   invalidation must become visible atomically so stale data never appears current.
5. Measure the full 100-Workspace target and burst recovery; expose backlog age,
   throughput, failures and freshness coverage. Specify hardware and storage,
   define operational alerts, and gate launch on measured acceptance.

One million daily assessments average about 11.6 per second across 24 hours;
finishing the same sweep in one hour requires about 278 per second. These are
arithmetic demand examples, not measurements or agreed freshness objectives.
Increasing a batch limit alone does not establish sufficient capacity.

Django recommends profiling and examining query plans before optimizing
([database optimization](https://docs.djangoproject.com/en/6.0/topics/db/optimization/)).
PostgreSQL documents SKIP LOCKED for competing consumers of queue-like work;
it is useful coordination, not a throughput guarantee
([SELECT locking](https://www.postgresql.org/docs/current/sql-select.html)).
No application code or worker configuration changed during this capacity review.


## First capacity increment (2026-09-11)

The UI/amendment checkpoint is published as `21a48aee`. Subsequent capacity work
is local and separate from that checkpoint:

- Invalidation now targets ACTIVE loans only. Closed loan detail retains balance,
  exposure, settlement and history but omits live delinquency/collateral/risk
  calculations. Operational alert lists and latest active-assessment diagnostics
  exclude closed loans without deleting historical alerts or assessments.
- Successful and failed refresh writes recheck loan state under its row lock.
  A concurrent closure discards the result, including first-failure attempts.
  Release reversal reactivates the loan and invalidates its projection.
- Refresh reuses its authoritative exposure in collateral valuation, then passes
  its delinquency/collateral results into risk assessment. Reused inputs must
  match the scoped loan and as-of date. There is no persistent cache or change to
  financial formulas, fingerprints, source-change checks or transaction locks.

### Reproducible initial baseline

Run `.\.venv314\Scripts\python.exe scripts/benchmark_monitoring.py`. The script
forces test settings and a disposable `test_rokkad_monitor_benchmark` database;
synthetic rows roll back after the test. Existing development rows are untouched.
It reserves new identities and bulk-copies read evidence from a command-created,
100-day-old bullet loan with one gold item, one contractual obligation and stale
quote/appraisal evidence. It preserves relational and tranche references needed
by the read path and checks monetary/flag parity against the seed. Synthetic
copies are not valid lifecycle fixtures or audited origination history.

Selection, portfolio reads and refresh writes run with an explicitly restricted
NOSUPERUSER/NOBYPASSRLS role under the Workspace context. Data setup uses the test
owner role. These are homogeneous portfolio-size microbenchmarks: one Workspace,
one local process, warm database, a 50-loan sample, no simultaneous user traffic.
They do not represent the full production workload, long histories, all product
variants, background contention, complete portfolio draining or 100 organizations.
Measured locally on Windows 11 (16 logical CPUs), Python 3.14.3, Django 6.0.3
and PostgreSQL 16.1. Wall times are single observations, affected by other local test activity; query
counts are the more stable evidence. Query logs are cleared between measurements
to avoid Django's 9,000-query logging limit truncating later samples.

| Active loans | Portfolio queries | Portfolio seconds before / after | Refresh-50 queries before / after | Refresh-50 seconds before / after |
| --- | --- | --- | --- | --- |
| 3,000 | 5 | 0.135 / 0.149 | 6,904 / 4,004 | 9.002 / 4.525 |
| 10,000 | 5 | 0.288 / 0.277 | 6,904 / 4,004 | 10.479 / 4.623 |

Removing repeated component reads cuts refresh queries by 42%. Remaining reads
include loan/collateral/event loads, schedule/obligation folds, policy resolution
and the two source fingerprints. The existing five-minute pause and long batch
transaction have not changed. Do not extrapolate these timings into a promise
that one worker supports the launch target.

### Remaining priority, in order

1. Expand the 3,000/10,000-loan benchmark to a reviewed mix of products, ages,
   collateral counts/metals, repayments, reversals, closed history and rate bursts;
   measure foreground latency, invalidation time and backlog age alongside refresh.
2. Optimize measured remaining reads and design short transactions plus prompt,
   bounded backlog draining with fair Workspace scheduling and retries. Preserve
   source-change detection, closure safety and explicit RLS contexts.
3. Run the complete 100-organization workload at the 300,000 and 1,000,000 active
   loan bounds, with 30-100 daily operations per organization and concurrent jobs.
   Record hardware, duration, p95/p99 foreground latency, throughput, errors and
   recovery/backlog age against agreed acceptance targets before launch claims.

This remains active work, not shelved future work. License scoping, Razorpay and
physical device acceptance remain separately deferred.


## Mixed workload and worker increment (2026-09-11)

The initial homogeneous fixture is now supplemented by
`scripts/benchmark_monitoring_mixed.py`. Run it with the repository Python. It
uses the same disposable test database and never connects to development loan
rows. The mixed run commits synthetic test data to measure real per-loan worker
transactions; Django's TransactionTestCase flushes that data at completion.
Do not run the two benchmark scripts simultaneously against that database.

The interleaved active mix has equal numbers of:

- 100-day bullet loans with one gold item;
- 7-day bullet loans with one gold item;
- 180-day periodic-interest bullet loans with gold and silver items;
- 400-day flexible loans with four gold/silver items;
- 180-day EMI loans with one gold item.

The last three profiles include three dated repayments and reversal of the latest
repayment. An additional closed, fully released silver-loan profile adds 600 closed
loans to the 3,000-active portfolio and 2,000 to the 10,000-active portfolio. Seed
loans use actual commands, numbering, frozen terms, photos and release evidence.
Copies preserve relational/tranche references used by the selectors; they remain
synthetic read-load fixtures, not auditable origination records or workflow tests.
Gold and silver quotes include historical and current evidence. Monetary, DPD,
coverage, flags and risk fingerprints are checked against their real seed profile.
Gold quote changes invalidate all active projections while closed loans stay out.

Measurements use a NOSUPERUSER/NOBYPASSRLS role. The script also measures an actual
worker pass after committing the dataset, with no surrounding transaction, and
asserts that an unset Workspace context cannot read the loans. Seed/setup writes
use the disposable owner role. This is a more varied synthetic baseline, not a
measured distribution of customer behavior or the full 100-organization workload.

### Measured read improvement

Schedule allocation reads were an N+1 cost: each obligation fetched its own
allocations, repeated by the exposure and delinquency selectors. The canonical
single-schedule selector now prefetches allocations through the requested date in
one query and feeds the same existing fold. Twelve obligations need two queries
instead of thirteen. Tests cover same-day repayment, reversal, historical dates,
amount parity and the constant query count.

| Profile / operation | Before | After |
| --- | --- | --- |
| Periodic-interest assessment queries | 119 | 97 |
| EMI assessment queries | 116 | 98 |
| Mixed refresh-50 queries, either portfolio size | 5,124 | 4,724 |

Other profiles retain their prior query counts. Local wall time did not show a
stable speedup from this smaller optimization; avoid claiming one. Repeated
tranche/event reads for older loans remain measurable work (the 400-day exposure
alone still needs 60 queries).

### Committed worker measurement and behavior

On the same local Windows/Python/PostgreSQL environment as the first baseline,
the final 10,000-active/2,000-closed run recorded:

| Operation | Queries | Seconds |
| --- | --- | --- |
| Loan health summary | 3 | 0.201 |
| First portfolio page | 2 | 0.307 |
| Older flexible-loan exposure | 60 | 0.473 |
| Existing in-context refresh of 50 | 4,724 | 6.472 |
| New worker pass, 50 separate loan commits | 5,199 | 7.593 |
| Gold quote invalidation at 10,000 active loans | 2 | 1.449 |

These are single local observations with other test activity, not p95/p99 latency
or a throughput guarantee. The new worker intentionally pays transaction/context
cost to release each loan promptly. A restricted-role concurrency test proves a
second connection can read and NOWAIT-lock the first committed loan while the
second candidate is processed. Competing passes keep one snapshot; bad candidates
are attempted once per pass, and foreign Workspace projections remain untouched.

Repeated command rounds give each explicitly configured Workspace a bounded turn.
Successful rounds use a one-second busy pause by default; empty/error-only rounds
use the configured longer idle interval. Dates and lifecycle are rechecked. No
worker was started against development or production data. See the
[worker decision](../adr/2026-09-11-monitoring-worker-turns.md) and
[operator guide](../flows/loan-health-monitoring.md).

The next acceptance step is the full multi-organization load test with explicit
freshness targets, sustained price changes, concurrent servicing, backlog age,
foreground p95/p99, worker recovery and bounded process counts. This requires
300,000 and 1,000,000 active-loan runs before launch-capacity claims. Further read
optimization and write/invalidation coalescing should follow measured failures.


### Owner-selected freshness target

The owner selected **within one hour after a metal-price change** for all affected
active loans. Treat this as the launch test's acceptance target, not a current
capacity claim. At 100 organizations, a platform-wide wave affecting 300,000 loans
requires at least 84 completed assessments/second; one affecting 1,000,000 loans
requires at least 278/second, before headroom, retries and foreground traffic.
The local committed-worker sample does not meet or prove those aggregate rates.

The next workload must verify current-source correctness during overlapping price
writes/assessment publication as well as throughput. It must cover backlog drain,
concurrent repayments/releases, worker interruption/restart, failed evidence,
closed-loan exclusion and cross-Workspace isolation. Do not declare success from
linear extrapolation or a small concurrency smoke test.

On 2026-09-12, the continuous 100 x 3,000-active local run failed: 121,869 of
300,000 loans were observed assessed at 3,589.09 seconds, with no errors and
passing sampled correctness checks. The 100 x 10,000 dataset is prepared, but
a 706-second measurement gap invalidated its timed phase. An uninterrupted
million-loan result remains outstanding. A subsequent retry was stopped at the
owner's request after 19,185 assessments were observed at 940.65 seconds. Further
large-scale testing is shelved until better hardware is available under
[FW-004](../plans/future-work.md#fw-004-launch-scale-loan-monitoring-capacity). These results
do not establish launch capacity; measured query costs remain documented for
later optimization review.

The reproducible full-size driver and its exact limits are documented in the
[capacity test](monitoring-capacity-test.md). The 100-Workspace measurements do
not establish regulatory NPA classification; see the [operational distinction](../flows/loan-health-monitoring.md#payment-performance-and-the-npa-distinction).
