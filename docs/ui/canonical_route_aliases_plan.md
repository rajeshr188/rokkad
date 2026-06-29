---
status: active
owner: project
updated: 2026-06-29
tags: [ui, routes, aliases, saas, control-plane]
related: [saas_information_architecture_audit.md, canonical_route_aliases_phase_review.md, phase4_invitation_team_flow_review.md, invitation_team_flow_cleanup_plan.md, ../AGENT_MEMORY.md, ../STATUS.md]
---

# Canonical Route Aliases Plan

## Purpose

This phase introduces clearer SaaS control-plane aliases while preserving existing `/orgs/...` compatibility URLs.

The goal is additive route clarity, not a route rewrite.

## Current Slice

Canonical aliases added through `django_project.shared_urlpatterns.CANONICAL_CONTROL_PLANE_URLPATTERNS`:

| Alias route name | Path | Existing view |
| --- | --- | --- |
| `app_dashboard` | `/app/` | `workspace_selector` |
| `app_workspaces` | `/app/workspaces/` | `workspace_selector` |
| `app_workspace_create` | `/app/workspaces/new/` | `workspace_create` |
| `app_invitations` | `/app/invitations/` | `team_invitations` |
| `app_memberships` | `/app/memberships/` | `my_memberships` |
| `workspace_settings_home` | `/workspace/<workspace_id>/settings/` | `workspace_detail` |
| `workspace_settings_preferences` | `/workspace/<workspace_id>/settings/preferences/` | `CompanyPreferenceBuilder` |
| `workspace_settings_team` | `/workspace/<workspace_id>/settings/team/` | `membership_list` |
| `workspace_settings_invitations` | `/workspace/<workspace_id>/settings/invitations/` | `companyinvitations_list` |
| `workspace_settings_invite` | `/workspace/<workspace_id>/settings/invitations/new/` | `team_invite` |
| `workspace_settings_leave` | `/workspace/<workspace_id>/settings/leave/` | `workspace_leave` |

Compatibility URLs under `/orgs/...` remain unchanged.

## Navigation Adoption Slice

Low-risk management navigation now uses canonical aliases for global control-plane links:

| Template | Link | Canonical route used | Legacy route still active-compatible |
| --- | --- | --- | --- |
| `components/navigation/workspace_manager_sidebar.html` | My Workspaces | `app_workspaces` | `workspace_selector` |
| `components/navigation/workspace_manager_sidebar.html` | New Workspace | `app_workspace_create` | `workspace_create` |
| `components/navigation/account_sidebar.html` | My Invitations | `app_invitations` | `team_invitations` |

The account settings, profile, billing, and leave-workspace links remain on legacy route names for now.

Workspace settings navigation has started moving to canonical aliases:

| Template | Link | Canonical route used | Legacy route still active-compatible |
| --- | --- | --- | --- |
| `components/navigation/workspace_settings_sidebar.html` | Settings | `workspace_settings_home` | `workspace_detail` |
| `components/navigation/workspace_settings_sidebar.html` | Preferences | `workspace_settings_preferences` | `workspace_preferences` |
| `components/navigation/workspace_settings_sidebar.html` | Team Members | `workspace_settings_team` | `team_members_list` |
| `components/navigation/workspace_settings_sidebar.html` | Invite Member | `workspace_settings_invite` | `team_invite` |
| `components/navigation/workspace_settings_sidebar.html` | Sent Invitations | `workspace_settings_invitations` | `team_invitations_list` |

Leave-workspace, account settings, profile, and billing links remain on legacy route names for now.

## Workspace Settings Redirect Characterization

`apps/orgs/tests.py` now characterizes the behavior that must stay stable before moving team and invitation settings links:

- `membership_list` accepts explicit `workspace_id` context and avoids selected-workspace fallback when the alias passes an id.
- `companyinvitations_list` accepts explicit `workspace_id` context and avoids query/profile fallback when the alias passes an id.
- `team_invite` success redirects to `team_invite_success` with `?workspace_id=<id>`.
- `invite_success` links back to the same workspace's sent-invitations list.
- `invitation_delete` returns to the same workspace's sent-invitations list after revoke.

## Redirect Adoption Slice

Sent-invitations return targets now use canonical workspace settings URLs:

| Flow | Previous target | Canonical target |
| --- | --- | --- |
| Invite success page back-link | `team_invitations_list?workspace_id=<id>` | `workspace_settings_invitations` |
| Invitation revoke return | `team_invitations_list?workspace_id=<id>` | `workspace_settings_invitations` |
| Invite POST success | `team_invite_success?workspace_id=<id>` | `workspace_settings_invitations` |

The legacy `team_invite_success` route/template remains available for old links, but new successful invite submissions now return directly to the canonical sent-invitations settings page.

## Guardrails

- Do not remove legacy `/orgs/...` paths in this phase.
- Do not change existing route names used by templates and redirects.
- Add new canonical route names for new links.
- Keep tenant ERP routes separate from global `/app/...` aliases.
- Move templates to canonical aliases only after alias route resolution is covered.

## Verification

`django_project/test_route_intent.py` guards:

- Canonical aliases are included before legacy org route bundle.
- New `/app/...` and `/workspace/<id>/settings/...` aliases resolve.
- Existing `/orgs/...` route reverses remain unchanged.

`django_project/test_template_layout_intent.py`, `django_project/test_shell_render_smoke.py`, and `django_project/test_management_shell_visual_smoke.py` now guard that adopted management links render through canonical route names while legacy route names remain active-compatible.

## Phase Review

The phase review is documented in `docs/ui/canonical_route_aliases_phase_review.md`.

It confirms:

- Legacy `/orgs/...` route names and paths still reverse.
- Adopted management/settings links render through canonical aliases.
- Invite POST success, invite-success back links, and revoke returns use `workspace_settings_invitations`.
- `workspace_settings_leave`, account settings/profile, and billing adoption should stay deferred to later, narrower slices.

## Next Recommended Slice

Commit this canonical route alias phase as one phase-level change set. After the worktree is clean, start Phase 5 authorization cleanup with an authorization inventory and guard-test pass for public/global/workspace-settings/tenant surfaces.
