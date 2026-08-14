---
status: active
owner: project
updated: 2026-07-04
tags: [django-tenants, tenancy, architecture, audit]
related: [../AGENT_MEMORY.md, ../STATUS.md, tenancy-architecture-audit-rls-vs-django-tenants.md, tenant-seeding.md]
---

# Django Tenants Architecture Audit

This audit reviews the current `django-tenants` implementation in Rokkad. It is documentation-only: no runtime or schema changes are made here.

## A. Executive Summary

The current `django-tenants` implementation is functional and materially healthier than an ad hoc multi-tenant setup. The project uses the core schema-per-tenant primitives correctly: `django_tenants.postgresql_backend`, `TenantSyncRouter`, `TenantMixin`, `DomainMixin`, separate public and tenant URLConfs, tenant file storage, cache key functions, tenant logging filters, tenant seed commands, and tenant-aware test setup.

The implementation is not fully idiomatic stock `django-tenants` because it intentionally replaces `TenantMainMiddleware` with `apps.orgs.middleware_v2.SecureWorkspaceMiddleware`. That is a defensible choice for this ERP because membership and subscription authorization must be checked before tenant ERP access. The tradeoff is that request resolution, URLConf switching, public-schema resets, and path/domain mismatch rules are now project-owned security logic.

Biggest strengths:

- Clear public/tenant app split in `django_project/settings/base.py`.
- Public control-plane data is centralized in `apps.orgs`, `accounts`, `apps.onboarding`, and `apps.subscriptions`.
- ERP data is tenant-scoped under `apps.tenant_apps.*`.
- Tenant creation creates schemas and domains, and onboarding explicitly seeds tenant defaults.
- Dangerous accounting paths guard against public-schema posting in DEA.
- Logs, default cache, files, and tests have explicit tenant-aware configuration.

Biggest risks:

- Background tasks and some management commands can touch tenant tables without a reliable schema contract.
- Onboarding schema naming uses `company.name.lower().replace(" ", "_")`, while other flows use `build_schema_name()`; this can create invalid or inconsistent schema slugs.
- `ALLOW_COMPANY_HARD_DELETE=True` makes hard deletion operationally dangerous even though `Company.auto_drop_schema` defaults to `False`.
- Global/shared routes are intentionally included in both public and tenant URLConfs, which is compatible but increases boundary complexity.
- `SHOW_PUBLIC_IF_NO_TENANT_FOUND=True` can hide domain provisioning mistakes by serving public pages for unknown hosts.

Overall recommendation: continue with `django-tenants` for now, harden the current usage, and keep the existing hybrid/RLS migration preparation path. Do not attempt a big-bang RLS rewrite now. The schema-per-tenant model is still a reasonable fit for small-business ERP isolation, but operational discipline around commands, jobs, migrations, and tenant lifecycle must improve before scale.

## B. Current Architecture Map

### Public Schema Responsibilities

Public schema owns platform/control-plane state:

- Tenant registry and domains: `apps.orgs.models.Company`, `apps.orgs.models.Domain`.
- Users and selected workspace pointer: `accounts.models.CustomUser`, `accounts.models.UserProfile`.
- Memberships, roles, invitations, audit logs: `apps.orgs.models.Membership`, `Role`, `CompanyInvitation`, `AuditLog`.
- Onboarding progress and setup state: `apps.onboarding.models`.
- Billing, subscriptions, provider events: `apps.subscriptions.models`.
- Public/auth/pages and third-party auth tables: `pages`, `allauth`, `invitations`, `django.contrib.auth`, `django.contrib.sessions`.

Evidence: `SHARED_APPS` in `django_project/settings/base.py`.

### Tenant Schema Responsibilities

Tenant schemas own business ERP state:

- Contacts and legacy customers: `apps.tenant_apps.contact`.
- Party/customer/supplier profile data and portal grants: `apps.tenant_apps.party`.
- Girvi loans, collateral, payments, notices, documents: `apps.tenant_apps.girvi`.
- Product/inventory/catalog data: `apps.tenant_apps.product`.
- Rates, terms, notifications: `apps.tenant_apps.rates`, `terms`, `notify`, `notify_v2`.
- DEA accounting, vouchers, ledgers, journals, business events, commodity accounting: `apps.tenant_apps.dea`.

