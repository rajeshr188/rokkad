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
| Global/top navbar | `templates/components/navigation/main_nav.html` | Includes user menu, language selector, and the reusable workspace switcher partial in navbar mode. |
| Tenant sidebar | `templates/components/navigation/sidebar.html` | Current source of truth for live tenant ERP navigation, per accepted sidebar ADRs. |
| Workspace switcher partial | `templates/components/navigation/workspace_switcher.html` | Reusable dropdown with standalone and navbar variants. |
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

Phase 3.3 checkpoint: the desktop workspace settings links now render from `components/navigation/workspace_settings_sidebar.html` with `workspace_settings_sidebar_variant="desktop"`.

Phase 3.4 checkpoint: the mobile workspace settings links now render from the same partial with `workspace_settings_sidebar_variant="mobile"`.

Phase 3.5 checkpoint: the desktop and mobile account-management links now render from `components/navigation/account_sidebar.html` with `account_sidebar_variant="desktop"` or `"mobile"`.

Phase 3.6 checkpoint: the desktop and mobile workspace-manager links now render from `components/navigation/workspace_manager_sidebar.html` with `workspace_manager_sidebar_variant="desktop"` or `"mobile"`.

Phase 3.7 checkpoint: `layouts/management.html` now has clean ASCII comments and acts as a shell around focused navigation partials.

Phase 3.8 checkpoint: authenticated management shell smoke coverage now verifies the partialized navigation still renders expected labels and route targets.

Phase 3.9 checkpoint: the visual-polish acceptance criteria for the global/settings management shell are documented in `management_shell_visual_polish_checklist.md` before CSS or layout-density changes.

Phase 3.10 checkpoint: the first restrained management-shell visual polish pass adds neutral shell styling, shared management nav-link classes, desktop/mobile active-state parity, and cleaner mobile offcanvas styling without changing route names, labels, partial ownership, or permission behavior.

Phase 3.11 checkpoint: rendered-shell review found the management shell was still constrained by the default `container-lg mt-4` base wrapper. `layouts/base.html` now exposes a compatible `main_wrapper_class` block, and `layouts/management.html` opts into a full-width `container-fluid p-0 mt-0` app-shell wrapper. Local headless Chrome was available but did not produce screenshot files in this environment, so the review used the rendered HTML snapshot plus guard tests.

Phase 3.12 checkpoint: `django_project/test_management_shell_visual_smoke.py` is the reproducible visual-smoke path for the current environment. It renders the management shell with an authenticated owner fixture and guards the full-width wrapper, desktop/mobile management nav classes, active states, and control-plane route safety.

Phase 3.13 checkpoint: management-shell CSS now lives in `static/css/management.css`, and `layouts/management.html` loads it through Django's static tag while preserving the existing `mgmt_extra_css` extension block.

Phase 3.14 checkpoint: static asset readiness is verified for `css/management.css`. `findstatic css/management.css --verbosity 2` resolves the file from the project `static/` directory, `collectstatic --dry-run --noinput --verbosity 1` completes successfully, and `django_project/test_management_shell_visual_smoke.py` now guards that Django staticfiles can discover the stylesheet.

Phase 3.15 checkpoint: final Phase 3 review and commit-preparation notes are recorded in `phase3_navigation_management_shell_review.md`. The review confirms route, label, permission, and partial-ownership behavior remains unchanged and lists the expected phase commit set.

## Management Navigation Partial Inventory

| Partial | Current variants | Owns |
| --- | --- | --- |
| `components/navigation/workspace_manager_sidebar.html` | `desktop`, `mobile` | Global workspace manager links: `workspace_selector`, `workspace_create`. |
| `components/navigation/workspace_settings_sidebar.html` | `desktop`, `mobile` | Workspace settings/team links: `workspace_detail`, `workspace_preferences`, `team_members_list`, `team_invite`, `team_invitations_list`. |
| `components/navigation/account_sidebar.html` | `desktop`, `mobile` | Account links: `team_invitations`, owner-only subscription dashboard handoff, `account_settings`, `profile`. |
| `components/navigation/workspace_switcher.html` | standalone default, `navbar` | Workspace switching dropdown for topbar and future shell reuse. |

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

## Phase 3.2 Checkpoint

Completed:

1. `components/navigation/main_nav.html` now delegates its authenticated workspace dropdown to `components/navigation/workspace_switcher.html`.
2. The switcher partial supports a `workspace_switcher_variant="navbar"` mode while keeping the existing standalone mode.
3. The navbar switcher keeps compatibility routes: `workspace_select`, `workspace_selector`, `workspace_create`, and `clear_workspace`.
4. Authenticated global and tenant shell smoke tests prove the switcher renders through the real shell inheritance path.

## Phase 3.3 Checkpoint

Completed:

1. `layouts/management.html` delegates desktop workspace settings/team/invitation links to `components/navigation/workspace_settings_sidebar.html`.
2. The settings sidebar partial owns the desktop route targets for `workspace_detail`, `workspace_preferences`, `team_members_list`, `team_invite`, and `team_invitations_list`.
3. Mobile management offcanvas links remain inline to avoid changing mobile behavior in the same slice.
4. Template layout intent tests guard desktop ownership and the remaining mobile include point.

## Phase 3.4 Checkpoint

Completed:

1. `layouts/management.html` delegates mobile workspace settings/team/invitation links to `components/navigation/workspace_settings_sidebar.html`.
2. The settings sidebar partial owns both desktop and mobile route targets for workspace detail, preferences, team members, invite member, and sent invitations.
3. Mobile labels and route targets are preserved while duplicate inline mobile workspace settings links are removed.
4. Template layout intent tests guard both desktop and mobile ownership.

