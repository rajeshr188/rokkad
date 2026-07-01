---
status: active
owner: project
updated: 2026-06-29
tags: [ui, saas, information-architecture, tenancy, audit]
related: [screen_designs.md, htmx_interactions.md, ../AGENT_MEMORY.md, ../STATUS.md, ../domain/workspace-auth.md, ../domain/accounting.md]
---

# SaaS Information Architecture Audit

This document records the current UI/route/schema audit and the recommended redesign plan for separating Rokkad into a clear SaaS product structure:

- public/platform area
- authenticated global workspace manager
- tenant/workspace ERP area
- workspace settings/admin area
- customer/member portal area

The current Phase 2 route/template ownership matrix is maintained in [route_template_inventory.md](route_template_inventory.md).

The current Phase 3 navigation and workspace switcher contract is maintained in [navigation_workspace_switcher_plan.md](navigation_workspace_switcher_plan.md).

No code changes were made for this audit.

## A. Current State Map

### Installed App Classification

Current classification comes from `django_project/settings/base.py`.

| Area | Apps |
| --- | --- |
| Shared/public schema | `django_tenants`, `apps.orgs`, Django core apps, `allauth`, `guardian`, `dynamic_preferences`, `accounts`, `apps.onboarding`, `apps.subscriptions`, `pages`, `invitations`, `slick_reporting` |
| Tenant schema | `apps.tenant_apps.contact`, `apps.tenant_apps.party`, `apps.tenant_apps.girvi`, `apps.tenant_apps.product`, `apps.tenant_apps.terms`, `apps.tenant_apps.rates`, `apps.tenant_apps.notify`, `apps.tenant_apps.notify_v2`, `apps.tenant_apps.dea` |
| Present but not runtime-installed | `apps.tenant_apps.Chitfund`, `apps.tenant_apps.savings_scheme`, some tenant utility subpackages |

### URL Structure

| URLConf | Current purpose | Audit finding |
| --- | --- | --- |
| `django_project.urls` | Public schema URLConf | Includes `shared_urlpatterns`; this exposes public, auth, orgs, onboarding, and subscriptions together. |
| `django_project.tenant_urls` | Tenant URLConf | Includes tenant apps and also `shared_urlpatterns`, so global/control-plane routes are reachable in tenant context. |
| `django_project.shared_urlpatterns` | Shared route bundle | Mixes public pages, auth, onboarding, orgs, dynamic preferences, subscriptions, and profile routes. |
| `django_project.public_urls` | More explicit public/global URLConf | Exists, but current `PUBLIC_SCHEMA_URLCONF` points to `django_project.urls`, not this file. |

Current major route families:

| Product area | Current route families |
| --- | --- |
| Public | `/`, `/about/`, `/privacy-policy/`, `/terms-and-conditions/`, `/contact/`, `/help/`, `/faq/`, `/accounts/*`, `/invitations/*` |
| Global authenticated | `/dashboard/`, `/workspace/`, `/orgs/workspace/*`, `/orgs/team/*`, `/profile/*`, `/onboarding/*` |
| Tenant ERP | `/girvi/`, `/party/`, `/contact/`, `/product/`, `/rates/`, `/notify/`, `/notify-v2/`, `/dea/` |
| Workspace settings | Mostly `/orgs/workspace/<id>/*`, with team routes also under `/orgs/team/*` |
| Billing | `/subscriptions/plans/`, `/subscriptions/checkout/<plan_id>/`, `/subscriptions/dashboard/`, `/subscriptions/invoices/*` |
| Customer/member portal | No clear portal route or app found in the current runtime URL map. |

### Template Structure

| Layout/template family | Current role |
| --- | --- |
| `templates/layouts/base.html` | Shared base for public, auth, global, subscription, and error pages. |
| `templates/layouts/management.html` | Account/workspace management layout. |
| `templates/layouts/workspace.html` | Tenant ERP layout with sidebar and workspace banner. |
| `templates/components/navigation/main_nav.html` | Main navbar used across public/global/tenant pages. |
| `templates/components/navigation/sidebar.html` | Live tenant sidebar source of truth. |
| `templates/company/*` | Workspace management, team, invitations, profile, settings. |
| `templates/dea/*`, `templates/girvi/*`, `templates/party/*`, `templates/product/*` | Tenant ERP screens. |

The project already has the beginning of a two-plane UI through `management.html` and `workspace.html`, but `base.html` and `main_nav.html` still serve too many unrelated contexts.

### Existing Flow Summary

| Flow | Current implementation |
| --- | --- |
| Signup/login/logout/password reset | Primarily Django Allauth under `/accounts/`, with local templates in `templates/account/`. |
| Dashboard after login | `pages.views.Dashboard` redirects to selected workspace dashboard, workspace selector, or workspace create. |
| Workspace creation | `apps.orgs.views.workspace_create` and onboarding company step both create workspaces. |
| Workspace switching | `workspace_select` sets `request.user.profile.workspace`; navbar and workspace switcher read profile workspace. |
| Invitation | `CompanyInvitation` extends django-invitations, with accept/manage flows in `apps.orgs.views`. |
| Team management | Membership and role changes are in `apps.orgs.views`, backed by `apps.orgs.services.role_policy`. |
| Authorization | Shared role permission definitions exist in `apps.orgs.permissions`; Girvi and DEA have stronger module-specific guards. |
| Subscription/billing | `apps.subscriptions` stores plans, subscriptions, invoices, payments against `Company`, but some view code still appears user-subscription oriented. |
| Onboarding | `apps.onboarding` provides profile, company, team, tour, complete steps. |
| Tenant dashboard | `workspace_dashboard` renders workspace-level metrics and activity through `templates/company/workspace_dashboard.html`. |

## B. Problems Found

### Fragmented Flows

- There is no stable global authenticated dashboard. `/dashboard/` often redirects away to a selected workspace.
- `/workspace/` also redirects to a selected workspace unless `?show_all=1` is used.
- Workspace creation exists both in orgs and onboarding.
- Billing lives under `/subscriptions/`, outside a clear workspace settings IA.
- Invitation management is split between `/invitations/`, `/orgs/team/invitations/`, and `/orgs/team/invitations/accept/<key>/`.

