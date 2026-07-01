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

The SaaS IA target routes now resolve for the top-level tenant entrypoints. The
low-risk Phase 13.3 entries `/w/<workspace_slug>/parties/`,
`/inventory/`, `/loans/`, and `/accounting/` direct-render their existing
module entry views while preserving the slug URL. Other tenant route-map entries
such as operations, sales, purchase, commodity, reports, and workspace setting
detail aliases still redirect to existing legacy targets.

This compatibility layer should not be described as full canonical route
ownership because deep app links and legacy tenant roots remain active.

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

Status: complete for the low-risk entrypoint set.

For top-level module entrypoints only, replace redirect-only slug views with
wrappers that preserve the `/w/<workspace_slug>/...` URL while delegating to the
existing entry view or equivalent read model.

Start with low-risk entrypoints:

- `/w/<workspace_slug>/parties/` - direct-renders the existing Party list view
  while preserving the slug URL.
- `/w/<workspace_slug>/inventory/` - direct-renders the existing Product home
  view while preserving the slug URL.
- `/w/<workspace_slug>/loans/` - direct-renders the existing Girvi dashboard
  view while preserving the slug URL.
- `/w/<workspace_slug>/accounting/` - direct-renders the existing DEA home view
  while preserving the slug URL.

The first Phase 13.3 slice converts `/w/<workspace_slug>/parties/` from a
redirect-only alias into a direct-render wrapper around the existing
`party_list` view. This keeps Party's current authorization and query behavior
as the source of truth while making the browser stay on the canonical slug
entry URL.

The second Phase 13.3 slice converts `/w/<workspace_slug>/inventory/` from a
redirect-only alias into a direct-render wrapper around the existing Product
home view. This preserves the current Product entrypoint policy: the dashboard
itself requires login, while detailed product, stock, pricing, image, and
attribute views continue to enforce their Product action guards.

The third Phase 13.3 slice converts `/w/<workspace_slug>/loans/` from a
redirect-only alias into a direct-render wrapper around the existing Girvi
dashboard view. This preserves Girvi's current entrypoint policy by keeping the
Girvi workspace access guard as the source of truth and leaving deep loan,
repayment, release, custody, print, notice, and report routes unchanged.

The fourth Phase 13.3 slice converts `/w/<workspace_slug>/accounting/` from a
redirect-only alias into a direct-render wrapper around the existing DEA home
view. This preserves the current target and keeps the slug wrapper's login
boundary while leaving DEA operations, sales, purchase, commodity, reports, and
deep accounting routes unchanged.

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

Proceed with Phase 13.4: inventory the remaining deep route canonicalization
work for DEA, Girvi, Party, Product, Rates, Notify, and data tools before
changing internal links or remounting nested route groups.