## Phase 3.5 Checkpoint

Completed:

1. `layouts/management.html` delegates desktop account links to `components/navigation/account_sidebar.html`.
2. `layouts/management.html` delegates mobile account links to the same partial.
3. The account sidebar partial owns invitations, owner-only billing, account settings, and profile route targets.
4. Template layout intent tests guard desktop and mobile account-link ownership.

## Phase 3.6 Checkpoint

Completed:

1. `layouts/management.html` delegates desktop workspace-manager links to `components/navigation/workspace_manager_sidebar.html`.
2. `layouts/management.html` delegates mobile workspace-manager links to the same partial.
3. The workspace manager sidebar partial owns `workspace_selector` and `workspace_create` route targets.
4. Template layout intent tests guard desktop and mobile workspace-manager ownership.

## Phase 3.7 Checkpoint

Completed:

1. `layouts/management.html` comments were cleaned to ASCII and now describe the current control-plane shell.
2. Obsolete duplicate-sidebar wording was removed from the mobile offcanvas section.
3. The final management navigation partial inventory is documented in this plan.
4. Template layout intent tests guard against stale duplicate-sidebar wording and mojibake comments returning.

## Phase 3.8 Checkpoint

Completed:

1. `django_project/test_shell_render_smoke.py` renders an authenticated owner management shell.
2. The smoke test asserts workspace-manager route targets still render.
3. The smoke test asserts workspace settings/team route targets still render.
4. The smoke test asserts account-management and owner billing route targets still render.
5. The smoke test asserts expected visible labels survive the sidebar partialization.

## Phase 3.9 Checkpoint

Completed:

1. `docs/ui/management_shell_visual_polish_checklist.md` records the compatibility constraints for the first visual polish pass.
2. The checklist defines desktop, mobile, route, label, permission, and responsive acceptance criteria.
3. The checklist keeps the management shell positioned as a workspace manager/settings surface rather than a tenant ERP surface.
4. Navigation intent tests guard the checklist so Phase 3.10 starts from an explicit review contract.

## Phase 3.10 Checkpoint

Completed:

1. `layouts/management.html` now uses a restrained neutral control-plane accent instead of the earlier purple gradient treatment.
2. Management navigation links share the `mgmt-nav-link` class across desktop and mobile sidebar partials.
3. Mobile sidebar links now use the same active-state logic as desktop links.
4. The mobile offcanvas uses management-shell classes instead of inline color/background styles.
5. Template intent tests guard the visual contract while route, label, partial, and permission behavior remain unchanged.

## Phase 3.11 Checkpoint

Completed:

1. A temporary rendered management-shell fixture was generated under `.tmp/` for desktop/mobile review.
2. Local Chrome headless execution was attempted for desktop and mobile screenshots, but this environment exited without producing screenshot files.
3. Rendered HTML review identified the management shell was inside the default constrained base wrapper.
4. `layouts/base.html` now exposes `main_wrapper_class` with the old `container-lg mt-4` default, preserving existing pages.
5. `layouts/management.html` overrides that block to render as a full-width control-plane shell.
6. Template intent tests guard the wrapper contract.

## Phase 3.12 Checkpoint

Completed:

1. `django_project/test_management_shell_visual_smoke.py` renders a representative authenticated management shell fixture.
2. The visual smoke test verifies the management shell uses the full-width app wrapper instead of the default constrained content wrapper.
3. The visual smoke test verifies desktop and mobile management links share `mgmt-nav-link` styling and avoid the old mobile-only `nav-link py-2` path.
4. The visual smoke test verifies active-state classes are present in both desktop and mobile navigation.
5. The visual smoke test verifies tenant ERP route names do not leak into the management shell.
6. The visual-polish checklist now points to the reproducible smoke path.

## Phase 3.13 Checkpoint

Completed:

1. `static/css/management.css` owns the management-shell visual styles previously inline in `layouts/management.html`.
2. `layouts/management.html` now loads `css/management.css` through `{% static %}` and keeps `mgmt_extra_css` available for page-specific additions.
3. Template intent tests verify the management stylesheet exists, contains the shell contract classes, and that the layout no longer embeds a `<style>` block.
4. Smoke-test rendering now uses plain staticfiles storage for synthetic tests so new static assets are not blocked by a stale collected manifest.
5. Visual behavior, routes, labels, permissions, and navigation partial ownership remain unchanged.

## Phase 3.14 Checkpoint

Completed:

1. `manage.py findstatic css/management.css --verbosity 2` finds `static/css/management.css`.
2. `manage.py collectstatic --dry-run --noinput --verbosity 1` completes successfully and includes `css/management.css` in the dry-run copy list.
3. `django_project/test_management_shell_visual_smoke.py` now asserts `finders.find("css/management.css")` succeeds.
4. The rendered management-shell smoke test asserts the stylesheet link resolves to `/static/css/management.css` under the synthetic non-manifest storage used by smoke tests.
5. No production staticfiles setting was changed.

## Phase 3.15 Checkpoint

Completed:

1. `docs/ui/phase3_navigation_management_shell_review.md` records the final review and commit-preparation checklist.
2. The review lists expected code, template, test, stylesheet, and documentation files for the phase commit.
3. The review records the compatibility outcome: no route, label, permission, or partial-ownership behavior changes beyond the intended management-shell standardization.
4. Navigation intent tests guard that the final review document exists.

## Next Recommended Step

Commit the Phase 3 navigation and management-shell standardization set, then proceed to Phase 4 invitation/team flow cleanup.
