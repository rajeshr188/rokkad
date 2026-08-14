---
status: active
owner: architecture
updated: 2026-07-02
tags: [tenancy, django-tenants, postgresql, rls, architecture, migration]
related: [../AGENT_MEMORY.md, ../STATUS.md, ../constitution.md, testing-and-migrations.md, workspace-context.md, tenant-seeding.md]
---

# Tenancy Architecture Audit: `django-tenants` vs PostgreSQL RLS

This document records the July 2026 tenancy architecture review for Rokkad. It is not an accepted ADR. It is an implementation reference for future planning around whether Rokkad should continue with schema-per-tenant isolation through `django-tenants` or migrate toward shared-schema PostgreSQL Row Level Security.

## Executive Summary

Rokkad is currently a real `django-tenants` schema-per-tenant application, not a light workspace abstraction.

Facts found in code:

- [django_project/settings/base.py](../../django_project/settings/base.py) defines `SHARED_APPS`, `TENANT_APPS`, `TENANT_MODEL = "orgs.Company"`, `TENANT_DOMAIN_MODEL = "orgs.Domain"`, `django_tenants.postgresql_backend`, `TenantSyncRouter`, tenant file/static storage, tenant-aware cache keys, tenant-aware logging, `ROOT_URLCONF = "django_project.tenant_urls"`, `PUBLIC_SCHEMA_URLCONF = "django_project.urls"`, and `TenantAwareDiscoverRunner`.
- [apps/orgs/models.py](../../apps/orgs/models.py) uses `Company(TenantMixin)` as both the workspace/control-plane entity and the PostgreSQL schema tenant.
- [apps/orgs/models.py](../../apps/orgs/models.py) uses `Domain(DomainMixin)` for hostname-to-tenant mapping.
- [apps/orgs/middleware_v2.py](../../apps/orgs/middleware_v2.py) resolves workspace by domain/path/profile, validates membership/subscription, then calls `connection.set_tenant(workspace)`.
- Business apps live under `apps/tenant_apps/` and generally rely on schema isolation rather than explicit `workspace_id`.
- Accounting and period-close code explicitly reject public-schema execution through `connection.schema_name`.
- Tests, seed commands, background jobs, and tenant maintenance commands use schema switching and `migrate_schemas`.

Recommendation:

`Prepare hybrid migration and switch later`.

Shared-schema PostgreSQL RLS is the cleaner long-term fit for the SaaS ERP target: many small tenants, users belonging to multiple workspaces, workspace switching, workspace subscriptions, customer portal access, cross-tenant admin, and reporting/analytics. However, the current project is moderately to heavily embedded in `django-tenants`, so a direct full migration now would be risky.

## Current Implementation Map