### Duplicated or Mixed Templates

- Auth/public/global/subscription pages all rely heavily on `layouts/base.html`.
- `account/signup.html` extends `pages/home.html`, which couples signup to landing-page markup.
- `account/password_change.html` extends `pages/dashboard.html`, not an auth/account layout.
- Some DEA reconciliation templates extend `"base.html"` even though the project base lives at `layouts/base.html`.
- `navigation.py` contains a dynamic navigation structure but is explicitly not the live source of truth; the live sidebar is template-coded.

### Schema Boundary Risks

- `shared_urlpatterns` are loaded into both public and tenant URLConfs.
- `SecureWorkspaceMiddleware` can use profile workspace fallback, so global routes can silently execute with a selected workspace.
- Public schema concepts, workspace management, subscription management, and tenant ERP screens are not clearly separated by URL prefix.
- Tenant business routes are protected by middleware, but route shape does not make the boundary obvious to users.

### Confusing Redirects

- Home redirects authenticated users to `/dashboard/`.
- `/dashboard/` redirects to a selected tenant dashboard if profile workspace is set.
- Workspace selector redirects to the selected workspace unless `show_all=1`.
- Billing mixin can auto-select the first available workspace in public-schema context.

### Authorization Gaps

- Girvi operational routes now have strong permission helpers.
- DEA high-risk legacy/accountant surfaces have strong owner/admin/accountant gates.
- Party, Product, Rates, Notify, and utility data-tool route groups now have explicit Phase 5 authorization guard coverage. Legacy Contact remains compatibility-only while Party replaces it. Broader DEA/Girvi domain hardening remains in dedicated accounting/loan permission tracks.
- Template-hidden buttons are not sufficient; every HTMX/action endpoint needs a server-side permission gate.

### Subscription/Billing Bugs and Risks

- `Subscription` is modeled as `company = OneToOneField(Company)`.
- `PaymentView` still calls `Subscription.objects.update_or_create(user=request.user, ...)`, which does not match the model shape.
- Invoice PDF/email code references `invoice.subscription.user`, which does not match the current company-linked subscription model.
- Billing should be workspace settings, not generic account navigation.

### UX Gaps

- Public pages do not yet read as a polished fintech SaaS funnel.
- Global authenticated pages are close to workspace management but still share global/tenant nav.
- Tenant area feels like a collection of modules rather than one ERP shell.
- Workspace switching exists but is not always obvious as a control-plane vs data-plane action.
- Workspace settings are not separated from daily ERP operations.
- Customer/member portal is not yet implemented as a distinct area.

## C. Recommended SaaS Information Architecture

### Target Route Map

```text
/                         public landing
/pricing/                 public pricing
/login/                   login
/signup/                  signup
/password/reset/          forgot password
/invitations/accept/<key> accept invitation

/app/                     global authenticated dashboard
/app/workspaces/          workspace list
/app/workspaces/new/      create workspace
/app/invitations/         pending invitations
/app/account/             account settings

/w/<workspace_slug>/      tenant ERP dashboard
/w/<workspace_slug>/operations/
/w/<workspace_slug>/parties/
/w/<workspace_slug>/sales/
/w/<workspace_slug>/purchase/
/w/<workspace_slug>/loans/
/w/<workspace_slug>/inventory/
/w/<workspace_slug>/commodity/
/w/<workspace_slug>/accounting/
/w/<workspace_slug>/reports/

/w/<workspace_slug>/settings/
/w/<workspace_slug>/settings/profile/
/w/<workspace_slug>/settings/team/
/w/<workspace_slug>/settings/invitations/
/w/<workspace_slug>/settings/roles/
/w/<workspace_slug>/settings/billing/
/w/<workspace_slug>/settings/modules/
/w/<workspace_slug>/settings/numbering/
/w/<workspace_slug>/settings/accounting/
/w/<workspace_slug>/settings/security/

/portal/
/portal/loans/
/portal/invoices/
/portal/payments/
/portal/documents/
/portal/statements/
```

This should be introduced incrementally through aliases and redirects, not as a big-bang route rewrite.

### App Structure Recommendation

| Area | Owner |
| --- | --- |
| Public pages | `pages` |
| Auth | Allauth templates plus local auth/account templates |
| Global workspace manager | `apps.orgs`, `accounts`; optionally a thin `global` URL namespace later |
| Workspace settings | `apps.orgs`, `apps.subscriptions`, and tenant setup selectors |
| Tenant ERP | `party`, `girvi`, `product`, `rates`, `notify_v2`, `dea` |
| Customer portal | New dedicated portal app or a tenant app with strict party/member scoping |

## D. Recommended Userflows

### New Visitor to Workspace Dashboard

```text
Landing
-> Pricing
-> Signup
-> Email verification if enabled
-> /app/workspaces/new
-> Create workspace
-> Provision tenant schema
-> Seed tenant defaults
-> Workspace setup checklist
-> Tenant dashboard
```

### Existing User to Tenant Dashboard

```text
Login
-> /app/
-> See workspaces and pending invitations
-> Choose workspace
-> Validate membership
-> Set selected workspace
-> Tenant dashboard
```

### Invited User Joins Workspace

```text
Accept invitation link
-> If logged out, login/signup
-> Validate key, email, company, status, expiry
-> Create membership
-> Mark invitation accepted
-> Set selected workspace
-> Show joined confirmation
-> Tenant dashboard or onboarding-lite
```

### Owner Invites Member

```text
Workspace settings
-> Team
-> Invite member
-> Enter email and role
-> Validate inviter permission and grantable role
-> Send invitation
-> Track pending invitation
-> Allow revoke/resend
```

### Owner Manages Subscription

```text
Workspace settings
-> Billing
-> Current plan, usage, invoices
-> Choose or change plan
-> Checkout
-> Payment confirmation/webhook
-> Update company subscription
```

### User Switches Workspace

```text
Tenant or global topbar
-> Workspace switcher
-> Choose membership
-> Validate access
-> Set profile workspace
-> Redirect to tenant dashboard or safe next URL
```

