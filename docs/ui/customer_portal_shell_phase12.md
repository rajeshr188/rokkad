---
status: active
owner: ui
updated: 2026-07-01
tags: [ui, saas-ia, portal, shell, navigation]
related:
  - docs/ui/customer_portal_phase12_plan.md
  - docs/ui/customer_portal_selector_contracts_phase12.md
  - templates/base_customer_portal.html
---

# Customer Portal Shell Phase 12

Phase 12.4 upgrades `base_customer_portal.html` from a thin base alias into a
real customer/member portal shell. It does not add live `/portal/...` routes.

## What Changed

- `base_customer_portal.html` now owns a portal topbar, identity pill, and
  `portal_content` block.
- `templates/components/navigation/customer_portal_nav.html` owns portal-only
  navigation labels for overview, loans, invoices, payments, documents, and
  statements.
- `static/css/customer_portal.css` owns the portal layout and visual contract.

## Route Policy

The portal navigation deliberately does not reverse route names such as
`customer_portal_loans` yet. Links are disabled and marked as pending until live
portal routes are introduced after identity binding and real Party-scoped
selectors exist.

## Boundary Rules

- No tenant ERP sidebar or workspace-admin navigation is included.
- No public marketing navbar is included.
- Account access is limited to the existing account-settings link.
- Portal content must use `{% block portal_content %}`.
- `/portal/...` routes remain absent.

## Workspace Slug Route-Map Verification

The tenant/workspace settings alias map from the SaaS IA target is available as
of Phase 11, except for the separate customer/member portal and the intentionally
skipped Contact route. It is not a full canonical replacement yet:
`/w/<workspace_slug>/...` entry routes still redirect to legacy tenant roots
such as `/dea/`, `/party/`, and `/girvi/`.

`docs/ui/tenant_route_canonicalization_phase13_plan.md` now tracks the separate
work needed to keep users on canonical slug URLs.

## Next Recommended Step

Proceed with Phase 13.2 before live portal routes: convert remaining visible
tenant sidebar/dashboard entry links to slug aliases while keeping legacy tenant
roots active.
