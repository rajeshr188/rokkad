---
status: active
owner: ui
updated: 2026-07-01
tags: [ui, saas-ia, routes, tenant, canonicalization]
related:
  - docs/ui/saas_information_architecture_audit.md
  - docs/ui/tenant_route_canonicalization_phase13_plan.md
  - django_project/tenant_urls.py
  - django_project/shared_urlpatterns.py
---

# Tenant Deep-Link Canonicalization Phase 13.4 Plan

Phase 13.4 is a planning and guard phase. It should not remount nested tenant
apps or rewrite internal links yet.

## Current Boundary

Phase 13.3 made the low-risk tenant entrypoints preserve the slug URL:

- `/w/<workspace_slug>/parties/`
- `/w/<workspace_slug>/inventory/`
- `/w/<workspace_slug>/loans/`
- `/w/<workspace_slug>/accounting/`

Legacy tenant roots remain active:

- `/party/`
- `/product/`
- `/girvi/`
- `/dea/`
- `/rates/`
- `/notify/`
- `/notify-v2/`
- `/data-tools/`
- `/contact/`

Operations, sales, purchase, commodity, reports, and workspace-settings detail
slug routes remain compatibility aliases that redirect to existing targets.
Deep module links still use legacy route names and paths.

## Non-Goals

- Do not include full app URLConfs under `/w/<workspace_slug>/...` yet.
- Do not remove legacy tenant roots.
- Do not change model `get_absolute_url()` methods yet.
- Do not rewrite HTMX partial endpoints before checking their targets.
- Do not add a canonical Contact route; Party remains the replacement.

## Proposed Module Order

### 1. Party

Recommended first deep-link module.

Why:

- Party already has focused access helpers and action guards.
- The route tree is smaller than DEA, Girvi, or Product.
- Contact is being phased out in favor of Party, so Party should become the
  canonical relationship surface before broader business modules move.

Initial canonical aliases:

- `/w/<workspace_slug>/parties/new/` -> `party_create`
- `/w/<workspace_slug>/parties/<pk>/` -> `party_detail`
- `/w/<workspace_slug>/parties/<pk>/edit/` -> `party_update`
- `/w/<workspace_slug>/parties/<pk>/merge/` -> `party_merge`

Keep nested mutations legacy-only until the detail/edit aliases are proven:

- contact save/delete/default;
- address save/delete/default;
- identifier save/delete;
- document save/delete;
- role add/end.

### 2. Product And Inventory

Recommended second deep-link module.

Why:

- Product authorization has already been cleaned up for catalog, stock,
  pricing, image, and attribute route groups.
- Product has many list/detail/form routes but fewer cross-module accounting
  side effects than DEA and Girvi.

Initial canonical aliases:

- `/w/<workspace_slug>/inventory/products/`
- `/w/<workspace_slug>/inventory/products/<pk>/`
- `/w/<workspace_slug>/inventory/product-types/`
- `/w/<workspace_slug>/inventory/variants/`
- `/w/<workspace_slug>/inventory/stock/`
- `/w/<workspace_slug>/inventory/pricing/`

Known issues to resolve before implementation:

- `stock/create/` is currently declared twice with different route names.
- HTMX list endpoints should keep stable `hx-get` targets until partial tests
  exist.
- Product `Dashboard` links in templates still point to `product_product_home`.

### 3. Rates

Recommended third module.

Why:

- The route tree is small and action-guarded.
- Rates are operationally important for commodity and jewellery workflows, but
  the module has limited nested routes.

Initial canonical aliases:

- `/w/<workspace_slug>/rates/`
- `/w/<workspace_slug>/rates/new/`
- `/w/<workspace_slug>/rates/<pk>/`
- `/w/<workspace_slug>/rate-sources/`

### 4. Notify And Notify V2

Recommended fourth module.

Why:

- Notification routes are smaller than DEA/Girvi but include print/send
  side-effect paths.
- `notify_v2_whatsapp_cloud_webhook` is intentionally public-ish and must not be
  accidentally moved behind workspace slug-only routing without a webhook design.