### Owner Configures Accounting and Opening Balances

```text
Workspace settings
-> Accounting setup
-> Fiscal year / accounting periods
-> Chart of accounts readiness
-> Ledgers and party account mappings
-> Opening balances
-> Stock opening balances
-> Commodity accounts
-> Verification report
-> Mark accounting setup complete
```

## E. Recommended Template and Layout Architecture

| Template | Purpose |
| --- | --- |
| `base_public.html` | Public landing, pricing, legal, unauthenticated marketing shell |
| `base_auth.html` | Login, signup, password reset, invitation accept |
| `base_global.html` | `/app/*` workspace manager and account pages |
| `base_tenant.html` | `/w/<workspace>/...` ERP screens |
| `base_workspace_settings.html` | `/w/<workspace>/settings/*` |
| `base_customer_portal.html` | Customer/member portal |
| `partials/navbar_public.html` | Public nav |
| `partials/topbar_global.html` | Global app topbar |
| `partials/topbar_tenant.html` | Tenant topbar with workspace switcher |
| `partials/sidebar_tenant.html` | ERP navigation |
| `partials/sidebar_settings.html` | Workspace settings navigation |
| `partials/breadcrumbs.html` | Consistent breadcrumbs |
| `partials/page_header.html` | Title, status, primary actions |
| `partials/empty_state.html` | Empty state standard |
| `partials/action_bar.html` | List/detail action rows |

Page mapping:

| Pages | Base |
| --- | --- |
| Landing, pricing, legal | `base_public.html` |
| Login, signup, password reset, invitation accept | `base_auth.html` |
| Workspace list, create workspace, global dashboard, account | `base_global.html` |
| Girvi, DEA, Party, Product, Rates, Reports | `base_tenant.html` |
| Business profile, team, invitations, roles, billing, numbering, accounting setup | `base_workspace_settings.html` |
| Customer loans, invoices, payments, statements | `base_customer_portal.html` |

## F. Navigation Design

### Public Navbar

```text
Rokkad | Product | Pricing | Security | Help | Login | Start trial
```

### Global Workspace Navbar

```text
Rokkad App | Workspaces | Invitations | Account | User menu
```

### Tenant Topbar

```text
Workspace name + role badge | Search | Create | Workspace switcher | Notifications | User menu
```

### Tenant Sidebar

```text
Home
Operations
Parties
Sales
Purchase
Loans
Inventory
Commodity
Accounting
Reports
Settings
```

### Workspace Settings Sidebar

```text
Business Profile
Team Members
Invitations
Roles and Permissions
Subscription and Billing
Modules
Numbering Series
Accounting Setup
Security and Audit Log
```

Mobile navigation should use offcanvas sidebars but keep workspace identity and switcher visible in the topbar.

## G. Authorization Design

### Core Roles

| Role | Purpose |
| --- | --- |
| Owner | Full workspace control, billing, destructive admin |
| Admin | Operational admin, team management except ownership/billing-destructive actions |
| Accountant | Accounting setup, periods, vouchers, reconciliation, reports |
| Manager | Daily operations across assigned modules |
| Staff | Create/update assigned operational documents |
| Viewer/Auditor | Read-only reports and audit trails |
| Customer/Portal User | Own portal documents only |

### Permission Matrix

| Area | Owner | Admin | Accountant | Manager | Staff | Viewer |
| --- | --- | --- | --- | --- | --- | --- |
| Workspace profile | full | edit | view | view | view | view |
| Team/invitations | full | manage non-owner | no | no | no | optional view |
| Billing | full | optional view | no | no | no | no |
| Accounting setup | full | full | full | view | no | view |
| Period close/lock | full | optional | full | no | no | view |
| Business events | full | full | full | create/approve | create | view |
| Girvi loans | full | full | accounting/report | full | create/payment | view |
| Inventory | full | full | report | full | create/update | view |
| Reports | full | full | full | operational | limited | read |

### Middleware and Redirect Rules

- Public URLConf should not resolve tenant ERP routes.
- Tenant URLConf should not expose public marketing routes except auth callbacks where necessary.
- Global `/app/*` pages should not read tenant business data.
- No login: redirect to login with safe `next`.
- No workspace: redirect to `/app/workspaces/`.
- No membership: redirect to `/app/workspaces/` and clear invalid selection.
- Lacks permission: render 403 or redirect to a safe dashboard with an explicit message.
- Subscription blocked: redirect to workspace billing/settings, not generic public pricing.

## H. Onboarding Design

Replace one-time generic onboarding with a tenant setup checklist visible from the workspace dashboard and settings.

Recommended checklist:

1. Business profile.
2. Fiscal year and accounting period.
3. Chart of accounts and ledger defaults.
4. Opening balances.
5. Customers, suppliers, and parties.
6. Products and item categories.
7. Opening stock and commodity accounts.
8. Loan/rate/numbering series.
9. Invite team.
10. Create first transaction.

Setup blockers should be actionable and close to the blocked action. Missing rates, missing series, missing DEA mappings, and missing commodity accounts should never silently produce zero or incomplete effects.

## I. Implementation Roadmap

### Phase 1: Audit and Documentation Only

- Keep this document as the current IA audit.
- Do not change code in this phase.
- Use it to define small implementation slices.

### Phase 2: Route and Template Standardization

- Split public, global, tenant, and settings route intent.
- Add new base templates without deleting old layouts.
- Keep compatibility aliases for old URLs.

Current checkpoint:

