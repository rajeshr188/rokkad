# Tenant Provisioning And Seeding Guide

Date: 2026-03-30
Audience: Engineering, DevOps, Support

## Purpose

This guide explains the complete tenant bootstrap lifecycle in this project:
- first deployment setup
- how template-schema cloning works
- how subsequent tenant provisioning works
- how tenant default seeding works
- how to extend seeding with additional datasets safely

This is the operational companion to the execution runbook.

## Architecture Summary

The platform uses schema-per-tenant with `django-tenants`:
- Public schema stores shared data (workspaces/companies, domains, roles, permissions).
- Tenant schemas store business data (`apps.tenant_apps.*`).

Seeding responsibilities are separated:
- Public defaults: `python manage.py seed_public_defaults`
- Tenant defaults (single schema): `python manage.py seed_tenant_defaults --schema <schema_name>`
- Tenant defaults (all schemas): `python manage.py seed_all_tenants`
- Drift validation: `python manage.py check_tenant_seed_parity --baseline-schema <schema_name>`

## Core Settings And Flags

Defined or used by the provisioning flow:
- `TENANT_AUTO_SEED_ON_CREATE` (default `False`): when enabled, new `Company` creation triggers automatic tenant seeding from signal.
- `ONBOARDING_TEMPLATE_SCHEMA`: optional schema name used as clone source during onboarding.
- `ONBOARDING_TEMPLATE_CLONE_MODE` (default `NODATA`): clone strategy passed to `CloneSchema`.

Recommended production default:
- `ONBOARDING_TEMPLATE_CLONE_MODE=NODATA`

Why: clone schema structure from template, then seed using explicit commands for deterministic baseline data.

## First Deployment Flow (Greenfield)

Use this flow when deploying the system the first time.

1. Run shared/public migrations.
2. Seed public schema defaults.
3. Create a template tenant schema (optional but recommended for clone-based onboarding).
4. Run tenant migrations on the template schema.
5. Seed tenant defaults into the template schema.
6. Optionally apply organization-specific baseline customizations to template.
7. Set onboarding clone settings.
8. Validate using parity checks and smoke tests.

### 1) Run Shared Migrations

```bash
python manage.py migrate_schemas --shared --noinput
```

### 2) Seed Public Defaults

```bash
python manage.py seed_public_defaults
```

This populates shared roles/permissions in public schema.

### 3) Create Template Tenant Schema

Create a template workspace in the public schema. You can do this from admin/onboarding, or from shell.

Example shell bootstrap:

```bash
python manage.py shell
```

```python
from django.contrib.auth import get_user_model
from django_tenants.utils import get_public_schema_name, schema_context
from apps.orgs.models import Company, Domain

User = get_user_model()

with schema_context(get_public_schema_name()):
    owner, _ = User.objects.get_or_create(
        username="template_owner",
        defaults={"email": "template-owner@example.com"},
    )

    template_company, _ = Company.objects.get_or_create(
        schema_name="template_base",
        defaults={
            "name": "Template Base",
            "owner": owner,
            "creator": owner,
        },
    )

    Domain.objects.update_or_create(
        domain="template_base.localhost",
        defaults={"tenant": template_company, "is_primary": True},
    )
```

### 4) Run Tenant Migrations On Template

```bash
python manage.py migrate_schemas --schema template_base --noinput
```

### 5) Seed Tenant Defaults Into Template

```bash
python manage.py seed_tenant_defaults --schema template_base
```

### 6) Optional Template Customization

If you need custom baseline defaults for all future tenants, apply them now in `template_base`.

Important:
- Keep customizations idempotent where possible.
- Prefer configuration/master records, avoid transactional data in template.

### 7) Configure Onboarding Clone

In environment configuration:

```env
ONBOARDING_TEMPLATE_SCHEMA=template_base
ONBOARDING_TEMPLATE_CLONE_MODE=NODATA
TENANT_AUTO_SEED_ON_CREATE=False
```

`TENANT_AUTO_SEED_ON_CREATE=False` is recommended because onboarding flow already calls explicit seeding right after provisioning.

### 8) Validate

Create two temporary schemas (baseline and target), seed both, and run parity:

```bash
python manage.py seed_tenant_defaults --schema ci_baseline
python manage.py seed_tenant_defaults --schema ci_target
python manage.py check_tenant_seed_parity --baseline-schema ci_baseline --schema ci_target --fail-on-drift
```

