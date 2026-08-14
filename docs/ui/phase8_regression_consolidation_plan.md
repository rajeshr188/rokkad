---
status: active
owner: ui
updated: 2026-06-30
tags: [ui, saas-ia, phase-8, regression, tests]
related:
  - docs/ui/saas_information_architecture_audit.md
  - docs/ui/phase7_modern_fintech_ui_polish_review.md
  - docs/ui/route_template_inventory.md
  - docs/ui/canonical_route_aliases_phase_review.md
  - docs/ui/authorization_cleanup_inventory.md
---

# Phase 8 Regression Consolidation Plan

Phase 8 closes the current SaaS information architecture plan by strengthening tests around the routes, templates, authorization boundaries, and render contracts already introduced in Phases 2-7.

This phase should not introduce new canonical URLs, remove legacy URLs, redesign screens, or roll out `/w/<workspace_slug>/...`. Those deferred items need the Phase 8 guardrail layer first.

## Goal

Before adding public/auth aliases or the full tenant route map, the project should have enough regression coverage to prove:

- public-schema routes do not expose tenant ERP routes;
- global authenticated routes do not accidentally require or leak tenant business context;
- workspace settings routes stay workspace-admin surfaces;
- tenant ERP routes stay tenant/workspace surfaces;
- existing compatibility URLs remain stable while aliases are added later;
- major shells render with the intended base templates and navigation contracts;
- invitation, workspace switching, onboarding, and setup flows keep their current behavior;
- authorization boundaries remain explicit for Party, Product, Rates, Notify, utility data tools, and known deferred domain-specific apps.

## Existing Guard Inventory

Current guard files that Phase 8 should preserve and extend:

- `django_project/test_route_intent.py`
- `django_project/test_template_layout_intent.py`
- `django_project/test_shell_render_smoke.py`
- `django_project/test_management_shell_visual_smoke.py`
- `django_project/test_invitation_team_flow_intent.py`
- `django_project/test_authorization_surface_intent.py`
- `django_project/test_onboarding_phase6_intent.py`
- `django_project/test_phase7_public_auth_intent.py`
- `django_project/test_phase7_public_auth_render_smoke.py`
- `django_project/test_phase7_ui_polish_intent.py`

## Regression Buckets

### 1. Route Boundary Regression

Add or tighten tests for:

- active `ROOT_URLCONF` and `PUBLIC_SCHEMA_URLCONF`;
- public URLConf excluding tenant ERP prefixes;
- tenant URLConf grouping current tenant ERP prefixes;
- canonical `/app/...` and `/workspace/<id>/settings/...` aliases resolving;
- legacy `/orgs/...`, allauth `/accounts/...`, and django-invitations paths still resolving;
- target aliases that are intentionally absent today, including `/pricing/`, short auth aliases, and `/w/<workspace_slug>/...`.

### 2. Template/Shell Regression

Add or tighten tests for:

- public templates extending `base_public.html`;
- auth templates extending `base_auth.html`;
- global account/workspace templates extending `base_global.html`;
- workspace settings templates extending `base_workspace_settings.html`;
- tenant templates extending `base_tenant.html`;
- static stylesheet ownership for `management.css`, `public.css`, and `workspace.css`;
- no reintroduction of broad inline shell style blocks.
- root `layouts/base.html` and `main_nav.html` inline style debt staying visible until a later extraction slice.

### 3. Auth/Public Flow Regression

Add or tighten tests for:

- landing page render;
- allauth login/signup/password reset render;
- Google OAuth CTA gating through `GOOGLE_OAUTH_ENABLED`;
- direct django-invitations compatibility route behavior;
- missing public templates remaining documented until implemented.

### 4. Workspace Flow Regression

Add or tighten tests for:

- workspace list/global dashboard render;
- workspace switch membership validation;
- selected workspace not granting access without membership;
- canonical workspace settings links;
- setup checklist advisory behavior;
- onboarding completion redirect to workspace setup when a selected workspace exists.

### 5. Invitation/Team Regression

Add or tighten tests for:

- invited user accept path for logged-out and authenticated users;
- authenticated email mismatch fail-closed behavior;
- sent invitation list workspace context;
- revoke return path;
- role-grant policy;
- member remove, role change, and self-leave boundaries.