- `django_project.shared_urlpatterns` now exposes named route groups for service, public platform, auth, and global authenticated routes, while preserving the current `shared_urlpatterns` aggregate.
- Intent-specific base aliases now exist: `base_public.html`, `base_auth.html`, `base_global.html`, `base_tenant.html`, `base_workspace_settings.html`, and `base_customer_portal.html`.
- Active public/auth/global/tenant templates have started moving to those aliases without changing view behavior.
- Phase 2.2 route intent cleanup now makes the active URLConf boundary explicit: `django_project.urls` is the active public-schema control-plane URLConf, `django_project.tenant_urls` groups tenant ERP routes in `TENANT_ERP_URLPATTERNS`, and legacy `django_project.public_urls` delegates to the same shared control-plane bundle for compatibility.
- Route ownership tests in `django_project/test_route_intent.py` guard the current settings, shared route aggregate order, absence of tenant ERP prefixes from the public URLConf, tenant ERP prefix grouping, and legacy public URLConf parity.
- Phase 2.3 template layout cleanup now removes remaining clear first-party direct extends of low-level layouts from onboarding, subscriptions, DEA reconciliation/report bases, dynamic preferences, company legacy pages, simple upload pages, and error pages. These pages now use the intent aliases with the correct `mgmt_content` or `workspace_content` block contracts.
- Template layout intent tests in `django_project/test_template_layout_intent.py` now guard that direct `layouts/base.html`, `layouts/management.html`, and `layouts/workspace.html` usage remains limited to infrastructure wrappers, and that alias children use the correct content block names.
- Phase 2.4 workspace settings layout separation moves clear workspace-admin/settings templates to `base_workspace_settings.html`: workspace detail, preferences, team members, sent invitations, invite member, leave workspace, delete workspace, dynamic preferences, and subscription screens. The management shell now exposes no-op `workspace_settings_sidebar` and `mobile_workspace_settings_sidebar` include points for a future settings sidebar without changing current navigation behavior.
- Phase 2.5 shell render smoke tests now render synthetic child templates against `base_public.html`, `base_auth.html`, `base_global.html`, `base_workspace_settings.html`, and `base_tenant.html`, proving the shell aliases and their expected content blocks render before navigation/sidebar visual changes.
- Phase 2.6 route/template inventory documentation now records current URLConf ownership, route families, shell ownership, guard tests, and mixed-boundary risks in `docs/ui/route_template_inventory.md`.
- Phase 2 should be read as complete for the route/template standardization scope only. It did not implement the full target `/w/<workspace_slug>/...` route map; that remains a future alias/redirect rollout after the current `/app/...` and `/workspace/<id>/settings/...` control-plane aliases are stable.
- Phase 3.1 navigation and workspace switcher planning now records topbar/sidebar ownership, workspace switcher behavior, mobile navigation rules, and guard tests in `docs/ui/navigation_workspace_switcher_plan.md`.
- Phase 3.2 workspace switcher reuse now moves the topbar workspace dropdown into the reusable `templates/components/navigation/workspace_switcher.html` partial using a navbar variant, with authenticated global and tenant shell smoke coverage.
- Phase 3.3 desktop settings-sidebar extraction now moves desktop workspace settings, preferences, team, invite, and sent-invitation links into `templates/components/navigation/workspace_settings_sidebar.html`, leaving mobile management links stable for the next slice.
- Phase 3.4 mobile settings-sidebar extraction now routes the mobile management offcanvas workspace settings, preferences, team, invite, and sent-invitation links through the same `templates/components/navigation/workspace_settings_sidebar.html` partial.
- Phase 3.5 account-management sidebar extraction now routes desktop and mobile invitations, owner billing, account settings, and profile links through `templates/components/navigation/account_sidebar.html`.
- Phase 3.6 workspace-manager sidebar extraction now routes desktop and mobile `My Workspaces` and `New Workspace` links through `templates/components/navigation/workspace_manager_sidebar.html`.
- Phase 3.7 management shell cleanup now removes obsolete duplicate-sidebar wording, cleans shell comments to ASCII, and records the final management navigation partial inventory in `docs/ui/navigation_workspace_switcher_plan.md`.
- Phase 3.8 management-shell compatibility review now renders an authenticated owner management shell and asserts expected labels plus route targets survive the sidebar partialization.
- Phase 3.9 management shell visual-polish checklist now documents compatibility constraints, desktop/mobile review criteria, and acceptance checks in `docs/ui/management_shell_visual_polish_checklist.md` before CSS or layout-density changes.
- Phase 3.10 first management-shell visual polish pass now applies restrained neutral control-plane styling, shared management nav-link classes, mobile active-state parity, and cleaner offcanvas styling without changing route names, visible labels, partial ownership, or permissions.
- Phase 3.11 rendered management-shell review now fixes the default base-container constraint by adding a backward-compatible `main_wrapper_class` block to `layouts/base.html` and using a full-width wrapper in `layouts/management.html`. Local Chrome headless screenshot attempts did not produce image files in this environment.
- Phase 3.12 reproducible management-shell visual smoke coverage now renders an authenticated owner management shell in `django_project/test_management_shell_visual_smoke.py` and guards the full-width wrapper, desktop/mobile navigation classes, active states, and control-plane route safety without adding browser dependencies.
- Phase 3.13 management-shell CSS extraction now moves shell styles to `static/css/management.css`, loads that stylesheet from `layouts/management.html`, and keeps visual behavior unchanged while avoiding further inline CSS growth.
- Phase 3.14 static asset readiness now verifies `css/management.css` through `findstatic`, a successful `collectstatic --dry-run --noinput` check, and visual smoke coverage for Django staticfiles discovery.
- Phase 3.15 final navigation/management-shell review now records compatibility findings, verification commands, and the phase-level commit set in `docs/ui/phase3_navigation_management_shell_review.md`.
- Phase 4.1 invitation/team flow intent audit now documents current incoming invitation, sent workspace invitation, and team-member route ownership in `docs/ui/invitation_team_flow_cleanup_plan.md`, with route/template guard tests in `django_project/test_invitation_team_flow_intent.py`.
- Phase 4.2 route-intent cleanup now groups `apps.orgs.urls` by workspace manager, account invitation, workspace invitation, team member, and account profile surfaces while preserving the same effective URL order.
- Phase 4.3 copy and heading clarification now distinguishes received invitations from sent workspace invitations, aligns team-invite wording, and guards known invitation/team mojibake cleanup.
- Phase 4.4 workspace-scoped redirect cleanup now carries explicit workspace context through invite success, sent-invitation list, and revoke return paths while keeping old URLs working.
- Phase 4.5 accept/decline characterization now documents that the direct django-invitations accept path is signal-bridged for membership creation, while the custom orgs POST accept path owns active workspace selection, orgs audit, and workspace-dashboard redirect behavior.
- Phase 4.6 authorization coverage now guards invite permissions, role-grant policy, revoke denial, team remove/change-role gates, sole-owner self-leave, and selected-workspace sent-invitation fallback.
- Phase 4.7 direct invitation accept adapter now keeps the existing accept path/name while sending authenticated matching users through the orgs control-plane accept flow and preserving django-invitations fallback for unauthenticated users.
- Phase 4 final review now records compatibility, authorization coverage, verification, and deferred follow-ups in `docs/ui/phase4_invitation_team_flow_review.md`.
- Canonical route aliases first slice now adds additive `/app/...` and `/workspace/<id>/settings/...` aliases through `django_project.shared_urlpatterns.CANONICAL_CONTROL_PLANE_URLPATTERNS` while preserving existing `/orgs/...` route names and paths.
- Low-risk management navigation now targets canonical aliases for workspace manager and global received-invitation links: `app_workspaces`, `app_workspace_create`, and `app_invitations`.
- Workspace settings navigation now targets canonical aliases for settings home and preferences: `workspace_settings_home` and `workspace_settings_preferences`.
- Workspace-scoped team/invitation behavior is now characterized before link adoption: explicit workspace ids, invite success, sent-invitation list, and revoke returns are covered in `apps/orgs/tests.py`.
- Workspace settings navigation now targets canonical aliases for team, invite-member, and sent-invitation links: `workspace_settings_team`, `workspace_settings_invite`, and `workspace_settings_invitations`.
- Sent-invitation return targets now use the canonical settings URL: invite-success back links and invitation revoke returns both target `workspace_settings_invitations`.
- Successful invite POSTs now redirect directly to `workspace_settings_invitations`; the legacy `team_invite_success` route/template remains available for old links.
- Canonical route alias phase review now records compatibility findings, residual risks, verification, and the recommended commit set in `docs/ui/canonical_route_aliases_phase_review.md`.
- Phase 5.1 authorization inventory now maps public, global authenticated, workspace settings, tenant ERP, and future portal surfaces in `docs/ui/authorization_cleanup_inventory.md`, with guard tests in `django_project/test_authorization_surface_intent.py`.
- Phase 5.2 middleware canonical settings path extraction now lets `SecureWorkspaceMiddleware` recognize `/workspace/<id>/settings/...` aliases as workspace-id-bearing paths.
- Phase 5.3 middleware tenant-prefix coverage now keeps every current tenant ERP prefix from `django_project.tenant_urls.TENANT_ERP_URLPATTERNS` behind workspace-required middleware handling.
- Phase 5.4 Party access helper scaffolding now provides reusable Party workspace, permission, action, decorator, and CBV mixin helpers in `apps.tenant_apps.party.access`.
- Phase 5.5 Party read/export authorization now routes Party list/detail through the Party view action guard and Party export through the Party export action permission.
- Phase 5.6 Party simple mutation authorization now routes Party create/customer-convert through the Party create action guard and Party update through the Party edit action guard.
- Phase 5.7 Party profile mutation authorization now routes profile-photo, contact-method, and address mutations through the Party edit action guard.
- Phase 5.8 Party KYC/relationship mutation authorization now routes identifier, document, and relationship mutations through the Party edit action guard.
- Phase 5.9 final Party mutation authorization now routes role add/end and duplicate merge through the Party edit action guard.
- Phase 5.10 Product catalog authorization now adds Product workspace/permission/action helper scaffolding and routes product, product type, generated product/variant, and product variant catalog paths through Product action guards backed by existing generic data permissions.
- Phase 5.11 Product stock authorization now routes stock list/detail/search, transaction/statement lists, split/merge/delete, stock-in/stock-out, physical audit, opening balance import, and import template paths through Product action guards backed by existing generic data permissions.
- Phase 5.12 Product pricing/image/attribute authorization now routes pricing tiers, product prices, price overrides, image views, and attribute views through Product action guards.
- Phase 5.13 Rates/Notify authorization now adds Rates and Notify shared access helpers and routes rate, rate-source, legacy Notify, and Notify v2 user-facing routes through action guards while keeping the external Notify v2 WhatsApp webhook public.
- Phase 5.14 authorization closeout now records that SaaS IA Phase 5 is complete for current Party, Product, Rates, Notify, and utility data-tool route groups, with DEA/Girvi remaining in their separate domain-specific permission tracks.
- Phase 6.1 onboarding inventory now documents the current user-level onboarding wizard, duplicate workspace creation paths, target workspace setup checklist, compatibility constraints, and safe implementation slices in `docs/ui/onboarding_phase6_plan.md`.
- Phase 6.2 adds `apps.onboarding.services.setup_checklist`, a read-only workspace setup checklist service with injectable metrics, best-effort tenant count collection, and focused tests. Existing `/onboarding/...` URLs, redirects, and dashboard templates remain unchanged.
- Phase 6.3 surfaces the read-only setup checklist on the workspace dashboard through `apps.orgs.services.dashboard_selectors.get_workspace_dashboard_context()` and `templates/company/workspace_dashboard.html`. It is advisory only: no onboarding redirects, ERP access gates, or setup-state mutations changed.
- Phase 6.4 adds a workspace settings setup page at canonical `workspace_settings_setup` (`/workspace/<id>/settings/setup/`) plus compatibility `workspace_setup` (`/orgs/workspace/<id>/setup/`). The page reuses the read-only checklist service and is linked from the workspace settings sidebar and dashboard setup card.
- Phase 6.5 routes completed onboarding users to `workspace_settings_setup` when a selected non-public workspace is available, while preserving `/onboarding/start/`, `/onboarding/complete/`, and `/onboarding/skip/` as compatibility entrypoints with `workspace_list` fallback.
- Phase 6.6 moves onboarding workspace row/domain/Owner membership creation behind `apps.orgs.services.control_plane.create_onboarding_workspace_from_form()`, while keeping existing onboarding tenant provisioning, seed callbacks, progress updates, choices, audit logging, messages, and redirects in place.
- Phase 6.7 moves onboarding team invitation creation/sending behind `apps.orgs.services.control_plane.send_onboarding_team_invitations()`, while preserving optional skip behavior, progress updates, messages, audit summary, and partial-failure logging.
- Phase 6.8 adds user-specific setup completion/dismiss state through `WorkspaceSetupState`, setup-state service helpers, dashboard card hide/show behavior, and canonical/legacy setup state POST routes without adding ERP access gates.
- Phase 6.9 review is documented in `docs/ui/phase6_onboarding_review.md`, including compatibility findings, verification commands, rollout notes, and the recommended phase-level commit.
- Phase 7.1 starts modern fintech UI polish with documentation and guard tests only. `docs/ui/phase7_modern_fintech_ui_polish_plan.md` defines the product-area visual targets, management/workspace setup first slice, non-negotiables, safe implementation order, and acceptance criteria. `django_project/test_phase7_ui_polish_intent.py` guards that the setup surfaces stay advisory, settings-shell owned, static-stylesheet backed, and canonical-route targeted before CSS/template polish begins.
- Phase 7.2 adds a small management/setup visual vocabulary to `static/css/management.css` and applies it only to `templates/company/workspace_setup.html`, replacing generic setup cards with setup-specific hero, progress, task, action, and status classes while preserving all routes, forms, links, setup state actions, and advisory behavior.
- Phase 7.3 applies the same setup visual vocabulary to the workspace dashboard setup card in `templates/company/workspace_dashboard.html`, preserving dashboard visibility, canonical setup link, dismiss POST behavior, checklist action URLs, and onboarding behavior.
- Preferences visibility checkpoint: workspace Preferences is already available at the canonical `workspace_settings_preferences` alias, and the settings sidebar now exposes it to `Owner`, `Admin`, and platform `Superuser` users instead of hiding it from admins.
- Phase 7.4 extracts repeated setup checklist task/status/action markup into `templates/components/setup/setup_checklist_task.html`, reused by both `workspace_setup.html` and `workspace_dashboard.html` with page-specific heading/id context and unchanged action URLs.
- Phase 7.5 polishes the global workspace selector/list surface in `templates/company/workspace_home.html` into a clearer workspace manager, with summary tiles, explicit active-workspace state, canonical create/invitations/settings links, and preserved `workspace_select` switching plus invitation POST behavior.
- Phase 7.6 records the public/auth route and template inventory in `docs/ui/phase7_public_auth_polish_plan.md` with guard tests in `django_project/test_phase7_public_auth_intent.py`. It deliberately does not implement `/pricing/`, short auth aliases, the `/invitations/accept/<key>` target alias, or missing public templates.
- Phase 7.7 applies the first public/auth visual polish pass: `static/css/public.css` now owns shared public/auth styling, `base_public.html` and `base_auth.html` load it, the landing page no longer uses inline CSS or a remote placeholder image, and login/signup/password reset use a consistent auth layout while preserving allauth/social-auth behavior.
- Phase 7.8 render-reviews the public/auth pages and fixes the no-`SocialApp` Google OAuth crash by exposing `GOOGLE_OAUTH_ENABLED` from `django_project.context_processors.google_oauth_context` and conditionally rendering Google auth CTAs.
- Phase 7.9 applies the first tenant ERP dashboard/navigation density pass: `static/css/workspace.css` owns tenant shell/sidebar/dashboard styles, `base_tenant.html` loads it, tenant layout/sidebar inline style blocks are removed, and the workspace dashboard uses denser static classes while preserving route names and workflow behavior.
- Phase 7.10 closes the first-pass UI polish track in `docs/ui/phase7_modern_fintech_ui_polish_review.md`. The review explicitly records that the current polish is basic infrastructure/surface cleanup, not the final high-fidelity fintech redesign. Deeper visual design, the full `/w/<workspace_slug>/...` target route map, `/pricing/`, short auth aliases, direct invitation accept aliases, missing public templates, and broader tenant ERP module polish remain separate future work.

