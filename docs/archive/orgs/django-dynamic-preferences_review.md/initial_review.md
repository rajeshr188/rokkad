---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

I'll review how `django dynamic preferences` is currently used and assess how it can be improved for this project.

Created 3 todos

Searched for regex `dynamic_preferences|global_preferences_registry|per_instance|CompanyPreferences|Section\(` (`**/*.{py,md}`), 51 results

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/preferences.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/django_project/context_processors.py#1-1), lines 1 to 220

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/django_project/DYNAMIC_PREFERENCES.md)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/requirements.txt)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/registries.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/girvi/dynamic_preferences_registry.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/models.py#280-280), lines 280 to 320

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/forms.py#1-1), lines 1 to 220

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/views.py#260-260), lines 260 to 380

Searched for regex `company_preference_form_builder|CompanyPreferences\(|\.preferences\[|dynamic_preferences.urls|DYNAMIC_PREFERENCES` (`**/*.{py,md}`), 29 results

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/girvi/views/loan.py#100-100), lines 100 to 190

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/django_project/shared_urlpatterns.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/django_project/settings/base.py#1-1), lines 1 to 140

Searched for regex `loan_haircut|loan_interest_deduction|loan_default_date|interest_rate_gold|interest_rate_silver|interest_rate_other` (`**/*.py`), 13 results

Searched for regex `company-preferences|CompanyPreferenceBuilder|company_preferences.html` (`**/*.{py,html}`), 11 results

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/apps.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/templates/company/company_preferences.html)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/forms.py#220-220), lines 220 to 265

## Review of `django-dynamic-preferences` in this project

### Current usage

From the codebase, the package is set up in a **sound but limited** way:

| Area | Current implementation | Status |
|---|---|---|
| App install | `dynamic_preferences` is in base.py | âœ… |
| Per-company storage | `CompanyPreferenceModel` in models.py + registry in registries.py | âœ… |
| Registration | wired in apps.py via `preference_models.register(...)` | âœ… |
| Runtime helper | `CompanyPreferences` in preferences.py merges company override + global fallback | âœ… |
| UI | `CompanyPreferenceBuilder` in views.py + company_preferences.html | âœ… |
| Actual business use | mainly in loan.py for `loan_default_date` and metal interest-rate defaults | âš ï¸ limited |

### Preferences currently defined

In dynamic_preferences_registry.py, I found these:

- `Loan__Interest_Deduction`
- `Loan__Default_Date`
- `Loan__Haircut`
- `Interest_Rate__gold`
- `Interest_Rate__silver`
- `Interest_Rate__other`

### Important observation

The package is **configured more broadly than it is actually used**.

Right now, only these are clearly consumed in runtime flow:

- `loan_default_date`
- `interest_rate_gold`
- `interest_rate_silver`
- `interest_rate_other`

`loan_haircut` and `loan_interest_deduction` are exposed in `CompanyPreferences`, but I did not find active business usage tied to them.

---

## Is it the right fit?

### Yes â€” for this kind of setting

It is a **good fit** for your project when the setting is:

- **company/workspace-level**
- changed occasionally by admins/owners
- used as a **default or policy toggle**
- not part of historical accounting truth

That matches your multi-tenant SaaS model well.

### Not the right fit for everything

It is **not** ideal for:

- transactional data
- per-loan/per-customer rules that need history
- finance rules requiring **effective dates / versioning / audit trace**
- large structured configuration objects

> In short: **good for defaults and policy knobs, not for historical finance state.**

---

## Where it fits especially well in your context

It can be leveraged much better for:

### 1. Girvi loan policy settings
Examples:
- `Loan__Accrual_Timing` â†’ `EOM` / `BOM`
- `Loan__Auto_Post_Accruals`
- `Loan__Catchup_On_Receipt`
- `Loan__Catchup_On_Release`
- `Loan__Catchup_On_Renewal`

This is especially relevant to the new interest accrual work.

### 2. Reminder / notification behavior
Examples:
- overdue reminder enable/disable
- reminder lead days
- WhatsApp/SMS template toggles
- branch-level default reminder schedule

### 3. Operational defaults
Examples:
- default loan series
- default approval requirements
- default print template
- receipt/reference behavior
- default grace period / overdue threshold

---

## Current gaps / concerns

### 1. Underused
The infrastructure is in place, but adoption is still narrow.

### 2. Access pattern is a bit view-centric
Current reads happen mainly in `girvi/views/loan.py`.  
For core business rules, these should be consumed more from **service layer code**, not just views.

### 3. Repeated DB lookup in `CompanyPreferences`
`CompanyPreferences.__init__()` loads overrides each time with:

- `CompanyPreferenceModel.objects.filter(instance=company)...`

This is acceptable now, but if used widely it should be **cached per request/service call**.

### 4. Built-in `dynamic_preferences/` URLs are still exposed
shared_urlpatterns.py includes:

- `path("dynamic_preferences/", include("dynamic_preferences.urls"))`

Your own docs already flag removing this in production. That is the right recommendation.

### 5. No audit/version layer yet
For finance-sensitive preferences, â€œwho changed what and whenâ€ matters.  
That is still a missing piece.

---

## Recommended next improvements

### High priority
1. **Use it for interest accrual scheduling**
   - add `Loan__Accrual_Timing` (`EOM` / `BOM`)
   - this is the cleanest place for that setting

2. **Move preference use into services**
   - keep UI defaults in views
   - but enforce policy in service modules

3. **Add validators**
   - non-negative bounds
   - sensible max values for rates/haircuts

4. **Harden access**
   - remove or lock down raw `dynamic_preferences/` routes in production
   - keep users on your custom company preferences page

### Medium priority
5. **Add audit trail**
   - log preference changes with user, old value, new value, timestamp

6. **Add request-level caching**
   - avoid repeated preference queries on heavy pages

7. **Expand sections**
   - `Loan`
   - `Interest_Rate`
   - `Notification`
   - `DEA`
   - UI

---

## Overall verdict

> **Yes, `django-dynamic-preferences` is the right fit for your project â€” but only for company-level configurable defaults and policy toggles.**

Right now it is **well wired, but under-leveraged**.  
The best immediate next use is to drive **interest accrual timing and related loan/accounting behavior** from company preferences.

If you want, I can next propose the exact preference definitions to add for the accrual feature.
