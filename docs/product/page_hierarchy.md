---
status: active
owner: project
updated: 2026-06-18
tags: [product, page-hierarchy, ux, navigation]
related: [../architecture/navigation_map.md, ../ui/screen_designs.md, ../flows/user-flow.md, ../domain/party.md, ../domain/accounting.md]
---

# Page Hierarchy

This document maps the current Rokkad page structure and proposes a clearer product hierarchy for daily ERP workflows.

Labels:

- EXISTING: present in the codebase now.
- PROPOSED: new page/screen or navigation concept.
- REFACTOR: current page exists but should be renamed, moved, merged, or redesigned.

## Current State Map

### Modules

- EXISTING: Public/shared shell through `django_project/shared_urlpatterns.py`, `pages`, allauth accounts, onboarding, orgs, subscriptions, profile, invitations, dynamic preferences.
- EXISTING: Tenant apps through `django_project/tenant_urls.py`: Contact, Girvi, Rates, Product, Notify, Notify V2, DEA, Purchase, Sales, Approval.
- EXISTING: New Party model app exists under `apps/tenant_apps/party`, but no UI routes exist yet.
- EXISTING: DEA owns accounting, vouchers, ledgers, journal entries, periods, opening balances, reports, and reconciliation.
- EXISTING: Girvi owns pawn/loan workflows, custody, storage boxes, releases, statements, notices, licenses, series, loan printing, and loan reports.
- EXISTING: Product owns catalog, variants, attributes, pricing, stock, stock transactions, stock journal entry, split/merge, audit, and opening balance import.
- EXISTING: Sales and Purchase own invoice/payment/receipt style workflows.
- EXISTING: Orgs owns workspace selection, workspace lifecycle, team, role, invitation, preferences, and membership flows.

### Current Live Navigation

- EXISTING: Live sidebar source is `templates/components/navigation/sidebar.html`.
- EXISTING: Top nav source is `templates/components/navigation/main_nav.html`.
- EXISTING: `django_project/navigation.py` is dormant by ADR and should not be treated as live navigation.
- EXISTING: Sidebar top-level links currently show Dashboard, My Invitations, Company Settings, Preferences, Billing, Contacts, Product, Notifications V2, Girvi, Sales, Purchase, Accounting, Rates.

### Current Pages

- EXISTING: Public pages: home, about, privacy, terms, workspace landing pages through `pages`.
- EXISTING: Authentication pages: allauth sign in, sign up, email, password, social account pages.
- EXISTING: Workspace pages: selector, create, detail/settings, preferences, member list, invite, invitation list, profile/account settings.
- EXISTING: Subscription pages: plan list, checkout, dashboard, invoice detail/PDF.
- EXISTING: Contact pages: customer list/create/detail/update/delete, address/contact/proof/picture child screens, merge, import/export, report.
- EXISTING: Party pages: none.
- EXISTING: Girvi pages: dashboard, loan list/create/detail/update/delete, transition, renewal, release, bulk release, loan item, license, series, statement, storage box, printing, reports, notices.
- EXISTING: DEA pages: dashboard/home, voucher hub/list/detail/form/post/reverse, payment voucher, journal entry voucher, sales/purchase invoice vouchers, ledger/account lists, transactions, periods, opening balance, reports, reconciliation.
- EXISTING: Product pages: dashboard/home, category/product type/product/variant/attribute, pricing tier/price override, stock list/detail/create/delete/split/merge/audit/opening balance.
- EXISTING: Sales pages: invoice list/create/detail/update/delete, item partials, receipt list/create/detail/update/delete/allocate.
- EXISTING: Purchase pages: purchase list/create/detail/update/delete, item partials, payment list/create/detail/update/delete/allocate.
- EXISTING: Rates pages: rate list/detail/create/update/delete and rate source list/detail/create/update/delete.
- EXISTING: Notification pages: legacy notify and notify v2 batch/settings pages.

## Problems Found

- REFACTOR: Navigation uses app names such as Contact/Product/Girvi instead of user jobs such as Parties, Inventory, Loans, Sales, Purchases, Accounting.
- REFACTOR: Contact remains user-facing even though Party is now the long-term domain model.
- REFACTOR: Multiple modules have duplicate or confusing URL paths:
  - Sales defines `sales/` for both invoice list and home.
  - Product defines `stock/create/` for two views.
  - Girvi has duplicate aliases for transitions, statements, storage boxes, and reports.
  - Girvi tenant URL prefix creates paths such as `/girvi/girvi/loan/`.
- REFACTOR: DEA exposes several overlapping entry points: home, dashboard, legacy dashboard, enhanced dashboard, voucher hub, journal entry list, reports hub.
- REFACTOR: Loan, sale, purchase, and stock pages do not consistently follow the same document page pattern.
- REFACTOR: Reports are scattered inside module pages rather than one clear Reports hierarchy.
- PROPOSED: No Party UI yet, despite Party model and bridge now existing.
- PROPOSED: No unified Activities page showing recent business documents, postings, stock movements, loan events, and audit activity.
- PROPOSED: No unified setup/readiness page for rates, DEA seed data, party/account mapping, subscription, licenses, and inventory prerequisites.

