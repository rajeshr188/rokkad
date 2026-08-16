---
status: active
owner: project
updated: 2026-06-18
tags: [ui, screen-designs, bootstrap, htmx]
related: [htmx_interactions.md, ../product/page_hierarchy.md, ../product/userflows.md, ../implementation/ui-principles.md]
---

# Screen Designs

This document defines target Bootstrap/HTMX screens. It marks whether each screen is EXISTING, PROPOSED, or REFACTOR.

## Workspace Dashboard

- Status: REFACTOR.
- Existing URL name: `workspace_dashboard`.
- Existing template family: `pages/company_dashboard.html`, `pages/workspace_home.html`, `pages/user_workspaces.html`.
- Purpose: daily landing page for selected workspace.
- Layout:
  - Header: workspace name, role, subscription/setup badges.
  - Action strip: Create Sale, Create Purchase, Create Loan, Receive Payment, Make Payment, Stock Adjustment.
  - Setup checklist.
  - Metrics bands: Accounting, Loans, Inventory, Sales/Purchase.
  - Recent activity table.
- Forms/tables/cards:
  - Setup checklist cards.
  - Recent documents table.
  - KPI cards with drill-down links.
- HTMX:
  - Refresh metrics.
  - Dismiss/complete setup checklist items.
  - Lazy-load recent activity.
- Empty states:
  - No workspace data: show Start Setup actions.
  - No rates: show Add Rate Source / Add Rate.
- Permission rules:
  - Visible to workspace members with `workspace_view`.
  - Action buttons gated by module create permissions.

## Party List

- Status: PROPOSED.
- Proposed URL name: `party_list`.
- Proposed template: `party/party_list.html`.
- Purpose: replace customer-first navigation with role-aware party management.
- Layout:
  - Header: Parties, New Party button.
  - Filter row: role, status, type, phone/email, PAN/GSTIN, search.
  - Table: code, name, roles, phone, email, status, credit hold, actions.
  - Side summary: counts by role and blocked/credit-hold parties.
- HTMX:
  - Filter table.
  - Quick role badges.
  - Inline status/credit hold toggle with confirmation.
- Empty states:
  - No parties: create first party.
  - No matching filter: clear filters.
- Permission rules:
  - `party_view` or current `contact_view` during transition.
  - Create requires `party_create`.

## Party Detail

- Status: PROPOSED.
- Proposed URL name: `party_detail`.
- Proposed template: `party/party_detail.html`.
- Purpose: unified profile for customers, suppliers, borrowers, lenders, employees, banks, and agents.
- Layout tabs:
  - Overview.
  - Roles.
  - Contacts.
  - Addresses.
  - Documents/KYC.
  - Accounts/Ledger.
  - Sales.
  - Purchases.
  - Loans.
  - Activity.
- HTMX:
  - Lazy-load tab panels.
  - Add role/contact/address/document in modal.
  - Ledger tab loads balances by role/purpose.
- Empty states:
  - No roles: prompt Add Role.
  - No accounting mapping: prompt Create Account Mapping after Phase 4.
- Permission rules:
  - View profile: `party_view`.
  - Manage roles: `party_role_manage`.
  - View accounts: `party_account_view` or accounting role.

## Contact Customer List

- Status: REFACTOR.
- Legacy Contact screen retired; bookmarks redirect to the Party list.
- Existing template family: `contact/customer_list.html` if present under app/templates or project templates.
- Purpose today: customer list.
- Target: keep as legacy compatibility route and redirect or visually label as Legacy Customers once Party UI exists.
- HTMX:
  - Existing filters can remain.
- Permission rules:
  - Current `contact_view`.

## Accounting Dashboard

- Status: REFACTOR.
- Existing URL names: `dea_home`, `dea_dashboard`, `dea_dashboard_enhanced`.
- Existing templates: `dea/dashboard*.html`, `dea/voucher_hub.html`, `dea/reports_hub.html`.
- Purpose: accounting command center.
- Layout:
  - Exceptions: unposted vouchers, failed postings, period lock alerts.
  - Actions: Create Voucher, Receive Payment, Make Payment, Journal Entry, Opening Balance.
  - Reports: Trial Balance, Balance Sheet, Profit/Loss, AR/AP Aging.
  - Audit: recent postings/reversals.
- HTMX:
  - Refresh exception counters.
  - Period selector updates report links.
- Empty states:
  - No accounting setup: seed/setup callout.
