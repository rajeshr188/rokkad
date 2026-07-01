---
status: active
owner: ui
updated: 2026-07-01
tags: [ui, saas-ia, routes, tenant, compatibility, canonicalization]
related:
  - docs/ui/saas_information_architecture_audit.md
  - docs/ui/tenant_route_canonicalization_phase13_review.md
  - docs/ui/tenant_party_deep_link_canonicalization_phase14.md
  - docs/ui/tenant_girvi_route_canonicalization_phase15.md
  - docs/ui/tenant_dea_route_canonicalization_phase16.md
  - django_project/tenant_urls.py
  - django_project/shared_urlpatterns.py
---

# Tenant Legacy Root Compatibility Phase 17

Phase 17 closes the compressed route-canonicalization work at a compatibility
boundary.

## Policy

Legacy tenant roots remain active:

- `/party/`
- `/product/`
- `/girvi/`
- `/dea/`
- `/rates/`
- `/notify/`
- `/notify-v2/`
- `/data-tools/`

They are compatibility routes, not the preferred long-term navigation surface.
Visible navigation and selected read-only deep links now prefer canonical
`/w/<workspace_slug>/...` aliases where coverage exists.

## Why Legacy Roots Stay

Do not remove or globally redirect legacy tenant roots yet because:

- many POST workflows still submit to legacy routes;
- HTMX endpoints still target legacy route names;
- module success redirects still return legacy paths;
- user bookmarks may still reference legacy roots;
- DEA posting and Girvi lifecycle workflows need module-specific regression
  coverage before redirecting mutation paths;
- Contact remains intentionally phased out in favor of Party.

## Completion Boundary

The compressed SaaS IA route-canonicalization work is complete for:

- low-risk Party/Product/Inventory/Rates/Notify/Data Tools read-only aliases;
- Girvi loan read-only aliases;
- DEA read-only accounting and commodity aliases;
- direct-render top-level tenant section aliases.

The remaining work is no longer a route-map rollout. It is module-specific workflow migration:

- move remaining internal links where workspace context is reliable;
- migrate POST success redirects module by module;
- add slug aliases for mutation endpoints only with focused tests;
- later decide whether legacy roots become permanent compatibility paths,
  redirects, or retired URLs.

## Next Recommended Step

Pause route canonicalization and return to product workflow hardening. The next
large route task should be either customer portal runtime access
(`PartyPortalAccess`) or a module-specific POST migration with tests, not a
blanket legacy-root redirect.