| Area | File | Current behavior | Coupling to `django-tenants` | RLS migration difficulty |
|---|---|---|---|---|
| Settings | `django_project/settings/base.py` | Defines shared/tenant apps, tenant DB backend/router, URLConfs, storage, cache, logging, test runner | Tight | Hard |
| Tenant/workspace model | `apps/orgs/models.py` | `Company(TenantMixin)` is workspace and schema tenant | Tight | Medium |
| Domain model | `apps/orgs/models.py` | `Domain(DomainMixin)` maps hostnames to tenants | Tight | Medium |
| Middleware | `apps/orgs/middleware_v2.py` | Validates membership before `connection.set_tenant(workspace)` | Tight | Medium-hard |
| Public control plane | `apps/orgs/models.py`, `apps/subscriptions/models.py` | Memberships, invitations, subscriptions, audit live in shared/public apps keyed by `Company` | Low | Easy |
| URL routing | `django_project/tenant_urls.py`, `django_project/urls.py` | Tenant ERP routes are tenant URLConf; public control-plane routes are public URLConf | Medium | Medium |
| Workspace slug route-map | `apps/orgs/middleware_v2.py` | `/w/<workspace_slug>/...` resolves by `Company.schema_name` | Tight | Medium |
| Control-plane services | `apps/orgs/services/control_plane.py` | Workspace/team/invitation mutations run inside `schema_context(public)` | Tight | Medium |
| Onboarding provisioning | `apps/onboarding/views.py` | Creates or clones tenant schema, then seeds tenant defaults | Tight | Hard |
| Admin | `apps/orgs/admin.py` | Uses `TenantAdminMixin`; public-only checks depend on `request.tenant.schema_name` | Tight | Medium |
| Tests | `django_project/test_runner.py`, tenant app tests | Test setup uses `migrate_schemas`; many tests call `connection.set_tenant(self.tenant)` | Tight | Medium |
| DEA posting | `apps/tenant_apps/dea/posting/engine.py` | Posting engine refuses to run in public schema | Tight | Medium |
| DEA period close | `apps/tenant_apps/dea/models/period.py` | Period close refuses public schema | Tight | Medium |
| SQL views | DEA/Product migrations | `ledger_balances`, `account_balances`, `inventory_balance`, `stock_balance` are schema-local | Tight | Medium-hard |
| Tenant seed/maintenance | `apps/orgs/management/commands/`, tenant app commands | Commands use `schema_context`, `tenant_context`, `get_tenant_model`, schema names | Tight | Medium |
| Background work | `apps/tenant_apps/girvi/tasks.py`, `apps/tenant_apps/contact/tasks.py` | Girvi accrual supports a `schema` argument; Contact has Celery task stubs | Medium/unknown | Medium |

## Embeddedness Assessment

Classification: `Moderately to heavily embedded`.

Concrete signals:

- Most tenant business tables do not have `workspace_id` or `tenant_id`.
- Uniqueness currently relies on schema isolation. Examples include Party codes, ledger codes/names, product names/SKUs, voucher fingerprints, voucher/document numbers, commodity movement numbers, and loan numbers.
- Business views and services usually assume the active PostgreSQL schema is the tenant boundary.
- Onboarding provisions schemas and optionally clones from a template schema.
- Seed commands, parity checks, and tests are schema-aware.
- Reporting SQL views are created per tenant schema.
- Public/shared control-plane models are already close to an RLS target, but tenant-owned business models are not.

This means migration is possible, but only through a phased refactor. A big-bang conversion would put accounting integrity, reporting correctness, and customer data isolation at unnecessary risk.

## Current Pain Points

- `Company` carries product workspace identity and database schema identity at the same time.
- `Company.schema_name` is currently used as the `/w/<workspace_slug>/...` compatibility slug.
- Control-plane rows are shared/public while business rows are physically separated by schema.
- Cross-tenant admin and analytics require schema iteration or ETL.
- Tenant app migrations scale with tenant count.
- Background jobs must know schema context.
- Future customer portal domain strategies become harder because portal identity is tenant-local before workspace resolution.
- SQL reports cannot naturally aggregate across tenants.

## Comparison for Rokkad

| Concern | `django-tenants` | Shared schema + RLS | Better long-term fit |
|---|---|---|---|
| Many small businesses | Many schemas and repeated migrations | One table set keyed by workspace | RLS |
| Isolation strength | Strong namespace separation | Strong if policies/session variables/roles are correct | Tie |
| Current migration risk | Already running | High refactor and data migration cost | `django-tenants` short-term |
| Workspace switching | Switch schema/search path | Set current workspace context | RLS |
| Multi-workspace users | Works through public membership plus schema switching | Natural | RLS |
| Workspace subscriptions | Already public keyed by `Company` | Natural global `Workspace` FK | Tie/RLS |
| Team invitations | Already public keyed by `Company` | Natural | Tie |
| Customer portal | Tenant path works; public/branded portal harder | Easier with `workspace_id` plus `party_id` policies | RLS |
| Cross-tenant admin | Schema iteration | Direct cross-workspace query with explicit admin bypass | RLS |
| Reporting/analytics | Hard across schemas | Natural with workspace filters/grouping | RLS |
| Accounting engine | Simple schema-local assumptions | Easier consolidated reporting, but needs strict workspace propagation | RLS after refactor |
| Backup/restore | Per-schema backup is simpler | Per-workspace logical restore is harder | `django-tenants` |
| Deployment migrations | Per tenant schema | One shared migration | RLS |
| Developer productivity | No explicit tenant filters, but schema bugs | Explicit ownership and simpler global tooling | RLS long-term |

