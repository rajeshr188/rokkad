# Dynamic Preferences (SaaS)

## Overview
This project uses django-dynamic-preferences to store tenant-specific (company) settings, with optional global defaults used as fallbacks. The registry is per company, and the data is stored using a per-instance preference model.

## Current Architecture
- Registry: `apps/orgs/registries.py` defines `CompanyPreferenceRegistry` (per-company).
- Model: `CompanyPreferenceModel` is defined in `apps/orgs/models.py` and registered in `apps/orgs/apps.py`.
- Preferences: `apps/tenant_apps/girvi/dynamic_preferences_registry.py` defines preferences and registers them both globally and per company.
- UI: `CompanyPreferenceBuilder` renders a preferences form for the current workspace.
- Runtime access: use `CompanyPreferences` in `apps/orgs/preferences.py` for consistent tenant-aware access.

## Global Defaults + Per-Company Overrides
The intended behavior is:
- If a company-specific override exists, use it.
- Otherwise, fall back to the global preference value.

The helper class implements this pattern:

```python
from apps.orgs.preferences import CompanyPreferences

prefs = CompanyPreferences(request.user.profile.workspace)
rate = prefs.interest_rate_gold
```

## Adding a New Preference
1) Define a base preference class in `apps/tenant_apps/girvi/dynamic_preferences_registry.py`.
2) Register a global default and a company override using that base class.
3) Add a property to `CompanyPreferences` for typed access.
4) Use the helper in business logic instead of raw string keys.

Example pattern:

```python
example_section = Section("Example")

class BaseExamplePreference(DecimalPreference):
    section = example_section
    name = "sample_rate"
    default = Decimal("1.00")
    required = True

@global_preferences_registry.register
class GlobalExamplePreference(BaseExamplePreference):
    pass

@company_preference_registry.register
class CompanyExamplePreference(BaseExamplePreference):
    pass
```

## UI Organization
Preferences are organized by section with a sidebar navigation. Users can:
- View all preferences at once
- Filter by section (e.g., "Loan", "Interest_Rate")

Preferred workspace UI route:
- `/orgs/workspace/<workspace_id>/preferences/`
- named URL: `workspace_preferences`

Legacy compatibility route:
- `/orgs/company-preferences/`
- named URL: `company-preferences`

The package's built-in page is also still mounted at:
- `/dynamic_preferences/`

For normal usage, the project should prefer the custom workspace preference page over the built-in package UI.

## Access Control
Company preference editing is restricted to authenticated users with the Owner or Admin role. See `CompanyPreferenceBuilder` in `apps/orgs/views.py`.

## TODO

- [ ] Add validation rules to numeric preferences (non-negative, bounds)
- [ ] Add preference change auditing (track who changed what and when)
- [ ] Remove built-in `dynamic_preferences/` URLs from production

## Future Enhancements

### Validation Rules
Add validators to numeric preferences (bounds, non-negative rules) to ensure data quality.

### Per-User Preferences (Hybrid Model)
Implement a four-layer resolution model for maximum flexibility:
1. **User-in-tenant** (user + company): personal UX within a workspace (dashboard layout, default filters, preferred series)
2. **Tenant** (company): business rules (interest rates, document templates, policy flags)
3. **User-global**: personal defaults across all tenants (language, timezone, theme, notifications)
4. **Global**: system-wide fallback for new tenants

**Resolution order**: user-in-tenant → tenant → user-global → global (first match wins)

**Implementation options**:
- **Option A (lighter)**: Store user prefs in UserProfile JSONField with a custom resolver
- **Option B (consistent)**: Create `UserPreferenceModel` and `UserPreferenceRegistry` using dynamic-preferences patterns

This enables personal UX customization without allowing users to override company policy.

### Preferences by Section
Split UI by section (Loan, Interest Rate, etc.) for better organization as preferences grow.

### Security Hardening
Remove default `dynamic_preferences/` URLs in production to avoid exposing built-in admin views.

### Audit Trail
Add auditing for preference changes (who changed what and when) using django-simple-history or custom logging.

### Performance Optimization
Cache preference overrides per request for heavy pages or APIs to reduce database queries.
