---
status: active
owner: ui
updated: 2026-06-30
tags: [ui, saas-ia, routes, workspace, review]
related:
  - docs/ui/workspace_slug_route_map_plan.md
  - docs/ui/workspace_slug_deferred_targets_plan.md
  - docs/ui/workspace_slug_route_map_review.md
  - docs/ui/saas_information_architecture_audit.md
---

# Workspace Slug Phase 11 Review

Phase 11 completes route availability for the remaining workspace slug
route-map entries from the SaaS IA target route map, except for the
intentionally separate customer/member portal. It does not make the slug routes
full canonical replacements for the legacy tenant app roots.

## Completed

- Phase 11.1 selected concrete targets for the deferred workspace slug routes.
- Phase 11.2 added safe redirect aliases for operations, sales, purchase,
  commodity, reports, settings/profile, settings/billing, and
  settings/accounting.
- Phase 11.3 added interim settings redirects for settings/roles and
  settings/numbering.
- Phase 11.4 added real workspace-owned settings screens for modules and
  security/audit before exposing their slug aliases.

## Route Coverage

The following target routes are now live:

- `/w/<workspace_slug>/`
- `/w/<workspace_slug>/operations/`
- `/w/<workspace_slug>/parties/`
- `/w/<workspace_slug>/sales/`
- `/w/<workspace_slug>/purchase/`
- `/w/<workspace_slug>/loans/`
- `/w/<workspace_slug>/inventory/`
- `/w/<workspace_slug>/commodity/`
- `/w/<workspace_slug>/accounting/`
- `/w/<workspace_slug>/reports/`
- `/w/<workspace_slug>/settings/`
- `/w/<workspace_slug>/settings/profile/`
- `/w/<workspace_slug>/settings/team/`
- `/w/<workspace_slug>/settings/invitations/`
- `/w/<workspace_slug>/settings/roles/`
- `/w/<workspace_slug>/settings/billing/`
- `/w/<workspace_slug>/settings/modules/`
- `/w/<workspace_slug>/settings/numbering/`
- `/w/<workspace_slug>/settings/accounting/`
- `/w/<workspace_slug>/settings/security/`

Contact remains intentionally absent because Party is the canonical replacement.

## Compatibility Findings

- Slug aliases use current `Company.schema_name` as the compatibility slug.
- Existing `/orgs/...`, `/workspace/<id>/settings/...`, and tenant module
  routes remain available.
- Tenant app roots such as `/dea/`, `/party/`, `/girvi/`, and `/product/`
  remain active compatibility routes. Many `/w/<workspace_slug>/...` entry
  routes currently redirect into those roots.
- Sales and purchase route to DEA business events because the old runtime sales
  and purchase apps were removed.
- Workspace security is not an account-level allauth security page; it reads
  workspace `AuditLog` activity.
- Modules is read-only because no module registry or enable/disable lifecycle
  exists yet.

## Verification

- `python manage.py test django_project.test_workspace_slug_route_map_intent django_project.test_workspace_slug_deferred_targets_intent django_project.test_route_intent django_project.test_template_layout_intent django_project.test_shell_render_smoke --keepdb`
- `python manage.py check`
- `git diff --check`

## Deferred

- Customer/member portal IA and routes:
  - `/portal/`
  - `/portal/loans/`
  - `/portal/invoices/`
  - `/portal/payments/`
  - `/portal/documents/`
  - `/portal/statements/`
- A dedicated immutable branded `Company.slug`.
- A real module enable/disable registry and lifecycle.
- A dedicated roles/permissions editor beyond the current team-management
  interim redirect.
- A unified numbering-series manager beyond the current Girvi series interim
  redirect.
- Full tenant route canonicalization that keeps the browser on
  `/w/<workspace_slug>/...` instead of redirecting to `/dea/`, `/party/`,
  `/girvi/`, or other legacy tenant roots. See
  `docs/ui/tenant_route_canonicalization_phase13_plan.md`.

## Next Recommended Step

After the customer/member portal shell checkpoint, start Phase 13 tenant route
canonicalization. Begin by converting remaining visible sidebar/dashboard
top-level tenant links to slug aliases while keeping legacy roots active.