Evidence: `TENANT_APPS` in `django_project/settings/base.py`.

### Tenant Resolution Flow

Request resolution is custom:

1. `SecureWorkspaceMiddleware.process_request()` skips exempt paths such as `/accounts/`, `/static/`, `/media/`, and `/__debug__/`.
2. It resolves candidates from domain, path workspace id, `/w/<workspace_slug>/`, and then profile fallback.
3. Domain is authoritative; mismatching path and domain tenants are rejected for normal users.
4. Unauthenticated tenant access redirects to login instead of serving tenant public content.
5. Authenticated users must pass membership and subscription checks.
6. On success it calls `connection.set_tenant(workspace)`, sets `request.tenant`, and uses `settings.ROOT_URLCONF`.
7. On public/unresolved paths it calls `connection.set_schema_to_public()` and uses `PUBLIC_SCHEMA_URLCONF`.

Evidence: `apps.orgs.middleware_v2.SecureWorkspaceMiddleware`.

### Workspace Onboarding Flow

Onboarding workspace creation:

1. `apps.onboarding.views.onboarding_company()` validates `CompanySetupForm`.
2. It delegates to `apps.orgs.services.control_plane.create_onboarding_workspace_from_form()`.
3. The service enters `schema_context(public)`.
4. It builds a `Company`, assigns `schema_name`, `creator`, and `owner`.
5. `_provision_company_schema()` either saves normally with `auto_create_schema=True` or clones from `ONBOARDING_TEMPLATE_SCHEMA`.
6. `_seed_company_schema_defaults()` calls `seed_tenant_defaults --schema <schema_name>`.
7. The service creates a subdomain `Domain` row and owner `Membership`.
8. The view stores the active workspace on `request.user.profile`.

Evidence: `apps.onboarding.views._provision_company_schema`, `_seed_company_schema_defaults`, `onboarding_company`; `apps.orgs.services.control_plane.create_onboarding_workspace_from_form`.

### User/Membership Flow

Users are global public-schema users. A user can belong to many workspaces through public-schema `Membership` rows. The selected workspace is stored on `UserProfile.workspace`, but request-time authoritative resolution should use `request.tenant` via `apps.orgs.tenant_context.resolve_request_workspace()`.

Invitations are public-schema workspace invitations through `CompanyInvitation`; accepted invitations create or stage public-schema memberships. Customer portal users are also global users, but tenant portal access is granted through tenant-schema `PartyPortalAccess` and resolved inside tenant portal routes.

Evidence: `accounts.models.UserProfile`, `apps.orgs.models.Membership`, `CompanyInvitation`, `apps.orgs.signals`, `apps.tenant_apps.party.portal_access`.

## C. Feature Usage Matrix

