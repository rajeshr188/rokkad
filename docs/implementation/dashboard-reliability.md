---
status: active
owner: project
updated: 2026-09-12
tags: [dashboard, performance, loans]
---

# Dashboard reliability and query baseline

## Current behavior

The Workspace dashboard renders daily work queues and, from 2026-09-12, a separate
business overview described below. It does not use the older monetary summary.
When any ACTIVE loan has no usable schedule or has inconsistent allocations, it
enters Schedule needs review. A visible warning now explains that those loans are
excluded from payment counts/amounts and links to the affected queue. This warning
is inside the existing data.view-authorized section. Valid queues remain usable.
Unexpected exceptions still propagate; this does not mask database/programming failures.

The exported get_workspace_pawn_loan_dashboard_summary selector currently has no
production caller. It now returns totals_complete, unavailable_balance_count and
as_of_date. If any active balance fails its existing validation handling, both
monetary totals are None instead of partial sums. Empty portfolios still return
complete zero totals; state counts remain available. It requires matching Workspace
context before querying. Future consumers must distinguish unavailable from zero.
No balance or contractual obligation calculation changed.

## Reproducible baseline

Run from the repository root in PowerShell, choosing a disposable test database:

```powershell
$env:DB_MIGRATION_NAME='rokkad_billing_0909'
.venv314\Scripts\python.exe scripts/benchmark_dashboard.py
```

The script forces test settings and uses Django's test database (test_ prefix),
rollback and in-memory photo storage. It reuses existing service-test fixtures to
create, approve and disburse 100 synthetic gold bullet loans; no real notifications
are dispatched. Fixture creation is outside timing. Three repeated queue-selector
reads per size use 2026-10-19, after the three-month maturity; all loans must appear
overdue. Only the explicitly named benchmark method runs, not inherited tests.

Local Windows/Python 3.14/PostgreSQL baseline on 2026-09-09:

| Active loans | SQL queries | Median selector time (ms) |
| --- | --- | --- |
| 1 | 5 | 6.0 |
| 10 | 41 | 40.3 |
| 50 | 201 | 205.0 |
| 100 | 401 | 417.9 |

These are owner-backed test-database measurements, not restricted-role load-test
results or end-to-end request latency. They include query instrumentation overhead.
One schedule/obligation per loan, no allocations or schedule replacements; larger
installment portfolios need additional coverage. Existing queue pagination limits
rendered rows, not calculation work.

## Batch implementation (2026-09-10)

The dashboard loads loan/borrower rows once, then schedule versions with dated
termination/reversal evidence. Only selected schedules receive prefetched payment
rows and effective-dated allocations. The batch and single-loan paths share the
same termination predicate and obligation fold. Prefetched models stay local to
one call; only calculated states are returned, so another date cannot reuse stale
prefetched allocations. All batch queries explicitly filter Workspace ownership,
in addition to PostgreSQL RLS. Missing schedules and integrity findings still enter
the review queue. No schema, indexes, loan mutations or cache were introduced.

| Active loans | Queries after | Owner median ms | Restricted-role median ms |
| --- | --- | --- | --- |
| 1 | 5 | 6.4 | 6.2 |
| 10 | 5 | 6.7 | 6.9 |
| 50 | 5 | 14.5 | 15.6 |
| 100 | 5 | 19.3 | 18.9 |

The same benchmark now measures both database roles and asserts five queries at
each size. It creates a temporary NOLOGIN/NOBYPASSRLS read-only role inside the test
transaction; rollback removes the role and grants. Timing includes instrumentation,
not fixture creation or role switching. These are synthetic local measurements,
not a production latency guarantee or full HTTP load test.

Validation: 54 targeted selector, template, repayment-schedule and loan-service
tests passed, plus the benchmark. Persisted 12-payment-row fixtures compare the
single and batch paths across partial payment/reversal dates, future replacement
schedules, termination and reactivation. Tests cover missing schedules,
over-allocation, review queues, wrong context and foreign Workspace rows under a
restricted role. Existing tests cover empty schedules. CI's Loans suite includes
the new regression module; timing remains an explicit diagnostic.

## Remaining limits

Query count is bounded for this portfolio shape, but computation and memory still
grow with loans, schedule history and obligations. Pagination limits display only.
Large mixed/installment portfolios need load and memory measurements before adding
chunking or projections. No new caching or index is justified by this result.
Routing/module organization subsequently completed; see the current active plan.

## Business metrics increment (2026-09-12)

The new `business_overview` selector adds current customer/borrower/loan counts,
principal and recorded interest, and period-filtered new lending/renewal activity.
See the [operator definitions](../flows/business-dashboard.md). Current balances
reuse `calculate_pawn_loan_balance`, without fetching collateral or recalculating
health. Loans/policies stream in batches with explicit-Workspace, dated event
prefetch; activity counts use SQL aggregates and cash evidence streams separately.
No new schema, cache or financial rule is introduced.

Within one nonempty balance batch, the entire new selector uses six queries:
customer count, active counts, loan/policy rows, events, activity counts and cash
evidence. Each additional 250-loan batch adds one event query. Tests force smaller
batches to verify transitions and compare money to the canonical single-loan fold,
including capitalization, repayments and reversals. These figures cover the new
metrics selector, not existing queues/setup or total HTTP query counts. CPU and
history size remain linear; no large-scale latency claim is made.

Read permission gates run before selector invocation. Restricted-role tests cover
foreign Workspace exclusion, and HTTP tests cover hidden metrics without access,
period validation and filter-preserving queue pagination. Invalid balance or cash
evidence cannot become a claimed complete total. Renewals and ordinary loan cash
have deliberately separate labels and counts.
