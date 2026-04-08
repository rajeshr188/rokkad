Scan tenant app migrations for seeding

Searched for files matching `**/apps/**/migrations/*.py`, 20 matches

Searched for files matching `**/apps/**/migrations/*.py`, 98 matches

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/rates/migrations/0002_load_metal_rates.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/migrations/0018_create_default_roles.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/notify/migrations/0003_seed_default_notice_types.py#1-1), lines 1 to 100

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/dea/migrations/0002_initial_fixture.py#1-1), lines 1 to 150

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/dea/migrations/0009_seed_girvi_payment_vouchertypes.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/dea/migrations/0010_seed_girvi_release_vouchertype.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/dea/migrations/0012_seed_expense_vouchertypes.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/dea/migrations/0014_seed_expense_ledgers.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/migrations/0003_auto_fixture.py#1-1), lines 1 to 150

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/girvi/migrations/0005_migrate_loan_data_to_givenloan_takenloan.py#1-1), lines 1 to 100

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/notify/migrations/0003_seed_default_notice_types.py#100-100), lines 100 to 200

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/dea/migrations/0002_initial_fixture.py#150-150), lines 150 to 300

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/onboarding/migrations/0001_initial.py#1-1), lines 1 to 100

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/subscriptions/migrations/0001_initial.py#1-1), lines 1 to 100

Searched for regex `def seed|def insert|loaddata|bulk_create|objects.create|update_or_create` (`**/apps/**/migrations/*.py`), 66 results

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/terms/migrations/0002_auto_20230723_1647.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/girvi/migrations/add_custody_tracking.py#1-1), lines 1 to 150

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/girvi/migrations/0013_archive_loanpayments_to_paymentvoucher.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/migrations/0013_opening_balance_and_purchase_touch_nullable.py)

Read memory