| django-tenants feature | Current usage | Status | Evidence | Recommendation | Priority |
|---|---|---:|---|---|---:|
| PostgreSQL schema-per-tenant isolation | Tenant business apps are in `TENANT_APPS`; DB engine is tenant backend. | Correctly Used | `django_project/settings/base.py`: `DATABASES`, `TENANT_APPS` | Continue. Add operational guardrails for commands/jobs. | High |
| `SHARED_APPS` / `TENANT_APPS` separation | Public apps and ERP apps are separated. | Correctly Used | `SHARED_APPS`, `TENANT_APPS` | Keep app placement stable; avoid putting business docs in shared apps. | High |
| Public schema for platform/auth/workspace registry | Users, orgs, onboarding, subscriptions are shared. | Correctly Used | `SHARED_APPS`; `apps.orgs.models`; `accounts.models`; `apps.subscriptions.models` | Continue. Keep memberships public. | High |
| Tenant schema for ERP data | Contact, Party, Girvi, Product, Rates, Notify, DEA are tenant apps. | Correctly Used | `TENANT_APPS` | Continue; future sales/purchase should be tenant apps. | High |
| `TenantMixin` | `Company` extends `TenantMixin`. | Correctly Used | `apps.orgs.models.Company` | Keep `Company` as registry tenant model. | Critical |
| `DomainMixin` | `Domain` extends `DomainMixin`. | Correctly Used | `apps.orgs.models.Domain` | Add stronger domain validation around onboarding duplicates. | High |
| Tenant/domain validation | Some uniqueness exists; schema generation differs by flow. | Partially Used | `build_schema_name()` vs onboarding raw `name.lower().replace(" ", "_")` | Standardize all workspace creation on `build_schema_name()`, validate reserved names, max length, and collisions. | High |
| Domain/subdomain routing | Domain lookup is used; `/w/<schema_name>/` path routing also exists. | Partially Used | `SecureWorkspaceMiddleware._resolve_workspace_from_domain`, `_resolve_workspace_from_path` | Keep domain authoritative; add tests for unknown domains and domain creation rollback. | Medium |
| Public URLConf vs tenant URLConf | `PUBLIC_SCHEMA_URLCONF=django_project.urls`, `ROOT_URLCONF=django_project.tenant_urls`. | Correctly Used | `settings/base.py`; `django_project/urls.py`; `tenant_urls.py` | Continue. Gradually reduce shared URLConf overlap when safe. | Medium |
| Tenant middleware | Custom middleware sets schema and URLConf after membership checks. | Partially Used | `apps.orgs.middleware_v2.SecureWorkspaceMiddleware` | Keep custom middleware, but treat it as a security-critical replacement for `TenantMainMiddleware`; keep regression tests. | Critical |
| Middleware order | Auth/session run before tenant resolution; tenant switch before rates/subscription middleware. | Partially Used | `MIDDLEWARE` in `settings/base.py` | Intentional for membership validation. Add tests that no tenant ORM access happens before schema switch except public registry reads. | High |
| `migrate_schemas` | Documented and used in README/CI/test runner. | Correctly Used | `README.md`; `.github/workflows/tenant-seed-smoke.yml`; `django_project/test_runner.py` | Continue; forbid plain `migrate` guidance in active docs. | Critical |
| `tenant_command` / `all_tenants_command` | Not used; custom commands loop schemas manually. | Missing | No active command uses these wrappers. | Not mandatory. Prefer wrappers for simple tenant commands; keep custom loops where cross-tenant summaries are needed. | Low |
| `BaseTenantCommand` | Not used. | Missing | No subclass found. | Useful for new single-tenant maintenance commands; not urgent. | Low |
| `schema_context` / `tenant_context` | Used in seed, parity, backfill, accrual commands and public control-plane services. | Partially Used | `control_plane.py`; `seed_tenant_defaults.py`; `accrue_loan_interest.py`; `migrate_jattributes_to_normalized.py` | Add a standard command/task helper that validates schema names and tenant existence. | High |
| Tenant-aware admin | `CompanyAdmin` uses `TenantAdminMixin`; public-only mixin exists. | Partially Used | `apps.orgs.admin.CompanyAdmin`, `PublicTenantOnlyMixin` | Apply public-only access consistently to registry models, or document why tenant admin access is allowed. | Medium |
| Tenant-aware caching | Default cache uses django-tenants key functions. | Partially Used | `CACHES["default"]`; rate middleware/signals cache simple keys | Default cache is good. Audit `select2` and task-time cache writes; avoid caching tenant model instances without tenant context. | Medium |
| Tenant-aware logging | Tenant context filter configured. | Correctly Used | `LOGGING.filters.tenant_context` | Continue; add workspace id/domain to audit events where useful. | Low |
| Tenant signals | `post_save Company` optionally seeds after commit. | Partially Used | `apps.orgs.signals.seed_tenant_on_company_create` | Consider official `post_schema_sync`/`schema_needs_to_be_sync` only if schema-create timing becomes flaky. | Medium |
| Parallel tenant migrations | Not configured. | Missing | No parallel executor setting found. | Defer until tenant count or migration windows justify it. | Low |
| `create_missing_schemas` | Not wired into active workflows. | Missing | No active command usage found. | Add as an ops runbook/check, not runtime code. | Medium |
| `clone_tenant` / clone schema | Onboarding can use `CloneSchema` template clone. | Partially Used | `apps.onboarding.views._provision_company_schema` | Keep optional. Validate template schema and seed parity after clone. | Medium |
| `rename_schema` | Not used. | Not Needed | No rename workflow found. | Avoid until workspace slug/schema rename requirements exist. | Low |
| `delete_tenant` / safe deletion | Soft delete default; hard delete explicitly drops schema. | Partially Used | `Company.delete`, `Company.hard_delete`, `ALLOW_COMPANY_HARD_DELETE=True` | Set hard delete disabled by default in production and require two-step ops workflow. | Critical |
| `auto_drop_schema` safety | `auto_drop_schema=False`; hard delete flips to true. | Partially Used | `Company.auto_drop_schema=False`; `hard_delete()` | Good model default, but setting currently allows hard delete globally. Tighten config. | Critical |
| `SHOW_PUBLIC_IF_NO_TENANT_FOUND` | Enabled. | Partially Used | `SHOW_PUBLIC_IF_NO_TENANT_FOUND=True`; custom public fallback | Acceptable for public SaaS pages, risky for domain misconfig. Log unknown host/domain misses. | Medium |
| `PG_EXTRA_SEARCH_PATHS` | Environment-configurable, default empty. | Correctly Used | `PG_EXTRA_SEARCH_PATHS = env.list(...)` | Keep empty unless shared extensions/reference schema is introduced. | Low |
| Subfolder tenancy | Not using package subfolder middleware; project has `/w/<schema>/` aliases. | Not Needed | `WORKSPACE_SLUG_PATTERNS`; no `TenantSubfolderMiddleware` | Current path aliases are product IA, not true subfolder tenancy. Do not adopt subfolder tenancy now. | Low |
| Multi-type tenants | Not configured. | Not Needed | No `HAS_MULTI_TYPE_TENANTS` / `TENANT_TYPES` | Avoid for now; every workspace needs same ERP baseline. | Low |
| Tenant-aware files/media | Tenant file storage and relative media root configured. | Correctly Used | `STORAGES.default`, `MULTITENANT_RELATIVE_MEDIA_ROOT`; tenant `FileField`s | Continue; verify shared public uploads such as profile pictures/company logos are intentionally under public. | Medium |

