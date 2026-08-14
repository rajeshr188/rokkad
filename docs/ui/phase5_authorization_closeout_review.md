---
status: active
owner: project
updated: 2026-06-29
tags: [ui, authorization, saas, review]
related: [authorization_cleanup_inventory.md, saas_information_architecture_audit.md, ../STATUS.md, ../AGENT_MEMORY.md]
---

# Phase 5 Authorization Closeout Review

This review closes the SaaS IA Phase 5 authorization cleanup scope for the current route groups.

## Completed Scope

- Middleware tenant-prefix coverage keeps every current tenant ERP prefix behind workspace-required handling.
- Party routes use Party action guards.
- Product catalog, stock, pricing, image, and attribute routes use Product action guards.
- Rates routes use Rate action guards.
- Legacy Notify routes and Notify v2 user-facing batch/settings routes use Notify action guards.
- Utility data import/export routes retain owner/admin workspace guards.
- Direct Contact cleanup is intentionally skipped because Party is replacing Contact; targeted patches are still allowed for unsafe compatibility routes before cutover.

## Intentional Boundaries

- Notify v2 WhatsApp Cloud webhook remains public because it is an external provider callback guarded by provider verification tokens.
- DEA and Girvi are not fully closed by this SaaS UI phase. They have broader accounting and loan permission semantics and remain in dedicated domain hardening tracks.
- Current Product/Rates/Notify guards use existing generic data permissions because module-specific codenames do not yet exist.

## Verification

Run:

```powershell
.\.venv314\Scripts\python.exe manage.py test apps.tenant_apps.product.tests_access django_project.test_authorization_surface_intent --keepdb
.\.venv314\Scripts\python.exe manage.py check
.\.venv314\Scripts\python.exe -m compileall apps\tenant_apps\product apps\tenant_apps\rates apps\tenant_apps\notify apps\tenant_apps\notify_v2
git diff --check
```

## Next Step

Commit the Phase 5 set, then begin Phase 6 onboarding.
