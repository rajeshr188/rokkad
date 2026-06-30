---
status: active
owner: project
updated: 2026-06-29
tags: [ui, onboarding, saas, phase6]
related: [saas_information_architecture_audit.md, phase5_authorization_closeout_review.md, ../STATUS.md, ../AGENT_MEMORY.md]
---

# Phase 6 Onboarding Plan

Phase 6 converts the current one-time onboarding wizard into a workspace setup checklist that is visible from the global workspace manager, workspace dashboard, and workspace settings.

The first slice was documentation and guard tests only. Phase 6.2 added a read-only checklist service. Phase 6.3 surfaces that checklist on the workspace dashboard. Phase 6.4 adds a workspace settings setup page using the same checklist service. Phase 6.5 routes completed onboarding users toward that setup page without removing onboarding entrypoints or blocking ERP access. Phase 6.6 moves onboarding workspace creation behind the orgs control-plane service while preserving existing onboarding form behavior. Phase 6.7 moves onboarding team invitations behind the orgs invitation control-plane service while preserving the optional team step. Phase 6.8 adds user-specific completion/dismiss state for the workspace setup checklist while keeping the checklist advisory.

## Current State

Current onboarding app:

- `apps.onboarding.urls` exposes `/onboarding/start/`, `/profile/`, `/company/`, `/team/`, `/tour/`, `/complete/`, and `/skip/`.
- `apps.onboarding.models.OnboardingProgress` tracks user-level progress: profile, company, team, tour, complete.
- `apps.onboarding.views.onboarding_company` delegates workspace/domain/Owner membership creation to `control_plane.create_onboarding_workspace_from_form()`, then selects the workspace, saves onboarding choices, logs completion, and marks onboarding step 2 complete.
- `apps.orgs.views.workspace_create` also creates a workspace through `control_plane.create_workspace_from_form()`, selects it, and redirects to the workspace manager.
- `apps.onboarding.views.onboarding_team` delegates team invitation creation/sending to `control_plane.send_onboarding_team_invitations()`, then keeps progress, messages, and onboarding audit summary in the onboarding view.
- `pages.views.Dashboard` and `workspace_selector` redirect users toward selected workspaces, workspace selector, or workspace creation.

## Problems

- Workspace creation previously existed in two places: onboarding and orgs. Phase 6.6 centralizes the onboarding creation path in the orgs control-plane service, but the normal workspace-create form still uses its existing canonical helper.
- Onboarding is user-level, but the target SaaS setup state is workspace-level.
- The current tour step stores preferences but does not drive a concrete workspace readiness checklist.
- Team invite behavior previously was split from the cleaned-up Phase 4 invitation/team control-plane flow. Phase 6.7 now delegates the onboarding team step to an orgs control-plane helper.
- Completion redirects previously pointed to legacy workspace list behavior. Phase 6.5 now sends completed onboarding users to the workspace setup page when a selected workspace exists.
- Setup state previously was not visible from tenant dashboard or workspace settings. Phase 6.3, Phase 6.4, and Phase 6.8 now expose checklist progress plus user-specific display state.

## Target Direction

Keep the old onboarding URLs as compatibility entrypoints, but move meaningful setup state toward a workspace checklist.

Target checklist:

- Business profile
- Accounting setup
- Opening balances
- Add customers/suppliers or Parties
- Add products
- Add opening stock
- Invite team
- Configure rates
- Create first transaction

Checklist ownership:

- Workspace-level checklist state belongs to workspace settings/admin or a dedicated setup service, not a user-only progress row.
- User-level `OnboardingProgress` can remain as a compatibility record for first-run UX.
- Workspace creation should use the orgs control-plane workspace service as the canonical path.
- Team invitations should use the orgs invitation control-plane service.

## Safe Phase 6 Slices

1. Phase 6.1: Inventory and guard tests only. Complete.
2. Phase 6.2: Extract a read-only workspace setup checklist service. Complete.
3. Phase 6.3: Surface the checklist on workspace dashboard without blocking workflows. Complete.
4. Phase 6.4: Add workspace settings setup page using the existing settings shell. Complete.
5. Phase 6.5: Route onboarding completion to the workspace setup checklist. Complete.
6. Phase 6.6: Move onboarding company creation to the orgs control-plane service. Complete.
7. Phase 6.7: Move onboarding team invites to the orgs invitation service. Complete.
8. Phase 6.8: Add completion/dismiss state and tests. Complete.
9. Phase 6.9: Review and commit Phase 6. Complete.

## Compatibility Constraints

- Do not remove existing `/onboarding/...` URLs in Phase 6.
- Do not break users with existing `OnboardingProgress` rows.
- Do not block tenant ERP access solely because checklist items are incomplete.
- Do not duplicate tenant schema provisioning logic further.
- Do not mix tenant business data into global onboarding screens.

## Phase 6.2 Service

`apps.onboarding.services.setup_checklist` now provides a read-only workspace setup checklist:

- `WorkspaceSetupMetrics` carries count inputs for setup decisions.
- `collect_workspace_setup_metrics(workspace=...)` collects best-effort counts for memberships, pending invitations, DEA setup, Party, Product, Stock, Rates, and first-transaction signals.
- `build_workspace_setup_checklist(workspace=..., metrics=...)` builds checklist items without mutating state.
- Tenant-app count collection fails closed to `unknown` when model lookup, schema, or database availability is unclear.
- Business profile is derived from workspace identity only; all business-data items remain incomplete or unknown unless tenant metrics are available.

Current checklist keys:

- `business_profile`
- `accounting_setup`
- `opening_balances`
- `parties`
- `products`
- `opening_stock`
- `invite_team`
- `rates`
- `first_transaction`

## Phase 6.3 Dashboard Surface

The workspace dashboard now includes the read-only setup checklist for users who can view owner/admin dashboard controls:

- `apps.orgs.services.dashboard_selectors.get_workspace_dashboard_context()` adds `setup_checklist`.
- `templates/company/workspace_dashboard.html` renders an advisory "Workspace setup" card with progress, item states, and action links.
- Checklist state does not redirect, block, or mutate onboarding progress.
- Existing `/onboarding/...` URLs and redirects remain unchanged.

## Phase 6.4 Workspace Settings Setup Page

Workspace settings now has a dedicated read-only setup page:

- Canonical route: `/workspace/<workspace_id>/settings/setup/` as `workspace_settings_setup`.
- Compatibility route: `/orgs/workspace/<workspace_id>/setup/` as `workspace_setup`.
- View: `apps.orgs.views.workspace_setup`.
- Template: `templates/company/workspace_setup.html`.
- Navigation: `templates/components/navigation/workspace_settings_sidebar.html` includes a Setup link for desktop and mobile variants.
- The workspace dashboard setup card links to the canonical settings setup page.
- The page uses the same `apps.onboarding.services.setup_checklist` read model and does not mutate setup state.

## Phase 6.5 Completion Routing

Completed onboarding now routes users toward the workspace setup checklist when a selected non-public workspace is available:

- `apps.onboarding.views._redirect_to_workspace_setup_or_list()` resolves the active workspace with profile fallback.
- `onboarding_start` redirects already-complete users to `workspace_settings_setup` when possible.
- `onboarding_complete` still logs completion, then redirects to `workspace_settings_setup` when possible.
- `onboarding_skip` completes progress and redirects to `workspace_settings_setup` when possible.
- If no usable workspace exists, the fallback remains `workspace_list`.
- Existing `/onboarding/start/`, `/onboarding/complete/`, and `/onboarding/skip/` route names remain available.

## Phase 6.6 Control-plane Workspace Creation

Onboarding workspace creation now runs through an orgs control-plane service:

- `apps.orgs.services.control_plane.create_onboarding_workspace_from_form()` owns onboarding company row setup, domain creation, and Owner membership creation.
- `apps.onboarding.views.onboarding_company` passes the existing `_provision_company_schema()` and `_seed_company_schema_defaults()` callbacks into the service so current fresh/template-clone provisioning behavior is preserved.
- The onboarding view still owns user-level progress, active workspace selection, onboarding choices, success messaging, and the `ONBOARDING_COMPANY_COMPLETE` audit event.
- Direct `Domain.objects.create()` and `Membership.objects.create()` calls were removed from `apps.onboarding.views`.
- Existing `/onboarding/company/` behavior and redirect flow remain compatible.

## Phase 6.7 Control-plane Team Invitations

Onboarding team invitations now run through an orgs control-plane service:

- `apps.orgs.services.control_plane.send_onboarding_team_invitations()` owns Member role resolution, role-policy validation, invitation row creation, and email send calls.
- `apps.onboarding.views.onboarding_team` passes the parsed email list to the service and keeps optional skip behavior, user-level progress, success messaging, and `ONBOARDING_TEAM_INVITE` audit summary.
- Direct `CompanyInvitation.objects.create()` and `Role.objects.get()` calls were removed from `apps.onboarding.views`.
- Partial invitation failures are returned to the onboarding view so they can still be logged without aborting the optional onboarding step.
- Existing `/onboarding/team/` POST and skip behavior remain compatible.

## Phase 6.8 Setup Completion and Dismiss State

Workspace setup now has lightweight user-specific state:

- `apps.onboarding.models.WorkspaceSetupState` stores per-user/per-workspace `dismissed_at` and `marked_complete_at` timestamps in the public/control-plane schema.
- `apps.onboarding.services.setup_state` exposes display state and mutation helpers so orgs views do not depend on storage details.
- The workspace dashboard setup card is hidden when the current user dismisses the card, manually marks setup complete, or the checklist is naturally complete.
- The workspace settings setup page remains available even when dismissed or complete, and exposes Mark complete, Dismiss dashboard card, Show on dashboard, and Reopen setup actions.
- Canonical route: `/workspace/<workspace_id>/settings/setup/state/` as `workspace_settings_setup_state`.
- Compatibility route: `/orgs/workspace/<workspace_id>/setup/state/` as `workspace_setup_state`.
- The checklist remains advisory: no ERP access gates or tenant business-data writes are introduced.

## Next Step

Commit Phase 6 as a single phase-level commit, then start Phase 7 modern fintech UI polish with the management/workspace setup surfaces as the first review targets.