### 6. Authorization Regression

Add or tighten tests for:

- middleware workspace-required coverage;
- Party action guards;
- Product action guards;
- Rates and Notify action guards;
- utility data-tool coverage;
- Contact compatibility gap remaining documented until Party cutover;
- DEA and Girvi remaining separate domain-specific permission tracks.

### 7. Render/HTMX Regression

Add practical render smoke tests before browser automation:

- public/auth render smoke;
- management/global shell render smoke;
- workspace settings render smoke;
- tenant shell render smoke;
- dashboard setup-card render smoke;
- high-value HTMX partial responses where the route already exists and has stable behavior.

Browser screenshot automation can be added later, but Phase 8 should keep command-line render checks reproducible first.

## Safe Implementation Slices

1. Phase 8.1: create this regression plan and guard the inventory. Complete.
2. Phase 8.2: strengthen route boundary tests for current aliases, legacy URLs, and intentionally absent future aliases. Complete.
3. Phase 8.3: strengthen template/shell regression tests for base-template ownership and static stylesheet contracts. Complete.
4. Phase 8.4: strengthen public/auth render and compatibility tests, including missing-template documentation. Complete.
5. Phase 8.5: strengthen workspace switching, setup, and onboarding regression tests. Complete.
6. Phase 8.6: strengthen invitation/team regression coverage around accept/revoke/role boundaries. Complete.
7. Phase 8.7: strengthen authorization regression coverage for current tenant utility surfaces and documented deferred gaps. Complete.
8. Phase 8.8: final Phase 8 review, verification list, and commit preparation. Complete.

## Deferred Until After Phase 8

- `/pricing/`
- short auth aliases: `/login/`, `/signup/`, `/password/reset/`
- public invitation alias: `/invitations/accept/<key>`
- missing public templates referenced by `pages.views`
- full `/w/<workspace_slug>/...` route-map rollout
- deeper high-fidelity product redesign

## Phase 8.2 Checkpoint

Phase 8.2 strengthens `django_project/test_route_intent.py` without changing URL behavior.

The route-boundary regression coverage now verifies:

- current canonical `/app/...` and `/workspace/<id>/settings/...` aliases resolve in both public and tenant URLConfs;
- legacy allauth, invitations, and `/orgs/...` compatibility paths remain resolvable;
- representative tenant ERP paths resolve only in the tenant URLConf;
- representative tenant ERP paths are rejected by the public URLConf;
- `/pricing/`, short auth aliases, `/invitations/accept/<key>`, and `/w/<workspace_slug>/...` remain intentionally absent until later rollout phases.

The tests also document current boundary quirks rather than hiding them: `/contact/` is currently a public page path, while tenant Contact lives under representative child paths such as `/contact/customer/`.

## Phase 8.3 Checkpoint

Phase 8.3 strengthens `django_project/test_template_layout_intent.py` without changing template behavior.

The template/shell regression coverage now verifies:

- shell aliases extend the intended low-level layouts;
- public/auth aliases own `css/public.css`;
- tenant alias owns `css/workspace.css`;
- global/settings aliases delegate to the management shell rather than loading public or tenant styles directly;
- management/workspace shell partials do not reintroduce inline style blocks;
- known root `layouts/base.html` and `main_nav.html` inline style debt remains visible until a later extraction slice.

## Phase 8.4 Checkpoint

Phase 8.4 strengthens `django_project/test_phase7_public_auth_render_smoke.py` without adding public/auth aliases or creating missing templates.

The public/auth render regression coverage now verifies:

- `/` renders the Phase 7 public landing surface;
- current renderable public pages `/about/`, `/privacy-policy/`, and `/terms-and-conditions/` use the public shell and `css/public.css`;
- current allauth login, signup, and password-reset paths render with the auth shell and Google OAuth CTA gating;
- current allauth compatibility route names still reverse to `/accounts/...`;
- current django-invitations compatibility accept path remains `/invitations/accept-invite/<key>`;
- invalid current invitation accept links fail closed with HTTP 410;
- confirmed missing public templates remain documented until implemented.

The tests also keep the current public/tenant `/contact/` ambiguity visible: `/contact/` is a public page route in the public URLConf but a tenant Contact prefix in the active tenant URLConf, so the future public/template cleanup should handle it deliberately.