## D. App Placement Audit

| App name | Currently shared/tenant | Should be | Reason | Required change |
|---|---|---|---|---|
| `django_tenants` | Shared | Shared | Required package app. | None |
| `apps.orgs` | Shared | Shared | Tenant registry, domains, memberships, roles, audit. | None |
| `django.contrib.auth` / `accounts` | Shared | Shared | Global user can join multiple workspaces. | None |
| `django.contrib.sessions` | Shared | Shared | Login/session is global. | None |
| `allauth`, `invitations` | Shared | Shared | Auth and invitation entrypoints are platform-level. | None |
| `apps.onboarding` | Shared | Shared | Onboarding creates/selects workspaces. | None |
| `apps.subscriptions` | Shared | Shared | Billing is workspace-level platform state tied to `Company`. | None |
| `pages` | Shared | Shared | Public marketing/platform pages. | None |
| `guardian`, `dynamic_preferences`, select2, import/export libs | Shared | Mostly shared | Framework support; table placement depends on app models. | Audit object permissions if tenant object permissions are later needed. |
| `apps.tenant_apps.contact` | Tenant | Tenant until retired | Legacy tenant customer/contact data. | Keep only targeted safety fixes; Party is replacement. |
| `apps.tenant_apps.party` | Tenant | Tenant | Parties, KYC, relationships, portal grants are business/workspace data. | None |
| `apps.tenant_apps.girvi` | Tenant | Tenant | Loans, collateral, payments are isolated business documents. | None |
| `apps.tenant_apps.product` | Tenant | Tenant | Inventory/catalog data varies per workspace. | None |
| `apps.tenant_apps.terms` | Tenant | Tenant | Workspace-visible business terms. | None |
| `apps.tenant_apps.rates` | Tenant | Tenant or future hybrid | Current rates are workspace data; future market rates could become shared reference data. | Keep tenant for now; revisit if central rate feeds are added. |
| `apps.tenant_apps.notify`, `notify_v2` | Tenant | Tenant | Notification policies/templates/events relate to tenant customers and documents. | Background delivery must pass schema context. |
| `apps.tenant_apps.dea` | Tenant | Tenant | Accounting ledgers, vouchers, periods, reports must be isolated. | None |
| Removed sales/purchase apps | Not installed | Future tenant apps | Operational commerce/procurement should be tenant-owned documents. | Rebuild around DEA/commodity/inventory boundaries if revived. |

No obvious active app is in the wrong schema. The main placement issue is route-plane overlap, not app installation: `shared_urlpatterns` are included in both public and tenant URLConfs for compatibility.

## E. Risk Register

