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

The tenant/workspace settings alias map from the SaaS IA target is complete as
of Phase 11, except for the separate customer/member portal and the intentionally
skipped Contact route. `docs/ui/workspace_slug_phase11_review.md` lists the live
`/w/<workspace_slug>/...` routes and `django_project.test_workspace_slug_route_map_intent`
guards the route names and paths.

## Next Recommended Step

Proceed with Phase 12.5 only after deciding whether to add a minimal portal URL
group with placeholder views or first implement the real `PartyPortalAccess`
model. The safer next slice is a portal route plan/review before adding live
`/portal/...` routes.
