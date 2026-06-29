---
status: active
owner: project
updated: 2026-06-28
tags: [ui, invitations, team, workspace-settings, saas, phase-4]
related: [saas_information_architecture_audit.md, navigation_workspace_switcher_plan.md, phase3_navigation_management_shell_review.md, ../AGENT_MEMORY.md, ../STATUS.md]
---

# Invitation and Team Flow Cleanup Plan

## Purpose

Phase 4 standardizes invitation and team-management intent without breaking current URLs. The current implementation already separates incoming invitations from workspace team administration at the template-shell level, but route names and route paths still make the flows easy to confuse.

## Current Route Map

### Incoming Invitations

These are global account/workspace-manager concerns because they belong to the authenticated user, not to the currently selected workspace.

| Route name | Current path | View/template | Current intent |
| --- | --- | --- | --- |
| `team_invitations` | `/orgs/team/invitations/` | `team_invitations` -> `company/workspace_invitations.html` | User reviews invitations received at their email and accepts or declines them. |
| `team_accept_invitation` | `/orgs/team/invitations/accept/<key>/` | `AcceptInvite.as_view()` | Compatibility entrypoint for django-invitations accept links. |

Current shell: `company/workspace_invitations.html` extends `base_global.html`.

### Workspace Invitations

These are workspace settings concerns because they manage invitations sent for a workspace.

| Route name | Current path | View/template | Current intent |
| --- | --- | --- | --- |
| `team_invite` | `/orgs/workspace/<workspace_id>/team/invite/` | `team_invite` -> `company/invitation_form.html` | Owner/Admin sends a workspace invitation with a grantable role. |
| `team_invitations_list` | `/orgs/team/invitations/list/` | `companyinvitations_list` -> `company/company_invitations_list.html` | Owner/Admin reviews sent invitations for the selected workspace, or inviter-scoped invitations when no workspace is selected. |
| `team_delete_invitation` | `/orgs/team/invitations/<invitation_id>/delete/` | `invitation_delete` | Inviter or authorized workspace admin revokes an invitation. |
| `team_invite_success` | `/orgs/team/invite/success/` | `invite_success` -> `company/invite_success.html` | Compatibility success page after sending an invitation. |

Current shells: invite form, sent-invitation list, and invite success extend `base_workspace_settings.html`.

### Team Members

These are workspace settings concerns because they mutate or inspect workspace membership.

| Route name | Current path | View/template | Current intent |
| --- | --- | --- | --- |
| `team_members_list` | `/orgs/team/members/` | `membership_list` -> `company/membership_list.html` | Lists members for the selected workspace. |
| `team_change_role` | `/orgs/workspace/<workspace_id>/team/member/<membership_id>/role/` | `team_change_role` -> `company/partials/role_form.html` | Changes a member role after role-policy validation. |
| `team_remove_member` | `/orgs/workspace/<workspace_id>/team/member/<membership_id>/remove/` | `team_remove_member` | Removes a member after role-policy validation. |
| `workspace_leave` | `/orgs/workspace/<workspace_id>/leave/` | `workspace_leave` -> `company/workspace_leave_confirm.html` | Current user leaves a workspace, except sole owners must transfer ownership first. |
| `my_memberships` | `/orgs/memberships/` | `my_memberships` -> `company/my_memberships.html` | User-level membership list. |

Current shell: `company/membership_list.html` extends `base_workspace_settings.html`.

## Current Risks

- The names `team_invitations` and `team_invitations_list` are too similar while representing different product areas: incoming user invitations versus sent workspace invitations.
- Sent invitations and team-member list screens still support selected workspace profile fallback; sent invitations also accept `workspace_id` query context until canonical workspace-scoped aliases are introduced.
- Incoming invitation accept links have two entrypoints: project-level django-invitations URLs and the orgs `team_accept_invitation` route. The direct `AcceptInvite` usage needs characterization before replacement because it may bypass the custom active-workspace handling in `team_invitations`.
- Global workspace manager pages expose invitation summaries, while workspace settings pages expose sent invitations. The labels must stay explicit so users know whether they are accepting an invite or managing invites they sent.
- Route paths under `/orgs/team/*` mix account-level and workspace-settings concerns.

## Target Intent

Phase 4 should preserve existing URLs first, then add aliases only after tests prove current behavior.

Future canonical intent:

```text
/app/invitations/                         incoming invitations for the user
/app/memberships/                         workspaces the user belongs to
/workspace/<id>/settings/team/            workspace members
/workspace/<id>/settings/invitations/     sent invitations for the workspace
/workspace/<id>/settings/invitations/new/ invite member
```

Compatibility routes under `/orgs/` should remain until redirects and bookmarked links are covered.

## Phase 4 Slices

### Phase 4.1: Intent Audit and Guard Tests

