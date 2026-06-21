---
status: active
owner: project
updated: 2026-06-18
tags: [architecture, navigation, urls, permissions]
related: [../adr/sidebar-navigation-source-of-truth.md, ../product/page_hierarchy.md, ../ui/screen_designs.md]
---

# Navigation Map

The current live navigation source of truth is:

- `templates/components/navigation/sidebar.html`

The future/dormant navigation config is:

- `django_project/navigation.py`

Do not partially migrate navigation. Follow the accepted ADR if moving to dynamic navigation later.

## Current URL Roots

### Public And Shared

- EXISTING: `/` through `pages.urls`.
- EXISTING: `/accounts/` through allauth.
- EXISTING: `/onboarding/`.
- EXISTING: `/orgs/`.
- EXISTING: `/profile/`.
- EXISTING: `/subscriptions/`.
- EXISTING: `/invitations/`.

### Tenant

- EXISTING: `/contact/`.
- EXISTING: `/girvi/`.
- EXISTING: `/rates/`.
- EXISTING: `/product/`.
- EXISTING: `/notify/`.
- EXISTING: `/notify-v2/`.
- EXISTING: `/dea/`.
- EXISTING: `/purchase/`.
- EXISTING: `/sales/`.
- EXISTING: `/approval/`.
- PROPOSED: `/party/` or `/parties/` once Party UI exists.

## Current Sidebar Items

- EXISTING: Dashboard -> `workspace_dashboard`.
- EXISTING: My Invitations -> `team_invitations`.
- EXISTING: Company Settings -> `workspace_detail`.
- EXISTING: Preferences -> `workspace_preferences`.
- EXISTING: Subscription -> `subscriptions:dashboard`.
- EXISTING: Contacts -> `contact_customer_list`.
- EXISTING: Product -> `product_product_home`.
- EXISTING: Notifications V2 -> `notify_v2_batch_list`.
- EXISTING: Girvi -> `girvi:girvi_dashboard`.
- EXISTING: Sales -> `sales:sales_invoice_list`.
- EXISTING: Purchase -> `purchase:purchase_invoice_list`.
- EXISTING: Accounting -> `dea_journal_entries_list`.
- EXISTING: Rates -> `rate_list`.
- EXISTING: Account & Workspaces -> `workspace_selector`.

## Proposed Sidebar

REFACTOR labels and grouping:

- Home
  - Workspace Dashboard
  - Activities
- Parties
  - Parties
  - Customers
  - Suppliers
  - Merge/Duplicates
- Operations
  - Sales
  - Purchases
  - Loans
  - Receipts
  - Payments
  - Commodity Settlement
- Inventory
  - Stock
  - Catalog
  - Pricing
  - Adjustments
- Accounting
  - Dashboard
  - Vouchers
  - Journal Entries
  - Ledgers
  - Party Accounts
  - Periods
  - Opening Balances
  - Reconciliation
- Reports
  - Financial
  - Loans
  - Inventory
  - Sales
  - Purchase
  - Parties
  - Audit
- Settings
  - Workspace
  - Team
  - Subscription
  - Rates
  - Loan Setup
  - Accounting Setup
  - Notifications

## Permission Map

EXISTING:

- Workspace/team permissions live in `apps.orgs.permissions`.
- Sidebar checks `user_permissions` and Owner/Admin role labels.
- Current module checks include:
  - `contact_view`
  - `data_view`
  - `girvi_loan_view`
  - `sales_invoice_view`
  - `purchase_order_view`
  - `dea_entry_view`

PROPOSED:

- Add Party permissions before Party UI ships.
- Add inventory-specific permissions instead of using generic `data_view`.
- Add voucher posting/reversal-specific permissions separate from `dea_entry_create`.

## Route Problems To Fix

- REFACTOR: Girvi is mounted at `/girvi/` but many child paths start with `girvi/`, producing `/girvi/girvi/...`.
- REFACTOR: Sales has duplicate `sales/` route for invoice list and home.
- REFACTOR: Product has duplicate `stock/create/` route for direct stock-in and journal-entry stock-in.
- REFACTOR: Girvi duplicates route names/paths for transition, statements, storage boxes, and reports.
- REFACTOR: Accounting sidebar goes to journal entries list instead of accounting dashboard or voucher hub.
- REFACTOR: Contact nav should become Parties once Party UI exists.

## Canonical Future Routes

PROPOSED:

- `/workspace/` -> global workspace selector.
- `/dashboard/` -> workspace dashboard.
- `/parties/` -> party list/dashboard.
- `/inventory/` -> inventory dashboard.
- `/sales/` -> sales dashboard/list.
- `/purchases/` -> purchase dashboard/list.
- `/loans/` -> loan dashboard/list.
- `/accounting/` -> accounting dashboard.
- `/reports/` -> reports hub.
- `/settings/` -> settings hub.

Implementation should keep old URL names as aliases during migration, but templates should move to canonical names.
