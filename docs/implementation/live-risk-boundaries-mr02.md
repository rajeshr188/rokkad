---
status: active
owner: loans
updated: 2026-10-11
tags: [implementation, monitoring, risk, tests]
---

# MR-02 live assessment safeguards

The [combined plan](../plans/combined-loan-monitoring-20261011.md) starts with
revalidation and narrow safeguards before policy changes or worker activation.
The [date/failure decision](../adr/2026-10-11-live-risk-assessment-boundary.md)
preserves the existing single live snapshot and explicit Workspace worker.

## Local changes

- The snapshot writer, rebuild, batch and worker pass reject a non-today date.
  Single-loan success and error writes recheck after obtaining the loan lock.
- The command rejects a non-today explicit `--as-of` before any turns. It reports
  expected access denial for one Workspace and continues the remaining turns;
  one-shot partial failure still exits unsuccessfully.
- Refresh screens catch invalid calendar dates as well as malformed strings and
  show the specific live-date rejection. Routine forms submit without a rendered
  hidden date so the request uses the server's current local date.
- Existing fixture dates now simulate actual date rollover when testing a later
  live refresh. Historical read-only selector behavior remains available.

## Validation

Validation uses a frozen source snapshot and the guarded
`test_rokkad_monitoring_20261011` disposable database, outside the shared review
database. The 22 focused checks pass. The 257-case broader run passed 255 cases;
two assertion failures were corrected and the 26-case final affected-class/extra
transfer acceptance rerun passes (280 cases covered across runs). One new test
used an unscoped count under the test owner role and counted another Workspace's
successful snapshot; it now explicitly checks the denied Workspace. An older
correction test expected bounded export to be refused, superseded by PC-06; it
now verifies the version-2 export retains both original payout/reversal IDs and
fingerprints, while retaining the exact-backup roundtrip. These changes do not
weaken domain guards. The commercial fixture uses the public access-policy API.

Tests cover past/future rejection with and without an existing snapshot,
unchanged financial/projection/event/alert evidence, a date change during success
or failure calculation, actual commercial access denial followed by another
Workspace's successful refresh, HTTP error handling, worker turn behavior and
restricted-role concurrency/isolation regressions.

All 12 candidate source/template files match the final tested snapshot and Python
syntax checks pass. Supported-app boundaries pass for 1,125 tracked Python files.
All 1,267 local links in 37 curated/changed documentation files pass. The
disposable test database is confirmed removed. No model or migration change is
required by MR-02.

No production policy, recurring worker or application release is changed.
Financial integrity/recovery semantics and database risk-evidence guards remain
the next slices; this date/failure fix does not make JCL's missing appraisal
evidence or unassessed loans disappear.
