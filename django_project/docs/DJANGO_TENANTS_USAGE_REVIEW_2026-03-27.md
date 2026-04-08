# Django-Tenants Usage Review and Recommendations

Date: 2026-03-27  
Last Updated: 2026-03-28  
Project: rokkad

## Purpose
This document records the current django-tenants implementation review, key risks, and recommended improvements for future hardening work.

## Current Strengths
- Shared and tenant app separation is configured in [settings base](../settings/base.py).
- Tenant and domain models are configured through `TENANT_MODEL` and `TENANT_DOMAIN_MODEL`.
- Tenant DB backend and router are in place (`django_tenants.postgresql_backend`, `TenantSyncRouter`).
- Tenant-aware cache keying is configured using django-tenants key functions.
- Tenant-aware media/static support is configured (`TenantFileSystemStorage`, `TenantFileSystemFinder`).
- Logging includes tenant schema context through `TenantContextFilter`.

## Key Findings

### 1) Core tenant resolution middleware is bypassed at runtime
- Active middleware in [settings base](../settings/base.py) uses [SecureWorkspaceMiddleware](../../apps/orgs/middleware_v2.py).
- This middleware sets schema mainly from the authenticated user profile workspace, not from hostname/domain lookup.
- The custom `TenantMainMiddleware` implementation in [legacy middleware](../../apps/orgs/middleware.py) exists but is not active in middleware order.

Why this matters:
- Domain-to-tenant mapping is the canonical isolation entrypoint in django-tenants.
- If runtime schema selection is primarily profile-driven, request host and tenant domain mapping are no longer the first authority.
- This increases risk of schema-selection drift and makes behavior less predictable across public/tenant URLs.

### 2) Public vs tenant URL routing enforcement is not centralized in active middleware
- URL split is configured (`ROOT_URLCONF` and `PUBLIC_SCHEMA_URLCONF`) in [settings base](../settings/base.py).
- Active secure middleware does not perform full django-tenants style URL conf selection per-request.

Risk:
- Requests can rely on app-level assumptions about schema and routing instead of one canonical middleware decision.

### 3) Tenant context source-of-truth is mixed
- Some flows use `request.tenant`.
- Others rely on `request.user.profile.workspace` directly (context processors, decorators, middleware).

Risk:
- If profile workspace and request tenant diverge, authorization and data access checks can become inconsistent.

### 4) Schema lifecycle policy needs explicit governance
- `Company` sets `auto_create_schema = True` and `auto_drop_schema = True` in [company model](../../apps/orgs/models.py).
- `delete()` is soft-delete, while hard-delete exists separately.

Risk:
- Without strict operational policy, schema lifecycle can be inconsistent (orphan schemas or accidental destructive actions).

### 5) Some management command schema switches are fragile
- At least one command uses schema context with tenant name instead of schema name in [import statement items](../../apps/tenant_apps/girvi/management/commands/import_statement_items.py).

Risk:
- Background/ops commands are a high-risk area for wrong-schema execution.

## What “Core Tenant Resolution Middleware Is Bypassed” Means
In django-tenants, the standard request path is:
1. Read request host (for example `acme.example.com`).
2. Find matching `Domain` row.
3. Resolve tenant from domain.
4. Switch DB schema to that tenant.
5. Apply public vs tenant URL routing accordingly.

In current runtime behavior, schema is mainly selected from the user’s selected workspace in profile. That means domain resolution is not the primary gate for schema assignment during request handling.

## Domain-Driven vs Profile-Driven Tenant Resolution

### Domain-driven tenant resolution
- Tenant is determined from request host/domain first.
- Best for strict isolation by hostname and predictable infrastructure behavior.
- Aligns with django-tenants default architecture and expected middleware lifecycle.

### Profile-driven switching
- Tenant is determined from user-selected workspace stored in profile/session.
- Useful for multi-workspace UX (switching from a selector screen).
- Should be treated as a preference input, not as the first authority for schema choice.