## Phase 8.5 Checkpoint

Phase 8.5 strengthens `django_project/test_onboarding_phase6_intent.py` without changing workspace switching, setup, or onboarding behavior.

The workspace/setup/onboarding regression coverage now verifies:

- canonical workspace setup routes stay `/workspace/<id>/settings/setup/` and `/workspace/<id>/settings/setup/state/`;
- legacy setup compatibility routes stay `/orgs/workspace/<id>/setup/` and `/orgs/workspace/<id>/setup/state/`;
- setup page and dashboard setup-card templates post to the canonical setup-state route rather than the legacy state route;
- workspace switching validates access before setting the selected workspace;
- workspace switching keeps safe `next` handling and `WORKSPACE_SWITCH` audit logging;
- existing runtime regression files for setup checklist, setup state, onboarding completion redirects, onboarding workspace creation, and onboarding team invites remain present.

## Phase 8.6 Checkpoint

Phase 8.6 strengthens `django_project/test_invitation_team_flow_intent.py` without changing invitation or team behavior.

The invitation/team regression coverage now verifies:

- existing runtime guard tests for invite permissions, role-grant policy, revoke denial, team remove/change-role gates, sole-owner self-leave, sent-invitation workspace context, and direct accept adapter behavior remain present;
- direct invitation accept keeps the current split: logged-out users fall back to `django-invitations`, authenticated matching users go through the orgs control plane, and authenticated email mismatches fail closed;
- sent invitation lists and revoke returns keep workspace-settings context through `workspace_settings_invitations`;
- team member removal and role changes keep workspace permission checks and route sensitive mutations through `apps.orgs.services.control_plane`;
- the control plane keeps role policy checks before membership/invitation mutations and owns `TEAM_INVITE`, `TEAM_INVITE_ACCEPT`, `TEAM_INVITE_DECLINE`, `TEAM_INVITE_REVOKE`, `TEAM_MEMBER_REMOVE`, and `TEAM_ROLE_CHANGE` audit actions.

## Phase 8.7 Checkpoint

Phase 8.7 strengthens `django_project/test_authorization_surface_intent.py` without changing permission behavior.

The authorization regression coverage now verifies:

- current tenant ERP prefixes remain exactly `party`, `contact`, `data-tools`, `girvi`, `rates`, `product`, `notify`, `notify-v2`, and `dea`;
- middleware workspace-required coverage continues to include every current tenant ERP prefix;
- Party, Product catalog, Product stock/pricing, Product image/attribute, Rates, legacy Notify, Notify v2, and utility data-tool surfaces retain action-guard or owner/admin guard coverage;
- Contact remains a documented legacy compatibility gap until Party cutover;
- Notify v2 WhatsApp webhook remains explicitly documented as intentionally unauthenticated for provider callbacks;
- DEA and Girvi remain documented as separate domain-specific permission tracks outside the generic SaaS IA Phase 5 route-group closeout.

## Phase 8.8 Checkpoint

Phase 8.8 closes the regression consolidation phase in `docs/ui/phase8_regression_consolidation_review.md`.

The review records:

- completed Phase 8 guard coverage across route, template, public/auth, workspace/setup/onboarding, invitation/team, and authorization buckets;
- deferred scope that still must not be confused with completed Phase 8 work;
- compatibility findings for current aliases, missing public templates, `/contact/` ambiguity, advisory setup behavior, and Contact-to-Party cutover;
- verification commands and expected log noise;
- the phase-level commit boundary for tests and documentation only.

## Acceptance Criteria

- Phase 8 adds regression confidence without changing runtime behavior.
- Existing public/global/tenant/settings route boundaries remain stable.
- Existing compatibility URLs remain stable.
- Deferred route aliases remain clearly documented and tested as absent until their rollout phase.
- Tests can run locally without browser or network dependencies.
- `docs/STATUS.md` and `docs/AGENT_MEMORY.md` record Phase 8 progress after meaningful slices.

## Next Recommended Step

Commit the Phase 8 set, then start a new follow-on phase for `/pricing/`, missing public templates, short auth aliases, `/invitations/accept/<key>`, and the full `/w/<workspace_slug>/...` route-map rollout.
