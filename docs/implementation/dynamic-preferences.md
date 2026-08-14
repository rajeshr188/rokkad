---
status: active
owner: project
updated: 2026-07-05
tags: [configuration, preferences, django-dynamic-preferences]
related: [../STATUS.md, ../AGENT_MEMORY.md]
---

# Dynamic Preferences (SaaS)

## Overview
This project uses django-dynamic-preferences for database-backed configuration that can change without deployment. The current architecture now has a centralized configuration foundation while preserving the older Girvi/company preference path for compatibility.

## Current Architecture
- Central app: `apps.configuration`.
- Central workspace registry: `apps.configuration.registries.workspace_preferences_registry`.
- Central workspace model: `apps.configuration.models.WorkspacePreferenceModel`.
- Central service: `apps.configuration.services.PreferenceService`.
- User preferences: `dynamic_preferences.users` is installed for user-scoped UI preferences.
- Audit log: `apps.configuration.models.PreferenceAuditLog` records service-layer preference writes.
- Legacy Girvi/company registry: `apps.orgs.registries.company_preference_registry` and `apps.orgs.preferences.CompanyPreferences` remain active as compatibility storage/facade while old rows exist.
- Legacy Girvi/company resolution now delegates to `PreferenceService.get_workspace_from_registry(...)` so the old keys are behind the central service boundary without moving stored rows yet.
- Girvi runtime adapter: `apps.tenant_apps.girvi.service_modules.preferences` exposes current Girvi runtime reads over `PreferenceService` while preserving legacy key storage.
- Legacy migration command: `migrate_preferences_to_workspace --dry-run` inventories old Girvi rows; `--apply` writes only explicit legacy Girvi mappings into central lowercase `loan__...` keys.
- Legacy UI: `CompanyPreferenceBuilder` continues to render the current workspace preference form for the existing Girvi preference keys.

## Global Defaults + Per-Company Overrides
The central service behavior is:
- Explicit user preference overrides are used only for allowlisted UI keys.
- Explicit workspace overrides are used for workspace/business keys.
- Global/platform values are fallbacks.
- Code defaults are final fallbacks.

Use the central service for new code:

```python
from apps.configuration.services import PreferenceService

currency = PreferenceService.get_effective(
    user=request.user,
    workspace=request.user.profile.workspace,
    key="accounting__default_currency",
    default="INR",
)
```

Legacy compatibility code may still use the compatibility helper while old rows exist:

```python
from apps.orgs.preferences import CompanyPreferences

prefs = CompanyPreferences(request.user.profile.workspace)
rate = prefs.interest_rate_gold
```

That helper preserves old key names and storage while using `PreferenceService` internally.

For Girvi runtime read paths, use the Girvi adapter instead of importing `CompanyPreferences`:

```python
from apps.tenant_apps.girvi.service_modules.preferences import get_interest_rate_for_metal

rate = get_interest_rate_for_metal(request.user.profile.workspace, "Gold")
```

## Adding a New Preference
1) Define the preference in `apps/configuration/dynamic_preferences_registry.py`.
2) Register workspace/business preferences through `workspace_preferences_registry` and global fallback defaults through `global_preferences_registry`.
3) Register user preferences only through `user_preferences_registry`.
4) Add typed service helpers only when repeated use justifies them.
5) Use `PreferenceService` from runtime code; do not call raw preference managers in business modules.

Example pattern:

```python
example_section = Section("Example")

class BaseExamplePreference(DecimalPreference):
    section = example_section
    name = "sample_rate"
    default = Decimal("1.00")
    required = True

@register_workspace_and_global
class ExamplePreference(DecimalPreference):
    section = Section("accounting")
    name = "sample_rate"
    default = Decimal("1.00")
    required = True
```

## UI Organization
Central preference sections are:
- `accounting`
- `commodity`
- `loan`
- `inventory`
- `notifications`
- `documents`
- `ui`
- `platform`

The older Girvi preference UI still exposes existing sections such as `Loan` and `Interest_Rate`.

Preferred workspace UI route:
- `/workspace/<workspace_id>/settings/preferences/`
- named URL: `workspace_settings_preferences`

Legacy compatibility route:
- `/orgs/workspace/<workspace_id>/preferences/`
- named URL: `workspace_preferences`

Legacy unscoped compatibility route:
- `/orgs/company-preferences/`
- named URL: `company-preferences`

The package's built-in page is also still mounted at:
- `/dynamic_preferences/`

For normal usage, the project should prefer the custom workspace preference page over the built-in package UI.

## Access Control
Company preference editing is restricted to authenticated users with the Owner or Admin role. See `CompanyPreferenceBuilder` in `apps/orgs/views.py`.

Target access rules for the central service/UI:
- Platform/global preferences: superadmin only.
- Workspace preferences: workspace Owner/Admin only.
- User preferences: current user only.
- Subscription/plan settings: subscription/platform-owned models, not generic preferences.

## TODO

- [ ] Add validation rules to numeric preferences (non-negative, bounds).
- [x] Add service-layer preference change auditing for new central writes.
- [ ] Remove built-in `dynamic_preferences/` URLs from production
- [x] Build central workspace settings UI grouped by module sections.
- [ ] Migrate existing Girvi `Loan__...` / `Interest_Rate__...` keys to central lowercase keys only after compatibility tests are in place.
- [x] Replace current Girvi runtime preference reads with `PreferenceService` through the Girvi adapter.
- [x] Add a dry-run/apply legacy Girvi preference migration command: `migrate_preferences_to_workspace`.
- [x] Add first Girvi snapshot tests for loan item interest rates and disbursal deduction components.
- [ ] Add broader snapshot tests for DEA/accounting defaults, document templates, commodity/rate defaults, and generated documents.

## Future Enhancements

### Validation Rules
Add validators to numeric preferences (bounds, non-negative rules) to ensure data quality.

### Per-User Preferences
`dynamic_preferences.users` is installed for personal UI preferences. The first allowlisted keys are:
- `ui__theme`
- `ui__sidebar_collapsed`
- `ui__dashboard_widgets`
- `ui__table_page_size`
- `ui__date_display_format`
- `ui__default_landing_page`

User preferences must not override accounting, posting, loan policy, ledger, currency, numbering, notice, or audit-sensitive workspace settings.

### Audit Safety

Preferences influence new decisions only. Posted vouchers, journal entries, historical rates, loan terms, rate-fixing results, generated legal document content, payment history, and secrets must not be represented as mutable preferences.

### Preferences by Section
Split UI by section (Loan, Interest Rate, etc.) for better organization as preferences grow.

### Security Hardening
Remove default `dynamic_preferences/` URLs in production to avoid exposing built-in admin views.

### Audit Trail
Add auditing for preference changes (who changed what and when) using django-simple-history or custom logging.

### Performance Optimization
Cache preference overrides per request for heavy pages or APIs to reduce database queries.