## Recommended Tenant Resolution Pattern
Recommended architecture:
1. Domain-driven resolution as primary source of truth in middleware.
2. Membership and RBAC checks as second-layer authorization.
3. Profile workspace used for UX and redirect decisions, not direct schema override.
4. Add a consistency check: if profile workspace conflicts with resolved domain tenant, reject or reconcile safely.

This gives:
- Correct isolation at the HTTP boundary.
- Clear and auditable control flow.
- Better compatibility with django-tenants tooling and conventions.

## Prioritized Enhancements
1. Restore canonical tenant resolution flow in active middleware (host/domain -> tenant -> schema -> URL conf).
2. Standardize request-time logic on `request.tenant`.
3. Keep profile workspace as UX preference only.
4. Add explicit schema lifecycle policy and operational commands for archive/restore/hard-delete.
5. Harden management commands with strict schema-name targeting and dry-run support.
6. Expand tenant isolation integration tests (domain resolution, cross-tenant denial, public routing).

## Suggested Follow-up Implementation Plan
Phase 1:
- Middleware hardening + URL conf selection normalization.
- Add cross-tenant regression tests.

Phase 2:
- Refactor decorators/context processors to use `request.tenant` consistently.
- Add profile-vs-tenant consistency guardrails.

Phase 3:
- Operational hardening for tenant lifecycle and schema-safe management commands.

## Practical Note: Why Profile-Driven Was Chosen
The initial choice of profile-driven workspace switching is understandable when infrastructure readiness for wildcard DNS, subdomains, and certificates is uncertain.

### Deferred TODO for Finding #1 (Infrastructure-Driven)
Until subdomain support on Linode is fully validated in production, keep the current transition strategy:
1. Domain-driven tenant resolution first.
2. Path-driven tenant hint fallback second.
3. Profile-driven workspace fallback last.

When subdomain support is stable (wildcard DNS + TLS + host routing validated), remove the profile fallback from request-time tenant resolution and keep it only as a UI preference signal.

---

## TODO: Stable TenantTestCase Base for Girvi / DEA Tests

**Status**: Deferred — attempted and rolled back. Needs a dedicated, isolated pass.

**Background**:
Girvi and DEA models are TENANT_APPS — their tables exist only inside tenant schemas, not the public schema. Current tests in `test_series_guardrails.py` use Django's base `TestCase`, which runs against the public schema. This works only because the test database happens to have those tables at the time the tests run. It is fragile: running the suite in combination with `apps.orgs.tests` causes `relation "girvi_license" does not exist` because schema isolation ordering breaks down.

**Goal**: Replace `TestCase` with `FastTenantTestCase` (from `django_tenants.test.cases`) for all girvi/DEA tests that hit the DB. This ensures every test runs inside a proper tenant schema with the correct tenant-app migrations applied.

---

### Step 1 — Add the Tenant Test Runner to settings

In `django_project/settings/dev.py` (or a dedicated `test.py` settings file), add:

```python
TEST_RUNNER = "django_project.test_runner.TenantAwareDiscoverRunner"
```

Without this, `FastTenantTestCase` does not run tenant-app migrations into the test tenant schema. This is the root cause of the `relation "girvi_license" does not exist` failures seen during the rolled-back attempt.

---

### Step 2 — Create a shared base class

In `apps/tenant_apps/girvi/tests/` (or a shared `conftest`-equivalent module), define:

```python
from django.contrib.auth import get_user_model
from django_tenants.test.cases import FastTenantTestCase

User = get_user_model()


class TenantTestBase(FastTenantTestCase):
    """
    Base class for girvi / DEA tests that need tenant-schema DB access.

    a tenant-aware test runner must be configured as TEST_RUNNER for
    tenant-app migrations to be applied to the test tenant schema before
    any test body runs.

    FastTenantTestCase creates one shared tenant per test class and wraps
    each test in a savepoint (fast), so schema lifecycle is stable across
    test methods.
    """

    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = "Test Tenant"
        owner = User.objects.create_user(username="tenant_test_owner")
        tenant.owner = owner
        tenant.creator = owner
        return tenant

    @classmethod
    def setup_domain(cls, domain):
        domain.domain = "test.localhost"
        domain.is_primary = True
        return domain
```

