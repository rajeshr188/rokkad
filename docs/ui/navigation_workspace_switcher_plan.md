---
status: active
owner: project
updated: 2026-06-28
tags: [ui, navigation, workspace-switcher, saas, phase-3]
related: [saas_information_architecture_audit.md, route_template_inventory.md, screen_designs.md, htmx_interactions.md, ../AGENT_MEMORY.md, ../STATUS.md]
---

# Navigation and Workspace Switcher Plan

This is the Phase 3.1 planning checkpoint for SaaS navigation standardization. It is intentionally compatibility-first: existing URLs, route names, redirects, sidebar rendering, and shell inheritance stay unchanged until the workspace identity and navigation ownership contract is stable.

## Current Runtime Sources

| Surface | Current source | Notes |
| --- | --- | --- |
| Global/top navbar | `templates/components/navigation/main_nav.html` | Includes user menu, language selector, and an inline workspace dropdown. |
| Tenant sidebar | `templates/components/navigation/sidebar.html` | Current source of truth for live tenant ERP navigation, per accepted sidebar ADRs. |
| Workspace switcher partial | `templates/components/navigation/workspace_switcher.html` | Existing reusable dropdown, not yet the only switcher implementation. |
| Workspace settings sidebar include point | `templates/components/navigation/workspace_settings_sidebar.html` | Placeholder include point added in Phase 2.4. |
| Global and settings shell | `templates/layouts/management.html` | Contains account/workspace management sidebar and duplicated mobile links. |
| Tenant shell | `templates/layouts/workspace.html` | Contains tenant identity banner, sidebar, and mobile offcanvas sidebar. |
| Future dynamic nav config | `django_project/navigation.py` | Retained for a later deliberate migration; not the live source of truth. |

## Phase 3 Navigation Ownership

| Product area | Topbar responsibility | Sidebar responsibility | Workspace identity rule |
| --- | --- | --- | --- |
| Public/platform | Brand, public links, login/signup | None | No selected workspace display. |
| Global authenticated | Account menu, workspace switcher, pending-invite affordance | Workspace manager/account navigation only | Selected workspace may be shown as a shortcut, but the page remains global/control-plane. |
| Tenant ERP | Current workspace, switch workspace, user/account menu | ERP modules and accounting-first workflows | Workspace name and role must be visible in the topbar or tenant banner. |
| Workspace settings | Current workspace, enter ERP shortcut, user/account menu | Settings/admin sections only | Settings must look workspace-scoped but not like an ERP module. |
| Customer portal | Portal account menu, business/customer relationship context | Customer/member portal sections only | Do not expose internal workspace/admin concepts. |

## Workspace Switcher Contract

The workspace switcher should become a single reusable partial used by global, tenant, and settings shells.

Required behavior:

1. Show the current selected workspace when present.
2. Show a clear empty state when no workspace is selected.
3. List only workspaces the user belongs to.
4. Switch via the existing `workspace_select` route for compatibility.
5. Link to the global workspace manager via `workspace_selector`.
6. Link to workspace creation via `workspace_create`.
7. Preserve `?next=` behavior when entering a workspace-specific destination.
8. Avoid tenant ERP links inside global-only switcher menus.
9. Avoid workspace settings/admin links inside the pure switcher menu.

Deferred behavior:

- Canonical redirect policy after switching still needs characterization of current `workspace_select` behavior.
- Tenant-domain switching should keep current compatibility routes until route aliases are explicitly tested.
- HTMX switcher refresh can be added after the server-side partial contract is stable.

## Sidebar Contract

For now, the accepted ADR remains in force: the active tenant sidebar source of truth is `templates/components/navigation/sidebar.html`.

Do not partially migrate sidebar items to `django_project/navigation.py`. A future dynamic navigation migration should happen only after route-name and permission alignment tests are added.

Target tenant sidebar grouping:

| Group | Intended entries |
| --- | --- |
| Home | Workspace dashboard and operational queues. |
| Activities | Business event entrypoints, recent work, tasks. |
| Parties | Parties first, legacy contacts only as compatibility. |
| Operations | Loans, sales, purchases, receipts, payments, commodity workflows. |
| Inventory | Product/catalog, stock, custody/location views. |
| Accounting | Business events, financial reports, commodity reports, accountant tools for accountant roles. |
| Reports | Operational, accounting, inventory, commodity, and audit reports. |
| Settings | Shortcut to workspace settings/admin shell, not full settings navigation inside ERP sidebar. |

## Settings Sidebar Contract

Workspace settings should gradually move into `components/navigation/workspace_settings_sidebar.html`, using the existing include points in `layouts/management.html`.

Target settings groups:

| Group | Intended entries |
| --- | --- |
| Business | Profile, preferences, numbering series, modules. |
| Team | Members, invitations, roles and permissions. |
| Billing | Subscription, plan, invoices. |
| Accounting setup | Ledgers, opening balances, fiscal periods, posting preferences. |
| Security | Audit log, access policy, session/security settings. |

Keep the current inline management sidebar links until the partial can render both desktop and mobile settings navigation without duplicating route logic.

## Mobile Navigation Contract

1. Mobile navigation should use the same partials as desktop wherever possible.
2. Tenant mobile offcanvas should expose the tenant ERP sidebar, not the global management sidebar.
3. Settings mobile offcanvas should expose settings/admin navigation, not tenant ERP modules.
4. Workspace switching must be reachable from mobile topbar before users open a sidebar.

## Guard Rails

Current guard tests that must stay green:

- `django_project/test_route_intent.py`
- `django_project/test_template_layout_intent.py`
- `django_project/test_shell_render_smoke.py`

Phase 3 adds `django_project/test_navigation_intent.py` to protect the planning contract:

- the workspace switcher partial remains control-plane safe;
- the tenant sidebar remains the live template source of truth;
- management and tenant shells keep their separate navigation include points.

## Next Recommended Step

Proceed to Phase 3.2: replace the inline workspace dropdown in `components/navigation/main_nav.html` with the existing `components/navigation/workspace_switcher.html` partial, keeping labels and route targets compatible. Add a render smoke test for authenticated global and tenant shells that proves the switcher still appears without changing effective URLs.
