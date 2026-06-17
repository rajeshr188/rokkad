---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Schema Migration Drift Report

Date: 2026-05-01
Environment: local
Command source: tenant schema introspection + migration recorder scan

## Executive Summary

Two tenant schemas are currently drifting and block full migrate_schemas runs:

1. rameshjewellery
2. test

Both have a girvi legacy structure mismatch where girvi_loan.status is missing, which breaks newer girvi data migrations.

## Findings by Schema

### public
Status: OK for tenant-app migration ordering
Notes:
- girvi_loan table missing in public (expected for tenant-scoped models)
- girvi_repledgedloanitem missing in public (expected)

### jsk
Status: OK

### rameshjewellery
Status: DRIFT
Issues:
- girvi_loan missing column status
Warnings:
- girvi_repledgedloanitem missing (can be expected on some legacy schemas)

### lakshmipawnbroker
Status: OK

### test
Status: DRIFT
Issues:
- girvi_loan missing column status
Warnings:
- girvi_repledgedloanitem missing (can be expected on some legacy schemas)

### jcl
Status: OK

## Already Repaired in This Session

1. Fixed migration dependency inconsistency:
- sales.0001_initial had been applied before product.0002_initial in drifted schemas.
- product.0002_initial was recorded as applied for:
  - rameshjewellery
  - test

2. Bridged girvi branch marker:
- girvi.0002_initial was recorded for:
  - rameshjewellery
  - test

3. Hardened a custody migration against missing legacy table:
- apps/tenant_apps/girvi/migrations/add_custody_tracking.py
- Added table-existence guard before reading girvi_repledgedloanitem.

## Current Blocker

Full migrate_schemas still fails in rameshjewellery (and likely test later) at girvi legacy data migration path due missing girvi_loan.status.

## Practical Next Steps

1. For normal development, migrate only active schema:
- py manage.py migrate_schemas --tenant --schema=jsk

2. For drifted legacy schemas, do targeted reconciliation before global migrate_schemas:
- Option A: schema-specific fake bridging for legacy girvi migrations where data already exists in compatible form
- Option B: add defensive guards in specific legacy data migrations that assume columns/tables not present in old tenants
- Option C: archive/decommission legacy tenant schemas if no longer used

3. After reconciliation of drifted schemas, rerun:
- py manage.py migrate_schemas

## Recommendation

Treat rameshjewellery and test as migration-repair projects. Keep jsk, jcl, lakshmipawnbroker on standard migration flow.

## Resolution Applied (2026-05-01)

Per operator decision, drifted schemas were decommissioned instead of repaired:

- Removed tenant schema and row: rameshjewellery
- Removed tenant schema and row: test

Remaining tenant schemas:

- public
- jsk
- jcl
- lakshmipawnbroker

Post-cleanup verification:

- rameshjewellery schema: absent
- test schema: absent
- migrate_schemas: successful across remaining schemas

