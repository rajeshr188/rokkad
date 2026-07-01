---
status: active
owner: ui
updated: 2026-07-01
tags: [ui, saas-ia, routes, tenant, girvi, loans, canonicalization]
related:
  - docs/ui/saas_information_architecture_audit.md
  - docs/ui/tenant_deep_link_canonicalization_phase13_4_plan.md
  - docs/ui/tenant_party_deep_link_canonicalization_phase14.md
  - django_project/shared_urlpatterns.py
  - apps/orgs/views.py
  - apps/tenant_apps/girvi/urls.py
---

# Tenant Girvi Route Canonicalization Phase 15

Phase 15 is the compressed Girvi/Loans route-canonicalization phase.

## Completed

Read-only loan and report aliases are available under `/w/<workspace_slug>/...`:

- `/w/<workspace_slug>/loans/list/`
- `/w/<workspace_slug>/loans/table/`
- `/w/<workspace_slug>/loans/<pk>/`
- `/w/<workspace_slug>/loans/<pk>/items/`
- `/w/<workspace_slug>/loans/<pk>/payments/`
- `/w/<workspace_slug>/loans/<pk>/transactions/`
- `/w/<workspace_slug>/loans/<pk>/statement/`
- `/w/<workspace_slug>/loans/<pk>/notices/`
- `/w/<workspace_slug>/loans/<pk>/release/`
- `/w/<workspace_slug>/loans/<pk>/pdf/`
- `/w/<workspace_slug>/loans/reports/time-series/`
- `/w/<workspace_slug>/loans/reports/by-customer/`
- `/w/<workspace_slug>/loans/reports/crosstab/`
- `/w/<workspace_slug>/loans/reports/list/`
- `/w/<workspace_slug>/loans/reports/reconciliation/`
- `/w/<workspace_slug>/loans/reports/operational-controls/`

Each wrapper validates the workspace slug and delegates to the existing Girvi
view, preserving Girvi's current workspace and permission guards.

## Deferred

The following stay on legacy Girvi routes until their lifecycle and accounting
effects are covered by focused regression tests:

- loan create/update/delete;
- loan renewal;
- repayments;
- release create/update/delete;
- custody and repledge workflows;
- lifecycle transition endpoints;
- operations console retry POST actions;
- template/document mutation routes;
- storage-box mutation routes;
- legacy root redirect/removal decisions.

## Next Recommended Step

Start the compressed DEA/Accounting phase with read-only accounting reports,
chart-of-accounts, commodity detail/report, and voucher detail aliases first.
Do not alias posting, period mutation, voucher creation, journal, payment,
expense, reconciliation import, or outbox retry actions until those workflows
have focused tests.
