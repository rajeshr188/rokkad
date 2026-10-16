---
status: verified-locally
owner: loans
updated: 2026-10-16
tags: [loans, monitoring, performance, verification]
related: [../adr/2026-10-16-measured-monitoring-invalidation.md, ../plans/loan-boundary-simplification-20261016.md]
---

# LS-06: measured invalidation and worker contention

Local implementation follows the approved six-slice order. No production access,
live loan/policy change, commit, push or deployment. Earlier LS work, committed
undeployed corrections and unrelated WhatsApp documentation are preserved.

## Reproducible bounded characterization

[MonitoringOperationsTests](../../apps/tenant_apps/loans/tests/test_monitoring_operations.py)
runs through Django test settings on the dedicated
`test_rokkad_ls06_20261016` PostgreSQL database. All measured operations use a
NOLOGIN/NOSUPERUSER/NOBYPASSRLS role, explicit Workspace contexts and fictional
data. Application-source fixtures are created through ordinary origination.

The fan-out case uses one genuine loan plus deliberately minimal synthetic
loan/item/projection rows at total sizes 1, 100 and 2,500 when measurement is
explicitly enabled; routine regression stops at 100. These extra rows are not
financial admissions and are never assessed as valid debt. Each size has five
CURRENT invalidations and five immediately repeated STALE invalidations. SQL
execution timing excludes fixture setup, source insert, reset/count assertions
and enclosing transaction commit. Baseline timings measure the UPDATE alone;
trial timings include both the lock SELECT and UPDATE, so the comparison does
not conceal the cost of retaining locks. The trial is not retained.

The worker case performs five single-item, 100-day-old, ordinary active-loan
passes. It includes candidate selection, calculation, persistence and per-loan
commit. Claim-to-return starts after the skip-locked claim query completes and
ends after the pass returns: an upper approximation of the subsequent lock hold,
not an exact database lock-release timestamp. Query counts include Workspace and
transaction scaffolding. This small history is not a complex-loan capacity test.

The contention case deliberately pauses a claimed worker. Actual
`pg_blocking_pids` establishes same-loan waiting; another loan remains lockable
with NOWAIT and a competing batch skips the claimed loan. The injected pause is
not a natural latency sample. Threads have bounded events, lock timeouts and
connection cleanup. Timing observations have no brittle absolute pass threshold.

To repeat locally, use a new isolated test database name through
`DB_MIGRATION_NAME`, set `ROKKAD_MONITORING_MEASURE=1`, and run:

```powershell
.venv314\Scripts\python.exe manage.py test apps.tenant_apps.loans.tests.test_monitoring_operations --settings django_project.settings.test --noinput --keepdb --verbosity 2
```

The environment flag prints aggregate synthetic measurements only; no borrower,
source-document, connection credential or production information is emitted.

## Original observations and decision

The initial four-case characterization passes in 80.682 seconds after schema setup.
Median source-invalidation statement times in milliseconds:

| Matching projections | Original CURRENT update | Original already-STALE update |
|---|---:|---:|
| 1 | 1.184 | 0.982 |
| 100 | 148.472 | 224.851 |
| 2,500 | 3,991.157 | 3,961.054 |

Every repeated save rewrites the full matching count. Worker pass median is
132.321 ms; claim-to-return median 121.255 ms, observed maximum 162.318 ms;
all five passes execute 120 queries. Same-loan waiting is demonstrated under an
injected pause; unrelated loan locking succeeds and the competitor selects zero.

The tested separate-lock/CURRENT-only-update trial records 9,015.596 ms for first
invalidation and 3,832.788 ms for repeated invalidation at 2,500 rows. That does
not demonstrate a useful improvement and worsens the first change. The trial is
removed; [risk_signals.py](../../apps/tenant_apps/loans/risk_signals.py) remains
unchanged. A CURRENT-only update without locking stale rows is unsafe: the late
source-change regression would miss a worker about to publish CURRENT.

The actual supported policy-amendment service reproduces a deadlock against a
worker after its final fingerprint check. Policy insertion's database guard and
service hold Workspace FOR UPDATE while waiting for the worker's snapshot. The
worker holds that snapshot while appending a STATUS_CHANGED transition, whose
Workspace foreign key needs KEY SHARE. PostgreSQL aborts one transaction.

Change that policy parent lock to FOR NO KEY UPDATE in both service and guard.
It remains exclusive against other policy writers and lifecycle/ownership
FOR UPDATE operations, while allowing KEY SHARE foreign-key checks. No worker
lock, source invalidation or immutability rule changes. Migration 0086 replaces
only that statement and has an exact reverse; it branches from deployed 0084.
Joining no-op 0087 keeps the complete checkout graph valid without making 0086
depend on undeployed financial corrections. See the
[decision](../adr/2026-10-16-measured-monitoring-invalidation.md).