Read [](file:///c%3A/Users/rajes/AppData/Roaming/Code/User/workspaceStorage/7914ab2b6b5df244df460c4b9f715f8d/GitHub.copilot-chat/chat-session-resources/088bc879-a95e-40b2-9df5-22797c039932/toolu_01XQTFX54ybppZoMFcedcGP1__vscode-1774588036600/content.txt#1-1), lines 1 to 100

Read [](file:///c%3A/Users/rajes/AppData/Roaming/Code/User/workspaceStorage/7914ab2b6b5df244df460c4b9f715f8d/GitHub.copilot-chat/chat-session-resources/088bc879-a95e-40b2-9df5-22797c039932/toolu_01XQTFX54ybppZoMFcedcGP1__vscode-1774588036600/content.txt#100-100), lines 100 to 250

Read [](file:///c%3A/Users/rajes/AppData/Roaming/Code/User/workspaceStorage/7914ab2b6b5df244df460c4b9f715f8d/GitHub.copilot-chat/chat-session-resources/088bc879-a95e-40b2-9df5-22797c039932/toolu_01XQTFX54ybppZoMFcedcGP1__vscode-1774588036600/content.txt#250-250), lines 250 to 400

Read [](file:///c%3A/Users/rajes/AppData/Roaming/Code/User/workspaceStorage/7914ab2b6b5df244df460c4b9f715f8d/GitHub.copilot-chat/chat-session-resources/088bc879-a95e-40b2-9df5-22797c039932/toolu_01XQTFX54ybppZoMFcedcGP1__vscode-1774588036600/content.txt#400-400), lines 400 to 546

Found **11+ data seeding migrations** across 8 tenant apps with mixed patterns (non-idempotent direct create, bulk_create, fixtures, update_or_create). Let me clarify your clone-schema strategy before planning the migration: 

Analyzing your answers...

Perfect. I'll create a comprehensive plan that handles **both** the new approach *and* refactoring existing migrations for clone-schema compatibility. 

Created memory file [](file:///c%3A/Users/rajes/AppData/Roaming/Code/User/workspaceStorage/7914ab2b6b5df244df460c4b9f715f8d/GitHub.copilot-chat/memory-tool/memories/MDg4YmM4NzktYTk1ZS00MGIyLTlkZjUtMjI3OTdjMDM5OTMy/migration-findings.md)

Now I'll create a comprehensive plan covering the new architecture + refactoring existing migrations: 

Created memory file [](file:///c%3A/Users/rajes/AppData/Roaming/Code/User/workspaceStorage/7914ab2b6b5df244df460c4b9f715f8d/GitHub.copilot-chat/memory-tool/memories/MDg4YmM4NzktYTk1ZS00MGIyLTlkZjUtMjI3OTdjMDM5OTMy/plan.md)

## Plan: Extract Data Seeding from Migrations to Management Commands + Fixtures

**TL;DR**: Move 11+ non-idempotent data seeding migrations → idempotent management commands + post-migrate signals + YAML fixtures. Enables clean clone-schema (DDL-only migrations) + global-updatable defaults. **Two phases: Build infrastructure, then refactor existing migrations.**

---

### Reference Documentation
See `/memories/session/plan.md` for complete implementation details.

---

## Steps Overview

### **Phase 1: Create Seeding Infrastructure** (Parallel-ready)

1. **Create fixture files** for static reference data:
   - `roles.yaml` (4 roles)
   - `account_chart.yaml` (70+ ledgers with MPPT hierarchy)
   - `product_catalog.yaml` (27 types, 40+ attributes, categories)
   - `notice_types.yaml` (50+ notification templates)
   - `metal_rates.yaml` (extract from existing fixture)
   - `terms_config.yaml` (extract from existing fixture)

2. **Create management command** `seed_tenant_defaults`
   - Idempotent: uses `loaddata` + `get_or_create` patterns
   - Loads all fixtures in dependency order (roles → chart → products → notices → rates)
   - Wrapped in `transaction.atomic()` for rollback safety
   - Flags: `--skip-roles`, `--skip-chart`, `--skip-products`, etc.

3. **Create post-migrate signal handler** (auto-seeding on deploy)
   - Checks if seeds exist (idempotent: no-op if already seeded)
   - Calls `seed_tenant_defaults` after first migration run
   - Lives in `django_project/signals.py` or `apps.py`

4. **Create batch command** `seed_all_tenants`
   - Backfill all existing tenants with defaults
   - Supports `--force` to re-seed, `--dry-run` to preview

### **Phase 2: Refactor Existing Migrations** (Delete non-idempotent, keep DDL-only)

| App | Action | Details |
|-----|--------|---------|
| **orgs** | **DELETE** 0018 | Roles seeded via fixture + signal |
| **product** | **Replace** 0003 | Keep DDL (CreateModel), move data to `product_catalog.yaml` |
| **dea** | **DELETE** 0002 | Chart seeded via `account_chart.yaml` + command |
| **dea** | **KEEP** 0009,0010,0012 | Already use `update_or_create()` (idempotent), mark as legacy |
| **notify** | **DELETE/Stub** 0003 | Notice types seeded via `notice_types.yaml` |
| **rates** | **KEEP** 0002 | Fixture-based, already documented |
| **terms** | **KEEP** 0002 | Fixture-based, already documented |
| **girvi** | **KEEP** ALL | Data transforms (not reference seeding), needed for existing tenants |

**New DDL-only migrations** to create:
- `orgs/0022_role_constraints.py` — Add UniqueConstraint on roles
- `product/0023_product_indexes.py` — Add performance indexes
- `dea/0015_dea_schema_only.py` — DDL equivalent of old 0002 (no data)
- `notify/0004_noticeconfig_indexes.py` — Indexes on notice configs

### **Phase 3: Integration & Validation**

1. **Update tenant creation flow** — Trigger `seed_tenant_defaults` on `Company.objects.create()`
2. **Create test suite** — `tests/test_seeding.py` with idempotency + data integrity tests
3. **Validate migrations** — Run clean migrate, verify seeding automatic
4. **Backfill existing tenants** — Run `seed_all_tenants --force`

### **Phase 4: Cleanup & Documentation**

1. **Remove deleted migrations** from git
2. **Create `TENANT_DATA_SEEDING.md`** — Architecture docs for team
3. **Create `FIXTURE_MAINTENANCE.md`** — How to update fixtures

---

## Relevant Files to Create/Modify

### **New Files (Phase 1)**:
- `apps/orgs/fixtures/roles.yaml`
- `apps/orgs/management/commands/seed_tenant_defaults.py`
- `apps/orgs/management/commands/seed_all_tenants.py`
- `apps/tenant_apps/dea/fixtures/account_chart.yaml`
- `apps/tenant_apps/product/fixtures/product_catalog.yaml`
- `apps/tenant_apps/notify/fixtures/notice_types.yaml`
- `django_project/signals.py` (or add to `apps.py`)
- `django_project/docs/TENANT_DATA_SEEDING.md`
- `tests/test_seeding.py`

### **Modify (Phase 2)**:
- **Delete**: `orgs/migrations/0018_create_default_roles.py`
- **Replace**: `product/migrations/0003_auto_fixture.py` → new DDL-only version
- **Delete**: `dea/migrations/0002_initial_fixture.py`
- **Delete/Stub**: `notify/migrations/0003_seed_default_notice_types.py`
- signals.py — Add trigger for `seed_tenant_defaults`
- base.py — Ensure FIXTURE_DIRS configured

### **Keep As-Is** (Already idempotent):
- `dea/0009, 0010, 0012` (update_or_create)
- `rates/0002, terms/0002` (fixture-based)
- All `girvi/*` migrations (data transforms)

---

## Verification Steps

**Phase 1 (Infrastructure)**:
1. ✅ `python manage.py seed_tenant_defaults --dry-run` → Lists actions
2. ✅ `python manage.py test tests/test_seeding.py` → All pass
3. ✅ Verify: `Role.objects.count() == 4`, `Ledger.objects.count() == 70`

**Phase 2 (Refactoring)**:
1. ✅ Drop DB, run `migrate` → DDL only, no data duplication
2. ✅ Create test tenant → Auto-seeded via signal
3. ✅ `seed_all_tenants --force` → Idempotent (counts unchanged)

**Phase 3 (Integration)**:
1. ✅ New tenant created → Defaults auto-seeded
2. ✅ Clone schema test → Both schemas identical post-seed

---

## Decisions & Key Assumptions

- **Clone schema approach**: DDL-only (structure copied, data seeded fresh) → allows shared defaults
- **Fixture strategy**: Mix (static data as YAML, complex logic in commands)
- **System vs. Tenant data**: Clear split (Roles+Chart+Vouchers = global, Products+Notices+Rates = per-tenant)
- **Keep girvi migrations**: They restructure existing tenant data, not reference seeding
- **Post-migrate signal**: Auto-seeds on first migrate (idempotent → safe to run multiple times)

---

## Further Considerations

1. **Natural Keys for Fixtures** → Needed for loaddata idempotency
   - Action: Verify/add `natural_key()` methods to Ledger, NoticeTypeConfig, etc. before Phase 1

2. **MPPT Tree Rebuild** → Account chart uses nested sets
   - Action: Call `Ledger.objects.rebuild()` after loading `account_chart.yaml`

3. **Backward Compatibility** → Removing migrations from git won't break production
   - Reason: Old migrations already in `django_migrations` table, Django skips missing migrations
   - Action: Keep deleted migrations in branch history for reference

4. **Permissions Model** → Clarify if Role just stores name or also permissions
   - Action: Determine current permissions structure before Phase 1

---

**Ready to proceed?** Would you like to:
- Start **Phase 1** (create fixtures + commands)?
- Ask clarifying questions on any phase?
- Adjust scope (e.g., refactor only most critical migrations first)?