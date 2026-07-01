---
status: active
owner: project
updated: 2026-07-01
tags: [domain, party, contact, accounting]
related: [../adr/2026-06-18-party-domain-model.md, contact.md, accounting.md, ../flows/dea-posting-flow.md]
---

# Party

Party is the long-term model for any business entity that interacts with a tenant workspace.

Party is implemented as a tenant app at `apps.tenant_apps.party`. It now has model, seed, bridge, DEA account mapping, posting resolver integration, and a tenant UI surface.

Canonical role types are seeded tenant data. They are created by `seed_party_roles` and included in tenant default seeding.

The compatibility bridge from `contact.Customer` to Party is nullable and one-to-one. Existing workflows continue using `Customer` until each operational app is migrated.

Existing tenant customers have been backfilled into Party records. Backfill is idempotent and can be rerun with `backfill_parties_from_customers --schema <schema> --only-missing`.

Operational documents are migrating to Party through nullable shadow foreign keys while legacy Customer fields remain in place. The current prioritized shadow-link scope covers Girvi `GivenLoan.borrower_party`, `TakenLoan.lender_party`, DEA sales/purchase invoice vouchers, legacy `notify.Notification.party`, and `notify_v2.NotificationRecipient.party`. Approval is intentionally skipped until approval workflows become a priority again.

The tenant Party UI is available under `/party/`. It exposes party list/search/filter, create/edit, detail tabs, role add/end, profile photo camera capture/upload/removal, editable contact/address/KYC/document data, party relationships, DEA account mapping visibility, and linked customer loan activity.

Party list export is available to Owner/Admin users as filtered CSV/XLSX. The first export shape is intentionally flat: Party identity fields, primary phone/email, tax identifiers, active roles, status, relation text, timestamps, and legacy customer linkage. Child profile data such as addresses, identifiers, documents, and detailed contact methods should remain separate exports instead of being flattened into one denormalized spreadsheet.

Party codes are tenant-local stable identifiers. Normal Party creation can leave the code blank; the system generates sequential codes such as `P-000001`. Manual/custom codes remain supported for imports, backfills, and explicit operator control. Legacy Customer bridge records use `CUST-000001` style codes.

Phone, mobile, and WhatsApp contact values are validated as Indian phone numbers and stored in E.164 format. Email and website contact values are validated before save.

Party profile identity supports textual relation labels such as `S/o`, `D/o`, `C/o`, `W/o`, `H/o`, `F/o`, `P/o`, and `O/o` with a related person name. This is separate from structured Party-to-Party relationships because the related person may not exist as a Party record.

Party duplicate merge archives the source Party rather than deleting it. Non-conflicting roles, contact methods, addresses, identifiers, documents, relationships, and DEA account mappings are moved to the target Party. Merges stop when both records are linked to legacy customers, when same-type identifiers have different values, or when active DEA account mappings overlap for the same role, purpose, and event key.

Examples include customers, suppliers, borrowers, lenders, retailers, wholesalers, manufacturers, employees, agents, brokers, banks, transporters, insurance providers, and government bodies.

## Core Concept

A Party is the identity. Roles explain why that party participates in a workflow.

One real-world entity can have many roles:

- A customer can also be a supplier.
- A borrower can also buy products.
- A bank can be a lending party and also have separate DEA bank accounts.
- An employee can also receive expenses, advances, or commission.

Parties can also be related to other parties, such as contact person, employer, employee, broker, agent, related business, family, or other relationship types.

## Party Types

Party type describes the legal/natural form of the entity:

- Individual
- Organization
- Bank
- Government body
- Internal workspace entity
- Other

Party type should not be used to infer accounting treatment.

## Party Roles

Roles should be seeded database records with stable system keys. Canonical roles include:

- `CUSTOMER`
- `SUPPLIER`
- `BORROWER`
- `LENDER`
- `RETAILER`
- `WHOLESALER`
- `MANUFACTURER`
- `EMPLOYEE`
- `AGENT`
- `BROKER`
- `BANK`
- `TRANSPORTER`
- `INSURANCE_PROVIDER`
- `PORTAL_CUSTOMER`

Retail and wholesale are customer segments unless a workflow specifically needs them as roles.

## Accounting Relationship

Party does not directly decide the DEA account. The business event decides which party account is required.

Account resolution should use:

- party
- role
- accounting purpose
- business event type

Examples:

- Sale to customer -> customer receivable account
- Purchase from supplier -> supplier payable account
- GivenLoan disbursal -> borrower loan receivable account
- TakenLoan repayment -> lender loan payable account
- Customer advance -> advance from customer account
- Supplier advance -> advance to supplier account

Gross balances should remain visible by account purpose. Net exposure can be shown in reports, but accounting should not collapse receivables and payables into one account.

## Relationship With Contact

`contact.Customer` remains the current compatibility model. It should be linked to Party during migration through a nullable one-to-one bridge.

Current `customer_type` values should map as follows:

- Retail -> Party role `CUSTOMER`, segment `RETAIL`
- Wholesale -> Party role `CUSTOMER`, segment `WHOLESALE`
- Supplier -> Party role `SUPPLIER`

The long-term direction is for operational apps to reference Party directly, while legacy Customer references remain readable until migration is complete.

During the shadow-FK phase, new document saves populate Party from `Customer.party` when the bridge exists. Posting account resolution prefers the explicit Party shadow field and falls back to Customer-based resolution for older or unbridged records.

Girvi given-loan creation has moved to a Party-first UI. Users choose an active Party as borrower; on save, the compatibility bridge creates or reuses the linked `Customer`, assigns the borrower role, and stores both the legacy borrower and `borrower_party` links on the loan.

## Tenant Scope

Party is a tenant app concept. Party records are isolated by tenant schema.

The same real-world person in two workspaces is represented by separate Party records. Cross-tenant identity linking should only happen later through explicit portal/user identity design.

## Portal Distinction

- Party: business entity.
- User: authentication identity.
- Workspace member: internal user with workspace permissions.
- Customer portal account: external user linked to a party with limited access.

`PartyPortalAccess` is the explicit tenant grant from a user to a Party. Portal access must not be inferred from matching email or phone values. Tenant `/portal/...` routes resolve an active `PartyPortalAccess`, validate the Party is active, and expose read-only dashboard, loans, invoices, payments, documents, and statements filtered to that Party.
