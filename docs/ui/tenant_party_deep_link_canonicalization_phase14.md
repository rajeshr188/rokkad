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

# Tenant Low-Risk Deep-Link Canonicalization Phase 14

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

## Phase 14.2 Completed

Visible Party GET links now prefer slug routes when `user_workspace` is
available:

- Party list create/detail/edit links;
- Party form back/cancel links;
- Party detail back/edit/related-party/cancel/edit-tab links;
- Convert Customer back link.

The Convert Customer workflow itself remains legacy-only because there is no
slug alias for that mutation-oriented flow yet.

Read-only slug aliases are also available for low-risk module surfaces:

- `/w/<workspace_slug>/inventory/products/`
- `/w/<workspace_slug>/inventory/products/<pk>/`
- `/w/<workspace_slug>/inventory/stock/`
- `/w/<workspace_slug>/inventory/stock/<pk>/`
- `/w/<workspace_slug>/inventory/stock/audit/`
- `/w/<workspace_slug>/inventory/transactions/`
- `/w/<workspace_slug>/inventory/statements/`
- `/w/<workspace_slug>/rates/`
- `/w/<workspace_slug>/rates/<pk>/`
- `/w/<workspace_slug>/rates/sources/`
- `/w/<workspace_slug>/rates/sources/<pk>/`
- `/w/<workspace_slug>/notifications/`
- `/w/<workspace_slug>/notifications/<pk>/`
- `/w/<workspace_slug>/notifications/notice-groups/`
- `/w/<workspace_slug>/notifications/notice-groups/<pk>/`
- `/w/<workspace_slug>/data-tools/export/`
- `/w/<workspace_slug>/data-tools/export/<model_name>/<export_format>/`

These wrappers validate the workspace slug and then delegate to existing module
views, preserving Product, Rates, Notify, and Data Tools authorization.

Mutation aliases remain absent for this low-risk batch:

- Product create/edit/delete and stock movement routes;
- Rates create/edit/delete routes;
- Notify create/delete/print routes;
- Data Tools import routes;
- nested Party mutation routes.

## Next Recommended Step

Start the compressed Girvi/Loans phase. Add read-only loan list/detail/report
aliases first, then handle repayment, release, custody, document, and lifecycle
mutation routes only after focused regression coverage exists.
