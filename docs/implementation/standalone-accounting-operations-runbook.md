---
status: active
owner: project
updated: 2026-08-07
tags: [accounting, operations, diagnostics, recovery, k7]
related: [../plans/standalone-accounting-k7-production-boundary.md]
---

# Standalone Accounting MVP Operations Runbook

## Routine Integrity Check

Run against one tenant only:

```powershell
python manage.py check_accounting_integrity --schema <tenant_schema> --json
```

An empty JSON array is a pass. Findings cover posted/batch relationships,
transaction subtypes, fingerprints, actor evidence, trial balance, balance
sheet, external classification reconciliation, open-item capacity, and failed
source deliveries. The command is read-only and exits unsuccessfully when it
finds any problem.

## Finding Response

1. Stop standalone-accounting delivery for the affected tenant. DEA remains the
   production authority during K7, so do not switch authority or replay traffic.
2. Preserve the command output, source delivery identity, application logs, and
   a current tenant backup.
3. Do not edit posted vouchers, batches, allocations, transition evidence, or
   source delivery rows. Corrections use reversal/replacement services only.
4. For `FAILED_DELIVERY`, correct configuration or input and retry the exact
   same event. Changed payload requires a new source version.
5. For balance, fingerprint, subtype, actor, or over-allocation findings, stop
   and escalate for code/database investigation before any retry.
6. Re-run diagnostics and retain the passing output with the incident record.

## Recovery Rehearsal

In a controlled environment with sufficient database capacity:

```powershell
python manage.py rehearse_accounting_schema_recovery `
  --schema <tenant_schema>
```

The command uses PostgreSQL `pg_dump` and `psql`, restores into a uniquely named
temporary `accounting_recovery_*` schema, compares every standalone-accounting
table count, runs integrity diagnostics, and removes the temporary schema even
on failure. It never writes the source schema. A passing rehearsal does not
authorize production traffic or DEA cutover.

## Deployment and Rollback

- Apply tenant migrations with `migrate_schemas --tenant`.
- Run integrity diagnostics before and after enabling any future caller.
- On failed posting, the adapter transaction leaves no partial voucher and the
  delivery remains failed for inspection/retry.
- Roll back caller enablement first. Do not reverse migrations containing
  retained accounting evidence without a separately approved data plan.