Opinionated conclusion: RLS is the better long-term product architecture, but not a safe immediate switch.

## Areas RLS Would Simplify

RLS/shared schema would simplify:

- Workspace switching: selected workspace becomes a row-level context, not a schema switch.
- Superadmin dashboards: direct queries across workspaces become practical.
- Reporting: accounting, inventory, commodity, and subscription analytics can group by workspace.
- Customer portal: portal policies can combine `workspace_id` and `party_id`.
- Onboarding: workspace creation becomes row creation plus workspace-scoped seed rows.
- Migrations: one migration set instead of per-tenant schema rollout.
- Testing: two workspaces can be tested in one schema with explicit isolation checks.
- Future API/mobile support: every request can carry current workspace context consistently.

RLS would introduce:

- Mandatory `workspace_id` on every tenant-owned row.
- Tenant-scoped uniqueness rewrites.
- Strict database role management; application role must not bypass RLS.
- Safe session-variable handling for pooled connections and background jobs.
- More tests proving fail-closed behavior.
- Careful design for materialized views/report tables.

## Target RLS Architecture

Global/control layer:

- User
- Workspace/Company
- WorkspaceMembership
- Role and permissions
- Invitation
- Subscription, Plan, BillingCustomer, BillingSubscription
- Domain or workspace slug
- Workspace setup state
- Audit log
- Feature flags/preferences

Tenant-owned business layer:

- Party, PartyRole, PartyContactMethod, PartyAddress, PartyIdentifier, PartyDocument, PartyRelationship, PartyPortalAccess
- Customer legacy bridge until deleted
- Ledger, Account, Voucher, VoucherLine, JournalEntry, LedgerTransaction, AccountTransaction
- AccountingPeriod, VoucherNumberSequence, LedgerCodeSequence, NumberingSequence
- PaymentVoucher, ExpenseVoucher, SalesInvoiceVoucher, PurchaseInvoiceVoucher, BusinessEventDraft
- Commodity, CommodityAccount, CommodityMovement, ExposureLine, RateFixing, RateFixingAllocation
- GivenLoan, TakenLoan, LoanItem, Release, LoanInterestAccrual, RepledgeHistory, Statement
- Product, ProductVariant, Category, ProductType, Attribute, Stock, StockItem, StockTransaction, StockStatement, pricing models
- Notify/Notify v2 operational rows
- Tenant-specific rates and templates

Every tenant-owned table should have:

- `workspace_id bigint NOT NULL REFERENCES orgs_workspace(id)`
- indexes beginning with `workspace_id` for hot paths
- tenant-scoped unique constraints
- RLS enabled
- policies for `SELECT`, `INSERT`, `UPDATE`, and restricted `DELETE`
- app-level RBAC checks above RLS

Example policy shape:

```sql
ALTER TABLE tenant_owned_table ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_owned_select ON tenant_owned_table
FOR SELECT
USING (workspace_id = current_setting('app.current_workspace_id')::bigint);

CREATE POLICY tenant_owned_insert ON tenant_owned_table
FOR INSERT
WITH CHECK (workspace_id = current_setting('app.current_workspace_id')::bigint);

CREATE POLICY tenant_owned_update ON tenant_owned_table
FOR UPDATE
USING (workspace_id = current_setting('app.current_workspace_id')::bigint)
WITH CHECK (workspace_id = current_setting('app.current_workspace_id')::bigint);
```

Middleware target:

- Resolve workspace from domain/path/selected workspace.
- Validate membership or portal grant before DB context is set.
- Set request attributes like `request.workspace`, not just `request.tenant`.
- Set database variables such as:
  - `app.current_workspace_id`
  - `app.current_user_id`
  - `app.current_party_id` for portal access
  - `app.access_mode` for ERP/portal/admin modes