Next recommended SaaS IA slice:

- Commit the Phase 7 set as one phase-level commit, then start Phase 8 regression consolidation for the SaaS IA plan. Keep pricing, short auth aliases, missing public templates, and the full `/w/<workspace_slug>/...` target route-map rollout as a later alias/redirect phase.

### Phase 3: Navigation and Workspace Switcher

- Create one canonical workspace switcher.
- Make workspace identity visible on every tenant screen.
- Separate tenant sidebar from settings sidebar.

### Phase 4: Invitation and Team Flow Cleanup

- Unify invitation accept/list/revoke/resend.
- Keep role-grant policy in services.
- Make accept-invite safe for logged-out and new users.
- Start from the compatibility map in `docs/ui/invitation_team_flow_cleanup_plan.md`: incoming invitations are global/account surfaces, while sent invitations and team members are workspace settings surfaces.

### Phase 5: Authorization Cleanup

- Add explicit permissions for Party, Product, and tenant utility endpoints. Skip broad Contact cleanup in favor of Party cutover unless a specific compatibility route is unsafe.
- Keep middleware as isolation defense, not as the only authorization layer.

### Phase 6: Onboarding

- Convert onboarding into a workspace setup checklist.
- Add accounting, inventory, commodity, rate, and numbering readiness checks.

