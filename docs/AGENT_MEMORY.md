---
status: active
owner: project
updated: 2026-06-17
tags: [agents, context, architecture]
related: [README.md, STATUS.md, constitution.md, domain/accounting.md, implementation/dependency-policy.md]
---

# Agent Memory

This document stores durable project context for AI agents. The root [AGENTS.md](../AGENTS.md) defines the operating rules; this file explains what the system is and how to reason about it.

## Project Identity

Rokkad is a tenant-aware SaaS mini ERP for small businesses, especially jewellery, pawn/loan, commodity, inventory, sales, and purchase businesses.

Accounting is the central source of truth. Sales, purchases, loans, inventory, and commodity transactions are business documents that produce accounting, stock, and commodity ledger effects.

The product must feel document-centric, not module-centric.

## Core Mental Model

Business Event
-> Source Document
-> Posting Engine
-> Voucher
-> Journal Entry
-> Financial Ledger
-> Inventory Ledger
-> Commodity Ledger
-> Reports

Users should create business documents, not manual journal entries.

## Core Modules

- Accounting
- Loans / Girvi
- Inventory
- Sales
- Purchase
- Commodity management
- Workspace management
- Subscription management
- Authorization
- Onboarding
- Customer portal
- Notifications

## Design Principles

1. Accounting is central.
2. Business documents create vouchers.
3. Vouchers post journal entries.
4. Journal entries are immutable.
5. Corrections happen through reversals.
6. Every accounting entry must link back to its source document.
7. Commodity is tracked as inventory/position, not as normal currency.
8. Multitenancy uses workspace/tenant isolation.
9. UI should follow business workflows, not database tables.
10. Normal users work with documents; accountants can inspect vouchers, journal entries, and ledgers.

## Important Domain Concepts

Use a generic party model where possible:

- Customer
- Supplier
- Broker
- Employee

A party can have multiple roles.

Use source documents:

- Sale
- Purchase
- Loan
- Receipt
- Payment
- Expense
- Stock Adjustment
- Commodity Contract
- Commodity Settlement

Do not make accounting models depend directly on UI forms. UI creates documents; posting rules create vouchers and journal entries.

## Accounting Architecture

Other domains should not bypass DEA for ledger effects.

Business documents are not ledger entries. Posting converts business intent into `Voucher`, `VoucherLine`, and `JournalEntry`.

Use immutable journal entries.

If a posted document changes:

1. Reverse the previous journal entry.
2. Create a new corrected journal entry.

Do not edit posted journal lines in place.

Use a posting engine:

- `PostingContext`
- `PostingRuleRegistry`
- `PostingRule`
- `PostingBundle`
- `Voucher`
- `VoucherLine`
- `JournalEntry`
- `LedgerLine`
- `AccountLine`

Each document should expose `get_economic_payload()` or equivalent structured data for fingerprinting and idempotency.

## Architecture Rules

- Other apps should import DEA through `apps.tenant_apps.dea.facade`.
- Other apps should import Girvi cross-domain reads through `apps.tenant_apps.girvi.facade` or selectors.
- Girvi lifecycle work should prefer command/use-case services over model methods or large view logic.
- Contacts should not directly know Girvi internals for loan summary data.
- Tenant seed/setup failures should surface as actionable setup messages, not silent zero values.
- Posting logic belongs in DEA posting services/rules, not views or templates.

## Multi-tenant SaaS Assumptions

The app is workspace-based.

A user can:

- own multiple workspaces
- belong to multiple workspaces
- switch workspace from navbar

Workspace features:

- members
- roles
- invitations
- subscription
- settings

All business data belongs to a workspace/tenant context.

Migration execution should respect the `django-tenants` split: tenant app changes use `migrate_schemas`, and shared app changes use `migrate_schemas --shared`.

## UX Memory

The home dashboard should be action-first:

- Create Sale
- Create Purchase
- Create Loan
- Receive Payment
- Make Payment
- Stock Adjustment
- Commodity Settlement

Every source document should follow a consistent page pattern:

- Overview
- Payments / Settlements
- Inventory Impact
- Commodity Impact
- Accounting Impact
- Attachments
- History / Timeline

Prefer timelines and activity feeds over isolated reports.

## Navigation Memory

Main sidebar direction:

- Home
- Activities
- Parties
  - Customers
  - Suppliers
- Operations
  - Sales
  - Purchases
  - Loans
  - Receipts
  - Payments
  - Commodity
- Inventory
- Accounting
- Reports
- Settings

## Tech Preferences

Backend:

- Django
- PostgreSQL
- HTMX
- Bootstrap 5
- `django-template-partials` where useful

Prefer server-rendered UI with HTMX partial updates. Avoid heavy SPA complexity unless clearly necessary.

## Current Active Work

The active design track is Girvi event-driven DEA posting. See [plans/active](plans/active.md) and the archived full spec at [GIRVI_EVENT_DRIVEN_DEA_POSTING_SPEC](archive/girvi/GIRVI_EVENT_DRIVEN_DEA_POSTING_SPEC.md).

## Documentation Memory

- Canonical docs live under `docs/`.
- Historical source docs live under `docs/archive/`.
- Accepted architecture decisions live under `docs/adr/`.
- Every markdown file under `docs/` should start with frontmatter.
- Every doc should link back to `README.md` where practical for navigation.
