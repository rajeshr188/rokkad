# Girvi Loan View Status

## Purpose

This document tracks the current state of Girvi loan-facing views and templates after the Django 6 native partial migration work completed on 2026-03-18.

## Canonical View Surface

### Loan list
- Canonical template: `templates/girvi/loan/loan_list.html`
- Native fragment host: `loan-table`
- Current pattern: full-page render plus HTMX fragment refresh from the same template

### Loan detail
- Canonical template: `templates/girvi/loan/loan_detail_1.html`
- Native fragment host: `loan-detail`
- Tab fragments now defined inline in the same template:
  - `items-tab`
  - `payments-tab`
  - `transactions-tab`
  - `statement-tab`
  - `notices-tab`
  - `release-tab`

### Print labels
- Canonical template: `templates/girvi/loan/print_labels.html`
- Native fragment host: `content`
- Legacy render-block flow removed from Girvi print views

### Storage boxes
- Canonical template: `templates/girvi/storagebox/storagebox_list.html`
- Native fragment host: `storagebox-list`

## Completed Standardization

### Done
- Girvi HTMX fragment responses now use `template.html#fragment` syntax for the migrated loan, print, and storagebox flows.
- Standalone tab templates under `templates/girvi/loan/partials/` were removed.
- `_loan_table.html` was inlined into `loan_list.html`.
- `storagebox_list_partial.html` was inlined into `storagebox_list.html`.
- Dead parallel loan detail templates `loan_detail.html` and `loan_detail_2.html` were removed.

### Confirmed conventions
- One canonical template per page surface.
- Inline `{% partialdef %}` for subsections of the same page.
- HTMX responses render canonical templates directly instead of block-render helpers.
- Mutations still use redirects or `204` responses where fragment replacement is not appropriate.

## Current Risks And Gaps

### Manual UX validation still pending
- Loan detail tab clicks need a browser smoke pass.
- Storagebox create, update, and delete flows need a browser smoke pass.
- Print labels HTMX flow should be exercised in-browser.

### Remaining architecture work outside Phase 6
- Repledged item lifecycle still needs a firm user-surface decision.
- Loan template management is still unclassified between admin-only and user-facing.
- Loan item media artifacts remain unclassified.
- Reports, notices, and archives still need source/query consistency review.

### Dependency cleanup still blocked
- `django-render-block` cannot yet be removed from the project because other apps still reference it:
  - `apps/tenant_apps/utils/htmx_utils.py`
  - `apps/orgs/views.py`
  - `apps/tenant_apps/sales/views/invoice.py`

## Validation Performed

### Automated checks
- `python manage.py check` passed.
- Tenant-scoped Django tests were not treated as blocking verification in this pass because Girvi runs under `django-tenants` and the current default test harness does not provision the tenant schema tables for this app.

### Static verification
- No remaining Girvi runtime references to `render_block`, `use_block`, or `@for_htmx` were found in migrated code paths.
- Deleted Girvi tab/table partials no longer have active runtime references.

## Recommended Next Steps

1. Run a browser smoke pass for loan tabs, print labels, and storagebox CRUD.
2. Add tenant-aware test setup for Girvi so schema-scoped tests can run under `django-tenants`.
3. Complete Phase 3 classification work for repledged items, templates, and media artifacts.
4. Decide whether to migrate non-Girvi render-block usage so the dependency can be removed project-wide.