## Improved Page Hierarchy

### Public

- EXISTING: `/` public home.
- EXISTING: `/privacy/`, `/terms/`, `/about/`.
- PROPOSED: `/pricing/` should point to subscription plan list for unauthenticated users.
- PROPOSED: `/help/` should explain core workflow concepts: sale, purchase, loan, voucher, posting, reversal.

### Authentication

- EXISTING: `/accounts/login/`, `/accounts/signup/`, allauth email/password/social routes.
- REFACTOR: After login, always route users to workspace selector or last active workspace dashboard; do not drop users into module pages without workspace context.

### Global User Area

- EXISTING: `/orgs/workspace/` workspace selector.
- EXISTING: profile/account settings under orgs/profile/shared profile routes.
- PROPOSED: `/home/` or workspace selector should be the global dashboard for users with multiple workspaces.

Global user dashboard sections:

- Workspaces
- Pending invitations
- Recent workspaces
- Subscription alerts
- Personal profile/account tasks

### Workspace Control Plane

- EXISTING: workspace create, detail/settings, preferences, team, invitations, subscription.
- PROPOSED: Workspace settings should use tabs:
  - Overview
  - Team
  - Invitations
  - Preferences
  - Subscription
  - Setup checklist
  - Audit

### Workspace Dashboard

- EXISTING: `workspace_dashboard`.
- REFACTOR: Make it the first operational screen after workspace selection.

Workspace dashboard sections:

- Today actions: create sale, create purchase, create loan, receive repayment, make payment, stock adjustment.
- Setup blockers: missing rate source, missing current rates, missing DEA seed data, missing license/series, missing party account mappings.
- Financial snapshot: cash/bank, receivables, payables, loan exposure.
- Operations snapshot: open loans, sales due, purchase due, low stock, notification batches.
- Recent activity: business documents, postings, reversals, stock movements.

### Module Dashboards

- PROPOSED: Each module should have one dashboard route and one list route.
- REFACTOR: Current modules sometimes use list pages as dashboards.

Recommended module dashboard routes:

- `/accounting/` -> Accounting dashboard.
- `/parties/` -> Party dashboard/list hybrid.
- `/inventory/` -> Inventory dashboard.
- `/sales/` -> Sales dashboard.
- `/purchases/` -> Purchase dashboard.
- `/loans/` -> Loan dashboard.
- `/reports/` -> Reports hub.
- `/settings/` -> Workspace settings hub.

### Accounting

- EXISTING: DEA pages under `/dea/`.
- REFACTOR: User-facing label should be Accounting, not DEA.

Hierarchy:

- Accounting dashboard.
- Create voucher hub.
- Vouchers.
- Journal entries.
- Ledgers and chart of accounts.
- Party accounts/subledgers.
- Periods and locks.
- Opening balances.
- Reconciliation.
- Financial reports.
- Audit trail.

### Parties

- EXISTING: Contact/customer UI.
- EXISTING: Party model and customer bridge.
- PROPOSED: Party UI.

Hierarchy:

- Party list.
- Party create/edit.
- Party detail:
  - Overview
  - Roles
  - Contacts
  - Addresses
  - KYC/Documents
  - Accounts/Ledger
  - Transactions
  - Sales
  - Purchases
  - Loans
  - Activity
- Duplicate merge.
- Legacy customer conversion.

### Inventory

- EXISTING: Product/catalog/stock pages.
- REFACTOR: User-facing label should be Inventory, with Catalog as a sub-area.

Hierarchy:

- Inventory dashboard.
- Stock list/detail.
- Stock inward/outward/adjustment.
- Stock audit.
- Opening balance import.
- Catalog:
  - Categories
  - Product types
  - Products
  - Variants
  - Attributes
  - Pricing tiers

### Sales And Purchases

- EXISTING: Separate sales invoice/receipt and purchase/payment flows.
- REFACTOR: Both should follow the same document pattern.

Document detail tabs:

- Overview
- Items
- Payments/Allocations
- Inventory Impact
- Accounting Impact
- Attachments
- Timeline

### Loans

- EXISTING: Girvi pages.
- REFACTOR: User-facing label should be Loans or Girvi Loans depending tenant terminology.

Loan detail tabs:

- Overview
- Collateral
- Payments/Repayments
- Custody
- Accounting Impact
- Notices
- Documents/Prints
- Timeline

### Reports

- EXISTING: Reports scattered in DEA, Girvi, Contact, Product.
- PROPOSED: Reports hub with module groups:
  - Financial reports
  - Party reports
  - Loan reports
  - Inventory reports
  - Sales reports
  - Purchase reports
  - Audit reports

### Settings/Admin

- EXISTING: workspace settings/preferences, rates/rate source, licenses/series, dynamic preferences, admin site.
- REFACTOR: Separate business setup from system admin.

Settings hierarchy:

- Workspace profile.
- Team and roles.
- Subscription.
- Rates and rate sources.
- Accounting setup.
- Loan licenses/series.
- Inventory/catalog setup.
- Notification templates.
- Import/export.
- Audit/security.
