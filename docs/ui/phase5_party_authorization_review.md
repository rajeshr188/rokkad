---
status: active
owner: project
updated: 2026-06-29
tags: [ui, authorization, party, saas, review]
related: [authorization_cleanup_inventory.md, saas_information_architecture_audit.md, ../STATUS.md, ../AGENT_MEMORY.md]
---

# Phase 5 Party Authorization Review

## Scope

This review closes the Party authorization slice of SaaS IA Phase 5.

Implemented changes:

- Added `apps.tenant_apps.party.access` as the shared Party authorization boundary.
- Added middleware tenant-prefix coverage for all current tenant ERP prefixes.
- Added canonical `/workspace/<id>/settings/...` path extraction in workspace middleware.
- Converted Party list/detail/export/create/update/customer-convert/profile/KYC/relationship/role/merge surfaces from login-only protection to Party action permissions.
- Added focused authorization tests for Party access helpers and denied no-access Party UI paths.
- Added static authorization surface tests for route-plane separation, middleware contracts, tenant ERP prefix coverage, and remaining non-Party login-only app gaps.

## Compatibility Findings

- No Party URL names or paths were removed.
- No Party form actions were changed.
- Owners and platform admins retain bypass behavior through the shared Party access helper.
- Workspace members retain allowed read/create/edit behavior based on the existing `RolePermissions` effective permission map.
- Party export remains separately gated by the export action permission.
- Product catalog, stock, pricing, image, and attribute authorization were completed in follow-on slices. Rates and Notify route groups also received shared action guards after this Party review.
- Contact is intentionally skipped for broad authorization cleanup because Party is replacing it; treat Contact as a legacy compatibility surface unless a specific unsafe route must be patched before cutover.

## Verification

Commands run:

- `.venv314\Scripts\python.exe manage.py test apps.tenant_apps.party.tests.test_party_access apps.tenant_apps.party.tests.test_party_ui --keepdb`
- `.venv314\Scripts\python.exe manage.py test apps.tenant_apps.party.tests.test_party_access apps.tenant_apps.party.tests.test_party_ui django_project.test_authorization_surface_intent django_project.test_route_intent django_project.test_invitation_team_flow_intent apps.orgs.tests --keepdb`
- `.venv314\Scripts\python.exe manage.py check`
- `git diff --check`

Latest results:

- Party test slice: 50 tests passed.
- Focused Phase 5 regression slice: 168 tests passed.
- Django system check passed.
- Whitespace diff check passed with only Git LF/CRLF warnings on Windows.

## Decision

Party authorization is complete for the current tenant Party UI surface.

Next recommended SaaS IA work:

1. Prepare the overall Phase 5 authorization closeout review.
2. Commit the Phase 5 set before starting Phase 6 onboarding.
