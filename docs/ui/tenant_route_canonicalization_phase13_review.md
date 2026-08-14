---
status: active
owner: ui
updated: 2026-07-01
tags: [ui, saas-ia, routes, tenant, canonicalization, review]
related:
  - docs/ui/saas_information_architecture_audit.md
  - docs/ui/tenant_route_canonicalization_phase13_plan.md
  - docs/ui/tenant_deep_link_canonicalization_phase13_4_plan.md
  - django_project/shared_urlpatterns.py
  - apps/orgs/views.py
---

# Tenant Route Canonicalization Phase 13 Review

Phase 13 is complete at the safe compatibility boundary.

It does not remove legacy tenant roots and it does not remount full tenant app
URLConfs under `/w/<workspace_slug>/...`.

## Completed

### Route Reality Correction

The project now records the correct distinction between:

- route availability;
- visible navigation aliases;
- direct-render entry wrappers;
- deep-link canonicalization;
- full canonical replacement.

Legacy roots remain active:

- `/party/`
- `/product/`
- `/girvi/`
- `/dea/`
- `/rates/`
- `/notify/`
- `/notify-v2/`
- `/data-tools/`
- `/contact/`

### Visible Tenant Entry Links

Visible tenant entry links now prefer slug aliases where workspace schema context
is available:

- operations;
- reports;
- commodity;
- accounting dashboard quick action.

### Direct-Render Top-Level Entry Wrappers

These top-level entries now preserve `/w/<workspace_slug>/...` in the browser:

- `/w/<workspace_slug>/parties/`
- `/w/<workspace_slug>/inventory/`
- `/w/<workspace_slug>/loans/`
- `/w/<workspace_slug>/accounting/`

They delegate to existing module entry views and leave deep module routes
unchanged.

### Deep-Link Plan

`docs/ui/tenant_deep_link_canonicalization_phase13_4_plan.md` records the
recommended module order:

1. Party
2. Product/Inventory
3. Rates
4. Notify/Notify V2
5. Data Tools
6. Girvi
7. DEA

### Party Read-Only Redirect Aliases

Phase 13.5a added Party read-only deep aliases as redirects:

- `/w/<workspace_slug>/parties/new/`
- `/w/<workspace_slug>/parties/<pk>/`
- `/w/<workspace_slug>/parties/<pk>/edit/`
- `/w/<workspace_slug>/parties/<pk>/merge/`

Nested Party mutation aliases remain absent by design.

## Deferred

The following work should move to the next phase:

- direct-render Party deep aliases;
- Party internal link migration;
- Party `get_absolute_url()` changes;
- nested Party mutation aliases;
- Product/Inventory deep aliases;
- Rates deep aliases;
- Notify/Notify V2 aliases;
- Data Tools import/export aliases;
- Girvi deep aliases;
- DEA deep aliases;
- legacy-root redirects or removal.

## Compatibility Findings

- Public URLConf still must not expose tenant ERP route roots.
- Tenant URLConf still exposes legacy roots for compatibility.
- Slug aliases validate the workspace slug before delegating or redirecting.
- Contact remains intentionally excluded from canonical slug routing because
  Party is the replacement relationship surface.
- Customer portal `/portal/...` remains out of scope until Party-backed portal
  identity and selector work is complete.

## Verification

Focused checks for this phase:

```text
python manage.py test django_project.test_tenant_route_canonicalization_intent django_project.test_workspace_slug_route_map_intent django_project.test_route_intent django_project.test_template_layout_intent django_project.test_shell_render_smoke --keepdb
python manage.py check
git diff --check
```

Known test-environment issue:

- Some broad rendered DEA tenant tests can fail in this environment when
  manifest staticfiles are not collected for `css/workspace.css` or
  `css/public.css`. That is separate from Phase 13 route behavior.

## Next Recommended Step

Start the next route-canonicalization phase with Party direct-render deep aliases
and Party internal link migration, keeping POST/nested mutation routes on legacy
paths until their behavior is covered.
