# Tenant Seeding And Migration Extraction Runbook

Date: 2026-03-29
Status: Phase A-E Complete
Owner: Platform Team

Related guide: `TENANT_PROVISIONING_AND_SEEDING_GUIDE.md`

## Goal

Separate baseline data seeding from migrations so migrations stay schema-focused.
For new tenant onboarding, create tenant schema then run explicit seeding so every tenant starts from the same baseline.

## Architecture Boundaries

### Public Schema Scope
- App source: `apps.orgs` in `SHARED_APPS`
- Seed command: `seed_public_defaults`
- Baseline examples: roles, shared permissions

### Tenant Schema Scope
- App source: `apps.tenant_apps.*` in `TENANT_APPS`
- Seed command: `seed_tenant_defaults --schema <schema_name>`
- Baseline examples: DEA account/chart defaults, voucher types, tenant starter fixtures (terms, rates, product)

### Keep In Migrations
- Historical data transformation migrations that move existing production data between structures
- Example: legacy loan model split/migration in girvi

## Final Execution Sequence

### Phase A: Preparation And Inventory
1. Freeze new migration-based default seeding (`RunPython` default inserts).
2. Classify current migration seeding into:
- public schema defaults
- tenant schema defaults
- historical transforms
3. Define canonical baseline tenant for parity checks.

### Phase B: Build Seeding Layer
1. Create `seed_public_defaults` command.
2. Create `seed_tenant_defaults` command.
3. Create `seed_all_tenants` command.
4. Reuse existing idempotent command paths where possible (`seed_core_ledgers`).
5. Ensure every command supports safe reruns.

### Phase C: Integrate Tenant Bootstrap
1. Tenant creation path: create/clone schema.
2. Immediately run `seed_tenant_defaults` on that schema.
3. Run post-seed validations.

### Phase D: Backfill Existing Tenants
1. Run `seed_all_tenants --dry-run`.
2. Execute actual batch seeding.
3. Validate parity against baseline tenant.

### Phase E: Refactor Legacy Migration Seeding
1. Convert migration seeding paths to legacy no-op/stub where safe.
2. Keep historical transform migrations intact.
3. Validate fresh migrate from empty DB.

### Phase F: Optional Squash After Stability
1. Wait at least one stable release cycle.
2. Squash schema migrations only.
3. Confirm no data seeding logic is reintroduced in squashed migrations.

## Go-Live Acceptance Criteria
1. New tenant onboarding is clone/create plus explicit seed.
2. No required baseline defaults depend on migration side effects.
3. Re-running seed commands does not duplicate records.
4. Public and tenant seeding responsibilities remain isolated.

## Implementation Tracking

### Completed
- Added runbook and phased sequence in this document.
- Added command scaffolds: `seed_public_defaults`, `seed_tenant_defaults`, `seed_all_tenants`.
- Added optional auto-seeding hook on `Company` create via `TENANT_AUTO_SEED_ON_CREATE` flag.
- Wired explicit onboarding seeding after schema provisioning in `apps/onboarding/views.py`.
- Added configurable onboarding clone mode (`ONBOARDING_TEMPLATE_CLONE_MODE`, default `NODATA`).
- Extracted DEA voucher-type migration seeds into `seed_tenant_defaults` (idempotent `update_or_create`).
- Added parity command: `check_tenant_seed_parity`.
- Executed backfill across all tenant schemas successfully (`seed_all_tenants`).
- Fixed product fixture encoding/content issues (UTF-16 + malformed transactional payload) and normalized it to UTF-8 canonical seed data.
- Added explicit product + notify seed manifests in `seed_tenant_defaults`.
- Added missing `Equity` account type to `seed_core_ledgers` to align with DEA canonical baseline.
- Converted migration-based tenant default seeders to legacy stubs/no-op:
	- `dea` (`0009`, `0010`, `0012`)
	- `notify` (`0003`)
	- `product` (`0003`)
	- `rates` (`0002`)
	- `terms` (`0002`)
- Updated parity command to canonical key-based validation and verified all tenant schemas pass with no drift.
- Added GitHub Actions smoke workflow with split modes:
	- PR fast smoke: bootstrap and seed target tenant
	- Push full smoke: bootstrap baseline + target tenants and enforce parity checks
	- File: `.github/workflows/tenant-seed-smoke.yml`

### Next
- Optional: reduce fixture-based terms/rates seeding to explicit Python manifests if fixture lifecycle control is needed.

## Initial Commands (Implemented)

- Public seed:
	- `python manage.py seed_public_defaults`

- Single tenant seed:
	- `python manage.py seed_tenant_defaults --schema <tenant_schema>`

- All tenants seed:
	- `python manage.py seed_all_tenants`
	- `python manage.py seed_all_tenants --dry-run`

- Parity check against baseline tenant:
	- `python manage.py check_tenant_seed_parity --baseline-schema <schema>`
	- `python manage.py check_tenant_seed_parity --baseline-schema <schema> --fail-on-drift`

## Feature Flag

- Setting: `TENANT_AUTO_SEED_ON_CREATE`
- Default: `False`
- Behavior:
	- When `True`, creating a new `Company` triggers `seed_tenant_defaults --schema <schema_name>` after transaction commit.
	- When `False`, seeding remains manual/operational.
