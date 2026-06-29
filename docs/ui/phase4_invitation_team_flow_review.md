---
status: complete
owner: project
updated: 2026-06-29
tags: [ui, invitations, team, workspace-settings, saas, phase-4, review]
related: [invitation_team_flow_cleanup_plan.md, saas_information_architecture_audit.md, phase3_navigation_management_shell_review.md, ../AGENT_MEMORY.md, ../STATUS.md]
---

# Phase 4 Invitation and Team Flow Review

## Scope

Phase 4 cleaned up invitation and team-management flow intent without removing existing URLs.

Completed slices:

- Phase 4.1: current-state plan and guard tests.
- Phase 4.2: route-intent grouping in `apps.orgs.urls`.
- Phase 4.3: copy and mojibake cleanup for received invitations, sent invitations, and team-member invite screens.
- Phase 4.4: workspace-scoped return context for invite success, sent invitations, and revoke flows.
- Phase 4.5: characterization of direct django-invitations accept behavior.
- Phase 4.6: focused authorization coverage for invite/team mutation paths.
- Phase 4.7: orgs-owned direct invitation accept adapter.

## Compatibility Review

Preserved:

- Existing route names remain in place.
- Existing `/orgs/` URL paths remain in place.
- Unauthenticated direct invitation accept still falls back to `invitations.views.AcceptInvite`.
- Received invitations remain a global/account surface.
- Sent invitations, invite member, team member list, role change, member removal, and workspace leave remain workspace settings surfaces.

Improved:

- `apps.orgs.urls` now exposes explicit route-intent groups.
- `team_accept_invitation` now routes authenticated matching users through the orgs control-plane accept flow.
- Invite success now renders in the workspace settings shell and links back to sent invitations in the same workspace context.
- Sent invitation revoke returns to the revoked invitation's workspace context.
- Visible copy distinguishes "Invitations for You" from "Sent Workspace Invitations".
- Known invitation/team mojibake has guard coverage.

## Authorization Review

New focused coverage protects:

- Workspace `team_invite` gate for invite form.
- Role-grant policy before invitation persistence.
- Revoke denial for non-inviter users without workspace invite permission.
- Workspace `team_remove` and `team_change_role` gates.
- Sole-owner self-leave blocking.
- Sent-invitation selected-workspace fallback requiring `team_invite`.
- Direct accept email mismatch fail-closed behavior.

## Verification Commands

Passed:

```powershell
.venv314\Scripts\python.exe manage.py test apps.orgs.tests.DirectInvitationAcceptAdapterTests apps.orgs.tests.InvitationTeamAuthorizationTests django_project.test_invitation_team_flow_intent apps.orgs.tests.InvitationSignalHandlerTests apps.orgs.tests.InvitationLifecycleStateTests --keepdb
.venv314\Scripts\python.exe manage.py test django_project.test_invitation_team_flow_intent django_project.test_route_intent django_project.test_template_layout_intent django_project.test_shell_render_smoke django_project.test_navigation_intent django_project.test_management_shell_visual_smoke --keepdb
.venv314\Scripts\python.exe manage.py check
git diff --check
```

`git diff --check` reported only line-ending normalization warnings.

## Deferred Follow-Ups

- Canonical `/app/...` and `/workspace/<id>/settings/...` route aliases remain deferred.
- A future signup completion flow should use pending invitation context to select the joined workspace after account creation.
- Phase 5 should continue with broader authorization cleanup outside orgs invitation/team screens.

## Recommendation

Commit the Phase 4 set as one phase-level commit, then start canonical route aliases or Phase 5 authorization cleanup as a separate phase.