Adjust `owner`/`creator` field assignment to match whatever `Company` requires at save time. Check `apps/orgs/models.py` for required fields if the base save fails.

---

### Step 3 — Migrate tests incrementally

**Target files in priority order:**

1. `apps/tenant_apps/girvi/tests/test_series_guardrails.py` — 17 DB tests, primary target. Remove the `Customer` FK setup that was ported from the old `TestCase` setUp; the guardrail tests do not require a Customer record at the series level.

2. `apps/tenant_apps/girvi/tests.py` — currently a stub. Expand here once the base class is verified.

3. `apps/tenant_apps/girvi/tests/test_payment_integration_pr1_pr2.py` — uses `SimpleTestCase` with mocks; does NOT need migration to `TenantTestBase` (no real DB access).

**Migration pattern for each file:**

```python
# Before
from django.test import TestCase

class SeriesGuardrailTests(TestCase):
    ...

# After
from apps.tenant_apps.girvi.tests.base import TenantTestBase

class SeriesGuardrailTests(TenantTestBase):
    ...
```

---

### Step 4 — Validate in isolation first, then combined

```bash
# Step A: isolated girvi tests only
python manage.py test apps.tenant_apps.girvi.tests --settings=django_project.settings.dev -v 2

# Step B: combined with orgs tests — this is what was failing before
python manage.py test apps.orgs.tests apps.tenant_apps.girvi.tests -v 2
```

Only proceed to Step B after Step A is green. The combined run is the regression gate.

---

### Known failure signature

If `TEST_RUNNER` is not set correctly, the failure looks like:

```
django.db.utils.ProgrammingError: relation "girvi_license" does not exist
LINE 1: ...FROM "girvi_license" WHERE ...
```

This means the test is running in the public schema (no tenant-app tables). Fix: verify `TEST_RUNNER = "django_project.test_runner.TenantAwareDiscoverRunner"` is in effect before debugging anything else.

---

### Why this matters

Running girvi tests against the public schema is an untested assumption. As migrations are added, or if the test database is rebuilt cleanly, public-schema access to TENANT_APPS tables will silently break. Anchoring these tests to `TenantTestBase` makes the isolation explicit and the failures loud and early.

This is a valid early-stage tradeoff, but for long-term safety it should be treated as a transition state rather than the final tenant isolation boundary.

## Safe Transition Path Without Immediate Subdomain Dependency
1. Keep current profile-based workspace selector for UX only.
2. Introduce deterministic request tenant resolution middleware as the authority.
3. Use one of these authority sources:
	- Preferred: host/domain (subdomain model).
	- Alternative: URL path prefix (for example, a workspace slug segment) if subdomains are not ready.
4. Keep membership and role checks after tenant resolution.
5. Add conflict guardrail: if profile workspace does not match resolved request tenant, block or reconcile safely and log the event.

## Infrastructure Reality Check
Most cloud setups including Linode/Akamai environments can support subdomains through DNS records and TLS setup.
The missing piece is usually configuration and automation, not provider capability.

If subdomain rollout is not immediate, path-based deterministic resolution is a safer intermediate architecture than profile-driven schema switching.

## Implementation Progress (Completed)

### Phase 1 (completed 2026-03-27)
- Deterministic tenant resolution is now active in middleware with priority: domain -> path -> profile fallback.
- Request context now records `tenant_resolution_source` for diagnostics.
- Public vs tenant URLConf and schema context are set explicitly in active middleware.
- Mismatch guardrails are in place and log security events when domain and profile workspace diverge.
- Shared tenant resolver utility has been introduced and reused across middleware, decorators, context processors, and billing/subscription paths.
- High-impact request flows in org, account, pages, onboarding, and rates middleware now prefer request tenant context over profile workspace.
- Regression tests were added/expanded for resolver behavior and deterministic tenant selection priority.

