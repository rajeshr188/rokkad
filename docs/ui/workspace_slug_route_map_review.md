---
status: active
owner: ui
updated: 2026-06-30
tags: [ui, saas-ia, routes, workspace, tenant, review]
related:
  - docs/ui/workspace_slug_route_map_plan.md
  - docs/ui/saas_information_architecture_audit.md
  - docs/ui/public_auth_alias_template_rollout_review.md
  - docs/ui/route_template_inventory.md
---

# Workspace Slug Route Map Review

Phase 10 introduced the first live `/w/<workspace_slug>/...` route-map layer
without removing existing id-based, orgs, tenant-prefix, or auth compatibility
routes.

## Completed Scope

- Added `docs/ui/workspace_slug_route_map_plan.md`.
- Chose `Company.schema_name` as the initial compatibility slug.
- Added middleware slug extraction in `SecureWorkspaceMiddleware`.
- Added minimal slug aliases:
  - `/w/<workspace_slug>/`
  - `/w/<workspace_slug>/settings/`
  - `/w/<workspace_slug>/settings/preferences/`
  - `/w/<workspace_slug>/settings/team/`
  - `/w/<workspace_slug>/settings/invitations/`
- Added tenant ERP section aliases:
  - `/w/<workspace_slug>/parties/`
  - `/w/<workspace_slug>/loans/`
  - `/w/<workspace_slug>/inventory/`
  - `/w/<workspace_slug>/accounting/`
- Moved selected tenant/sidebar settings navigation to slug aliases where
  workspace schema context is reliable.
- Kept current compatibility routes live:
  - `/app/...`
  - `/workspace/<id>/settings/...`
  - `/orgs/...`
  - tenant prefixes such as `/party/`, `/girvi/`, `/product/`, and `/dea/`

## Compatibility Findings

- Slug aliases are redirect aliases, not duplicated business views.
- Middleware still validates workspace membership before setting tenant context.
- Domain mapping remains authoritative over path workspace hints.
- `Company.schema_name` is a compatibility slug, not an editable branded URL.
- Contact is intentionally not exposed as `/w/<workspace_slug>/contact/` because
  Party is replacing Contact.
- Operations, sales, purchase, commodity, reports, setup, invite, billing,
  notifications, rates, data tools, and deeper accounting/report links still use
  current routes until dedicated product targets are selected.

## Verification

Focused verification used:

```text
.venv314\Scripts\python.exe manage.py test django_project.test_workspace_slug_route_map_intent django_project.test_route_intent django_project.test_template_layout_intent django_project.test_shell_render_smoke django_project.test_navigation_intent django_project.test_management_shell_visual_smoke --keepdb
```

Result: 65 tests passed.

Additional regression verification should include the route, auth, public,
authorization, and shell test groups before committing.

## Deferred Scope

- Dedicated immutable `Company.slug`.
- Workspace slug rename and redirect policy.
- `/w/<workspace_slug>/operations/`.
- `/w/<workspace_slug>/sales/`.
- `/w/<workspace_slug>/purchase/`.
- `/w/<workspace_slug>/commodity/`.
- `/w/<workspace_slug>/reports/`.
- `/w/<workspace_slug>/settings/profile/`.
- `/w/<workspace_slug>/settings/roles/`.
- `/w/<workspace_slug>/settings/billing/`.
- `/w/<workspace_slug>/settings/modules/`.
- `/w/<workspace_slug>/settings/numbering/`.
- `/w/<workspace_slug>/settings/accounting/`.
- `/w/<workspace_slug>/settings/security/`.
- Customer portal route-map rollout.

## Commit Boundary

This phase is ready to commit after the broader focused regression set passes.
The next SaaS IA step should be either:

- choose targets for the remaining `/w/<workspace_slug>/...` deferred routes; or
- start a customer/member portal IA phase if portal work is now higher priority.

## Follow-Up Decision

Phase 11.1 target selection is documented in
`docs/ui/workspace_slug_deferred_targets_plan.md`. It chooses existing redirect
targets for operations, sales, purchase, commodity, reports, profile, billing,
and accounting; records interim targets for roles and numbering; and keeps
modules plus security absent until real workspace-owned screens exist.

The next safe implementation slice is Phase 11.2: add only the safe redirect
aliases.

## Phase 11.2 Follow-Up

Phase 11.2 is implemented. The safe redirect aliases are now live for:

- `/w/<workspace_slug>/operations/`
- `/w/<workspace_slug>/sales/`
- `/w/<workspace_slug>/purchase/`
- `/w/<workspace_slug>/commodity/`
- `/w/<workspace_slug>/reports/`
- `/w/<workspace_slug>/settings/profile/`
- `/w/<workspace_slug>/settings/billing/`
- `/w/<workspace_slug>/settings/accounting/`

Contact remains intentionally absent. Settings roles, modules, numbering, and
security also remain absent until the interim redirect or real-screen decisions
are made.

## Phase 11.3 Follow-Up

Phase 11.3 is implemented. The interim redirect aliases are now live for:

- `/w/<workspace_slug>/settings/roles/`
- `/w/<workspace_slug>/settings/numbering/`

Roles currently redirects to workspace team management because there is no
dedicated roles/permissions editor yet. Numbering currently redirects to Girvi
series because it is the only live numbering-series surface. Settings modules
and security remain absent until real workspace-owned screens exist.

## Phase 11.4 Follow-Up

Phase 11.4 is implemented. Workspace-owned settings screens are now live for:

- `/workspace/<workspace_id>/settings/modules/`
- `/workspace/<workspace_id>/settings/security/`
- `/w/<workspace_slug>/settings/modules/`
- `/w/<workspace_slug>/settings/security/`

Modules is a read-only installed-module map with links to current operational
entrypoints. Security is a workspace audit/security surface backed by
`AuditLog`, not an account-level security redirect.
