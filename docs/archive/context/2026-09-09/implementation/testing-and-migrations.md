---
status: archived
owner: project
updated: 2026-06-17
tags: [implementation, testing, migrations]
related: [../plans/backlog.md, ../archive/root/SCHEMA_MIGRATION_DRIFT_REPORT_2026-05-01.md]
---

> Historical snapshot from docs/implementation/testing-and-migrations.md before the 2026-09-09 documentation cleanup.
> Old priorities and architecture statements are preserved as evidence, not current instructions.
> Use [current documentation](../../../../README.md) first.


# Testing And Migrations

## Testing Focus

- Architecture import tests for facade boundaries.
- Posting rule registration tests for DEA voucher types.
- Period-lock tests inside posting engine paths.
- Girvi lifecycle command tests around disbursal, repayment, release, renewal, auction, sale, and undo.
- Tenant setup tests for required seeds and visible recovery paths.

## Migration Focus

- Prefer named constraints over legacy anonymous uniqueness.
- Treat schema drift reports as risk inputs before changing tenant schemas.
- Keep data migrations reversible or documented when reversibility is not practical.

Source drift report: [SCHEMA_MIGRATION_DRIFT_REPORT_2026-05-01](../../../root/SCHEMA_MIGRATION_DRIFT_REPORT_2026-05-01.md).