### Phase 2 (completed 2026-03-28) — Four findings remediated

**Finding #1 — Deferred (infrastructure-gated)**
- Documented as a deferred infra TODO; trigger condition: wildcard DNS + TLS + host routing validated on Linode.
- When ready: remove profile fallback from request-time resolution; keep as UI preference signal only.

**Finding #2 — Middleware routing enforcement hardened** (`apps/orgs/middleware_v2.py`)
- Added `/approval/` and `/notify/` to `WORKSPACE_REQUIRED_URLS`.
- Added unauthenticated-user branch: if path requires a workspace, do a safety reset (`connection.set_schema_to_public()` + public URLConf) then redirect to login.
- Safety reset is required because DB connections are reused across requests; leaving a tenant schema active on a public redirect is a schema-leak risk.
- Added explanatory inline comment above the redirect branch for maintainer clarity.

**Finding #3 — Tenant context source-of-truth standardized** (`apps/orgs/tenant_context.py`)
- `resolve_request_workspace()` now defaults to `allow_profile_fallback=False`.
- Profile fallback is opt-in (`allow_profile_fallback=True`), required explicitly in: `pages/views.py` (Dashboard, company_dashboard), `accounts/views.py` (workspace UX flows), `apps/orgs/views.py` (workspace_selector).
- All other call-sites (middleware, audit, decorators) default to tenant-first, no profile fallback.
- Tests updated: `test_does_not_fallback_to_profile_workspace_by_default`, `test_profile_fallback_only_when_opted_in`, `test_unauthenticated_required_tenant_path_redirects_to_login`.

**Finding #4 — Company lifecycle policy formalized** (`apps/orgs/models.py`, `apps/orgs/admin.py`, `apps/orgs/views.py`)
- `auto_drop_schema = False` (was `True`); schema drop is now explicit and guarded.
- `archive()`: soft-delete — sets `is_deleted=True`, saves with `update_fields`.
- `delete(hard=False)`: defaults to `archive()`; `hard=True` routes to `hard_delete()`.
- `hard_delete(force=False)`: requires `settings.ALLOW_COMPANY_HARD_DELETE=True` or `force=True`; sets `auto_drop_schema=True` only when explicitly authorized; raises `ValueError` otherwise.
- `restore()`: sets `is_deleted=False`, saves with `update_fields`.
- Admin actions updated to use policy methods; per-company `ValueError` feedback shown to operator.
- `workspace_delete` view now calls `company.archive()` instead of bare `company.delete()`.

### Phase 3 (completed 2026-03-28) — Decorator consolidation
- `apps/orgs/decorators.py` deleted.
- All functionality (live and useful) merged into `apps/orgs/decorators_v2.py`:
  - `permission_required` — fine-grained; checks `role.permissions` M2M by codename; audit-logged.
  - `any_permission_required` — OR variant of above.
  - `object_permission_required` — Guardian object-level permission check.
  - `roles_required` — coarse role-name gate; migrated from old file; rewritten with `select_related`, `PermissionDenied`, and public/tenant schema handling.
  - `workspace_required` — lightweight "must have a resolved workspace" gate.
- Dead/buggy functions dropped: `role_required`, `company_member_required`, `membership_required`.
- All callers updated: `pages/views.py`, `apps/orgs/views.py`.
- 20/20 orgs tests pass; Django system check clean.

## Remaining Work (Recommended)
1. Add integration tests for authenticated domain/path/profile conflict cases and redirect behavior.
2. Complete migration of remaining low-risk profile-workspace usages in non-critical paths.
3. Finalize and document an infrastructure rollout path:
	- subdomain-based authority when DNS/TLS is ready, or
	- path-based deterministic authority as intermediate architecture.
4. Migrate girvi/DEA tests to `FastTenantTestCase` (see deferred TODO above).
