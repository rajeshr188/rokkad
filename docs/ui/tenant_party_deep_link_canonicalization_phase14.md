---
status: active
owner: ui
updated: 2026-07-01
tags: [ui, saas-ia, routes, tenant, party, canonicalization]
related:
  - docs/ui/saas_information_architecture_audit.md
  - docs/ui/tenant_route_canonicalization_phase13_review.md
  - docs/ui/tenant_deep_link_canonicalization_phase13_4_plan.md
  - django_project/shared_urlpatterns.py
  - apps/orgs/views.py
  - apps/tenant_apps/party/views.py
---

# Tenant Party Deep-Link Canonicalization Phase 14

Phase 14 starts the post-Phase-13 route-canonicalization work.

## Phase 14.1 Completed

Party read-only deep aliases now direct-render the existing Party views instead
of redirecting back to `/party/...`:

- `/w/<workspace_slug>/parties/new/`
- `/w/<workspace_slug>/parties/<pk>/`
- `/w/<workspace_slug>/parties/<pk>/edit/`
- `/w/<workspace_slug>/parties/<pk>/merge/`

The wrappers still validate the workspace slug first, then delegate to the
existing Party view functions. Party's current `party_action_required(...)`
decorators remain the source of authorization truth.

## Still Deferred

- Party internal links still mostly point at the legacy `party:*` route names.
- Party `_party_detail_url()` and successful form redirects still return legacy
  `/party/...` targets.
- Nested Party mutation routes remain legacy-only until POST behavior, HTMX
  partials, CSRF, permissions, and safe redirects are covered:
  - contacts;
  - addresses;
  - identifiers;
  - documents;
  - roles.
- Legacy `/party/...` routes remain active compatibility routes.

## Next Recommended Step

Migrate visible Party page-level links to slug routes where workspace schema
context is reliable, starting with list-to-detail/create/edit/merge links.
Keep nested form actions and HTMX mutation endpoints on legacy routes until
dedicated POST regression tests exist.