| Risk | Severity | Affected files/modules | Why it matters | Fix |
|---|---:|---|---|---|
| Hard delete can drop tenant schemas because `ALLOW_COMPANY_HARD_DELETE=True`. | Critical | `django_project/settings/base.py`; `apps.orgs.models.Company.hard_delete`; `apps.orgs.admin.CompanyAdmin.hard_delete_companies` | A mistaken admin action can permanently delete a workspace schema. | Default this off in production, require explicit environment opt-in, add confirmation/runbook, consider backup-before-delete. |
| Background tasks query tenant models without schema argument/context. | High | `apps.tenant_apps.girvi.tasks.export_table`, `notify_Loan_reminder` | Celery workers may run in public schema or stale schema, causing missing-table errors or wrong tenant data access. | Require `schema_name` for tenant tasks and wrap body in `tenant_context`/`schema_context`; add task tests. |
| `import_statement_items` uses tenant name as schema. | High | `apps.tenant_apps.girvi.management.commands.import_statement_items` | Workspace display names are not schema identifiers; command can fail or hit wrong schema. | Resolve by `schema_name`, validate tenant exists, then use `schema_context(tenant.schema_name)`. |
| Onboarding schema naming is inconsistent and weak. | High | `apps.orgs.services.control_plane.create_onboarding_workspace_from_form`; `apps.onboarding.forms.CompanySetupForm` | Invalid names, reserved names, or collisions can create broken tenants/domains. | Use `build_schema_name()` everywhere and check `Company.all_objects` for collisions. |
| Domain creation is not transactional with schema clone/seed in an all-or-nothing way. | High | `create_onboarding_workspace_from_form`; `_provision_company_schema`; `_seed_company_schema_defaults` | Failures can leave a schema without domain/membership or public rows without successful seed. | Add provisioning state, compensating cleanup, or background provisioning workflow with retry. |
| Public and tenant route planes overlap. | Medium | `django_project/shared_urlpatterns.py`; `django_project/urls.py`; `tenant_urls.py` | Public flows can behave tenant-aware; URL reversing and authorization boundaries are harder to reason about. | Continue phased route separation; keep guard tests around aliases and tenant-only prefixes. |
| Unknown tenant domains fall back to public. | Medium | `SHOW_PUBLIC_IF_NO_TENANT_FOUND`; `SecureWorkspaceMiddleware` | Misconfigured customer domains may silently show public pages. | Log/monitor domain misses; consider stricter behavior for production tenant host patterns. |
| App-level cache keys are simple but tenant safety relies on default cache key function and active schema. | Medium | `apps.tenant_apps.rates.middleware`, `rates.signals`, Girvi managers/services, DEA resolver | Task-time or public-schema cache writes can poison tenant values. | Prefix explicit cache keys with `connection.schema_name` or use helper; avoid caching model instances. |
| Some maintenance commands loop all `Company.objects` including public or deleted tenants. | Medium | `migrate_jattributes_to_normalized`, `update_loans`, seed commands | Commands can process public/deleted schemas or fail on missing schemas. | Use `get_public_schema_name()`, `is_deleted=False`, `schema_exists()`, and consistent tenant queryset helpers. |
| Public control-plane services rely on manual `schema_context(public)`. | Medium | `apps.orgs.services.control_plane` | Correct today, but missed wrappers in new org mutations could write public data into tenant schema. | Add architecture tests for org mutations requiring `_public_schema_context()`. |
| Normal `migrate` appears in archived docs. | Low | `docs/archive/**` | Archived docs can mislead agents/users if not recognized as historical. | Active docs already say `migrate_schemas`; keep archive clearly historical. |

## F. Recommended Phased Roadmap

### Phase 1: Critical Safety Fixes

1. Disable production hard delete by default:
   - Set `ALLOW_COMPANY_HARD_DELETE` from environment with default `False`.
   - Keep `Company.auto_drop_schema=False`.
   - Add tests that admin hard delete is blocked unless explicitly enabled.

2. Fix tenant context for background tasks:
   - Change Girvi tenant tasks to require `schema_name`.
   - Resolve `Company` in public schema.
   - Wrap tenant work in `tenant_context(tenant)` or `schema_context(schema_name)`.
   - Add tests proving public-schema execution fails closed.