- Reset/replace these values safely per request and per background job.

## Model Classification

Global models:

- `accounts.CustomUser`
- `accounts.UserProfile`
- `orgs.Company` after refactor to canonical Workspace identity
- `orgs.Domain`
- `orgs.Membership`
- `orgs.Role`, unless per-workspace custom roles are later introduced
- `orgs.CompanyInvitation`
- `orgs.PendingInvitation`
- `orgs.CompanyPreferenceModel`
- `orgs.AuditLog`
- `subscriptions.Plan`
- `subscriptions.Subscription`
- `subscriptions.Invoice`
- `subscriptions.Payment`
- `subscriptions.UsageMetrics`
- `subscriptions.PriceOverride`
- `onboarding.OnboardingProgress`
- `onboarding.OnboardingChoice`
- `onboarding.WorkspaceSetupState`

Tenant-owned models needing `workspace_id`:

- Party app models, including portal access grants.
- Contact legacy models until Party fully replaces Contact.
- Girvi loan, collateral, release, accrual, custody, event outbox, statement, template, and legacy compatibility models.
- DEA accounting, voucher, journal, ledger, account, period, payment, expense, invoice, commodity, audit, bank, reconciliation, asset, prepaid, and business event models.
- Product/catalog/inventory/price/attribute models.
- Notify and Notify v2 tenant operational models.
- Rates when rates are workspace-specific.

Ambiguous design decisions:

- `Commodity`: likely split later into global commodity definitions plus workspace-owned commodity accounts/configuration.
- `RateSource` and `Rate`: platform market rates can be global; shop-entered rates should be workspace-owned.
- Product catalog: currently best treated as workspace-owned; a future global catalog should be a separate product decision.
- Roles: current global roles are acceptable; custom workspace roles would require workspace ownership.

Legacy/refactor candidates:

- `contact.Customer` should continue being bridged into Party, then retired.
- Legacy `girvi.Loan` and `LoanPayment` should remain compatibility-only.
- `RepledgedLoanItem` is historical compatibility data.

## Constraint Rewrites Required

Examples of constraints that must become tenant-scoped under shared schema:

- `Party.party_code` -> unique per workspace.
- `PartyCodeSequence.key` -> unique per workspace.
- `Ledger.code` -> unique per workspace.
- `Ledger.name` and `Ledger(name, parent)` -> unique per workspace.
- `VoucherNumberSequence(voucher_type, period, date_key)` -> unique per workspace.
- `Voucher.fingerprint` active uniqueness -> unique per workspace.
- `Voucher(doc_content_type, doc_object_id, voucher_type)` active posted uniqueness -> include workspace.
- `AccountingPeriod(start_date, end_date)` -> unique per workspace.
- `GivenLoan(series, loan_id)` and `TakenLoan(series, loan_id)` -> include workspace or rely on workspace-owned `Series`.
- `Product.name`, `ProductVariant.sku`, `ProductVariant.product_code` -> unique per workspace.
- `Stock.serial_no`, `Stock.huid`, `StockItem.serial_no`, `StockItem.huid` -> likely unique per workspace unless business rules require platform-global HUID uniqueness.
- Commodity movement/exposure/fixing numbers -> unique per workspace.

## Accounting-Specific Impact

Accounting is the highest-risk part of an RLS migration.

Facts from code:

- `Voucher` uses generic source document links and active fingerprint uniqueness.
- `JournalEntry` links to `Voucher`.
- `LedgerTransaction` and `AccountTransaction` link to `JournalEntry`.
- `AccountingPeriod` has a manager accepting `workspace=None`, but the model currently relies on schema locality and has commented workspace code.
- `BasePostingEngine.post()` rejects public schema.
- `AccountingPeriod.close_period()` rejects public schema.
- Balance views are schema-local SQL views.

Target accounting model under RLS:

- `Voucher`, `VoucherLine`, `JournalEntry`, `LedgerTransaction`, `AccountTransaction`, `LedgerStatement`, `AccountStatement`, `AccountingPeriod`, `Ledger`, `Account`, `VoucherNumberSequence`, and all business documents should carry `workspace_id`.
- Posting engine should assert that source document, voucher, period, ledgers, accounts, party mappings, journal entries, and lines all share one workspace.
- Voucher/document numbering should use locked sequence rows scoped by workspace.
- Ledger/account uniqueness should be workspace-scoped.
- Report and balance views must expose and group by `workspace_id`.

Recommended accounting indexes:

- `Voucher(workspace_id, voucher_date, status)`
- `Voucher(workspace_id, doc_content_type_id, doc_object_id, voucher_type_id, status)`
- `Voucher(workspace_id, fingerprint)` for active posted/corrected rows
- `JournalEntry(workspace_id, period_id, posted_at)`
- `LedgerTransaction(workspace_id, ledgerno_id, created)`
- `LedgerTransaction(workspace_id, ledgerno_dr_id, created)`
- `AccountTransaction(workspace_id, Account_id, created)`
- `AccountTransaction(workspace_id, ledgerno_id, created)`
- `AccountingPeriod(workspace_id, start_date, end_date)`
- `Ledger(workspace_id, code)`
- `Ledger(workspace_id, name, parent_id)`

Required accounting tests:

- Same voucher number, ledger code, party code, and product SKU can exist in two workspaces.
- Posting in workspace A cannot use ledger/account/period/source document from workspace B.
- Reports and SQL views return only workspace-local totals.
- Fingerprint/idempotency uniqueness is workspace-scoped.
- Period close operates only on one workspace.

## Reporting and SQL View Impact

Current SQL views are schema-local:

- `apps/tenant_apps/dea/migrations/0003_create_ledger_balance_view.py`
- `apps/tenant_apps/product/migrations/0011_pr6_unified_balance_views.py`

Under RLS:

- Views need `workspace_id` in projections.
- Aggregations must group by `workspace_id`.
- Materialized report tables need their own policies or safe access views.
- Avoid `SECURITY DEFINER` report views unless carefully reviewed.
- Cross-workspace admin reports should use a distinct audited admin role/path.

## Migration Options

### Option A: Stay with `django-tenants`

Safest short-term option.

Needed cleanup:

- Add a real immutable `Company.slug` separate from `schema_name`.
- Keep schema-aware commands explicit and documented.
- Harden background jobs with explicit schema arguments.
- Continue service/facade/selector extraction.
- Build analytics through ETL or schema iteration.
- Keep using `migrate_schemas` for tenant app migrations.

Best when MVP speed and per-tenant backup/restore matter more than analytics and operational simplicity.

### Option B: Full migration to shared-schema RLS

Best long-term but highest immediate risk.

Required work:

- Add workspace ownership to all tenant-owned models.
- Rewrite unique constraints.
- Migrate tenant schemas into shared tables.
- Replace schema middleware with RLS context middleware.
- Refactor tests, commands, background jobs, admin, reports, storage, and cache.
- Enable RLS table by table.
- Remove `django-tenants` backend, router, tenant storage, and tenant URL assumptions.

Main risks:

- Accounting data integrity.
- Generic foreign key remapping.
- Duplicate identifiers across schemas.
- SQL report correctness.
- Background job context leakage.
- Rollback complexity after data merge.

### Option C: Hybrid transition

Recommended.

Plan:

- Keep `django-tenants` running.
- Introduce explicit workspace identity and slug.
- Add nullable `workspace_id` to tenant-owned models gradually.
- Backfill each tenant schema with the current tenant company id.
- Refactor services, views, reports, jobs, and tests to accept current workspace.
- Add RLS-ready constraints and isolation tests.
- Later migrate tenant schemas into shared tables and remove `django-tenants`.

This is practical because the control plane is already mostly shared/public and workspace-keyed, while the business apps can be made explicit gradually.

## Recommended Roadmap

Phase 0: Audit and safety preparation.

- Inventory all tenant-owned tables, constraints, SQL views, schema commands, tests, and background jobs.
- Acceptance: complete migration checklist and no runtime behavior change.