The focused **11-case lock/migration/concurrency selection passes** in **76.615
seconds**. It includes both late source races, competing workers/amendments,
foreign/unset RLS context, isolated per-loan commits, concurrent closure, unchanged
policy evidence and exact reversal of the populated guard migration.

Real receipt/reversal characterization passes. A receipt with ordinary completed
monthly-charge catch-up issues seven per-loan invalidations (5.139 ms total in the
focused sample); reversal issues three (1.720 ms). Monitoring refresh itself adds
no financial events. An intermediate receipt-count assertion incorrectly assumed
servicing would add only the receipt; the corrected test accounts for the existing
catch-up and checks monitoring independently. No servicing calculation is changed.
The policy deadlock was separately reproduced with the original invalidation
mechanism and supported amendment service before the lock-mode fix.

The final **277-case affected regression passes** in **758.874 seconds**, including
the populated historical-upgrade rehearsals. Focused and broader selections
overlap; their counts must not be added. Coverage includes all current valuation
methods, scheduled evidence/day rollover, independent financial reads, errors and
non-cure, bronze rates, correction lineage, immutable risk evidence, capture/book
reviews, dashboards, policy immutability and adversarial restricted-role isolation.

In this final run, 2,500-row CURRENT invalidation has a median of **4,240.335 ms**;
already-stale invalidation **4,107.076 ms**. The single-item worker pass median is
**106.066 ms**, claim-to-return median **97.040 ms**, observed maximum **155.501 ms**;
all five passes still execute **120 queries**. Receipt/reversal invalidate seven/
three times respectively, with **5.631/2.068 ms** summed invalidation statement
time. Different runs vary; no production performance guarantee follows.

Django system and migration consistency checks pass, with no unintended model
change. Tracked/new-source import boundaries, documentation links and whitespace
checks pass (1,574 local links in 63 curated files). The smaller default regression
mode separately passes in 9.083 seconds; its coverage overlaps the broader run.
Migration graph inspection confirms 0086 excludes pending financial corrections,
and final function readback confirms the narrower installed guard. The exact
isolated test database is removed; absence and measurement-role cleanup are
verified. No ordinary development or production data is changed.

This completes LS-06 locally. All six implementation slices await a coordinated
release; the retained pending corrections and unrelated work are not implicitly
authorized for deployment by these test results.

## Source-change contract

| Source change | Existing invalidation / currentness boundary |
|---|---|
| Loan dates/state/terms and ordinary saves | Loan signal; ACTIVE results invalidated, closed loans excluded from current portfolio |
| Financial events, schedule versions, obligations, allocations and schedule changes | Per-loan post-save signals inside the posting transaction |
| Collateral measurements/custody and appraisals | Item/appraisal signals; reappraisal additionally invalidates explicitly |
| Rate creation, supersession or withdrawal | Existing broad same-Workspace invalidation includes applicable old/new metal signatures and assessment dates |
| Monitoring policy creation/amendment | Existing Workspace/licence and assessment-period invalidation; narrower parent lock preserves writer serialization and avoids the reproduced FK cycle |
| Agreement/checkpoint/collateral corrections that use bulk updates | Explicit invalidation in the correction service; retain correction/source lineage |
| Book review and future capture choice | Explicit invalidation in the review storage service |
| New day, obsolete calculation contract or scheduled evidence becoming applicable | Shared currentness predicate excludes the projection without requiring a source save |
| Failure, competing worker or concurrent closure | Existing error/state/fingerprint/claim checks; never treat failure as healthy or duplicate a committed projection |

Relevant signals are in `risk_signals`; explicit invalidations remain in
`agreement_corrections`, `opening_corrections`, `collateral_corrections`,
`collateral_reappraisal` and `transaction_reviews`. Raw SQL, QuerySet updates and
bulk creation do not emit post-save signals. New supported mutation paths must
provide equivalent atomic invalidation; a fingerprint checked only during refresh
does not itself invalidate a previously saved current result.

Tests verify source/invalidation rollback together and a simulated unavailable
monitoring table prevents the source commit. This preserves the existing storage
dependency. It is not a claim that recording a real receipt requires usable
collateral evidence: evidence-unavailable calculations and database availability
are different concerns.

## Scope limits and next operational step

No worker/revision rewrite is warranted by this bounded workload. The measured
policy lock cycle is corrected with the narrower parent lock. Existing
same-loan waits are real; long histories, overlapping broad writes and foreground
servicing still need representative measurements before choosing another design.
The initial CURRENT fan-out remains proportional to affected loans. These local
measurements are not production timings or acceptance of the separately shelved
[FW-004 capacity programme](../plans/future-work.md#fw-004-launch-scale-loan-monitoring-capacity).

All LS slices require coordinated application release and matching V11 readers;
local completion does not establish deployment. Do not include undeployed
financial corrections or unrelated changes accidentally. Review the actual release
candidate, schema compatibility, backup/recovery and staff acceptance separately.
