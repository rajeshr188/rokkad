---
status: active
owner: ui
updated: 2026-06-30
tags: [ui, saas-ia, routes, workspace, tenant, decisions]
related:
  - docs/ui/workspace_slug_route_map_plan.md
  - docs/ui/workspace_slug_route_map_review.md
  - docs/ui/saas_information_architecture_audit.md
---

# Workspace Slug Deferred Targets Plan

This phase chooses concrete targets for the remaining deferred
`/w/<workspace_slug>/...` route-map items. It does not add runtime routes yet.

## Decision Principles

- Prefer existing stable tenant entrypoints for initial redirect aliases.
- Do not resurrect removed `sales` or `purchase` runtime apps.
- Route sales and purchase through DEA business-event screens until dedicated
  commerce/procurement modules are rebuilt.
- Keep Contact out of canonical slug routes; Party is the canonical replacement.
- Do not redirect workspace security/audit routes to account-level security
  pages because that would mix workspace-admin and user-account concepts.
- Do not expose placeholder routes unless the target screen has a clear product
  owner and permission boundary.

## Tenant Route Targets

| Future slug route | Initial target | Target status | Reason |
| --- | --- | --- | --- |
| `/w/<workspace_slug>/operations/` | `dea_business_events_dashboard` | safe redirect target | This is the current source-document operations hub for sales, purchase, settlement, rate fixing, and commodity movement previews. |
| `/w/<workspace_slug>/sales/` | `dea_business_events_dashboard` | safe redirect target | Dedicated sales runtime app was removed; current sales work should enter through DEA business events, not a legacy sales app. |
| `/w/<workspace_slug>/purchase/` | `dea_business_events_dashboard` | safe redirect target | Dedicated purchase runtime app was removed; current purchase work should enter through DEA business events. |
| `/w/<workspace_slug>/commodity/` | `dea_commodity_list` | safe redirect target | Current commodity master and account setup live in DEA. Future hub should include movements, exposure, valuation, and rate fixing. |
| `/w/<workspace_slug>/reports/` | `dea_reports_hub` | safe redirect target | DEA is the central reporting hub today. Future hub can aggregate Girvi operational reports and product reports. |

## Workspace Settings Targets

| Future slug route | Initial target | Target status | Reason |
| --- | --- | --- | --- |
| `/w/<workspace_slug>/settings/profile/` | `workspace_update` | safe redirect target | Current business profile edit route owns workspace name/logo/theme fields. |
| `/w/<workspace_slug>/settings/roles/` | `workspace_settings_team` | interim redirect target | There is no dedicated roles/permissions editor yet. Team management is the current closest workspace-admin surface. |
| `/w/<workspace_slug>/settings/billing/` | `subscriptions:dashboard` | safe redirect target | Current subscription dashboard is the billing surface. The slug view should resolve/select workspace before redirecting. |
| `/w/<workspace_slug>/settings/modules/` | new workspace modules screen | wait for new screen | No module registry/admin screen exists. Do not fake this with setup checklist after the route is live. |
| `/w/<workspace_slug>/settings/numbering/` | `girvi:girvi_series_list` | interim redirect target | Girvi series is the current numbering implementation. Future target should be a unified numbering-series manager. |
| `/w/<workspace_slug>/settings/accounting/` | `dea_chart_of_accounts` | safe redirect target | Chart of accounts is the best current accounting setup entrypoint. Opening balances remain available through the setup checklist. |
| `/w/<workspace_slug>/settings/security/` | new workspace security/audit screen | wait for new screen | Audit logs exist in the data model/admin, but no workspace-owned security/audit UI exists. Do not redirect to account settings. |

## Implementation Order

### Phase 11.1: Target Decision

Status: complete.

Record this target plan and guard it with tests. Do not add runtime routes.

### Phase 11.2: Safe Redirect Aliases

Add redirect aliases only for targets marked `safe redirect target`:

- operations;
- sales;
- purchase;
- commodity;
- reports;
- settings/profile;
- settings/billing;
- settings/accounting.

Keep compatibility routes and existing tenant prefixes available.

### Phase 11.3: Interim Redirect Aliases

Add interim aliases only if the user experience is acceptable:

- settings/roles -> team management;
- settings/numbering -> Girvi series.

Document in the UI that these are current operational surfaces, not final
workspace settings modules.

### Phase 11.4: New Workspace Settings Screens

Design and implement real screens before adding live aliases for:

- settings/modules;
- settings/security.

`settings/security` should read from workspace audit/security events, not from
account-level allauth settings.

## Next Recommended Step

Proceed with Phase 11.2: implement safe redirect aliases for operations, sales,
purchase, commodity, reports, profile, billing, and accounting. Keep modules and
security absent until real workspace-owned screens exist.
