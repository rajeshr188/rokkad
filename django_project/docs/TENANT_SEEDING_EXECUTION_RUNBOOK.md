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

## Phase F Checklist (Squash Execution)

### Go/No-Go Gates
1. No pending hotfixes touching migration graph.
2. Seed commands are canonical for baseline data (`seed_public_defaults`, `seed_tenant_defaults`).
3. Parity checks are green on representative tenants.
4. CI smoke workflow is green for bootstrap + seed + parity.
5. Team agrees on a short migration freeze window.

### Pre-Squash Preparation
1. Create a dedicated branch for squash work.
2. Snapshot current migration graph and applied state in staging/prod.
3. Identify migrations to preserve as historical transforms (do not squash away business-critical transforms).
4. Ensure migration-based baseline seeders are already no-op/stub where intended.
5. Take a database backup from staging before test rehearsal.

### Squash Steps
1. Generate squashed migrations per app boundary (schema-only focus).
2. Keep dependency graph deterministic across shared and tenant apps.
3. Review squashed files manually:
- remove accidental seed inserts
- keep only schema operations and required transforms
4. Mark replaced migrations with `replaces = [...]` where applicable.
5. Keep old migrations in repository until all active environments pass transition.

### Validation Matrix (Required)
1. Fresh database bootstrap:
- migrate shared + tenant schemas
- run `seed_public_defaults`
- run `seed_tenant_defaults --schema <new_schema>`
- run parity check with `--fail-on-drift`
2. Existing upgraded database:
- migrate from current head to squashed head
- validate no destructive drift in tenant data
3. Onboarding flow:
- create/clone tenant
- ensure seed path executes and new tenant passes parity
4. CI:
- ensure PR fast smoke and push full smoke both pass.

### Rollout Strategy
1. Deploy squashed migrations first to staging.
2. Run full tenant parity checks in staging.
3. Deploy to production in low-traffic window.
4. Monitor migration runtime and error logs.
5. Keep rollback plan ready (backup restore + prior release artifact).

### Post-Rollout Cleanup
1. After one stable cycle, remove superseded old migration files.
2. Re-run full parity checks across tenants.
3. Update architecture docs and onboarding runbooks with new baseline migration point.

## Phase F Candidate Matrix

### Convert To Command / Remove From Baseline Path
- `apps/tenant_apps/dea/migrations/0002_initial_fixture.py`
	- Current role: seeds DEA baseline masters + ledgers.
	- Phase F target: remove baseline seeding from migration path and keep DEA seeding in `seed_core_ledgers` / `seed_tenant_defaults`.
- `apps/orgs/migrations/0018_create_default_roles.py`
	- Current role: seeds default roles.
	- Phase F target: move baseline ownership fully to `seed_public_defaults`.

### Already Converted To No-Op (Good Candidates To Disappear In Squash)
- `apps/tenant_apps/dea/migrations/0009_seed_girvi_payment_vouchertypes.py`
- `apps/tenant_apps/dea/migrations/0010_seed_girvi_release_vouchertype.py`
- `apps/tenant_apps/dea/migrations/0012_seed_expense_vouchertypes.py`
- `apps/tenant_apps/notify/migrations/0003_seed_default_notice_types.py`
- `apps/tenant_apps/product/migrations/0003_auto_fixture.py`
- `apps/tenant_apps/rates/migrations/0002_load_metal_rates.py`
- `apps/tenant_apps/terms/migrations/0002_auto_20230723_1647.py`

### Keep As Historical Data Transforms
- `apps/tenant_apps/girvi/migrations/0005_migrate_loan_data_to_givenloan_takenloan.py`
- `apps/tenant_apps/girvi/migrations/0013_archive_loanpayments_to_paymentvoucher.py`
- `apps/tenant_apps/girvi/migrations/add_custody_tracking.py`
- `apps/tenant_apps/product/migrations/0006_attribute_filterable_in_dashboard_and_more.py`
- `apps/tenant_apps/product/migrations/0014_pricing_constraints_and_resolver_hardening.py`

### Keep As Schema/Infrastructure Migrations
- `apps/tenant_apps/dea/migrations/0003_create_ledger_balance_view.py`
- `apps/tenant_apps/product/migrations/0004_auto_views.py`
- `apps/tenant_apps/product/migrations/0011_pr6_unified_balance_views.py`
- `apps/orgs/migrations/0001_initial.py`
	- Note: keep `hstore` extension setup until product historical HStore usage is eliminated from baseline migration path.

### Safe Early Squash Candidates
- `accounts`
- `pages`
- `apps/onboarding`
- `apps/subscriptions`

### Deferred Squash Candidates
- `apps/tenant_apps/dea`
- `apps/tenant_apps/girvi`
- `apps/tenant_apps/product`
- `apps/orgs`

## App-By-App Squash Sequence

### Wave 1: Low-Risk Schema-Only Apps
1. `accounts`
2. `pages`
3. `apps/onboarding`
4. `apps/subscriptions`

Execution notes:
- These apps are the safest first batch because they are largely schema-only.
- Squash them together or in parallel if migration dependencies remain isolated.
- Validation after Wave 1:
	- fresh migrate on empty database
	- existing database upgrade rehearsal
	- smoke login and onboarding entry paths

