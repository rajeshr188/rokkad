---
status: active
owner: project
updated: 2026-06-28
tags: [ui, navigation, management-shell, visual-polish, saas, phase-3]
related: [navigation_workspace_switcher_plan.md, saas_information_architecture_audit.md, route_template_inventory.md, ../AGENT_MEMORY.md, ../STATUS.md]
---

# Management Shell Visual Polish Checklist

This is the Phase 3.9 checklist for the global/settings management shell. It is documentation-only: no CSS, spacing, color, route, permission, or layout-density changes are included in this slice.

## Scope

The next visual pass should improve the management shell as a workspace manager and workspace-admin surface, not as a tenant ERP module screen.

Covered surfaces:

- `templates/layouts/management.html`
- `templates/components/navigation/workspace_manager_sidebar.html`
- `templates/components/navigation/workspace_settings_sidebar.html`
- `templates/components/navigation/account_sidebar.html`
- `templates/components/navigation/workspace_switcher.html`
- `templates/components/navigation/main_nav.html`

## Compatibility Constraints

- Do not change effective URLs or route names.
- Do not change visible navigation labels unless tests are updated in the same slice.
- Do not change role or permission behavior.
- Do not add tenant ERP module links to global/account management navigation.
- Do not add public/platform concepts to workspace settings screens.
- Preserve the current desktop and mobile partial ownership.
- Keep the shell render smoke tests passing before and after visual changes.

## Visual Checklist

- Sidebar sections are visually grouped as workspace manager, workspace settings, and account management.
- Active and hover states are clear, restrained, and consistent with Bootstrap.
- Mobile offcanvas shows the same route families as desktop through the shared partials.
- Workspace identity is visible from the topbar or switcher when a workspace is selected.
- Empty workspace state is understandable when no selected workspace exists.
- Account settings and workspace settings are visually distinct.
- Owner-only billing access remains understandable without exposing broken routes to non-owners.
- Link density is appropriate for repeated operational use.
- Text does not overlap or overflow in desktop, tablet, or mobile widths.
- Button/link sizing remains stable when labels or badges change.
- The shell does not use nested cards for structural navigation.
- The shell avoids decorative blobs, one-note color palettes, and marketing-style hero treatment.
- The management shell feels quieter than public pages and less operationally dense than tenant ERP pages.

## Acceptance Criteria

- Desktop review covers global workspace list, workspace detail/settings, team members, invitations, billing handoff, account settings, and profile screens.
- Mobile review covers the management offcanvas and workspace switcher.
- Rendered visual smoke coverage exists in `django_project/test_management_shell_visual_smoke.py` for the full-width shell wrapper, desktop/mobile navigation classes, active states, and control-plane route safety.
- No route or label regression appears in `django_project/test_shell_render_smoke.py`.
- No template ownership regression appears in `django_project/test_template_layout_intent.py`.
- No route boundary regression appears in `django_project/test_route_intent.py`.
- No navigation contract regression appears in `django_project/test_navigation_intent.py`.
- `manage.py check` remains clean.

## Phase 3.10 Recommendation

Proceed to Phase 3.10 with the first management-shell visual polish pass. Keep it restrained: adjust spacing, section headings, active states, and responsive behavior while preserving route names, visible labels, partial ownership, and permission behavior.

## Phase 3.12 Visual Smoke Path

`django_project/test_management_shell_visual_smoke.py` is the reproducible visual smoke path for the current environment. It does not replace a true browser screenshot pass, but it guards the management shell risks that have already caused regressions:

- the management shell must render outside the default constrained content wrapper;
- desktop and mobile management navigation must share visual classes;
- active states must be present for desktop and mobile links;
- global/settings navigation must remain control-plane safe.

A future browser automation slice should build on this rendered smoke test instead of replacing the route, label, and template ownership tests.
