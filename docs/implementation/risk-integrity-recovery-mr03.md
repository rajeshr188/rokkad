---
status: active
owner: loans
updated: 2026-10-11
tags: [implementation, monitoring, risk, tests]
---

# MR-03 financial integrity and alert recovery

The [accepted decision](../adr/2026-10-11-risk-integrity-and-confirmed-recovery.md)
implements the next correctness slice of the
[combined plan](../plans/combined-loan-monitoring-20261011.md).

## Changes

Exposure identifies missing schedules for active unsettled loans or unpaid positions and negative debt in
addition to its existing over-allocation/principal/component checks. DPD refuses
inconsistent obligations instead of netting negative components into plausible
amounts. Live risk and saved assessment both reject integrity findings. Prepared
exposure is reused in the scoped/date-checked risk selector; collateral retains
independent value evidence but blocks LTV on an inconsistent debt basis.
Cancelled zero-debt renewal positions remain valid without an active schedule.

Failed saved attempts clear unsafe current metrics, identify UNKNOWN performance
and retain financial diagnostics under ERROR. Successful missing-valuation
assessments remain distinct from failed financial calculations. The V7 contract
makes older saved projections outdated; no schema migration or source-history
rewrite is required.

LTV escalation no longer creates a false cure. Alerts stay open while their
condition is unknown or assessment failed. Known continuing risk updates the
same alert's severity, preserving its original source. Genuine resolution retains
the corresponding event, with a current confirmation event when a retained alert
has no matching old flag. A predecessor event ID distinguishes later identical
incidents; repeating the unchanged current projection creates no extra incident.

## Validation

The 29 focused classification/transition/DPD/orchestration checks and seven
additional notice/dispatch boundary checks pass, without outbound communication.
Integration ran in a frozen source snapshot and guarded disposable
`test_rokkad_mr03_20261011` database. It covers real reappraisal escalation,
freshness expiry, financial-integrity failure, metric clearing, dashboard exclusion,
recovery references, same-day recurrence with a fixed clock, source immutability,
restricted worker/context regressions and native/paper/imported servicing.

The broad run passed 203 runnable cases and found one compatibility regression:
a cancelled, fully reversed renewal successor was incorrectly required to have
an active schedule. Narrowing the missing-schedule guard preserves that valid
zero-debt position. The affected integration rerun passed 58 cases; its additional
real-payment test exposed a fixture assumption about paying only posted debt.
Using the ordinary current servicing balance also covers interest due since the
last posting. The final 34-case focused/integration rerun passes, including actual
payment, zero DPD and the linked DELINQUENCY_CURED event. Initial failing source
and fixture copies are retained separately from the final tested snapshot.

All 16 candidate Python files match the final tested source and pass syntax,
import-boundary and diff checks. The tracked application import check also passes
for 1,125 Python files. The disposable test database is removed; documentation
links are checked with the other pending documentation changes.

The independently running review app and shared/production databases remain
unchanged. No production worker or policy is enabled. MR-04 database reference
and immutable-event protection remains next before valuation/worker rollout.
