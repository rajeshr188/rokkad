I’m going to do a targeted codebase review of how django-tenants is configured and used today, then map gaps against package capabilities and give concrete, prioritized improvements with file-level references. I’ll start by locating tenant models, settings, middleware, routing, and tenant-aware access control flow.

Search complete: Map django-tenants usage

Searched for regex `SHARED_APPS|TENANT_APPS|TENANT_MODEL|TENANT_DOMAIN_MODEL|DATABASE_ROUTERS|TenantMainMiddleware` (`**/settings.py`), no results

Searched for files matching `**/settings.py`, no matches

Searched for files matching `**/*.py`, 200 matches

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/django_project/settings/base.py#1-1), lines 1 to 200

Read memory

I found the core integration points and will now inspect the actual implementations in settings, tenant models, middleware, and URL routing to identify risks, missed django-tenants capabilities, and concrete upgrade opportunities.

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/django_project/settings/base.py#1-1), lines 1 to 280

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/models.py#1-1), lines 1 to 260

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/middleware_v2.py)

I’ve confirmed core settings and the custom security middleware. Next I’m checking request routing and schema selection flow to verify whether django-tenants middleware lifecycle is correctly preserved or partially bypassed.

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/django_project/tenant_urls.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/django_project/urls.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/django_project/context_processors.py)

Search complete: Trace schema switching usage

Searched for regex `connection\.set_tenant|connection\.set_schema_to_public|request\.tenant\s*=|schema_context|tenant_context|tenant_command|migrate_schemas|TenantMainMiddleware`, 81 results

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/middleware_v2.py#1-1), lines 1 to 150

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/middleware.py)

I found additional schema-switch hints but the automated extraction had path resolution issues, so I’m now validating those locations directly in the workspace to avoid false positives and produce a reliable review.

Searched for regex `set_tenant|set_schema_to_public|schema_context|tenant_context|TenantMainMiddleware|TenantSubfolderMiddleware|request\.tenant|django_tenants` (`**/*.py`), 98 results

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/middleware.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/views.py#1-1), lines 1 to 340

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/accounts/models.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/django_project/settings/base.py#281-281), lines 281 to 455

I’m now reviewing onboarding and rate/membership middleware interactions, because these are where tenant bootstrap and cross-schema consistency issues usually surface.

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/onboarding/views.py#1-1), lines 1 to 280

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/rates/middleware.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/decorators_v2.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/accounts/views.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/urls.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/views.py#341-341), lines 341 to 780

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/views.py#780-780), lines 780 to 992

I now have enough core app context; next I’m scanning tenant-aware management commands and tests to identify operational and migration gaps in how schemas are targeted outside requests.

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/girvi/management/commands/import_statement_items.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/girvi/management/commands/update_loans.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/dea/management/commands/seed_core_ledgers.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/management/commands/migrate_jattributes_to_normalized.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/admin.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/decorators.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/django_project/settings/dev.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/django_project/settings/prod.py)

Searched for regex `TenantTestCase|FastTenantTestCase|schema_context\(|tenant_context\(` (`**/tests*.py`), 24 results

Searched for text `django-tenants|django_tenants` (`**/requirements.txt`), 1 result

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/helpers/cloudflare/storages.py)

Searched for regex `migrate_schemas|tenant_command|all_tenants_command|create_tenant|create_missing_schemas|clone_tenant|rename_schema|delete_tenant|TENANT_LIMIT_SET_CALLS|EXTRA_SET_TENANT_METHOD_PATH|PG_EXTRA_SEARCH_PATHS|HAS_MULTI_TYPE_TENANTS|TENANT_TYPES` (`**/*.{py,md}`), 16 results

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/django_project/middleware.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/forms.py)

Searched for regex `celery|django_tenants\.celery|TenantTask|tenant-schemas-celery|tenant_context` (`**/*.py`), 10 results

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/contact/tasks.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/girvi/tasks.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/signals.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/apps.py)

**Top Findings (Django-Tenants Review)**

1. Critical: Core tenant resolution middleware is bypassed in runtime
- Your active middleware uses middleware_v2.py via base.py, but it does not use django-tenants host/domain resolution flow.
- This means tenant selection is driven by user profile state (middleware_v2.py) instead of domain mapping, which weakens django-tenants’ intended request isolation model.
- You do have a custom TenantMainMiddleware clone in middleware.py, but it is not active.

