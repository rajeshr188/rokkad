---
status: active
owner: project
updated: 2026-06-28
tags: [ui, routes, templates, saas, phase-2]
related: [saas_information_architecture_audit.md, screen_designs.md, htmx_interactions.md, ../AGENT_MEMORY.md, ../STATUS.md]
---

# Route and Template Inventory

This document is the Phase 2.6 route/template ownership checkpoint for the SaaS information architecture work. It records the current compatibility shape after route grouping, shell aliases, workspace-settings separation, and shell render smoke tests.

No behavior changes are made by this document. Route moves, sidebar redesign, and workspace-switcher changes belong to later phases.

## Active URLConfs

| URLConf | Current role | Notes |
| --- | --- | --- |
| `django_project.urls` | Active public-schema URLConf | Loaded by `PUBLIC_SCHEMA_URLCONF`; includes platform admin plus `shared_urlpatterns`. |
| `django_project.tenant_urls` | Active tenant/workspace URLConf | Loaded by `ROOT_URLCONF`; includes tenant ERP routes plus `shared_urlpatterns` for compatibility. |
| `django_project.shared_urlpatterns` | Compatibility control-plane bundle | Contains service, public, auth/invitation, onboarding, orgs, profile, and subscription routes. |
| `django_project.public_urls` | Legacy parity public URLConf | Kept equivalent to the active public control-plane bundle for local overrides. |

## Route Ownership Matrix

| Area | Current route families | Current URL owner | Current template shell | Boundary status |
| --- | --- | --- | --- | --- |
| Service/cross-plane | `/i18n/`, `/dynamic_preferences/`, `/select2/` | `SERVICE_URLPATTERNS` | Mixed, mostly settings/global | Shared intentionally for now. |
| Public/platform | `/`, `/about/`, `/privacy-policy/`, `/terms-and-conditions/`, `/contact/`, `/help/`, `/faq/` | `pages.urls` through `PUBLIC_PLATFORM_URLPATTERNS` | `base_public.html` | Public shell named; route bundle still shared into tenant URLConf for compatibility. |
| Auth/invitations | `/accounts/*`, `/invitations/*` | `AUTH_URLPATTERNS` and django-invitations | `base_auth.html` for local account templates; package templates may use wrappers | Shared intentionally because users can arrive from public or tenant domains. |
| Global workspace manager | `/dashboard/`, `/workspace/`, `/orgs/workspace/`, `/orgs/workspace/create/`, `/orgs/workspace/list/`, `/profile/*`, `/onboarding/*` | `pages.urls`, `apps.orgs.urls`, `accounts.urls`, `apps.onboarding.urls` | `base_global.html` | Named shell exists; global routes still included on tenant URLConf for compatibility. |
| Workspace settings/admin | `/orgs/workspace/<id>/`, `/orgs/workspace/<id>/edit/`, `/orgs/workspace/<id>/delete/`, `/orgs/workspace/<id>/preferences/`, `/orgs/workspace/<id>/team/*`, `/orgs/team/invitations/list/`, `/subscriptions/*`, `/dynamic_preferences/*` | `apps.orgs.urls`, `apps.subscriptions.urls`, dynamic preferences | `base_workspace_settings.html` for current settings/admin screens | Shell separated; URL shape still control-plane compatibility style, not final `/w/<workspace>/settings/*`. |
| Tenant ERP | `/party/`, `/contact/`, `/data-tools/`, `/girvi/`, `/rates/`, `/product/`, `/notify/`, `/notify-v2/`, `/dea/` | `TENANT_ERP_URLPATTERNS` in `django_project.tenant_urls` | `base_tenant.html` | Tenant prefixes are grouped and excluded from public URLConf by tests. |
| Customer/member portal | None | None | `base_customer_portal.html` exists only as a future shell alias | Not implemented. |

## Template Shell Ownership

| Shell | Current purpose | Current examples | Guard coverage |
| --- | --- | --- | --- |
| `base_public.html` | Public/platform and public error pages | `pages/home.html`, legal pages, `404.html`, `500.html` | `test_shell_render_smoke.py`; low-level extend guard. |
| `base_auth.html` | Login/signup/password reset/logout | `templates/account/*` auth templates | `test_shell_render_smoke.py`; alias block guard. |
| `base_global.html` | Global authenticated workspace/account manager | workspace lists, onboarding, profile/account pages | `test_shell_render_smoke.py`; alias block guard. |
| `base_workspace_settings.html` | Workspace-scoped admin/settings/billing shell | workspace detail, preferences, team, invitations, subscriptions, dynamic preferences | `test_template_layout_intent.py`; `test_shell_render_smoke.py`. |
| `base_tenant.html` | Tenant ERP/data-plane shell | DEA, Girvi, Party, Product, Rates, Notify, Data Tools | `test_template_layout_intent.py`; `test_shell_render_smoke.py`. |
| `base_customer_portal.html` | Future customer/member portal shell | No active runtime screens | Shell alias exists; no route ownership yet. |

## Known Mixed Boundaries To Defer

| Boundary | Current issue | Defer to |
| --- | --- | --- |
| `shared_urlpatterns` in tenant URLConf | Public/global/auth routes remain reachable in tenant context. | Phase 3 route/navigation design, then later route alias/redirect work. |
| `/dashboard/` and `/workspace/` | Smart redirects blur global dashboard vs selected workspace dashboard. | Phase 3 workspace switcher and global dashboard flow. |
| `pages.urls` imports orgs workspace views | Global workspace routes are partly exposed from `pages`. | Future global app/URL namespace cleanup. |
| Workspace settings URL shape | Settings pages live under `/orgs/*` and `/subscriptions/*`, not `/w/<workspace>/settings/*`. | Later compatibility aliases after navigation/workspace identity is stable. |
| Billing ownership | Subscription routes are company-backed but not fully nested under workspace settings routes. | Billing characterization/fix slice before payment-flow changes. |
| Dynamic preferences | `/dynamic_preferences/*` is cross-plane service-style but renders as workspace settings. | Settings IA and permission hardening. |
| Customer portal | Shell exists but no route, app, membership model, or ownership policy is defined. | Dedicated portal design phase. |

## Current Guard Rails

| Test module | Purpose |
| --- | --- |
| `django_project/test_route_intent.py` | Guards active public/tenant URLConf settings, shared route aggregate order, public URLConf tenant-prefix exclusion, tenant ERP prefix grouping, and legacy public URLConf parity. |
| `django_project/test_template_layout_intent.py` | Guards low-level layout usage, alias block contracts, workspace-settings template ownership, and settings-sidebar include points. |
| `django_project/test_shell_render_smoke.py` | Renders synthetic children through all active shell aliases before visible navigation/sidebar refactors. |

## Next Recommended Step

Start Phase 3 with navigation and workspace switcher planning before changing visible navigation:

1. Define the exact global vs tenant topbar responsibilities.
2. Decide whether the canonical workspace switcher redirects to global workspace list, tenant dashboard, or safe `next`.
3. Replace duplicated workspace switcher links with a single partial.
4. Keep current route aliases until switcher and shell render coverage are stable.
