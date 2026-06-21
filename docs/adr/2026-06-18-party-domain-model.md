---
status: accepted
owner: project
updated: 2026-06-18
tags: [adr, party, contact, accounting, architecture]
related: [../domain/party.md, ../domain/contact.md, ../domain/accounting.md, ../GLOSSARY.md]
---

# Adopt Party As The Long-Term External Entity Model

## Context

Rokkad currently uses `contact.Customer` as the main external entity model. That model has a single `customer_type` value such as retail, wholesale, or supplier. Several apps depend on it directly, including Girvi, DEA, Sales, Purchase, Approval, and Notify.

This is too narrow for the product direction. A real-world person or organization can be a customer, supplier, borrower, lender, agent, bank, employee, manufacturer, broker, transporter, or portal user at the same time.

The accounting model also needs more precision. A single party can require several subledger accounts for different accounting purposes, such as customer receivable, supplier payable, borrower loan receivable, lender loan payable, customer advance, and supplier advance.

## Decision

Introduce a new tenant app named `party` as the long-term model for external and internal business entities.

`contact.Customer` will remain during migration for backward compatibility. The new Party model will be introduced in parallel and linked from Customer before operational documents are migrated.

Party roles will be seeded database records with stable system keys, not only static choices. Tenants may later extend role labels or add non-system roles, but posting and workflow code should use canonical role keys.

Accounting account selection must be based on business event, party role, and accounting purpose. It must not depend on party identity alone.

## Recommended Policies

- Banks may be parties when they appear as counterparties, but DEA bank/cash accounts remain accounting/payment instruments.
- Retail and wholesale are customer segments, not party types.
- Suppliers, customers, borrowers, lenders, employees, banks, brokers, and agents are roles.
- PAN, GSTIN, phone, and name duplicates should be detected and reviewed before strict uniqueness is enforced.
- Employees can be parties when they receive/pay money or appear on business documents.
- A portal account is a user identity linked to a party; it is not the same as a workspace member.

## Consequences

- A single Party can have multiple active roles.
- A single Party can have multiple DEA accounts by role and purpose.
- Existing Customer-based workflows can continue while migration proceeds.
- New accounting-sensitive work should prefer party-aware account resolution.
- Cross-app references should move toward facades/selectors instead of direct Customer imports.

## Migration Direction

1. Create the `party` tenant app.
2. Seed canonical `PartyRoleType` records.
3. Add a nullable `Customer.party` bridge.
4. Backfill existing customers into parties and roles.
5. Add a DEA party account resolver with fallback to existing Customer accounts.
6. Migrate Girvi first, then Sales and Purchase.
7. Retire direct `customer_type`-based accounting decisions after replacement paths are stable.