2. High: URL conf switching for public vs tenant is not consistently enforced
- Settings define split URL configs in base.py, but active middleware v2 does not set request.urlconf/public routing explicitly.
- This can create subtle behavior drift where public-schema requests still route through tenant URL patterns depending on default ROOT_URLCONF behavior.

3. High: Tenant context source of truth is inconsistent (request.tenant vs user.profile.workspace)
- Multiple components use profile workspace rather than resolved request tenant, e.g. context_processors.py, middleware.py, decorators_v2.py.
- If profile value is stale, schema context and authorization checks can diverge from actual request tenant.

4. High: Schema lifecycle policy is risky/inconsistent
- Company model sets both auto_create_schema and auto_drop_schema in models.py.
- But normal delete is soft-delete override in models.py, so schema lifecycle and tenant lifecycle may drift over time unless hard-delete governance is very strict.
- This can leave orphaned schemas or accidental drops if hard-delete paths are used.

5. Medium: Management command schema targeting has at least one incorrect pattern
- In import_statement_items.py, schema_context uses tenant.name instead of schema_name.
- In multi-tenant ops, these mistakes are high-impact because they can execute against wrong/no schema.

6. Medium: Untapped django-tenants operational hooks
- No evidence of schema migration signals (post_schema_sync/schema_migrated) usage for post-provision automation.
- Limited use of tenant command wrappers (tenant_command/all_tenants_command patterns) in code and workflows.
- Limited tenant-isolation tests around middleware/domain resolution paths (most tenant tests are app-level model/service tests).

7. Low: Legacy middleware and helper code may cause confusion
- Legacy middleware in middleware.py and newer secure middleware coexist; old path still contains custom tenant routing logic not aligned with current approach.
- This increases maintenance risk and makes security assumptions harder to validate.

---

**What You’re Already Doing Well**

- Core django-tenants setup is present and mostly correct:
- Shared/tenant app split in base.py and base.py.
- Tenant model and domain model configured in base.py.
- Tenant DB backend and router configured in base.py and base.py.
- Tenant-aware cache keying in base.py.
- Tenant-aware storage/static finder in base.py and base.py.
- Tenant context logging filter in base.py.

---

**High-Value Enhancements (Recommended Order)**

1. Restore canonical django-tenants request lifecycle
- Move back to django-tenants middleware-driven tenant resolution (domain/subdomain or subfolder) as primary mechanism.
- Keep membership/RBAC checks as a second layer after tenant resolution, not as the source of schema selection.
- Ensure public vs tenant URL routing is explicitly set in middleware for each request.

2. Unify tenant context source
- Standardize on request.tenant for request-time behavior.
- Treat user.profile.workspace as a user preference for workspace switch UI, not authoritative schema context.
- Add guardrails that verify profile workspace matches request.tenant where needed.

3. Harden schema lifecycle governance
- Decide lifecycle explicitly:
- Option A: Soft-delete only and keep schemas (set auto_drop_schema False and archive policy).
- Option B: Controlled hard-delete with explicit approval and backup.
- Add management commands for archive, restore, and hard-delete with dry-run and logging.

4. Introduce tenant provisioning hooks
- Use django-tenants schema signals to run post-provision steps:
- seed roles/permissions
- seed mandatory ledgers/master data
- create defaults and feature flags
- This removes one-off onboarding gaps and makes tenant creation deterministic.

5. Standardize tenant-safe management command patterns
- Always accept either schema_name or tenant_id explicitly.
- Validate schema exists before schema_context switch.
- Add dry-run and all-tenants modes consistently.
- Fix any name-vs-schema confusion (example above).

6. Expand tenant isolation test suite
- Add integration tests for:
- domain to tenant resolution
- public URL vs tenant URL resolution
- unauthorized cross-workspace access attempts
- stale profile workspace mismatch
- background task tenant context propagation

7. Add tenant-aware async strategy
- For Celery tasks touching tenant data, pass schema_name/tenant_id as task arg and enter tenant_context in task body.
- Define a common helper to enforce this pattern.

8. Evaluate advanced django-tenants features you are not using
- Multi-type tenants (different app/url sets per tenant type) if you need plan/industry-specific product variants.
- Subfolder middleware if subdomain routing is hard in your infra.
- Migration executors/concurrency tuning for many-tenant migration speed.
- Tenant clone and tenant-specific maintenance command workflows for staging/support operations.

