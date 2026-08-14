---
status: active
owner: ui
updated: 2026-06-30
tags: [ui, saas-ia, phase-7, visual-polish]
related:
  - docs/ui/saas_information_architecture_audit.md
  - docs/ui/management_shell_visual_polish_checklist.md
  - docs/ui/onboarding_phase6_plan.md
  - docs/ui/phase6_onboarding_review.md
  - docs/ui/phase7_public_auth_polish_plan.md
  - docs/ui/phase7_modern_fintech_ui_polish_review.md
---

# Phase 7 Modern Fintech UI Polish Plan

Phase 7 turns the SaaS information architecture work into a more coherent product surface without changing route behavior, authorization behavior, tenant isolation, or onboarding semantics.

The first review target is the management/workspace setup surfaces because Phase 6 made them functional and visible:

- `templates/layouts/management.html`
- `static/css/management.css`
- `templates/company/workspace_setup.html`
- `templates/company/workspace_dashboard.html`
- `templates/components/navigation/workspace_settings_sidebar.html`

## Product Target

Public pages should feel like a polished SaaS fintech funnel. Authenticated global pages should feel like a workspace manager. Tenant ERP pages should feel dense, stable, and operational. Workspace settings should feel administrative, not like tenant transaction screens.

Users should always be able to answer:

- Which account area am I in?
- Which workspace am I managing?
- Am I configuring the workspace or operating inside the ERP?
- What is the next practical setup step?
- What business/accounting impact will a major action have?

## Non-Negotiables

- No route changes in Phase 7.1.
- No permission or middleware behavior changes in Phase 7.1.
- No schema changes in Phase 7.1.
- No broad template rewrites before guard coverage exists.
- Workspace setup remains advisory and non-blocking.
- Public/schema concepts must not leak into tenant ERP screens.
- Tenant business data must not leak into global/public management screens.
- Bootstrap/HTMX remains the UI foundation.
- Avoid decorative gradient/orb-heavy styling; use restrained contrast, spacing, typography, and clear action hierarchy.

## Visual Direction

Use a serious SaaS operations style:

- restrained neutral base colors;
- one or two semantic accents for active state and primary actions;
- compact cards with 8px or smaller radius unless an existing component requires otherwise;
- clear page headers, breadcrumbs, empty states, and action bars;
- dense but readable ERP tables and document surfaces;
- stable dimensions for navigation, setup progress, buttons, badges, and checklist rows;
- mobile navigation that preserves the same information architecture as desktop.

## Current Management/Setup Findings

- The management shell already owns a dedicated stylesheet through `static/css/management.css`.
- The workspace setup page correctly extends `base_workspace_settings.html`.
- The dashboard setup card correctly links to the canonical `workspace_settings_setup` page and posts state changes to `workspace_settings_setup_state`.
- The dashboard still contains inline dashboard styling that should be extracted in a later visual slice.
- The workspace setup checklist is useful but visually basic: progress, state alerts, task cards, and action hierarchy need polish.
- The dashboard setup card and setup page duplicate checklist rendering; extract only after the visual target is clear.

## Safe Implementation Slices

1. Phase 7.1: document the visual target and add intent tests. Complete.
2. Phase 7.2: management/setup visual token audit and small CSS extension only; no route/template behavior changes. Complete.
3. Phase 7.3: polish the workspace dashboard setup card with the shared setup vocabulary while preserving dismiss behavior. Complete.
4. Phase 7.4: extract duplicate setup checklist markup only if it reduces real duplication without changing routes or state behavior. Complete.
5. Phase 7.5: polish global workspace selector/dashboard surfaces around workspace identity and switching. Complete.
6. Phase 7.6: public/auth route and template inventory plus guard tests before visual changes. Complete.
7. Phase 7.7: first public/auth visual polish pass as a SaaS fintech funnel. Complete.
8. Phase 7.8: render-review public/auth pages, then apply focused overflow/spacing fixes where needed. Complete.
9. Phase 7.9: polish tenant ERP dashboard/navigation density without changing business workflows. Complete.
10. Phase 7.10: run final rendered/browser review where practical, document findings, and prepare the phase-level commit. Complete.

## Acceptance Criteria

- Existing URLs and route names continue to resolve.
- Existing permission checks and middleware behavior are unchanged.
- Setup checklist completion/dismiss behavior remains advisory.
- Management and workspace settings pages keep using the management shell and static stylesheet.
- Any visual changes have focused tests or render smoke coverage.
- Documentation records what changed, what was intentionally deferred, and the next safe slice.

## Phase 7.2 Checkpoint

Phase 7.2 added a small management/setup visual vocabulary to `static/css/management.css` and applied it only to `templates/company/workspace_setup.html`.

The change keeps setup advisory and preserves:

- canonical `workspace_settings_setup_state` POST targets;
- setup complete, dismiss, and reopen actions;
- checklist item links to existing workspace, accounting, party, product, stock, team, rate, and business-event surfaces;
- the `base_workspace_settings.html` shell;
- existing dashboard setup-card behavior.

## Phase 7.3 Checkpoint

Phase 7.3 applied the same setup vocabulary to the workspace dashboard setup card in `templates/company/workspace_dashboard.html`.

The change preserves:

- `setup_state.should_show_dashboard_card` visibility behavior;
- the canonical `workspace_settings_setup` link;
- the canonical `workspace_settings_setup_state` dismiss POST target;
- all checklist item action URLs;
- existing dashboard and onboarding behavior.

