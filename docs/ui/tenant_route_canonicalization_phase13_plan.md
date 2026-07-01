---
status: active
owner: ui
updated: 2026-07-01
tags: [ui, saas-ia, routes, tenant, canonicalization]
related:
  - docs/ui/saas_information_architecture_audit.md
  - docs/ui/workspace_slug_phase11_review.md
  - django_project/tenant_urls.py
  - django_project/shared_urlpatterns.py
---

# Tenant Route Canonicalization Phase 13 Plan

Phase 13 exists because the `/w/<workspace_slug>/...` routes are currently
available as aliases, not as full canonical replacements for the tenant app
roots.

## Current Reality

The tenant URLConf still mounts runtime apps at their original tenant roots:

- `/party/`
- `/contact/`
- `/data-tools/`
- `/girvi/`
- `/rates/`
- `/product/`
- `/notify/`
- `/notify-v2/`
- `/dea/`

The SaaS IA target routes such as `/w/<workspace_slug>/accounting/` and
`/w/<workspace_slug>/loans/` currently resolve, but the route views redirect to
the existing app entrypoints. That means the browser still lands on URLs such as
`/dea/`, `/party/`, and `/girvi/`.

This was intentional for compatibility, but it should not be described as full
canonical route ownership.

## Boundary Clarification

Phase 11 completed route availability for the tenant/workspace settings target
map. It did not remove legacy tenant roots, remount app URLConfs under
`/w/<workspace_slug>/...`, or rewrite deep app links.

Full canonicalization is a separate phase because it touches:

- tenant URLConf ownership;
- middleware workspace resolution;
- reverse names and templates across DEA, Girvi, Party, Product, Rates, Notify,
  and data tools;
- HTMX endpoints and partial links;
- model `get_absolute_url()` methods;
- tests and existing bookmarks.

## Recommended Direction

Do not big-bang remount all tenant apps under `/w/<workspace_slug>/...`.

Proceed in small groups:

1. Keep legacy tenant roots active as compatibility routes.
2. Convert visible navigation and dashboard entrypoints to the slug routes.
3. For each module, decide whether the slug route should render the target view
   directly, include a nested URL group, or remain a redirect.
4. Update one module's internal links and `get_absolute_url()` behavior at a
   time.
5. Add redirects from legacy roots only after module-level tests prove no loops,
   HTMX regressions, or cross-workspace leaks.

## Suggested Phase 13 Slices

### Phase 13.1: Documentation And Guard Baseline

Status: complete.

Record that legacy tenant app roots are still active and that slug routes are
currently compatibility aliases. Add tests so future work cannot accidentally
claim the legacy roots are gone.

### Phase 13.2: Sidebar And Dashboard Entry Links

Status: complete.

Move remaining visible top-level tenant navigation links to the existing slug
aliases where `effective_workspace.schema_name` is available:

- business events -> `/w/<workspace_slug>/operations/`
- financial reports -> `/w/<workspace_slug>/reports/`
- commodity master -> `/w/<workspace_slug>/commodity/`
- accounting entrypoint -> `/w/<workspace_slug>/accounting/` where a top-level
  accounting link is shown

Do not change deep accounting tool links yet.

Phase 13.2 converted the tenant sidebar's Business Events, Financial Reports,
and Commodity Master entry links to slug aliases. It also converted the
workspace dashboard DEA Dashboard quick action to `/w/<workspace_slug>/accounting/`.
Legacy tenant roots remain active.

### Phase 13.3: Direct-Render Entry Wrappers

For top-level module entrypoints only, replace redirect-only slug views with
wrappers that preserve the `/w/<workspace_slug>/...` URL while delegating to the
existing entry view or equivalent read model.

Start with low-risk entrypoints:

- `/w/<workspace_slug>/parties/`
- `/w/<workspace_slug>/inventory/`
- `/w/<workspace_slug>/loans/`
- `/w/<workspace_slug>/accounting/`

### Phase 13.4: Module Deep-Link Plan

Inventory and plan deep route canonicalization for:

- DEA vouchers, reports, accounts, periods, business events, commodity.
- Girvi loan detail, create, repayment, release, custody, reports.
- Party detail/profile/merge/export.
- Product stock, pricing, attributes, images.
- Rates, Notify, data tools.

### Phase 13.5: Module-By-Module Canonicalization

Move deep links one module at a time, keeping legacy URLs as redirects until
bookmarks and tests stabilize.

## Non-Negotiables

- Public URLConf must still reject tenant ERP roots.
- Legacy tenant roots must not be removed without regression coverage.
- No redirect loops between `/w/<workspace_slug>/...` and `/dea/` or similar
  roots.
- Workspace slug resolution must continue to reject inaccessible workspaces.
- Contact should not receive a canonical slug route because Party replaces it.

## Next Recommended Step

Proceed with Phase 13.3: replace redirect-only slug entry wrappers with
direct-render wrappers for one low-risk module entrypoint at a time, while
keeping legacy roots active.