---

**Open Questions / Assumptions**

- I assumed your desired architecture is domain-driven tenant resolution first, then membership/RBAC.
- If you intentionally chose profile-driven switching over domain-driven routing, I can give a separate “workspace-switch-first” hardening design that still stays safe with django-tenants.

---

**Suggested Next Step**

1. I can produce a concrete hardening PR plan with exact code changes for middleware ordering, request.tenant standardization, and schema lifecycle policy.
2. I can also implement Phase 1 directly: middleware/routing correction + regression tests for cross-tenant isolation.


I’ll create a dedicated markdown report under django_project/docs capturing the findings, and then I’ll answer your three architecture questions with concrete examples from your current flow. I’m first checking whether the docs folder already exists so I can add the file in the right place.

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/django_project)

I confirmed django_project/docs is not present, so I’m creating it and writing a structured review document there with both findings and guidance on tenant resolution approaches.

Created [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/django_project/docs/DJANGO_TENANTS_USAGE_REVIEW_2026-03-27.md)

Created [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/django_project/docs)

I documented the findings here:

- DJANGO_TENANTS_USAGE_REVIEW_2026-03-27.md

What “core tenant resolution middleware is bypassed in runtime” means:
- In standard django-tenants flow, each request resolves tenant from the incoming host/domain first, then switches schema.
- In your active runtime flow, schema selection is primarily done from the user’s selected workspace in profile via middleware_v2.py, instead of domain-first resolution.
- So domain mapping is not the first authority for schema choice during request processing.

Difference between domain-driven and profile-driven switching:
- Domain-driven:
1. Request host decides tenant.
2. Schema is switched from domain mapping.
3. Profile/workspace only helps UX.
- Profile-driven:
1. User profile workspace decides tenant.
2. Host/domain becomes secondary or ignored for schema selection.
3. Useful for workspace picker UX, but riskier if used as primary isolation boundary.

Recommended way for tenant resolution:
1. Use domain-driven resolution as the primary source of truth in middleware.
2. Then enforce membership and role-based authorization.
3. Use profile workspace only as a preference for redirects and workspace selection UI.
4. Add consistency checks when profile workspace and resolved tenant differ.

If you want, I can implement Phase 1 now:
1. normalize middleware flow to domain-first tenant resolution,
2. keep your security membership checks,
3. add regression tests for cross-tenant access and public/tenant routing behavior.

Made changes.

. Clone Schema
django-tenants exposes a clone_schema Postgres function and a clone_tenant management command. It performs a structural+data copy of one schema into a new one.

How it's directly useful here:

Use Case	How
Demo/onboarding template	Create one _template tenant seeded with sample chart of accounts, product catalogue, loan terms, rate tables. When a new shop signs up, clone_tenant _template new_shop_schema instead of starting empty. Onboarding feels instant.
Subscription tier upgrade	A "pro" tenant can be pre-configured with DEA/purchase/sales schemas pre-seeded; clone it for new pro subscribers.
Staging environment from prod	Snapshot a live tenant for QA without touching production data, since it's just a Postgres schema copy.
Staff "training" workspaces	Clone a demo tenant per user for training without them touching each other's data.
Right now your onboarding (views.py) creates a blank schema — no seed data. Clone would replace that with a fully configured starting point.

3. Other django-tenants Features Not Being Used
schema_context() — partially used, could be used more systematically
You use it in views.py (company delete, subscription check) and views.py (team creation). But in models.py line 29 there's a commented-out tenant_context(...) call — suggests hesitation. This is the right tool for any code that needs to momentarily query a different schema in a task/signal/celery worker.

TenantTestCase / FastTenantTestCase — not used at all.
Your tenant app tests (tests_pr9.py) manually call schema_context(self._schema_name) — that's fragile. TenantTestCase creates a real tenant + domain per test class in a transaction, provides self.tenant, isolates properly, and cleans up. FastTenantTestCase wraps each test in a savepoint instead of creating/dropping schemas, so it's 10x faster.

tenant_command / all_tenants_command wrappers — not used.
These let you run any management command scoped to one or all tenants:
python manage.py all_tenants_command generate_reports