3. Fix `import_statement_items`:
   - Treat CLI argument as schema name.
   - Query `Company.objects.get(schema_name=...)`.
   - Use `schema_context(tenant.schema_name)`.

4. Standardize schema name generation:
   - Use `build_schema_name()` in onboarding and non-onboarding workspace creation.
   - Validate against `public`, empty names, leading digits, length, and collisions.

Tests before/with Phase 1:

- Middleware tests for domain/path/profile resolution and public reset.
- Command tests for `import_statement_items --tenant <schema_name>`.
- Celery task unit tests that verify `tenant_context` is entered.
- Hard-delete admin/model tests.

### Phase 2: Correctness and Cleanup

1. Add a tenant maintenance helper module for:
   - Public-schema tenant lookup.
   - Excluding public/deleted tenants.
   - `schema_exists()` validation.
   - Standard dry-run and continue-on-error behavior.

2. Update cross-tenant commands to use the helper:
   - `seed_all_tenants`.
   - `check_tenant_seed_parity`.
   - `migrate_jattributes_to_normalized`.
   - `update_loans`.
   - DEA audit/seed commands.

3. Add explicit provisioning state to `Company` or a separate provisioning model:
   - `creating`, `schema_created`, `seeded`, `domain_created`, `ready`, `failed`.
   - This avoids treating half-provisioned tenants as usable.

4. Tighten domain creation:
   - Check duplicate domains in onboarding.
   - Avoid creating subdomains from raw `request.get_host()` when the host is localhost or a tenant host.

### Phase 3: Better Use of Missed django-tenants Features

1. Introduce `BaseTenantCommand` or `tenant_command` for simple single-tenant commands where it reduces custom boilerplate.
2. Add an ops runbook for `create_missing_schemas` and schema drift detection.
3. Evaluate official `post_schema_sync` only if post-save seeding proves timing-sensitive. Current explicit onboarding seeding is acceptable.
4. Add public-only admin mixin consistently to tenant registry admin models if tenant admin exposure is not intended.

Avoid for now:

- Multi-type tenants: all jewellery ERP workspaces need the same schema baseline.
- Subfolder tenancy middleware: current `/w/<schema>/...` routes are route aliases, not a need for package-level subfolder tenancy.
- Rename schema workflows: schema names are currently compatibility slugs and should not become editable branding slugs yet.

### Phase 4: Scalability and Operations

1. Define deployment migration policy:
   - `migrate_schemas --shared` for shared changes.
   - `migrate_schemas --tenant` or selected schema rollout for tenant changes.
   - Smoke seed selected tenant after migration.

2. Add migration observability:
   - Track tenant migration duration.
   - Detect schema drift before deploy.
   - Keep failed tenant migration reports.

3. Evaluate parallel migrations when tenant count makes serial migration windows too slow.

4. Define backup/restore:
   - Whole database backup.
   - Per-schema logical backup before hard delete or high-risk migrations.
   - Tenant restore rehearsal.

5. Make tenant provisioning asynchronous only after provisioning state exists. A background provisioning job should be idempotent and retryable.

### Phase 5: Optional Future RLS Path

The existing RLS audit remains directionally right: do not switch now, but prepare. Before moving away from `django-tenants`:

1. Add explicit `workspace/company` ownership to tenant-owned models where feasible.
2. Stop using `schema_name` as a product-facing workspace slug.
3. Move background jobs to pass explicit workspace identity, not implicit DB schema.
4. Build isolation tests that assert queries cannot cross workspace boundaries.
5. Only then plan shared-table migration with PostgreSQL RLS.

## G. Questions / Assumptions

- Assumption: production uses PostgreSQL, not SQLite, because the configured engine is `django_tenants.postgresql_backend`.
- Assumption: active operational docs are under `docs/` and archived docs are historical; archived `python manage.py migrate` references are not current guidance.
- Question: Is `ALLOW_COMPANY_HARD_DELETE=True` intentional for local development only, or currently deployed?
- Question: Are Girvi reminder/export Celery tasks actively scheduled? If yes, tenant context hardening is urgent.
- Question: Are tenant subdomains used in production, or is path-based `/w/<schema>/...` the main access pattern?
- Question: Should rates become central market reference data later, or remain per-workspace business data?
- Question: Does the project need branded customer portal domains soon, or is tenant-path portal access still the MVP boundary?

