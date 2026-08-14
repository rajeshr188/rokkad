---
status: active
owner: project
updated: 2026-06-29
tags: [ui, routes, aliases, saas, review]
related: [canonical_route_aliases_plan.md, saas_information_architecture_audit.md, phase4_invitation_team_flow_review.md, ../STATUS.md, ../AGENT_MEMORY.md]
---

# Canonical Route Aliases Phase Review

## Scope Completed

This phase introduced additive SaaS control-plane route aliases while preserving existing compatibility routes.

Implemented alias groups:

- Global app aliases under `/app/...` for workspace dashboard/list, workspace creation, received invitations, and memberships.
- Workspace settings aliases under `/workspace/<workspace_id>/settings/...` for settings home, preferences, team, sent invitations, invite-member, and leave-workspace.
- Management navigation adoption for `app_workspaces`, `app_workspace_create`, and `app_invitations`.
- Workspace settings navigation adoption for `workspace_settings_home`, `workspace_settings_preferences`, `workspace_settings_team`, `workspace_settings_invite`, and `workspace_settings_invitations`.
- Sent-invitation return adoption for invite POST success, invite-success back links, and invitation revoke returns.

The phase deliberately did not remove or rename the existing `/orgs/...` route names or paths.

## Compatibility Findings

Legacy route compatibility is preserved:

- Existing `/orgs/...` route names still reverse and resolve.
- The legacy `team_invite_success` route and template remain available for old links.
- Active-state checks in navigation partials still recognize legacy route names where those names can render the same screen.
- Tenant ERP route groups were not changed in this phase.

Schema-boundary intent is clearer, but not fully solved:

- `/app/...` now represents authenticated global workspace-manager surfaces.
- `/workspace/<workspace_id>/settings/...` now represents workspace-admin/settings surfaces.
- Existing selected-workspace fallback behavior remains in place for legacy routes and should be handled in a later authorization/settings cleanup slice.

## Verification

Focused regression coverage passed with:

```powershell
.venv314\Scripts\python.exe manage.py test apps.orgs.tests django_project.test_route_intent django_project.test_invitation_team_flow_intent django_project.test_template_layout_intent django_project.test_shell_render_smoke django_project.test_navigation_intent django_project.test_management_shell_visual_smoke --keepdb
```

Result: 140 tests passed.

Project checks passed with:

```powershell
.venv314\Scripts\python.exe manage.py check
```

Result: no system check issues.

Diff hygiene passed with:

```powershell
git diff --check
```

Result: no whitespace errors. PowerShell reported line-ending warnings for existing CRLF/LF conversions only.

## Residual Risks

- Account settings, profile, and billing surfaces still use legacy route names. Those should receive aliases only after deciding whether they belong under `/app/account/...`, `/app/billing/...`, or workspace settings.
- `workspace_settings_leave` exists as an alias, but leave-workspace navigation and redirects have not yet been adopted.
- The legacy `team_invite_success` screen is still reachable. Keep it until bookmarks and email links are known safe or a compatibility redirect plan exists.
- Public/global/tenant boundary risks remain broader than this route-alias phase, especially where global routes infer workspace context from profiles or query strings.
- Authorization cleanup remains separate: route aliases clarify intent, but they are not a substitute for permission checks.

## Commit Recommendation

Commit this canonical route alias phase as one phase-level change set.

Suggested commit message:

```text
Standardize canonical control-plane route aliases
```

Expected commit contents:

- `django_project/shared_urlpatterns.py`
- `apps/orgs/views.py`
- `apps/orgs/tests.py`
- Route/template/shell intent tests under `django_project/`
- Management navigation partials under `templates/components/navigation/`
- SaaS IA documentation updates under `docs/`

## Next Recommended Step

First commit this phase-level route-alias set so the worktree is clean.

After that, start Phase 5 authorization cleanup with route boundaries now clearer. The first safe Phase 5 slice should be an authorization inventory and guard-test pass for public/global/workspace-settings/tenant surfaces before changing permission behavior.