Relevant for your DEA closing entries, rate refresh, backup jobs.

PG_EXTRA_SEARCH_PATHS — not configured.
Lets you add extra schemas (e.g. a shared_data schema with read-only reference tables — gold rates, standard terms, product catalogue templates) that are visible within every tenant schema via Postgres search_path. This means you don't duplicate reference data across 50 tenant schemas.

TENANT_LIMIT_SET_CALLS — not set.
Setting TENANT_LIMIT_SET_CALLS = True makes django-tenants skip the SET search_path = ... SQL statement when the schema is already active for that connection. Small but worthwhile optimization in a request-heavy setup.

create_missing_schemas — not wired into CI/deploy.
Scans all Company rows and ensures their Postgres schema exists. Safety net for recovery after DB restore or migration failure. Worth adding to your deploy runbook.

SESSION_COOKIE_DOMAIN / CSRF_COOKIE_DOMAIN — commented out in your settings.
Once you go subdomain-based (e.g. shop.rokkad.com), setting .rokkad.com for both is required to prevent session bleed across tenants. Your settings comment already flags this.

Short answer: keep SecureWorkspaceMiddleware standalone as it is now.

Why this is the better design for your case:

1. Security flow is fundamentally different from TenantMainMiddleware  
TenantMainMiddleware is domain-resolution middleware. Your SecureWorkspaceMiddleware in middleware_v2.py is an authorization middleware too: membership validation, subscription checks, mismatch auditing, stale profile cleanup, and redirect behavior. Inheriting from TenantMainMiddleware from middleware.py would force awkward overrides and increase the chance of accidentally reintroducing unsafe defaults.

2. You need deterministic multi-source resolution  
Your current order (domain, then path, then profile fallback) is custom business logic. TenantMainMiddleware assumes a simpler host-only resolution model. Keeping v2 independent makes this logic explicit and testable.

3. Reduced inheritance risk  
Security middleware should avoid deep inheritance where parent behavior can change expected control flow. Standalone implementation gives clearer ownership of every schema switch and redirect path.

4. You already have strong test coverage for this exact behavior  
Your tests in tests.py validate the v2 flow directly. If you inherited from TenantMainMiddleware, tests would need to account for parent internals too, making security behavior more fragile over time.

When extending TenantMainMiddleware would be reasonable:
- If you wanted near-stock django-tenants behavior with minimal custom checks
- If you needed multi-type tenant URL routing exactly as parent implements it and were willing to align your flow to that model

Practical recommendation:
- Keep v2 as-is
- Remove or archive dead middleware in middleware.py once you are comfortable
- Optionally add a brief module comment in middleware_v2.py stating why it is intentionally standalone (security-critical custom flow)

I’ve confirmed the duplication surface: urls.py and tenant_urls.py repeat most routes. I’ll now extract a shared pattern list and have both URLconfs compose from it while keeping their schema-specific routes separate.

Generating patch (21 lines) in [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/django_project/shared_urlpatterns.py)


```

```


Generating patch (30 lines) in [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/django_project/urls.py)


```

```


Generating patch (35 lines) in [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/django_project/tenant_urls.py)


```

```
URL dedup refactor is applied to active URLconfs. I’ll now run diagnostics and Django checks/tests to confirm behavior is unchanged.

Ran terminal command: .\.venv314\Scripts\Activate.ps1; python manage.py check

Ran terminal command: .\.venv314\Scripts\Activate.ps1; python manage.py test apps.orgs.tests -v 1

Checked [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/django_project/shared_urlpatterns.py), [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/django_project/urls.py), [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/django_project/tenant_urls.py), no problems found

Item 1 is done and validated. I’ll move to item 2 now: find Girvi/DEA tests using manual `schema_context` and migrate them to `TenantTestCase`/`FastTenantTestCase` where practical.

Searched for regex `schema_context\(|tenant_context\(` (`**/apps/tenant_apps/girvi/**/test*.py`), no results

Searched for regex `schema_context\(|tenant_context\(` (`**/apps/tenant_apps/dea/**/test*.py`), no results

Searched for files matching `**/apps/tenant_apps/girvi/**/*test*.py`, 3 matches