### Phase 7: Modern Fintech UI Polish

- Polish public pages as a SaaS fintech funnel.
- Make global app feel like a workspace manager.
- Make tenant ERP denser, clearer, and operational.
- Current status: first-pass infrastructure and surface cleanup is complete; deeper high-fidelity product-design polish remains future work.

### Phase 8: Tests and Regression Checks

- Add route/schema/permission tests before removing old aliases.
- Add visual and HTMX regression coverage for high-value flows where practical.
- Current checkpoint: Phase 8.1 creates `docs/ui/phase8_regression_consolidation_plan.md`, mapping the existing guard inventory, route/template/auth/workspace/invitation/authorization/render regression buckets, and the deferred alias/design work that must wait until the guard layer is stronger.
- Phase 8.2 strengthens route-boundary regression tests for current canonical aliases, legacy compatibility URLs, representative tenant ERP paths, public URLConf tenant exclusion, and intentionally absent future aliases including `/pricing/`, short auth aliases, `/invitations/accept/<key>`, and `/w/<workspace_slug>/...`.
- Phase 8.3 strengthens template/shell regression tests for base-template ownership, static stylesheet contracts, no inline style reintroduction in extracted shells, and known root `layouts/base.html` / `main_nav.html` inline style debt.
- Phase 8.4 strengthens public/auth render and compatibility regression tests for renderable public pages, allauth compatibility paths, Google OAuth CTA gating, django-invitations accept compatibility, invalid invite fail-closed behavior, and documented missing public templates.
- Phase 8.5 strengthens workspace switching, setup, and onboarding regression tests for canonical/legacy setup routes, canonical setup-state form targets, membership-safe workspace switching, safe `next` handling, audit logging, and existing onboarding runtime regression files.
- Phase 8.6 strengthens invitation/team regression tests for existing runtime guard coverage, direct accept adapter behavior, authenticated email mismatch fail-closed behavior, sent-invitation workspace context, revoke return targets, role/member mutation boundaries, control-plane policy checks, and invitation/team audit actions.
- Phase 8.7 strengthens authorization regression tests for exact tenant ERP prefix coverage, middleware workspace-required coverage, Party/Product/Rates/Notify/utility data-tool guards, Contact's documented legacy gap, the intentionally public Notify v2 webhook, and DEA/Girvi as separate domain-specific permission tracks.
- Phase 8.8 closes the regression consolidation phase in `docs/ui/phase8_regression_consolidation_review.md`, recording completed guard coverage, deferred scope, compatibility findings, verification commands, expected test log noise, and the tests/documentation-only commit boundary.
- Phase 9.1 starts the follow-on public/auth alias and template rollout in `docs/ui/public_auth_alias_template_rollout_plan.md` with guard tests only. Runtime behavior is unchanged: `/pricing/`, short auth aliases, `/invitations/accept/<key>`, missing public templates, and `/w/<workspace_slug>/...` remain deferred. The next safe slice is Phase 9.2: add `/pricing/` and the missing public templates before auth or invitation aliases.
- Phase 9.2 adds `/pricing/`, `PricingPageView`, and public templates for pricing, tenant/workspace explanation, cancellation/refund, contact, help, and FAQ pages. Short auth aliases, `/invitations/accept/<key>`, and `/w/<workspace_slug>/...` remain deferred. The next safe slice is Phase 9.3: add short auth aliases while preserving `/accounts/...` compatibility paths.
- Phase 9.3 adds short auth redirect aliases for `/login/`, `/signup/`, and `/password/reset/`, preserving query strings and the existing allauth `/accounts/...` implementation paths. `/invitations/accept/<key>` and `/w/<workspace_slug>/...` remain deferred. The next safe slice is Phase 9.4: add the public invitation accept alias to the orgs-owned adapter.
- Phase 9.4 adds `/invitations/accept/<key>` as `public_invitation_accept`, pointing to the orgs-owned `team_accept_invitation` adapter while preserving the existing django-invitations `/invitations/accept-invite/<key>` compatibility path. The next safe slice is Phase 9.5: public/auth alias rollout review and commit preparation before the separate `/w/<workspace_slug>/...` route-map phase.
- Phase 9.5 closes the public/auth alias-template rollout in `docs/ui/public_auth_alias_template_rollout_review.md`, recording completed pricing/templates/auth/invitation aliases, compatibility findings, verification commands, and the commit boundary. The next safe phase is separate `/w/<workspace_slug>/...` route-map planning before slug routes are added.
- Phase 10.1 starts the separate workspace slug route-map phase in `docs/ui/workspace_slug_route_map_plan.md` with guard tests only. Runtime behavior is unchanged and `/w/<workspace_slug>/...` routes remain intentionally absent until Phase 10.2 decides whether the slug source is current `Company.schema_name` or a dedicated `Company.slug`.
- Phase 10.2 chooses current `Company.schema_name` as the initial compatibility slug for `/w/<workspace_slug>/...`, avoiding a shared-schema migration during route-map rollout. A dedicated immutable `Company.slug` remains deferred until workspace rename and branded URL requirements are clear.
- Phase 10.3 adds middleware slug extraction for future `/w/<workspace_slug>/...` paths through `SecureWorkspaceMiddleware`, resolving by `Company.schema_name` and preserving public-schema exclusion. No `/w/...` URL patterns are live yet; the next safe slice is minimal dashboard/settings aliases.
- Phase 10.4 adds the first live `/w/<workspace_slug>/...` aliases for dashboard and workspace settings, implemented as redirects to existing id-based views. Tenant ERP section aliases remain intentionally absent until Phase 10.5.
- Phase 10.5 adds live `/w/<workspace_slug>/parties/`, `/loans/`, `/inventory/`, and `/accounting/` aliases as redirects to current Party, Girvi, Product, and DEA entrypoints. Contact remains skipped in favor of Party; operations, sales, purchase, commodity, and reports stay deferred until their targets are selected.
- Phase 10.6 moves selected navigation links to slug aliases where workspace schema context is reliable: tenant sidebar dashboard/Parties/Girvi/Product and workspace settings home/preferences/team/sent-invitations. Deep module, reports, setup, invite, billing, rates, notifications, data tools, business events, and commodity links remain on existing routes.
- Phase 10.7 closes the workspace slug route-map phase in `docs/ui/workspace_slug_route_map_review.md`. The first live `/w/<workspace_slug>/...` layer is implemented and reviewed; remaining target route-map items are deferred until their product targets are selected.
- Phase 11.1 selects targets for the remaining deferred `/w/<workspace_slug>/...` routes in `docs/ui/workspace_slug_deferred_targets_plan.md`. Sales and purchase stay routed through DEA business events rather than removed runtime apps. Modules and security are intentionally not given live redirect targets until real workspace-owned settings screens exist. Phase 11.2 should implement only the safe redirect aliases before interim role/numbering aliases or new modules/security screens.
- Phase 11.2 implements the safe deferred `/w/<workspace_slug>/...` redirect aliases for operations, sales, purchase, commodity, reports, settings/profile, settings/billing, and settings/accounting. Contact remains skipped in favor of Party. Settings roles, modules, numbering, and security remain absent until interim redirect or real-screen decisions are made.
- Phase 11.3 implements interim settings aliases for `/w/<workspace_slug>/settings/roles/` and `/w/<workspace_slug>/settings/numbering/`, redirecting to workspace team management and Girvi series respectively. Settings modules and security remain absent until real workspace-owned screens exist.
- Phase 11.4 implements real workspace-owned settings screens for modules and security/audit, then exposes `/w/<workspace_slug>/settings/modules/` and `/w/<workspace_slug>/settings/security/` as redirects to those pages. Workspace security reads `AuditLog` activity and does not reuse account-level security pages.
- Phase 11 final review in `docs/ui/workspace_slug_phase11_review.md` closes the workspace slug route-map rollout for tenant ERP and workspace settings. The remaining target route-map gap is the separate customer/member portal.
- Phase 12.1 starts customer/member portal IA in `docs/ui/customer_portal_phase12_plan.md`. `/portal/...` routes remain intentionally absent until tenant Party identity binding, portal access helpers, read-only selectors, and a real customer portal shell are designed. Phase 12.2 should choose the portal identity model.
- Phase 12.2 chooses a Party-backed portal identity model in `docs/ui/customer_portal_identity_phase12.md`, with a future explicit `PartyPortalAccess`-style tenant binding and a fail-closed `resolve_portal_identity()` helper scaffold. `/portal/...` routes remain absent. Phase 12.3 should define read-only selector contracts around `PortalIdentity`.
- Phase 12.3 defines fail-closed customer/member portal selector contracts in `docs/ui/customer_portal_selector_contracts_phase12.md`. `apps.tenant_apps.party.portal_selectors` validates `PortalIdentity` before dashboard, loan, invoice, payment, document, or statement reads, then raises `PortalSelectorNotImplemented` until real PartyPortalAccess-backed tenant data sources are wired. `/portal/...` routes remain absent. Phase 12.4 should upgrade the portal shell/navigation without exposing live routes.
- Phase 12.4 upgrades the customer/member portal shell in `docs/ui/customer_portal_shell_phase12.md`. `base_customer_portal.html` now has portal-only navigation and a `portal_content` block while keeping `/portal/...` routes absent.
- Phase 12 closes in `docs/ui/customer_portal_phase12_review.md`. Live `/portal/...` routes remain intentionally deferred until `PartyPortalAccess` or an equivalent tenant Party access grant exists with implemented selectors and cross-party denial tests.
- Phase 13.1 corrects the tenant route-map interpretation in `docs/ui/tenant_route_canonicalization_phase13_plan.md`: `/w/<workspace_slug>/...` route availability exists, but legacy tenant roots such as `/dea/`, `/party/`, `/girvi/`, and `/product/` remain active and many slug entrypoints redirect into them. Full canonical replacement is a separate module-by-module migration. Next: Phase 13.2 visible tenant sidebar/dashboard entry links.
- Phase 13.2 moves remaining visible tenant sidebar/dashboard top-level DEA entry links to existing slug aliases: operations, reports, commodity, and accounting dashboard. Legacy tenant roots remain active.
- Phase 13.3 has started direct-render slug entry wrappers. `/w/<workspace_slug>/parties/` now renders the existing Party list view in place and keeps Party authorization as the source of truth. `/w/<workspace_slug>/inventory/` now renders the existing Product home view in place while detailed Product routes keep their existing action guards. `/w/<workspace_slug>/loans/` now renders the existing Girvi dashboard in place while keeping the Girvi workspace access guard. Accounting and DEA-backed entries still redirect until each target view is verified.