Initial canonical aliases:

- `/w/<workspace_slug>/notifications/`
- `/w/<workspace_slug>/notifications/batches/`
- `/w/<workspace_slug>/notifications/batches/<pk>/`
- `/w/<workspace_slug>/notifications/templates/` only after template ownership
  is clarified.

Keep webhooks on current routes until webhook tenancy and provider callback URLs
are explicitly designed.

### 5. Data Tools

Recommended fifth module.

Why:

- Routes are few, but import/export has broad model access implications.

Initial canonical aliases:

- `/w/<workspace_slug>/data/export/`
- `/w/<workspace_slug>/data/import/`
- `/w/<workspace_slug>/data/model-fields/`

Required before implementation:

- Explicit allowed model registry per workspace role.
- Export/import permission tests.
- Confirmation that public/global models cannot be selected from tenant import
  screens.

### 6. Girvi

Recommended after Party/Product/Rates/Notify/Data Tools.

Why:

- Route tree is large and mixes loan lifecycle, repayments, release, custody,
  print, notices, statements, storage boxes, templates, series, and reports.
- Some URL paths still include nested `girvi/loan/...` under the `/girvi/` root.
- Lifecycle compatibility aliases should remain until bookmarked transition URLs
  and imported statuses are retired.

Suggested sub-phases:

1. Read-only loan list/detail/statement/report aliases.
2. Loan create/edit/delete and bulk operations.
3. Repayment and release workflows.
4. Custody and repledge workflows.
5. Print/template/document routes.
6. Legacy lifecycle transition aliases.

### 7. DEA

Recommended last among core ERP modules.

Why:

- DEA is the accounting core and has the highest blast radius.
- Routes include business events, commodity master, reports, vouchers, payments,
  expenses, journals, ledgers, accounts, periods, reconciliation, dashboards, and
  AJAX endpoints.
- Accountant-only tools and normal staff business-event/report surfaces should
  remain distinct.

Suggested sub-phases:

1. Read-only accounting reports and chart-of-accounts aliases.
2. Business-event aliases for operations/sales/purchase.
3. Commodity master and commodity reports.
4. Voucher/payment/expense/journal read-only routes.
5. Voucher/posting/mutation routes.
6. Period lock/unlock/close routes.
7. AJAX/dashboard metric endpoints.

## Route Naming Direction

Do not rename existing route names yet. Add slug aliases with new route names
only where needed, then move templates gradually.

Preferred alias naming pattern:

- `workspace_slug_party_detail`
- `workspace_slug_inventory_stock_list`
- `workspace_slug_rate_list`
- `workspace_slug_notification_batch_detail`
- `workspace_slug_girvi_loan_detail`
- `workspace_slug_dea_report_hub`

Legacy names should remain available until module-level compatibility tests prove
the alias surface is stable.

## Template Migration Rules

For each module:

1. Move only visible navigation and page-level links first.
2. Keep form actions on legacy routes until POST behavior is covered.
3. Keep HTMX endpoints on legacy routes until partial render tests exist.
4. Update `get_absolute_url()` only after detail aliases are live.
5. Add redirects from legacy roots only after deep links are stable.

## Required Tests Before Phase 13.5

- Public URLConf still rejects tenant ERP roots and `/w/...` tenant paths.
- Tenant URLConf resolves both legacy and canonical aliases.
- Canonical aliases do not redirect back to legacy roots for migrated views.
- Legacy roots remain active compatibility routes.
- HTMX list/search/filter links continue to render partials.
- POST routes preserve CSRF, permission checks, safe redirects, and audit events.
- Cross-workspace slug mismatch fails closed.
- Customer portal `/portal/...` remains out of scope.

## Next Recommended Step

Phase 13.5a is complete for Party read-only redirect aliases. Start the next
route-canonicalization phase with Party direct-render deep aliases and internal
link migration, then move to Product/Inventory, Rates, Notify, Data Tools,
Girvi, and DEA in that order.
