---
status: active
owner: project
updated: 2026-06-30
tags: [ui, onboarding, saas, phase6, review]
related: [onboarding_phase6_plan.md, saas_information_architecture_audit.md, ../STATUS.md, ../AGENT_MEMORY.md]
---

# Phase 6 Onboarding Review

Phase 6 converts onboarding from a one-time user wizard into a workspace setup checklist while preserving existing onboarding URLs and keeping ERP access non-blocking.

## Completed Scope

- Phase 6.1 documented current onboarding routes, duplicate workspace creation paths, and safe implementation slices.
- Phase 6.2 added `apps.onboarding.services.setup_checklist` as a read-only workspace setup checklist service.
- Phase 6.3 surfaced the checklist on the workspace dashboard for owner/admin dashboard users.
- Phase 6.4 added the workspace settings setup page with canonical and compatibility routes.
- Phase 6.5 redirected completed onboarding flows to workspace setup when a selected workspace exists.
- Phase 6.6 moved onboarding workspace creation behind the orgs control-plane service.
- Phase 6.7 moved onboarding team invitations behind the orgs invitation control-plane service.
- Phase 6.8 added user-specific setup completion/dismiss state and dashboard hide/show behavior.

## Compatibility Findings

- Existing `/onboarding/start/`, `/onboarding/profile/`, `/onboarding/company/`, `/onboarding/team/`, `/onboarding/tour/`, `/onboarding/complete/`, and `/onboarding/skip/` routes remain available.
- Existing orgs workspace creation still uses `control_plane.create_workspace_from_form()`.
- Onboarding-created workspaces preserve existing provisioning behavior through `_provision_company_schema()` and `_seed_company_schema_defaults()` callbacks.
- Workspace setup remains advisory. Incomplete setup does not block tenant ERP access.
- Setup state is public/control-plane data and does not write tenant business data.
- The new `WorkspaceSetupState` migration is shared-app state. Rollout should use tenant-aware shared migration guidance, not plain tenant-only migration guidance.

## Guard Coverage

- Route guards cover canonical and compatibility setup/setup-state routes.
- Render smoke tests cover dashboard checklist card, setup page, and setup action forms.
- Service tests cover checklist status composition and setup state display/mutation behavior.
- View tests cover onboarding completion redirects, onboarding workspace creation delegation, onboarding team invitation delegation, and setup-state POST actions.
- Control-plane tests cover onboarding workspace creation callbacks and onboarding batch invitation behavior.

## Verification

Commands used for Phase 6.9 review:

- `.venv314\Scripts\python.exe manage.py test apps.onboarding.tests_setup_state apps.onboarding.tests_setup_checklist apps.onboarding.tests_company_creation apps.onboarding.tests_team_invites apps.onboarding.tests_completion_redirects django_project.test_onboarding_phase6_intent django_project.test_route_intent django_project.test_template_layout_intent django_project.test_shell_render_smoke apps.orgs.tests.OrgNavigationFlowTests apps.orgs.tests.WorkspaceSetupStateViewTests apps.orgs.tests.ControlPlaneIntegrityTests --keepdb`
- `.venv314\Scripts\python.exe manage.py makemigrations --check --dry-run`
- `.venv314\Scripts\python.exe manage.py check`
- `.venv314\Scripts\python.exe -m compileall apps\onboarding apps\orgs django_project`

## Remaining Risks

- The checklist uses best-effort counts from tenant app models. Unknown states are expected when model lookup or schema access is unavailable.
- Some checklist action URLs point into tenant ERP modules and assume the user is in a valid tenant context.
- The workspace setup checklist is functional, but visual polish is still basic and should be handled in Phase 7.
- A future onboarding/tour cleanup can decide whether the legacy feature tour should become a real setup preference screen or be retired.

## Next Recommendation

Commit Phase 6 as a single phase-level commit, then start Phase 7 modern fintech UI polish with the management/workspace setup surfaces as the first review targets.