Phase 1: Introduce canonical Workspace identity.

- Add immutable `Company.slug` or equivalent canonical workspace slug separate from `schema_name`.
- Keep `schema_name` as legacy infrastructure metadata.
- Acceptance: routes can resolve by product slug without exposing schema identity as the long-term slug.

Phase 2: Normalize users, memberships, invitations, subscriptions.

- Keep these in the global control plane.
- Rename/alias concepts toward Workspace where helpful.
- Acceptance: workspace switch, team invitation, and billing tests still pass.

Phase 3: Add `workspace_id` to tenant-owned models.

- Add nullable FKs first.
- Backfill inside each tenant schema.
- Add indexes.
- Acceptance: new tenant-owned rows get workspace ownership automatically.

Phase 4: Build shared-table backfill tooling.

- Export each schema, map schema to workspace, preserve/remap references.
- Acceptance: dry-run row counts and accounting totals match.

Phase 5: Refactor queries/services/views to current workspace.

- Prefer `request.workspace`/service context over `request.tenant`.
- Add workspace consistency checks at domain boundaries.
- Acceptance: two-workspace fixtures pass in key app tests.

Phase 6: Add RLS policies.

- Enable RLS table by table after ownership is complete.
- Add fail-closed policies.
- Acceptance: direct ORM/raw SQL isolation tests pass.

Phase 7: Add tenant isolation tests.

- Party, DEA, Girvi, Product, portal, notifications, and reports need two-workspace tests.
- Acceptance: no workspace can read or mutate another workspace's rows.

Phase 8: Refactor reports and SQL views.

- Add `workspace_id` to view projections/grouping.
- Add indexes for hot reports.
- Acceptance: accounting/inventory/commodity totals are workspace-local and cross-workspace admin reports are explicit.

Phase 9: Refactor background jobs.

- Replace schema args with `workspace_id`.
- Worker wrapper sets RLS context.
- Acceptance: jobs fail closed without workspace context.

Phase 10: Remove `django-tenants` dependencies.

- Replace DB engine, router, middleware, test runner, storage/cache/logging assumptions.
- Acceptance: full suite and migration rehearsal pass on shared schema.

Phase 11: Production cutover and rollback.

- Dry-run migration.
- Verify row counts, balances, loan states, inventory balances, portal grants.
- Freeze writes, copy, verify, cut over.
- Keep old schema DB snapshot for rollback.

## Required Tests Before Any Migration

- Middleware resolves workspace and validates membership before setting DB context.
- User in workspace A cannot read Party, Voucher, JournalEntry, LedgerTransaction, Loan, Stock, Notification, or portal rows from workspace B.
- Same tenant-local identifiers can exist in two workspaces.
- Posting rejects mixed-workspace source docs, ledgers, accounts, vouchers, and periods.
- Voucher fingerprint idempotency is workspace-scoped.
- Period close is workspace-scoped.
- Ledger/account balance reports are workspace-scoped.
- Inventory balance reports are workspace-scoped.
- Portal users see only granted party rows in the selected workspace.
- Background jobs require workspace context.
- Superadmin access is explicit and audited.

## Final Recommendation

Final recommendation:

`Prepare hybrid migration and switch later`

Confidence:

`High`

Reason:

Shared-schema PostgreSQL RLS is a better long-term fit for Rokkad's SaaS ERP target, but the current codebase is already meaningfully embedded in `django-tenants`. The safe path is to keep schema tenancy operational while making workspace ownership explicit, then migrate once models, constraints, reports, tests, and background jobs are RLS-ready.

When to reconsider:

- Stay with `django-tenants` if MVP delivery and per-tenant backup/restore are the dominant priorities.
- Accelerate RLS if tenant count, cross-tenant analytics, customer portal domain strategy, or workspace switching creates near-term operational pain.

Immediate next step:

Create a migration-prep plan that inventories every tenant-owned table and adds a canonical `Workspace.slug` separate from `Company.schema_name`, without changing runtime isolation yet.