## J. Files to Change Later

Likely future refactor targets:

- `django_project/settings/base.py`
- `django_project/urls.py`
- `django_project/tenant_urls.py`
- `django_project/shared_urlpatterns.py`
- `django_project/public_urls.py`
- `django_project/middleware.py`
- `apps/orgs/middleware_v2.py`
- `pages/urls.py`
- `pages/views.py`
- `apps/orgs/urls.py`
- `apps/orgs/views.py`
- `accounts/urls.py`
- `accounts/views.py`
- `apps/onboarding/views.py`
- `apps/subscriptions/views.py`
- `apps/tenant_apps/girvi/urls.py`
- `apps/tenant_apps/dea/urls.py`
- `apps/tenant_apps/party/views.py`
- `apps/tenant_apps/product/views/`
- `apps/tenant_apps/contact/views/`
- `templates/layouts/base.html`
- `templates/layouts/workspace.html`
- `templates/layouts/management.html`
- `templates/components/navigation/main_nav.html`
- `templates/components/navigation/sidebar.html`
- `templates/components/navigation/workspace_switcher.html`

## K. Tests Needed

Recommended test coverage:

- Public routes resolve only public pages/auth/pricing.
- Public URLConf does not expose tenant ERP routes.
- Tenant URLConf exposes ERP routes only in tenant context.
- `/app/*` global routes do not read tenant business data.
- Workspace switch validates membership and safe `next`.
- Selected workspace does not grant access without membership.
- Invitation accept works for logged-out, new-user, and existing-user cases.
- Invitation expired, revoked, duplicate, and already-accepted cases.
- Owner/Admin/Member/Accountant permission boundaries.
- Product, Party, and Contact mutation views deny unauthorized members.
- Billing pages require workspace owner.
- Subscription payment updates a company subscription, not a user subscription.
- Tenant business document detail pages link accounting, inventory, commodity, and audit impact.
- Onboarding checklist completion and blocking states.
- Customer portal exposes only the current portal user's own loans, invoices, payments, documents, and statements.

## Open Uncertainties

- Customer/member portal ownership is not yet clear: it may be a tenant app, a shared app with tenant-scoped selectors, or a separate public-facing tenant-domain surface.
- The final canonical route shape can be domain-based, path-based, or hybrid. Current middleware supports domain resolution and path/profile fallback; the route redesign should decide which behavior is authoritative.
- Existing bookmarks and legacy aliases need an inventory before route removals.
- Subscription/payment code needs focused characterization before fixes because current model and view assumptions conflict.
