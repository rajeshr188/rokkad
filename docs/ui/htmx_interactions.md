---
status: active
owner: project
updated: 2026-06-18
tags: [ui, htmx, interactions]
related: [screen_designs.md, ../product/workflows.md, ../implementation/ui-principles.md]
---

# HTMX Interactions

This document standardizes HTMX usage for the ERP UI.

## Current HTMX Usage

- EXISTING: Girvi loan detail has lazy-loaded tab endpoints for items, payments, transactions, statement, notices, and release.
- EXISTING: Girvi loan create preview endpoint exists.
- EXISTING: Girvi loan table partial endpoint exists.
- EXISTING: Sales and purchase item add/edit/delete flows use partial templates.
- EXISTING: DEA dashboard metrics AJAX and period status AJAX exist.
- EXISTING: DEA opening balance validation AJAX exists.
- EXISTING: Shared partial templates exist under `templates/partials/`.

## Problems

- REFACTOR: HTMX patterns are module-specific and inconsistent.
- REFACTOR: Some pages use full redirects where modal/drawer interaction would be clearer.
- REFACTOR: Some partials are named by implementation detail rather than screen responsibility.
- REFACTOR: Validation errors are not consistently returned as field-level, line-level, and page-level blocks.

## Standard Patterns

### Filtered Table

Use for:

- Party list.
- Loan list.
- Voucher list.
- Sales/Purchase lists.
- Stock list.
- Reports.

Pattern:

- Filter form targets table container.
- Pagination links target the same container.
- Browser URL should update for shareable filters when useful.

Expected fragments:

- `*_table.html`
- `*_filters.html`
- `*_empty_state.html`

### Line Item Editor

Use for:

- Sale items.
- Purchase items.
- Loan collateral items.
- Repledged items.
- Voucher lines.
- Stock adjustment lines.

Pattern:

- Add line opens inline row or modal.
- Save line replaces row.
- Delete line removes row and refreshes summary.
- Summary totals refresh after line mutation.

Required containers:

- Line table.
- Totals panel.
- Validation summary.

### Action Modal

Use for:

- Receive repayment.
- Make payment.
- Allocate receipt/payment.
- Add role/contact/address/document.
- Confirm low-risk status transition.

Pattern:

- Button loads form into modal body.
- Submit returns updated fragment or validation errors.
- Success emits event to refresh affected panels.

### Confirmation Page

Use full page instead of modal for:

- Period close/lock/unlock.
- Posting correction/reversal.
- Bulk release.
- Duplicate party merge.
- Workspace delete/archive.
- High-value loan auction/sale.

### Setup Blocker

Use for:

- Missing rate source.
- Missing rates.
- Missing DEA voucher type.
- Missing party account mapping.
- Missing license/series.

Pattern:

- Show alert near action.
- Include direct setup link.
- Include "Retry" action after setup.
- Do not silently return zero values.

### Lazy Detail Tabs

Use for:

- Loan detail.
- Party detail.
- Sale detail.
- Purchase detail.
- Stock detail.
- Voucher detail.

Pattern:

- Initial page renders Overview.
- Other tabs lazy-load on first click.
- Loaded tabs show spinner then fragment.
- Tab URLs should be stable enough for direct linking when practical.

## Event Names

PROPOSED common client events:

- `rokkad:table-refresh`
- `rokkad:totals-refresh`
- `rokkad:timeline-refresh`
- `rokkad:accounting-impact-refresh`
- `rokkad:inventory-impact-refresh`
- `rokkad:modal-close`
- `rokkad:toast`

## Validation Response Rules

- Field error: return form fragment with field errors.
- Line error: return row fragment with inline message.
- Cross-document error: return validation summary panel.
- Permission error: return 403 page or modal-safe forbidden fragment.
- Posting error: return unchanged source document with setup/actionable error.

## Template Naming

REFACTOR target:

- Full page: `module/document_detail.html`
- Tab partial: `module/document/tabs/<tab>.html`
- Table partial: `module/document/_table.html`
- Form partial: `module/document/_form.html`
- Modal body: `module/document/_modal_form.html`
- Empty state: `module/document/_empty.html`

## Permission Rules

- Buttons hidden by template permissions are not enough.
- Every HTMX endpoint must enforce the same permission server-side.
- Permission denial should be explicit and safe for modal/table replacement.