- Document current incoming, sent, and team-member route ownership.
- Add guard tests for route names, route targets, template shell intent, and no URL breakage.
- Record the success-page shell gap for a later behavior-preserving cleanup.

### Phase 4.2: Route Intent Cleanup Without URL Breakage

- Add comments/constants or tests that classify account-level invitation routes separately from workspace-settings routes.
- Keep route names and paths stable.
- Make future canonical paths explicit in documentation only.

Status: complete. `apps.orgs.urls` now exposes intent-grouped route lists for workspace manager, account invitations, workspace invitations, team members, and account profile routes. `urlpatterns` remains an aggregate in the same compatibility order, and `django_project/test_invitation_team_flow_intent.py` guards both the grouping and current paths.

### Phase 4.3: Copy and Heading Clarification

- Rename visible headings to distinguish "Invitations for You" from "Sent Workspace Invitations".
- Keep route names and form actions unchanged.
- Fix mojibake in existing invitation/member templates as part of copy cleanup.

Status: complete. `company/workspace_invitations.html` now clearly labels received invitations as "Invitations for You"; `company/company_invitations_list.html` labels sent workspace invitations explicitly; `company/invitation_form.html` and `company/invite_success.html` use team-member/workspace-invitation wording; and `company/membership_list.html` uses an ASCII-safe HTML entity for the workspace/member separator. Tests guard the wording split and known mojibake cleanup.

### Phase 4.4: Workspace-Scoped Redirect Cleanup

- Return sent-invitation actions to the relevant workspace context.
- Replace the unbased invite success fragment with a workspace-settings shell page or redirect back to sent invitations.
- Keep old success URL working.

Status: complete. `team_invite` now redirects to the existing success URL with `?workspace_id=<id>`, `invite_success` renders through `base_workspace_settings.html` and links back to sent invitations in the same workspace context, and `invitation_delete` redirects to the sent-invitation list with the revoked invitation's workspace id. The old success and sent-list URLs still work without query context.

### Phase 4.5: Accept/Decline Characterization

- Characterize django-invitations direct accept behavior.
- Decide whether `team_accept_invitation` should delegate to the orgs control-plane service so membership creation, active workspace selection, audit, and messages are consistent.

Status: complete. The direct `team_accept_invitation` route still uses `invitations.views.AcceptInvite`. With current settings, GET confirms the invite, acceptance happens before signup, and the redirect target is `account_signup`. The `invite_accepted` signal bridges membership creation for existing users and stages `PendingInvitation` for unknown users, but it does not select the active workspace, emit orgs audit logs, or redirect to the workspace dashboard. The custom `team_invitations` POST flow uses `control_plane.accept_invitation`, emits audit, sets `user.profile.workspace`, and redirects to `workspace_dashboard`.

Recommended direction for a later implementation slice: keep the old accept URL, but replace or wrap `views.AcceptInvite.as_view()` with an orgs-owned adapter that delegates to the same service path as `team_invitations` when the accepting user is authenticated and matches the invited email. For unauthenticated or unknown users, preserve the django-invitations signup/login behavior while retaining enough invitation context to select the workspace after signup.

### Phase 4.6: Authorization Coverage

- Cover invite, revoke, role change, remove member, self-leave, and selected-workspace fallback.
- Prove members cannot grant roles or revoke invitations outside policy.

Status: complete. `apps.orgs.tests.InvitationTeamAuthorizationTests` now covers workspace `team_invite` gating, role-grant policy enforcement before invitation persistence, revoke denial for non-inviter/non-authorized users, `team_remove` and `team_change_role` workspace gates, sole-owner self-leave blocking through `workspace_leave`, and selected-workspace sent-invitation fallback requiring `team_invite`.

### Phase 4.7: Compatibility Aliases

- Add future canonical aliases only after the old routes are tested.
- Keep redirects explicit and reversible.

Status: complete for the direct invitation accept adapter scope. The existing `team_accept_invitation` path and route name are preserved, but the route now points to `apps.orgs.views.team_accept_invitation`. Authenticated users whose email matches the invitation now accept through the orgs control-plane flow, which creates/ensures membership, emits orgs audit through the service, selects the active workspace, and redirects to the workspace dashboard. Unauthenticated users still fall through to `invitations.views.AcceptInvite` so existing signup/login behavior remains compatible. Authenticated email mismatches fail closed and redirect to received invitations.

Canonical route aliases remain intentionally deferred until this adapter behavior is reviewed and committed.

## Acceptance Criteria

- No current URL or route name breaks during Phase 4.
- Incoming invitations remain a global account/workspace-manager surface.
- Sent invitations, invite member, team members, role changes, removals, and workspace leave remain workspace settings surfaces.
- Role-grant and membership mutation policy stays in `apps.orgs.services`.
- Users can distinguish received invitations from invitations they sent.
- Tenant ERP navigation and data do not leak into account-level invitation screens.