## Subsequent Tenant Provisioning User Flow

This is the runtime flow when a new workspace is created from onboarding.

1. User submits company setup form.
2. App enters public schema transaction.
3. `_provision_company_schema(company)` decides provisioning mode:
   - no template configured: fresh schema via normal tenant save
   - template configured and valid: clone from template via `CloneSchema().clone_schema(...)`
4. App immediately runs `_seed_company_schema_defaults(company)`.
5. Domain and owner membership are created.
6. Workspace is set active for user.
7. Onboarding step is marked complete and audit event is logged.

Implementation locations:
- Provisioning + explicit seed call: `apps/onboarding/views.py`
- Optional signal-based auto-seed path: `apps/orgs/signals.py`

## Seeding Internals

Tenant seeding command:
- `seed_tenant_defaults --schema <schema_name>`

Default actions currently include:
- DEA core ledgers via `seed_core_ledgers`
- DEA voucher types
- Terms fixture
- Rates fixture
- Product defaults (movement/category/product types/attributes)
- Notify defaults (`NoticeTypeConfig` presets)

All paths are designed for safe reruns:
- `update_or_create` or `get_or_create` is used for canonical records.
- Fixture loading is centralized and explicit.

Action control flags:
- `--skip-dea-core`
- `--skip-terms`
- `--skip-rates`
- `--skip-product`
- `--skip-notify`
- `--dry-run`

Batch operations:
- `seed_all_tenants` applies tenant seeding to all non-public schemas.
- Use `--continue-on-error` for long-running fleet backfills.

## How To Add New Seed Datasets

When introducing new baseline data for all tenants, follow this pattern.

1. Add idempotent seed logic to `apps/orgs/management/commands/seed_tenant_defaults.py`.
2. Add a skip flag if the dataset is operationally optional.
3. Prefer explicit Python manifests for stable canonical records.
4. If using fixtures, keep them UTF-8 and baseline-only (no transactional rows).
5. Update parity expectations in `apps/orgs/management/commands/check_tenant_seed_parity.py`.
6. Run local validation and backfill existing tenants.
7. Verify CI smoke workflow passes.

### Minimal Change Checklist

- Add new `_seed_<dataset>()` method with `get_or_create` / `update_or_create`.
- Wire method into action list in `handle()`.
- Add `--skip-<dataset>` option if needed.
- Add expected canonical keys to `EXPECTED_SEEDS` in parity command.
- Run:

```bash
python manage.py seed_tenant_defaults --schema <test_schema>
python manage.py seed_all_tenants --dry-run
python manage.py check_tenant_seed_parity --baseline-schema <baseline_schema> --fail-on-drift
```

## Operations Playbook

### A) Backfill Existing Tenants After Seed Changes

```bash
python manage.py seed_all_tenants --dry-run
python manage.py seed_all_tenants --continue-on-error
python manage.py check_tenant_seed_parity --baseline-schema <baseline_schema> --fail-on-drift
```

### B) Seed One Tenant Only

```bash
python manage.py seed_tenant_defaults --schema <schema_name>
```

### C) Public-Only Reseed

```bash
python manage.py seed_public_defaults
```

## CI Coverage

The workflow `.github/workflows/tenant-seed-smoke.yml` validates the flow in two modes:
- PR fast smoke: create target tenant, migrate, seed.
- Push full smoke: create baseline+target, migrate, seed, parity check with fail-on-drift.

This protects against regressions in tenant bootstrap and canonical seed completeness.

## Troubleshooting

### New tenant created but baseline defaults missing

Check:
- onboarding path executed `_seed_company_schema_defaults`
- seeding command logs for target schema
- no skip flags were passed unexpectedly

Fix:
- run `seed_tenant_defaults` manually for affected schema
- run parity command against baseline schema

### Duplicate defaults after reseed

Expected behavior should be no duplicates for canonical datasets.

Check:
- new dataset path uses idempotent writes
- fixture does not contain duplicate keys

### Drift detected by parity

Check:
- missing key list in command output
- canonical list in `EXPECTED_SEEDS`
- recently added seeds included in both command and parity map

## Design Guardrails

- Keep schema shape in migrations, not baseline data.
- Keep tenant baseline data in management commands.
- Keep seed logic idempotent and deterministic.
- Keep parity checks key-based, not count-based.
- Keep onboarding flow explicit: provision -> seed -> bind domain/membership.
