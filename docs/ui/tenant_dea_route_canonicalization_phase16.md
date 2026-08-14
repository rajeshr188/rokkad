---
status: active
owner: ui
updated: 2026-07-01
tags: [ui, saas-ia, routes, tenant, dea, accounting, canonicalization]
related:
  - docs/ui/saas_information_architecture_audit.md
  - docs/ui/tenant_deep_link_canonicalization_phase13_4_plan.md
  - docs/ui/tenant_girvi_route_canonicalization_phase15.md
  - django_project/shared_urlpatterns.py
  - apps/orgs/views.py
  - apps/tenant_apps/dea/urls.py
---

# Tenant DEA Route Canonicalization Phase 16

Phase 16 is the compressed DEA/Accounting read-only route-canonicalization
phase.

## Completed

The top-level DEA slug aliases now direct-render existing views instead of
redirecting back to `/dea/...`:

- `/w/<workspace_slug>/operations/`
- `/w/<workspace_slug>/sales/`
- `/w/<workspace_slug>/purchase/`
- `/w/<workspace_slug>/commodity/`
- `/w/<workspace_slug>/reports/`

Read-only accounting aliases are available under `/w/<workspace_slug>/...`:

- chart of accounts;
- account list and detail;
- ledger list and detail;
- unified transaction list;
- financial statement and aging reports;
- voucher list and detail;
- payment voucher list and detail;
- expense voucher list and detail;
- journal entry voucher list and detail;
- accounting period list and detail;
- bank reconciliation list and detail;
- commodity detail and commodity reports.

Each wrapper validates the workspace slug and delegates to the existing DEA
view, preserving the current DEA permission and accountant-tool behavior.

## Deferred

These stay on legacy DEA routes until focused accounting/posting regression
coverage exists:

- voucher create/edit/delete/post/reverse;
- payment create/edit/delete;
- expense create/edit/delete/post;
- journal-entry voucher create/edit/delete;
- manual journal entry mutation routes;
- opening-balance wizard, bulk import, and validation endpoints;
- period create/update/delete/close/lock/unlock;
- reconciliation import/auto-match/manual-match/unmatch;
- business-event preview, detail, confirm, and posting workflows;
- commodity create/edit/deactivate/account setup;
- dashboard AJAX metric endpoints;
- legacy root redirect/removal decisions.

## Next Recommended Step

Run the final compatibility phase: document the legacy-root policy, keep current
legacy roots active, and add regression coverage that canonical aliases and
legacy routes coexist. Do not remove or redirect legacy roots until real
bookmarks, HTMX endpoints, POST workflows, and accounting posting paths have
module-specific tests.
