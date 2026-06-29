---
status: active
owner: project
updated: 2026-06-29
tags: [ui, authorization, saas, security, inventory]
related: [saas_information_architecture_audit.md, canonical_route_aliases_phase_review.md, invitation_team_flow_cleanup_plan.md, ../STATUS.md, ../AGENT_MEMORY.md]
---

# Authorization Cleanup Inventory

## Purpose

Phase 5 starts with an inventory and guard-test pass before changing permission behavior.

The goal is to make the current authorization model explicit across the SaaS route planes:

- Public/platform area
- Authenticated global area
- Workspace settings/admin area
- Tenant/workspace ERP area
- Future customer/member portal area

This document records the current state, known gaps, and the safest implementation order.

## Current Authorization Layers

### Middleware Isolation

`apps.orgs.middleware_v2.SecureWorkspaceMiddleware` is the primary tenant isolation layer.

Current behavior:

- Resolves workspace by domain first.
- Falls back to workspace id in known `/orgs/workspace/<id>/...` and `/orgs/company/<id>/...` paths.
- Falls back to workspace id in canonical `/workspace/<id>/settings/...` paths.
- Requires workspace context for every current tenant ERP prefix in `django_project.tenant_urls.TENANT_ERP_URLPATTERNS`.
- Falls back to user profile workspace during the transition period.
- Rejects tenant domain and path workspace mismatches.
- Requires membership before switching to a tenant schema.
- Redirects unauthenticated tenant-domain users to login.
- Sends public/unresolved routes to the public schema.

Current limitation:

- Middleware is a defense layer, not a replacement for view-level permissions.
- The middleware path-id extractor covers current legacy workspace paths and canonical settings aliases, but not future non-settings workspace-scoped aliases.

### Workspace Resolution Helper

`apps.orgs.tenant_context.resolve_request_workspace()` is the safer helper for view code.

Current behavior:

- Treats `request.tenant` as source of truth.
- Does not use profile fallback unless explicitly requested.
- Keeps public workspace handling opt-in.

Preferred future rule:

- Tenant ERP and workspace settings views should resolve workspace from `request.tenant` or explicit path id, then check membership/permission.
- Profile fallback should stay limited to non-authoritative UX hints and compatibility routes.

## Route Plane Inventory

### Public / Platform

Route source:

- `django_project.urls`
- `django_project.shared_urlpatterns.PUBLIC_PLATFORM_URLPATTERNS`
- `django_project.shared_urlpatterns.AUTH_URLPATTERNS`

Current examples:

- Landing/dashboard redirect routes from `pages.urls`
- Allauth login/signup/password routes
- Django invitations package routes

Expected authorization:

- Public pages must not read tenant business data.
- Auth pages must stay public-schema safe.
- Accept-invite entrypoints must validate invitation key, email, and workspace membership creation rules.

Current guardrails:

- Public URLConf does not include tenant ERP prefixes.
- Direct invitation accept now delegates authenticated matching users through the orgs-owned adapter while retaining django-invitations fallback.

### Global Authenticated

Route source:

- `django_project.shared_urlpatterns.GLOBAL_AUTHENTICATED_URLPATTERNS`
- Canonical aliases under `/app/...`
- Legacy compatibility routes under `/orgs/...`
- Account/profile routes under `/profile/...`
- Onboarding and subscription routes

Current examples:

- `app_dashboard`
- `app_workspaces`
- `app_workspace_create`
- `app_invitations`
- `app_memberships`
- `workspace_selector`
- `workspace_create`
- `team_invitations`
- `my_memberships`

Expected authorization:

- Requires authenticated user.
- May list only workspaces where the user is owner/member or has platform override.
- Must not expose tenant business documents.
- Workspace switching must verify membership before selecting a workspace.

Current guardrails:

- Orgs views are broadly `@login_required`.
- Workspace access helpers check owner/member/platform-admin for workspace-specific routes.
- Invitation/team authorization coverage exists for invite, revoke, accept, role change, member removal, and self-leave.

Known gaps:

- Account settings/profile/billing route aliases are not canonicalized yet.
- Some global routes still rely on selected profile workspace fallback for compatibility.

### Workspace Settings / Admin

Route source:

- Canonical aliases under `/workspace/<workspace_id>/settings/...`
- Legacy compatibility routes under `/orgs/workspace/<workspace_id>/...` and `/orgs/team/...`

Current examples:

- `workspace_settings_home`
- `workspace_settings_preferences`
- `workspace_settings_team`
- `workspace_settings_invitations`
- `workspace_settings_invite`
- `workspace_settings_leave`
- `workspace_detail`
- `workspace_preferences`
- `team_members_list`
- `team_invitations_list`
- `team_invite`
- `workspace_leave`

Expected authorization:

- Requires authenticated user.
- Requires membership in the target workspace.
- Mutations require owner/admin or explicit workspace permission.
- Billing/subscription settings should require owner-level or billing-management permission.

Current guardrails:

- Workspace settings views use `_assert_workspace_access`, `_assert_workspace_owner`, role policy services, and invitation control-plane services.
- Invitation/team tests cover selected authorization boundaries.

Known gaps:

- `team_members_list` and `team_invitations_list` retain selected-workspace fallback for old URLs.
- Leave-workspace canonical alias exists, but navigation/redirect adoption is deferred.
- Middleware path-id extraction now recognizes canonical `/workspace/<id>/settings/...` paths, but future workspace-scoped aliases still need explicit coverage.

### Tenant / Workspace ERP

Route source:

- `django_project.tenant_urls.TENANT_ERP_URLPATTERNS`

Current prefixes:

- `/party/`
- `/contact/`
- `/data-tools/`
- `/girvi/`
- `/rates/`
- `/product/`
- `/notify/`
- `/notify-v2/`
- `/dea/`

Expected authorization:

- Requires tenant schema context.
- Requires workspace membership.
- Mutations require explicit module permissions.
- Accounting tools should be role-gated separately from normal business-event workflows.

Current guardrails:

- Girvi has `girvi_workspace_required`, `girvi_permission_required`, `GirviWorkspaceRequiredMixin`, and `GirviPermissionRequiredMixin`.
- DEA has `dea_accountant_required` and `DeaAccountantRequiredMixin` for accountant-only surfaces.
- Party has `assert_party_workspace_access`, `assert_party_permission`, `assert_party_action_permission`, `party_action_required`, and `PartyPermissionRequiredMixin` available for view adoption.
- Party list/detail read paths use the Party view action guard, and Party export uses the Party export action permission.
- Party create, customer-convert, and update paths use Party create/edit action guards.
- Party profile-photo, contact-method, and address mutation paths use the Party edit action guard.
- Party identifier, document, and relationship mutation paths use the Party edit action guard.
- Party role add/end and duplicate merge mutation paths use the Party edit action guard.
- Secure middleware requires membership before setting tenant context for all current tenant ERP prefixes: `party`, `contact`, `data-tools`, `girvi`, `rates`, `product`, `notify`, `notify-v2`, and `dea`.

Known gaps:

- Contact, Product, and some Rates/Notify surfaces are still mostly login-only at the view layer.
- Several DEA business-event and report surfaces are login-only or role-dependent by navigation rather than consistently using shared access helpers.
- Some legacy Girvi surfaces still use plain login-only guards and need route-by-route review.

### Customer / Member Portal

Current status:

- No canonical customer portal route plane is implemented yet.

Expected future authorization:

- Portal users must see only their own loans, invoices, payments, documents, and statements.
- Portal selectors should bind by portal identity and tenant context, not by arbitrary party/customer ids from the URL.
- Portal routes should not reuse internal staff ERP permission assumptions.

## Role / Permission Model Snapshot

Current role labels:

- Owner
- Admin
- Member
- Viewer
- Accountant appears as a functional role in DEA access checks, but is not yet part of `RolePermissions`.
- Platform admin is represented by Django superuser/staff-style override checks.

Permission source:

- `apps.orgs.permissions.RolePermissions`
- `apps.orgs.permissions.get_effective_permissions()`
- App-specific helpers such as Girvi and DEA access modules.

Important current mismatch:

- The role-permission map contains broad module codenames, but not every tenant app view consumes those codenames yet.

## Phase 5 Guard Tests Added

`django_project/test_authorization_surface_intent.py` documents and guards:

- This inventory exists and names public/global/workspace-settings/tenant/portal planes.
- Public URLConf excludes tenant ERP prefixes.
- Tenant URLConf keeps tenant ERP prefixes grouped separately.
- Canonical control-plane aliases are treated as global/workspace-settings routes, not tenant ERP routes.
- Middleware workspace-required prefixes cover current tenant ERP prefixes.
- Secure middleware still checks membership before tenant schema switching.
- Girvi and DEA shared access helper contracts remain present.
- Known login-only tenant app gaps stay visible until fixed.

## Recommended Cleanup Order

1. Keep this inventory and guard tests as the Phase 5.1 baseline.
2. Review Party authorization coverage as a completed first tenant-app conversion and commit the Phase 5 Party set.
3. Add shared tenant app access helpers for Contact, Product, Rates, Notify, and utility data tools.
4. Convert Contact and Product mutation views in small route groups.
5. Audit DEA login-only business-event/report routes and split normal business-event access from accountant-only tools.
6. Audit remaining Girvi login-only legacy surfaces and either convert them to Girvi helpers or document why they are safe.
7. Add subscription/billing permission gates after ownership semantics are settled.

## Deferred Decisions

- Whether account settings/profile/billing should live under `/app/account/...`, `/app/billing/...`, or workspace settings.
- Whether `Accountant` should become a first-class role in `RolePermissions`.
- Whether future customer portal routes live on tenant domains, a portal subdomain, or a separate public-schema entrypoint with tenant-scoped selectors.