### Wave 2: Public-Schema Support Apps With Limited Data Concerns
1. `apps/orgs` preparation only, not squash yet
2. `apps/tenant_apps/terms`
3. `apps/tenant_apps/rates`
4. `apps/tenant_apps/notify`

Execution notes:
- `terms`, `rates`, and `notify` have seed migrations already converted to no-op, so they are good early tenant-app squash candidates.
- `orgs` should not be squashed in this wave; only prepare it by ensuring `seed_public_defaults` is the sole baseline source for roles/permissions.
- Validation after Wave 2:
	- `python manage.py seed_public_defaults`
	- `python manage.py seed_tenant_defaults --schema <test_schema>`
	- parity check on a newly created tenant schema

### Wave 3: Product Hardening Before Squash
1. `apps/tenant_apps/product` prep

Required prep before squash:
- Remove remaining dependency on historical HStore baseline path.
- Separate schema/view migrations from historical data repair logic.
- Preserve required data transforms such as attribute-link copy and pricing dedupe as explicit historical migrations or one-time upgrade scripts.

Go/no-go for product squash:
- no unresolved HStore dependency in baseline migration path
- inventory views recreated correctly on fresh install
- pricing and stock balance validations pass on upgrade rehearsal

### Wave 4: DEA Hardening Before Squash
1. `apps/tenant_apps/dea` prep

Required prep before squash:
- Move baseline DEA seeding fully out of `0002_initial_fixture.py` into command-only path.
- Keep ledger/account balance view creation as schema/infrastructure in squashed baseline.
- Confirm fresh tenant bootstrap works with:
	- migrate
	- `seed_tenant_defaults`
	- parity check

Go/no-go for DEA squash:
- `seed_core_ledgers` and `seed_tenant_defaults` reproduce complete DEA baseline
- fresh install does not depend on migration-side seed data
- ledger views build correctly on empty database and upgraded database

### Wave 5: Girvi Final Historical-Transform Wave
1. `apps/tenant_apps/girvi`

Required prep before squash:
- Preserve business-critical historical transforms:
	- loan restructure migration
	- archived loan payment migration
	- custody/repledge migration
- Confirm DEA dependencies referenced by Girvi transforms are stable in post-squash graph.

Go/no-go for girvi squash:
- upgrade rehearsal on database containing legacy loan records
- posting, payment archive, and custody history verified
- no broken cross-app dependency with DEA squashed migrations

### Wave 6: Orgs Final Public-Schema Cleanup
1. `apps/orgs`

Required prep before squash:
- keep or relocate extension setup only where still required by active historical migrations
- remove role/default baseline dependence from migration path
- confirm invitations, memberships, domains, and workspace ownership upgrade cleanly

Go/no-go for orgs squash:
- public schema bootstrap succeeds from empty database
- default roles come only from `seed_public_defaults`
- invitation and membership flows still work after upgrade rehearsal

## Recommended Overall Order
1. Wave 1: `accounts`, `pages`, `apps/onboarding`, `apps/subscriptions`
2. Wave 2: `apps/tenant_apps/terms`, `apps/tenant_apps/rates`, `apps/tenant_apps/notify`
3. Wave 3: prepare and squash `apps/tenant_apps/product`
4. Wave 4: prepare and squash `apps/tenant_apps/dea`
5. Wave 5: squash `apps/tenant_apps/girvi`
6. Wave 6: squash `apps/orgs`

## Stop Conditions
1. Any fresh-install migration error on empty database.
2. Any upgrade drift between current head and squashed head.
3. Any tenant parity regression after seed commands.
4. Any broken cross-app dependency between DEA, Girvi, Product, and Orgs.

## Per-App Checklist Matrix

| App | Target Wave | Status | Main Blockers | Prep Needed |
| --- | --- | --- | --- | --- |
| `accounts` | 1 | Safe now | None identified | Fresh install + upgrade rehearsal |
| `pages` | 1 | Safe now | None identified | Fresh install check |
| `apps/onboarding` | 1 | Safe now | None identified | Verify onboarding entry flow after squash |
| `apps/subscriptions` | 1 | Safe now | None identified | Fresh install + subscription flow smoke |
| `apps/tenant_apps/terms` | 2 | Low risk | Historical seed migration retained as noop | Verify command-based fixture load only |
| `apps/tenant_apps/rates` | 2 | Low risk | Historical seed migration retained as noop | Verify command-based fixture load only |
| `apps/tenant_apps/notify` | 2 | Low risk | Historical seed migration retained as noop | Verify notice defaults come from `seed_tenant_defaults` |
| `apps/tenant_apps/product` | 3 | Deferred | HStore legacy path, views, data repair migrations | Remove HStore baseline dependency, preserve transforms, verify views |
| `apps/tenant_apps/dea` | 4 | Deferred | `0002` still seeds baseline, views, ledger bootstrapping history | Move baseline ownership fully to commands, preserve view migrations |
| `apps/tenant_apps/girvi` | 5 | Deferred | Historical business data transforms and DEA coupling | Rehearse upgrade with legacy data and preserve transforms |
| `apps/orgs` | 6 | Deferred | Public-schema defaults in migration, extension compatibility, tenant bootstrap coupling | Make `seed_public_defaults` canonical and verify invitation/workspace flows |

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
