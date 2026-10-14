---
status: active
owner: loans
updated: 2026-10-11
tags: [implementation, monitoring, risk, database, tests]
---

# MR-04 risk evidence guards

The [decision](../adr/2026-10-11-risk-evidence-database-protection.md) implements
the next correctness slice in the [combined plan](../plans/combined-loan-monitoring-20261011.md).

## Changes

Migration 0072 protects risk-event UPDATE/DELETE, snapshot and alert anchors,
matching Workspace/loan links and exact borrower-notice source bindings.
Snapshots still refresh, alerts still change severity and resolve, and notice
routing remains writable under the existing workflow. RLS stays forced.
No balances, original agreements, retained events or historical cures are rewritten.

The migration first checks retained snapshot/loan, event/snapshot, alert/source,
alert/recovery and notice/source relationships. The same count-only preflight is
available before migration:

```powershell
python manage.py check_risk_evidence --settings django_project.settings.migration
python manage.py migrate --settings django_project.settings.migration
```

The command uses a repeatable-read read-only transaction and rejects a restricted
role before reading tenant tables. Invalid reference counts block the migration;
legacy resolved alerts with no cure link are separately reported and preserved.
Live preflight and migration belong to the later coordinated release.

## Validation

Local validation is complete against frozen source in
`.tmp/mr04-review-20261011/source` and the guarded disposable
`test_rokkad_mr04_20261011` database. Adversarial DML runs as a non-superuser,
NOBYPASSRLS role with ordinary CRUD and sequence grants. Populated migration
rehearsals use independently created, uniquely named test databases; they never
downgrade the suite database or migrate the shared review/production database.

The first 127-case regression run passed 119 existing cases, including MR-03 real
payment/cure and recurrence, competing workers, denied Workspace turns, capture
transitions and transaction-reviewed notices. Eight new guard cases initially
stopped in a reused fixture: it needed distinct Workspace loan numbers, shared
standing monitoring policy, and explicit timestamps for raw notice insertion.
Those fixture corrections do not change production code. All eight guard cases
now pass, covering:

- QuerySet, bulk, raw and no-op event updates/deletes under a restricted role.
- Cross-Workspace and same-Workspace/wrong-loan references; paired notice
  pointers must match the alert's exact source, not merely any same-loan event.
- Fixed snapshot/alert/notice anchors, and an owner-with-bypass attempt to move
  a parent loan out of its snapshot's Workspace.
- Normal restricted reassessment, escalation, linked cure and notice-routing
  updates, with unchanged source financial events and no outbound communication.
- No-context denial, foreign-row invisibility, refusal of runtime preflight,
  and refusal of trigger removal/TRUNCATE privileges.
- A populated 0071-to-0072 upgrade preserving all snapshot/event/alert/notice
  values and a legacy resolution without a cure; event mutation is blocked.
- A separate populated upgrade with one violation in each of the five reference
  categories: preflight reports them, migration refuses before installing its
  guard/recording completion, and retained events remain unchanged.

Thus 127 regression cases are covered across the broad and corrected-fixture
runs. Initial fixtures are archived separately from the tested final source.
All five candidate Python files match frozen source; syntax, application import
boundaries and model/migration consistency pass. PostgreSQL metadata confirms all
five composite foreign keys are validated and immediate, all four existing
tables retain forced RLS, and the four guards use invoker privileges. The disposable
database is removed. All 1,310 local links in 42 curated/changed documents pass.

The shared review app, production schema and recorded business data remain
unchanged. Production cleanliness still requires the explicit owner-only live
preflight before the coordinated MR-06 release. MR-05 independent current
monitoring valuation is next; this slice does not start a monitoring worker or
change original valuation methods.