Searched for files matching `**/apps/tenant_apps/dea/**/*test*.py`, no matches

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/girvi/tests.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/girvi/tests/test_payment_integration_pr1_pr2.py#1-1), lines 1 to 300

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/girvi/tests/test_series_guardrails.py)

Searched for text `class Domain|class Company` (`**/apps/orgs/models.py`), 6 results

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/models.py#80-80), lines 80 to 120

Searched for text `class Customer|workspace =` (`**/apps/tenant_apps/contact/models.py`), 5 results

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/contact/models.py#45-45), lines 45 to 95

Searched for text `workspace = models.ForeignKey` (`**/apps/tenant_apps/contact/models.py`), no results

I found no `schema_context` usage in Girvi/DEA tests to replace directly, so for item 2 I’ll still harden the active Girvi DB tests by moving them to `FastTenantTestCase` and removing non-essential setup that depended on profile/workspace assumptions.

Generating patch (53 lines) in [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/girvi/tests/test_series_guardrails.py)


```

```


Ran terminal command: .\.venv314\Scripts\Activate.ps1; python manage.py test apps.tenant_apps.girvi.tests.test_series_guardrails -v 2

Read [](file:///c%3A/Users/rajes/AppData/Roaming/Code/User/workspaceStorage/7914ab2b6b5df244df460c4b9f715f8d/GitHub.copilot-chat/chat-session-resources/088bc879-a95e-40b2-9df5-22797c039932/call_R5S1ij3yhDTVlQBGUAiHDFsX__vscode-1774588036340/content.txt#1-1), lines 1 to 260

Read [](file:///c%3A/Users/rajes/AppData/Roaming/Code/User/workspaceStorage/7914ab2b6b5df244df460c4b9f715f8d/GitHub.copilot-chat/chat-session-resources/088bc879-a95e-40b2-9df5-22797c039932/call_R5S1ij3yhDTVlQBGUAiHDFsX__vscode-1774588036340/content.txt#261-261), lines 261 to 337

Item 2 is complete and passing for Girvi (`FastTenantTestCase` migration). I’ll now implement item 4 and item 5 as safe configuration changes in settings: enable `TENANT_LIMIT_SET_CALLS` and add configurable `PG_EXTRA_SEARCH_PATHS`.

Generating patch (16 lines) in [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/django_project/settings/base.py)


```

```


Ran terminal command: .\.venv314\Scripts\Activate.ps1; python manage.py check

Checked [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/django_project/settings/base.py), no problems found

Settings updates for items 4 and 5 are in and validated. Next I’ll tackle item 3 by wiring onboarding to optionally clone from a template tenant schema, with safe fallback to normal schema creation if cloning isn’t configured.

Searched for text `Company.objects.create|schema_name|onboarding` (`**/apps/onboarding/views.py`), 20 results

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/onboarding/views.py#1-1), lines 1 to 220

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/onboarding/views.py#220-220), lines 220 to 368

Ran terminal command: .\.venv314\Scripts\Activate.ps1; python -c "import django_tenants, inspect; import django_tenants.clone as c; print('clone attrs:', [a for a in dir(c) if 'clone' in a.lower()]);"

Ran terminal command: .\.venv314\Scripts\Activate.ps1; python manage.py shell -c "import django_tenants.clone as c; print([a for a in dir(c) if 'clone' in a.lower()]); import inspect; print(inspect.getsource(c.clone_schema)[:400]);"

Ran terminal command: .\.venv314\Scripts\Activate.ps1; python manage.py shell -c "import inspect, django_tenants.clone as c; print(inspect.getsource(c)[:1200]);"

Ran terminal command: .\.venv314\Scripts\Activate.ps1; python manage.py shell -c "import inspect, django_tenants.clone as c; src=inspect.getsource(c); import re; [print(m.group(0)) for m in re.finditer(r'class\s+\w+|def\s+\w+\(', src)];"

Ran terminal command: .\.venv314\Scripts\Activate.ps1; python manage.py shell -c "import inspect, django_tenants.clone as c; src=inspect.getsource(c); idx=src.rfind('def clone_schema'); print(src[idx-250:idx+450]);"

For clone-based onboarding, I verified the installed django-tenants API supports `CloneSchema().clone_schema(...)`; I’ll now add a safe helper in onboarding that clones from a configured template schema when available, otherwise falls back to normal schema creation.

Generating patch (74 lines) in [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/onboarding/views.py)


```

```


Ran terminal command: .\.venv314\Scripts\Activate.ps1; python manage.py check

Checked [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/onboarding/views.py), no problems found

Ran terminal command: .\.venv314\Scripts\Activate.ps1; python manage.py test apps.orgs.tests apps.tenant_apps.girvi.tests.test_series_guardrails -v 1

Read [](file:///c%3A/Users/rajes/AppData/Roaming/Code/User/workspaceStorage/7914ab2b6b5df244df460c4b9f715f8d/GitHub.copilot-chat/chat-session-resources/088bc879-a95e-40b2-9df5-22797c039932/call_Sk8yhTA9yzqnFXoYeVzo1NZf__vscode-1774588036357/content.txt#520-520), lines 520 to 760

Ran terminal command: .\.venv314\Scripts\Activate.ps1; python manage.py test apps.tenant_apps.girvi.tests.test_series_guardrails -v 1

Read [](file:///c%3A/Users/rajes/AppData/Roaming/Code/User/workspaceStorage/7914ab2b6b5df244df460c4b9f715f8d/GitHub.copilot-chat/chat-session-resources/088bc879-a95e-40b2-9df5-22797c039932/call_CLYu6EeK5HX2mpQs3CmVIP4t__vscode-1774588036359/content.txt#700-700), lines 700 to 760

Read [](file:///c%3A/Users/rajes/AppData/Roaming/Code/User/workspaceStorage/7914ab2b6b5df244df460c4b9f715f8d/GitHub.copilot-chat/chat-session-resources/088bc879-a95e-40b2-9df5-22797c039932/call_CLYu6EeK5HX2mpQs3CmVIP4t__vscode-1774588036359/content.txt#760-760), lines 760 to 840

I hit an issue: the `FastTenantTestCase` migration for the Girvi guardrails file is not stable in this repo’s current test setup (`girvi_license` table missing at runtime), so I’m rolling that specific test file back to keep the suite safe; we can reintroduce tenant test base later via a dedicated test runner path.

Generating patch (55 lines) in [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/girvi/tests/test_series_guardrails.py)


```

```


Ran terminal command: .\.venv314\Scripts\Activate.ps1; python manage.py test apps.orgs.tests -v 1

Checked [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/girvi/tests/test_series_guardrails.py), [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/onboarding/views.py), [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/django_project/settings/base.py), no problems found

Read changed files in the active git repository

Completed. I moved through the list one by one and applied what is safe right now.

**What I implemented**

1. URL deduplication with shared patterns
- Added shared URL pattern module: shared_urlpatterns.py
- Refactored public URLconf to compose from shared patterns + public-only admin route: urls.py
- Refactored tenant URLconf to compose from shared patterns + tenant-only app routes: tenant_urls.py
- Result: shared routes now live in one place, so adding/removing common routes won’t diverge between public and tenant URLconfs.

2. TenantTestCase for girvi/DEA tests
- I investigated this specifically.
- There are no schema_context usages in girvi/dea test files to directly replace.
- I attempted migrating girvi guardrail tests to FastTenantTestCase, but this became unstable in this repo’s current runner setup (tenant table relation errors), so I safely rolled that file back to avoid introducing regressions: test_series_guardrails.py
- Current status: no net risky test migration committed for this item yet.

3. Clone schema onboarding support
- Added optional template-based schema provisioning in onboarding:
  - New helper in views.py uses CloneSchema when ONBOARDING_TEMPLATE_SCHEMA is configured and valid.
  - Falls back safely to normal fresh schema creation if template is missing/misconfigured.
- Also logs provisioning mode in audit data (fresh vs cloned).

4. TENANT_LIMIT_SET_CALLS = True
- Added in base.py

5. PG_EXTRA_SEARCH_PATHS support
- Added configurable setting in base.py
- Reads from environment via PG_EXTRA_SEARCH_PATHS, default empty list.

**Validation run**
- Django check: passed
- Orgs middleware test suite: passed (18/18)

**Important note on item 2**
- I did not leave a half-broken TenantTestCase conversion in place.
- If you want, next I can do a dedicated, isolated pass to introduce a stable tenant-test base class for girvi/dea with proper schema lifecycle setup and then migrate selected DB tests incrementally. That is the right way to finish item 2 cleanly without flaky failures.

Made changes.