- Permission rules:
  - `dea_entry_view`.
  - Posting actions require `dea_entry_create` or stricter future posting permission.

## Voucher Detail

- Status: REFACTOR.
- Existing URL names: `dea_voucher_detail`, payment/journal/sales/purchase voucher details.
- Existing templates: `dea/voucher_detail.html`, `dea/paymentvoucher_detail.html`, voucher-specific templates.
- Layout:
  - Header: voucher number, status, date, source document.
  - Lines table.
  - Journal entry impact.
  - Source document link.
  - Timeline/audit.
  - Actions: Post, Reverse, Export.
- HTMX:
  - Post/reverse confirmation modal.
  - Refresh journal impact after posting.
- Validation:
  - Show period lock, imbalance, missing rule, missing account.

## Loan Dashboard

- Status: REFACTOR.
- Existing URL name: `girvi:girvi_dashboard`.
- Existing template: `girvi/dashboard.html`.
- Purpose: operational loan command center.
- Layout:
  - Actions: New Given Loan, New Taken Loan, Receive Repayment, Release Loan, Print Labels.
  - Metrics: active/current/overdue/NPA, pure weight, current value.
  - Setup: rates, rate source, license, series.
  - Lists: due today, long dead loans, recent payments.
- HTMX:
  - Refresh metrics.
  - Lazy-load due loans table.
- Permission rules:
  - `girvi_loan_view`; actions gated by create/payment/release permissions.

## Loan Detail

- Status: REFACTOR.
- Existing URL name: `girvi:girvi_loan_detail`.
- Existing template: `girvi/loan/loan_detail_1.html`.
- Existing HTMX tab endpoints: items, payments, transactions, statement, notices, release.
- Layout:
  - Header: loan ID, party, status, loan amount, collateral value.
  - Tabs: Overview, Collateral, Payments, Custody, Accounting Impact, Notices, Documents/Prints, Timeline.
  - Action bar: Approve, Disburse, Receive Repayment, Release, Renew, Auction/Sell, Print.
- HTMX:
  - Keep lazy tab loading.
  - Transition action modal.
  - Repayment drawer/modal.
- Empty states:
  - No collateral: add item.
  - No rates: setup blocker.
- Permission rules:
  - View: `girvi_loan_view`.
  - Transitions: specific Girvi permissions and backend service checks.

## Sale Detail

- Status: REFACTOR.
- Existing URL name: `sales:sales_invoice_detail`.
- Existing template: `sales/invoice_detail.html`.
- Layout:
  - Header: sale number, party, status, total, due.
  - Tabs: Items, Receipts/Allocations, Inventory Impact, Accounting Impact, Attachments, Timeline.
  - Actions: Edit Draft, Add Receipt, Post, Reverse.
- HTMX:
  - Item line add/edit/delete.
  - Rate/GST toggles.
  - Receipt allocation modal.

## Purchase Detail

- Status: REFACTOR.
- Existing URL name: `purchase:purchase_invoice_detail`.
- Existing template: `purchase/purchase_detail.html`.
- Layout:
  - Header: purchase number, supplier party, status, outstanding.
  - Tabs: Items, Payments, Stock Inward, Accounting Impact, Attachments, Timeline.
  - Actions: Generate Stock, Make Payment, Post, Reverse.
- HTMX:
  - Item line add/edit/delete.
  - Payment allocation modal.

## Inventory Dashboard

- Status: REFACTOR.
- Existing URL name: `product_product_home`.
- Existing template: `product/home.html`.
- Layout:
  - Metrics: stock value, metal weight, low stock, unposted movements.
  - Actions: Stock In, Stock Out, Adjustment, Audit, Import Opening Balance.
  - Sections: Stock, Catalog, Pricing, Reports.
- Permission rules:
  - Currently gated by `data_view`; propose inventory-specific permissions later.

## Reports Hub

- Status: PROPOSED.
- Proposed URL name: `reports_hub`.
- Purpose: one report entrypoint across modules.
- Layout:
  - Financial.
  - Loans.
  - Inventory.
  - Sales.
  - Purchase.
  - Parties.
  - Audit.
- HTMX:
  - Filter/date period selector.
  - Export action with permission check.

## Settings Hub

- Status: PROPOSED.
- Purpose: separate business setup from daily operations.
- Sections:
  - Workspace.
  - Team and roles.
  - Subscription.
  - Rates/rate sources.
  - Accounting setup.
  - Loan licenses/series.
  - Inventory catalog setup.
  - Notifications.
  - Import/export.
