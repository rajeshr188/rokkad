---
status: active
owner: project
updated: 2026-06-18
tags: [product, userflows, ux]
related: [page_hierarchy.md, workflows.md, ../ui/screen_designs.md, ../flows/user-flow.md]
---

# Userflows

This document defines target userflows for the ERP product. Existing screens are preserved where possible, but the flows are organized by user job instead of app boundary.

## User Roles

- EXISTING: Owner, Admin, Member, Viewer are defined through orgs role permissions.
- EXISTING: Platform admin override is superuser-only.
- EXISTING: Accounting permissions include `dea_entry_view`, `dea_entry_create`, period close/reconciliation/report permissions.
- EXISTING: Module permissions exist for Girvi, Sales, Purchase, Contact, Reports, Billing, Workspace, Team.
- PROPOSED: Add Party-specific permissions when Party UI ships: `party_view`, `party_create`, `party_edit`, `party_role_manage`, `party_document_manage`, `party_account_view`, `party_merge`.
- PROPOSED: Add role-oriented UI presets: Owner, Accountant, Cashier, Loan Officer, Inventory Clerk, Sales Clerk, Viewer.

## New User Signup And Onboarding

Current:

- EXISTING: allauth handles signup/login.
- EXISTING: onboarding app provides profile, company, team, tour, complete, skip steps.
- EXISTING: workspace creation can seed tenant defaults.

Improved flow:

1. User signs up.
2. System creates user profile and onboarding progress.
3. User lands on onboarding start.
4. User creates or joins workspace.
5. Workspace schema is provisioned.
6. Tenant defaults are seeded: DEA, product, rates, notify, party roles.
7. User sees setup checklist before entering daily workflows.

Edge cases:

- REFACTOR: If schema provisioning fails, show recovery screen with retry, not a generic error.
- REFACTOR: If seeding fails, mark setup incomplete and show action in dashboard.
- PROPOSED: Onboarding should create sample setup checklist rows rather than silently relying on fixtures.

## Create Workspace

Current:

- EXISTING: `workspace_create`, `workspace_selector`, `workspace_dashboard`.
- EXISTING: orgs control-plane services handle workspace creation and memberships.

Improved flow:

1. User clicks Create Workspace.
2. Form captures business name, schema/domain-safe slug, owner preferences.
3. System validates slug collision/reserved words.
4. System creates workspace, owner membership, domain, audit event.
5. System provisions tenant schema and seeds defaults.
6. User lands on workspace dashboard setup checklist.

Required screens:

- Workspace form.
- Provisioning progress or result.
- Setup checklist.

## Invite Team Member

Current:

- EXISTING: team invite and invitation views exist in orgs.
- EXISTING: role policy prevents privilege escalation.

Improved flow:

1. Owner/Admin opens Team tab.
2. User enters email and allowed role.
3. Role choices are filtered by actor permission.
4. Invitation is created or duplicate validation is shown.
5. Invitee accepts from global invitation inbox.
6. Membership is created and audit event recorded.

Edge cases:

- Prevent owner self-removal without transfer.
- Prevent last-owner demotion/removal.
- Show expired/revoked invitation status.

## Switch Workspace

Current:

- EXISTING: top nav workspace dropdown and `workspace_selector`.
- EXISTING: tenant context is resolved through middleware/context processors.

Improved flow:

1. User opens workspace switcher.
2. Switcher lists active memberships, role, subscription/setup state.
3. User selects workspace.
4. Profile active workspace updates.
5. User lands on selected workspace dashboard.

Edge cases:

- If subscription expired, allow billing/setup pages only.
- If user no longer member, clear workspace and show explanation.

## Create Party / Customer / Vendor

Current:

- EXISTING: Contact customer CRUD exists.
- EXISTING: Party model and Customer bridge exist.
- PROPOSED: Party UI does not exist yet.

Improved flow:

1. User opens Parties.
2. User clicks New Party.
3. User chooses party type and role(s).
4. Form captures identity, contact, address, tax/KYC.
5. Duplicate detection suggests existing parties.
6. System saves Party and role rows.
7. Detail page opens with role-aware tabs.

Edge cases:

- If party already exists as Customer, offer link/merge.
- If proof duplicate exists, block or require review.
- If role needs accounting account, show setup state until DEA resolver creates mapping.

## Create Sale

Current:

- EXISTING: Sales invoice create/detail and invoice item HTMX flows exist.
- EXISTING: Sales currently references `Customer`.

Improved flow:

1. User opens Sales.
2. User clicks New Sale.
3. Select/create Party with Customer role.
4. Add items via HTMX line editor.
5. Inventory availability validates per item.
6. User saves draft.
7. User approves/posts sale.
8. DEA creates voucher and immutable journal entry.
9. Inventory movement records stock outward.
10. Detail page shows accounting and inventory impact.

