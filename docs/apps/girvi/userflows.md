---
status: active
owner: girvi
updated: 2026-06-18
tags: [girvi, userflows, htmx]
related: [README.md, architecture.md, workflows.md]
---

# Girvi Userflows

## Navigation Shape

The Girvi dashboard is the hub at the app root URL. It links to loan creation, loan lists, releases, licenses, series, storage boxes, payments, statements, notifications, reports, archives, and templates.

Most operational pages are server-rendered templates under `templates/girvi/`. HTMX is used for modal forms, list refreshes, partial tab loads, and table pagination/sorting.

## Dashboard Quick Actions

Path:

1. User opens the Girvi dashboard.
2. Dashboard cards and sidebar links provide shortcuts for create loan, release, repayment, storage, statements, notices, reports, and template tools.
3. Clicking a shortcut usually opens a modal or navigates to the relevant HTMX-driven page.

Files:

- `views/dashboard.py::girvi_dashboard`
- `templates/girvi/dashboard.html`

## Dashboard to New Loan

Path:

1. User opens Girvi dashboard.
2. User clicks Create Loan.
3. HTMX loads `girvi_loan_create` into `#modal-content`.
4. `loan_form.html` renders borrower/series/date/tenure and initial collateral item rows.
5. Changing borrower, series, date, tenure, interest type, or item fields refreshes `_creation_preview.html`.
6. POST creates the loan and returns an `HX-Redirect` to the loan detail page.

Files:

- `views/dashboard.py::girvi_dashboard`
- `views/loan.py::loan_create`
- `templates/girvi/dashboard.html`
- `templates/girvi/loan/loan_form.html`
- `templates/girvi/loan/_creation_preview.html`

## Loan List

Path:

1. User opens `girvi/loan/`.
2. `loan_list.html#loan-content` shows tabs/filter controls and bulk actions.
3. `loan_table_partial` loads the table into `#loan-table-container`.
4. User switches `loan_kind` between Given, Taken, and All.
5. Quick filters and advanced filters call `loan_table_partial` with HTMX.
6. Table header sorting and pagination also call `loan_table_partial`.

Bulk actions available from the table include printing labels, bulk release, notice generation, merge, and delete. Merge is only allowed for Given loans; delete is disabled from the All tab.

Files:

- `views/loan.py::loan_list`
- `views/loan.py::loan_table_partial`
- `templates/girvi/loan/loan_list.html`
- `templates/girvi/loan/table_htmx_loan_list.html`
- `tables.py`
- `filters.py`
- `selectors.py`

## Storage Boxes

Path:

1. User opens the storage box page from the sidebar or dashboard.
2. List view shows the current storage boxes.
3. Add, edit, and delete actions are handled with HTMX forms and partial updates.
4. Storage box detail shows the box metadata and related items.

Files:

- `views/storagebox.py`
- `templates/girvi/storagebox/`

## Notices and Overdue Reminders

Path:

1. User opens the notice page or triggers a notice from loan detail.
2. Overdue reminder generation builds print-oriented notice output.
3. V2 notice flow provides the newer notice print path.
4. Loan detail notices tab surfaces notice-related context for the selected loan.

Files:

- `views/notice.py`
- `views/prints.py::notify_print`
- `views/prints.py::notify_print_v2`
- `templates/girvi/loan/loan_detail_1.html`
- `templates/girvi/loan/loan_transition_form.html`

## Reports and Exports

Path:

1. User opens report pages from sidebar or dashboard.
2. Report views render loan summaries, customer summaries, crosstab data, series activity, and license expiry reports.
3. Export actions download ledger, inventory audit, unreleased loan, or Excel/PDF output.
4. Some report pages are read-only while others produce files for offline use.

Files:

- `views/reports.py`
- `views/prints.py`
- `templates/girvi/reports/`
- `templates/girvi/loan_archive.html`

## Archive Browsing

Path:

1. User opens loan archive pages from the archive route set.
2. Year, month, week, day, and today views help browse historical GivenLoan records.
3. The archive pages are read-only and use date-based drill-down navigation.

Files:

- `views/archives.py`
- `templates/girvi/loan_archive.html`

## Given Loan Detail

Path:

1. User clicks a loan id from the list.
2. HTMX loads `girvi_loan_detail` into `#content`.
3. Detail page shows status, borrower, collateral summary, due/interest reporting, transition actions, release action, and operations dropdown.
4. Tabs lazy-load content:
   - Items
   - Payments
   - Transactions
   - Statement
   - Notices
   - Release

Important interactions:

- Edit loan opens `girvi_loan_update` in a modal.
- Delete loan uses `hx-delete`.
- Split items posts to `split_loan_items`.
- Custody summary loads into `#content`.
- Transition actions go to the transition form URL.
- Release action goes through custody check first.

Files:

- `views/loan.py::loan_detail`
- `views/loan.py::loan_detail_*_tab`
- `templates/girvi/loan/loan_detail_1.html`

## Transition Form

Path:

1. User clicks a transition action such as Submit for Approval, Approve Loan, Disburse Loan, Mark NPA, Request Closure, Request Renewal, or Write Off.
2. Browser opens `loan/<pk>/transition/?transition=<key>`.
3. `loan_transition_view` resolves aliases and picks the configured form.
4. User submits the form.
5. `LoanTransitionService` executes the flow and command.
6. User is redirected back to loan detail with a success/error message.

Files:

- `views/loan.py::loan_transition_view`
- `templates/girvi/loan/loan_transition_form.html`
- `templates/girvi/loan/_transition_form_inner.html`
- `transition_registry.py`
- `service_modules/transitions.py`

## Item Management

Path:

1. User opens the Items tab on loan detail.
2. Existing items render with inline edit/delete controls.
3. Add Item loads `loanitem_create_update` into `#form`.
4. Submit returns the new/updated item partial.
5. Picture button opens item picture modal.

Files:

- `views/loanitem.py`
- `templates/girvi/partials/item-form.html`
- `templates/girvi/partials/item-inline-new.html`
- `templates/girvi/partials/item-picture-modal.html`

## Release

Path:

1. User clicks Start Release Workflow from loan detail.
2. `release_loan_check_custody` checks whether collateral is in vault or with lenders.
3. If items are with lenders, user sees `release_custody_check.html` and must return items or run return-with-release.
4. If release can proceed, user opens `girvi_release_create` for the loan.
5. `release_form.html` shows release date, released by, and preview/validation.
6. Submit creates the release, moves lifecycle toward `Closed`, posts release accounting, and redirects to loan detail.

Files:

- `views/custody_views.py::release_loan_check_custody`
- `views/release.py::release_create`
- `templates/girvi/release_custody_check.html`
- `templates/girvi/release/release_form.html`

## Bulk Release

Path:

1. User selects rows in the Given loan list.
2. Bulk Release action loads `bulk_release` into `#content`.
3. User chooses release date.
4. Service builds a release formset preview.
5. User chooses strict or partial commit policy.
6. Submit calls `submit_release_formset` and renders success or row-level errors.

Files:

- `views/release.py::bulk_release`
- `views/release.py::submit_release_formset`
- `templates/girvi/release/bulk_release.html`
- `templates/girvi/release/release_formset.html`

## Repayment

Given loan path:

1. User opens repayment form for a Given loan.
2. Form posts to `girvi_loanpayment_create`.
3. Optional receipt catch-up accrual runs.
4. Payment is created and posted.
5. User returns to loan detail.

Taken loan path:

1. User opens taken-loan repayment form.
2. Form posts to `takenloan_payment_create`.
3. Payment is created through `TakenLoan.create_payment()` and posted.
4. User returns to taken-loan collateral detail.

Files:

- `views/loanpayment.py`
- `templates/girvi/loanpayment/givenloan_repayment_form.html`
- `templates/girvi/loanpayment/takenloan_repayment_form.html`

## Custody and Taken Loan Collateral

Path:

1. User opens custody summary from Given loan detail.
2. User can return items from lender, start release, or create repledge.
3. Create Repledge shows available in-vault items grouped by borrower.
4. POST creates a `TakenLoan` and moves selected collateral to lender custody.
5. Taken-loan collateral detail shows collateral grouped by original borrower and provides return-all action.

Files:

- `views/custody_views.py`
- `templates/girvi/loan_custody_summary.html`
- `templates/girvi/repledge_select_items.html`
- `templates/girvi/taken_loan_collateral.html`

## Licenses and Series

Path:

1. User opens license list.
2. User creates/updates/deletes licenses.
3. License detail shows series and documents.
4. Series pages manage numbering setup and activation.
5. Series guardrails run automatically after loan create/delete.

Files:

- `views/license.py`
- `views/series.py`
- `templates/girvi/license/`
- `templates/girvi/series/`

## Statements

Path:

1. User opens statement list.
2. User creates a verification session.
3. User adds/scans statement items.
4. User toggles completion to generate discrepancy rows.

Files:

- `views/statement.py`
- `templates/girvi/statement/`

## Template Administration and Printing

Path:

1. Workspace admin opens loan template list.
2. Admin creates template and frames, or creates starter frames.
3. Admin previews/test-prints using the latest sample loan.
4. Admin sets a ready template as default.
5. Loan print endpoints use the default template for PDF rendering.

Files:

- `views/template.py`
- `service_modules/printing.py`
- `documents/loan_ticket.py`
- `templates/girvi/template/`

## Expanded Print Workflow

Path:

1. User prints a loan ticket, labels, or a grid template from loan detail or list pages.
2. Template preview/test-print validates the chosen template against sample loan data.
3. Download template pack gives admins a reusable template bundle for setup or migration.

Files:

- `views/prints.py`
- `views/template.py`
- `templates/girvi/loan/loan_detail_1.html`
- `templates/girvi/release/release_list.html`
This userflow inventory reflects the current Girvi runtime surface as of 2026-06-21.
Keep this inventory in sync with `urls.py` and the active `views/` modules when routes change.