## Phase 7.4 Checkpoint

Phase 7.4 extracted repeated setup task/status/action markup into `templates/components/setup/setup_checklist_task.html`.

The settings setup page and dashboard setup card now include the same partial with different heading/id context:

- settings page: `task_id_prefix="setup-task"` and `heading_level="h2"`;
- dashboard card: `task_id_prefix="dashboard-setup-task"` and `heading_level="h3"`.

The partial preserves all existing checklist action URLs and does not change setup state, routes, permissions, dashboard visibility, or onboarding behavior.

## Phase 7.5 Checkpoint

Phase 7.5 polished the global workspace selector/list surface in `templates/company/workspace_home.html`.

The change:

- makes the page read as a global workspace manager instead of a generic welcome page;
- adds workspace summary tiles for available workspaces, pending invites, and sent invites;
- makes the active workspace visually explicit;
- keeps `workspace_select` as the switching action;
- uses canonical `app_workspace_create`, `app_invitations`, and `workspace_settings_home` links where appropriate;
- removes the old create-workspace modal and inline card CSS from this page.

No membership checks, selected-workspace redirect behavior, invitation accept/decline POST behavior, or workspace selection behavior changed.

## Phase 7.6 Checkpoint

Phase 7.6 records the current public/auth route and template inventory in `docs/ui/phase7_public_auth_polish_plan.md` and adds guard tests in `django_project/test_phase7_public_auth_intent.py`.

The checkpoint keeps visible that:

- `/pricing/`, `/login/`, `/signup/`, `/password/reset/`, and `/invitations/accept/<key>` target aliases are not implemented yet;
- current authentication routes remain django-allauth `/accounts/...` compatibility paths;
- current direct invitation routes remain django-invitations compatibility paths;
- missing public templates referenced by `pages.views` are inventory findings, not fixed in this slice;
- public/auth visual changes should preserve current form actions, CSRF handling, social auth links, route names, and shell ownership.

## Phase 7.7 Checkpoint

Phase 7.7 completed the first public/auth visual polish pass.

The change:

- adds `static/css/public.css` as the shared public/auth stylesheet;
- makes `base_public.html` and `base_auth.html` load that stylesheet and use full-width shell wrapper classes;
- replaces the legacy inline landing-page CSS, purple gradient treatment, remote placeholder image, and mojibake statistic in `templates/pages/home.html`;
- gives the landing page a product-specific SaaS ERP funnel with an HTML product preview for workspace metrics and document-impact rows;
- gives login, signup, and password reset pages a consistent two-column auth panel/card layout;
- preserves allauth form submission, CSRF tokens, Google social login links, password reset action, route names, and shell ownership.

Pricing, short auth aliases, direct invitation alias cleanup, and missing public templates remain deferred from the Phase 7.6 inventory.

## Phase 7.8 Checkpoint

Phase 7.8 completed the public/auth render review and one focused render-safety fix.

The review confirmed:

- `/` renders with `css/public.css`, the public shell, and the new product-specific landing sections;
- `/accounts/login/`, `/accounts/signup/`, and `/accounts/password/reset/` render with the auth shell and shared auth card layout;
- the no-`SocialApp` Google OAuth case no longer crashes auth pages;
- Google OAuth CTA and One Tap markup remain available only when `GOOGLE_OAUTH_ENABLED` is true.

The render-safety fix lives in `django_project.context_processors.google_oauth_context`, `templates/account/login.html`, and `templates/account/signup.html`. It does not change local login, signup, password reset, allauth route names, CSRF handling, or password-reset form action.

## Phase 7.9 Checkpoint

Phase 7.9 completed the first tenant ERP dashboard/navigation density pass.

The change:

- adds `static/css/workspace.css` as the tenant workspace shell/sidebar/dashboard stylesheet;
- makes `base_tenant.html` load that stylesheet;
- moves tenant layout, mobile sidebar, workspace context bar, and sidebar visual rules out of inline template style blocks;
- gives `templates/components/navigation/sidebar.html` explicit `workspace-*` classes while preserving existing labels, route names, permission conditions, and Contact compatibility links;
- gives `templates/company/workspace_dashboard.html` denser page header, stat grid, and quick-action classes while preserving existing dashboard links, setup-card behavior, subscription messaging, and data conditions.

No tenant ERP route, middleware, posting, permission, or business workflow behavior changed.

## Phase 7.10 Checkpoint

Phase 7.10 closes the Phase 7 work in `docs/ui/phase7_modern_fintech_ui_polish_review.md`.

The review records that Phase 7 is a first-pass UI infrastructure and surface cleanup, not the final high-fidelity fintech redesign. It also keeps the deferred scope visible:

- deeper product-design polish;
- the full target `/w/<workspace_slug>/...` route map;
- `/pricing/`, short auth aliases, and direct invitation accept aliases;
- missing public templates from the public/auth inventory;
- lower workspace-dashboard and broader tenant ERP module page polish;
- Contact compatibility cleanup after Party cutover;
- browser screenshot review beyond the reproducible render/static checks.

## Next Recommended Slice

Commit the Phase 7 set as one phase-level commit, then start Phase 8 regression consolidation for the SaaS IA plan. Keep the target route-map rollout as a separate alias/redirect phase after Phase 8.