Edge cases:

- Missing party account mapping: show setup action.
- Insufficient stock: show item-level error.
- Period locked: posting blocked by DEA with clear period message.
- Posted sale correction: reverse and repost, never mutate posted journal lines.

## Create Purchase

Current:

- EXISTING: Purchase create/detail/item/payment flows exist.
- EXISTING: Purchase currently references `Customer` as supplier.

Improved flow:

1. User opens Purchases.
2. User clicks New Purchase.
3. Select/create Party with Supplier role.
4. Add purchase items.
5. Generate stock inward.
6. Post accounting voucher.
7. Detail page shows items, payment allocations, inventory, accounting impact.

Edge cases:

- Supplier missing payable account mapping.
- Duplicate HUID/serial.
- Rate missing.
- Period locked.

## Create Loan

Current:

- EXISTING: Girvi loan create, preview, detail, transition, payment, release, custody, print flows exist.
- EXISTING: Girvi uses `Customer` borrower/lender and `GivenLoan`/`TakenLoan`.

Improved flow:

1. User opens Loans.
2. User clicks New Given Loan or New Taken Loan.
3. Select/create Party with Borrower or Lender role.
4. Add collateral items.
5. System validates current rates and collateral value.
6. Save draft.
7. Approve.
8. Disburse through DEA posting service.
9. Detail page shows collateral, custody, repayments, accounting, notices, timeline.

Edge cases:

- Missing rates/rate source: setup blocker with direct link.
- Loan amount exceeds collateral value: item-level validation.
- Missing voucher type or party account: self-heal or setup action.
- Period locked: disbursal blocked by DEA.

## Receive Repayment

Current:

- EXISTING: Girvi loanpayment views and templates exist.
- EXISTING: DEA posting rules exist for loan receipts/repayments.

Improved flow:

1. User opens Loan detail.
2. Click Receive Repayment.
3. Modal/drawer shows principal, interest, charges, payment mode.
4. User previews allocation.
5. Submit posts receipt voucher.
6. Loan balance and accounting impact update through HTMX.

Edge cases:

- Overpayment requires confirmation or advance treatment.
- Interest waiver requires permission.
- Posted repayment correction requires reversal.

## Post Voucher To Accounting

Current:

- EXISTING: DEA voucher hub/list/detail/post URLs exist.
- EXISTING: Business docs can post through rules.

Improved flow:

1. User creates or triggers business document.
2. DEA creates draft voucher.
3. User/command validates voucher.
4. Posting engine checks period lock, rule registration, balanced lines, idempotency.
5. Posted voucher creates immutable journal entry.
6. Source document links to voucher/journal entry.

Edge cases:

- Missing posting rule.
- Period locked.
- Imbalanced voucher.
- Duplicate fingerprint.
- Missing subledger/party account.

## View Ledger / Journal Impact

Current:

- EXISTING: DEA ledgers, accounts, journal entries, transactions, voucher detail pages exist.
- EXISTING: Sale/purchase/loan detail pages have inconsistent accounting impact visibility.

Improved flow:

1. User opens source document.
2. Accounting Impact tab shows voucher, journal entry, ledger lines, account/subledger lines.
3. User can open full voucher or journal entry.
4. Accountant can trace from report -> ledger -> journal entry -> voucher -> source document.

## Stock Inward / Outward

Current:

- EXISTING: Product stock and movement services exist.
- EXISTING: Purchase generates stock; Sales moves stock outward.

Improved flow:

- Purchase inward: Purchase -> Items -> Generate Stock -> Inventory Movement -> Accounting.
- Sale outward: Sale -> Items -> Stock Selection -> Inventory Movement -> Accounting.
- Manual adjustment: Inventory -> Adjustment -> Reason -> Approval if material -> Movement -> Accounting if value changes.

Edge cases:

- Duplicate serial/HUID.
- Negative stock.
- Posted document reversal.
- Stock and accounting mismatch.

## Commodity / Gold / Silver Settlement

Current:

- EXISTING: Gold/silver rates and metal balances exist in Sales/Purchase/Product/Girvi.
- PROPOSED: Dedicated commodity settlement UI is not clearly present.

Improved flow:

1. User opens Commodity Settlement.
2. Select party, metal, quantity/weight, rate, settlement mode.
3. System previews metal ledger and accounting impact.
4. Post voucher and commodity movement.
5. Show settlement detail and audit trail.

## Reports And Audit Trail

Current:

- EXISTING: DEA financial reports.
- EXISTING: Girvi reports.
- EXISTING: Contact report.
- EXISTING: AuditLog in orgs and accounting audit events in DEA.

Improved flow:

1. User opens Reports hub.
2. Choose report group.
3. Apply filters.
4. Drill down to document/source.
5. Export with permission check.
6. Audit trail shows who created, approved, posted, reversed, edited, and exported.
