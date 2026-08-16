---
status: active
owner: project
updated: 2026-08-14
tags: [implementation, tenancy, constraints, uniqueness, foreign-keys, rls]
related: [django-tenants-removal-phase0-inventory.md, ../adr/2026-08-14-shared-schema-workspace-rls-tenancy.md, ../plans/django-tenants-removal.md]
---

# Django-Tenants Removal Integrity Inventory

## Scope And Method

This inventory was generated from the live Django model registry. It counts
field uniqueness, `unique_together`, `UniqueConstraint`, concrete tenant-model
foreign keys, generic relations, and unmanaged models. It defines the
constraint surface that must be reviewed when schema-local tables become shared.

## Summary

| Metric | Count |
|---|---:|
| Tenant-app models | 212 |
| Models containing one or more uniqueness rules | 166 |
| Field/tuple/constraint uniqueness rules | 252 |
| Tenant-model foreign-key edges | 358 |
| Cross-tenant-app foreign-key edges | 28 |
| Generic foreign-key/relation surfaces | 10 |
| Unmanaged balance-view models | 3 |

These counts are a baseline, not a mechanical instruction to prefix every
constraint or index with Workspace. Each rule must be classified as platform
global, Workspace-local, parent-scoped, or globally immutable identity.

## Per-App Constraint Surface

| App | Models with uniqueness | Rules | Tenant FKs | Cross-app FKs |
|---|---:|---:|---:|---:|
| contact | 6 | 8 | 7 | 1 |
| dea | 32 | 42 | 78 | 10 |
| girvi | 12 | 17 | 33 | 7 |
| loans | 69 | 123 | 145 | 3 |
| notify | 4 | 4 | 6 | 2 |
| notify_v2 | 6 | 7 | 14 | 2 |
| party | 9 | 9 | 10 | 0 |
| product | 13 | 17 | 33 | 2 |
| rates | 1 | 1 | 1 | 0 |
| standalone_accounting | 14 | 24 | 31 | 1 |
| terms | 0 | 0 | 0 | 0 |
| **Total** | **166** | **252** | **358** | **28** |

## Uniqueness Conversion Policy

### Add Workspace directly

Identifiers currently unique only because of schema locality must become
Workspace-scoped, including:

- Party code and Party sequence keys;
- Contact identity rules where the parent alone does not already carry the
  complete Workspace scope;
- Girvi license, loan, release, series, sequence, repayment-reference, outbox,
  and accrual identities;
- DEA account/ledger/document numbers, period ranges, business-event source
  references, voucher fingerprints, commodity/exposure/fixing identifiers, and
  idempotency keys;
- Product category/product/variant/SKU/code/serial/HUID and pricing-tier names;
- Rates timestamp/purity identity and payment terms;
- legacy Notify codes/group names and Notify v2 event/template/policy/job/
  provider identities;
- standalone accounting organization integration keys where provider scope is
  not provably global.

### Parent scope may remain structurally sufficient

Rules such as `(voucher, line_no)`, `(loan, version)`, `(schedule, sequence)`,
or `(layout, version)` are semantically parent-scoped. They need not always add
Workspace to the uniqueness tuple if a composite same-Workspace FK proves the
parent relationship and the child has direct Workspace ownership.

The acceptance condition is both:

1. the uniqueness meaning is correct; and
2. the database proves the child's Workspace equals the parent's Workspace.

### Review before changing

- public IDs may intentionally be globally unique for unguessable routing;
- provider message/event IDs may be provider-global or Workspace-local;
- UUID accounting identities are globally collision-resistant but still need
  Workspace ownership and RLS;
- one-to-one reversal/evidence links may stay globally unique while also
  receiving composite same-Workspace protection.

## Cross-App Foreign-Key Graph

These 28 concrete edges establish the app conversion dependency order.

### Party and Contact foundations

- `contact.Customer.party -> party.Party`
- DEA Account/Balance, CommodityAccount, ExposureLine, PartyAccountMapping,
  Purchase/Sales invoices, and RateFixing reference Contact or Party.
- Girvi Given/Taken loans and Release reference Contact and/or Party.
- Loans PawnLoan, FundingLoan, and communication consent reference Party.
- legacy Notify and Notify v2 recipients reference Contact and/or Party.
- Product Price references Contact.
- standalone accounting ExternalAccount references Party.

Party and Contact must therefore be converted before the dependent financial,
loan, inventory-pricing, and notification aggregates.

### Accounting and inventory edges

- `girvi.LoanInterestAccrual.journal_entry_voucher -> dea.JournalEntryVoucher`
- `product.StockTransaction.journal_entry -> dea.JournalEntry`

The Girvi and inventory cutovers cannot be complete until their accounting
links have same-Workspace database protection.

### Product collateral edge

- `girvi.LoanItem.item -> product.ProductVariant`

This legacy Girvi relationship requires Product ownership before Girvi's final
shared-schema gate, or a deliberate model-boundary replacement.

## Composite Same-Workspace Protection

For a security-critical parent relation:

```text
Parent UNIQUE (workspace_id, id)

Child workspace_id NOT NULL
Child parent_id NOT NULL
FOREIGN KEY (workspace_id, parent_id)
  REFERENCES Parent(workspace_id, id)
```

Keep the ordinary Django FK for ORM navigation. Add the composite constraint
through the approved migration operation. Required first-wave aggregates:

- Party children and Party-to-Party relationships;
- Customer children and relationships;
- PawnLoan and FundingLoan children/evidence;
- GivenLoan/TakenLoan children/evidence;
- Voucher/Journal/Transaction chains;
- Accounting Book/Period/Ledger/Voucher/OpenItem chains;
- Product/Variant/Stock/Transaction chains;
- notification Event/Job/Artifact/Attempt/Receipt chains;
- document Layout/Profile/Revision/Assignment/Issue chains.

## Generic Relation Risks

The registry exposes ten generic surfaces:

| Model field | Kind | Required protection |
|---|---|---|
| `dea.Voucher.business_doc` | Generic FK | Direct Workspace, source service validation, financial trigger/check |
| `dea.PaymentVoucher.source_document` | Generic FK | Direct Workspace and allowed source-type validation |
| `dea.CommodityMovement.source` | Generic FK | Direct Workspace and source consistency validation |
| `dea.ExposureLine.source` | Generic FK | Direct Workspace and source consistency validation |
| `dea.SalesInvoiceVoucher.payments` | Generic relation | Payment source Workspace proof |
| `dea.PurchaseInvoiceVoucher.payments` | Generic relation | Payment source Workspace proof |
| `girvi.LoanChangeLog.loan` | Generic FK | Direct Workspace and allowed loan type validation |
| `girvi.GivenLoan.payments` | Generic relation | Payment source Workspace proof |
| `girvi.TakenLoan.payments` | Generic relation | Payment source Workspace proof |
| `notify.NotificationItem.content_object` | Generic FK | Direct Workspace and allowed source validation |

PostgreSQL cannot express a normal FK to an arbitrary ContentType target.
Security-critical generic links therefore require all of:

1. direct Workspace ownership on the generic-link row;
2. service validation against the resolved source;
3. a bounded allowed ContentType set where practical;
4. database triggers for financial source relationships;
5. adversarial tests using a valid foreign-Workspace object ID.

The integer object ID is not globally meaningful across Workspace ownership;
`(workspace_id, content_type_id, object_id)` is the minimum shared-table
identity for uniqueness and lookup.

## Unmanaged/View Models

The three unmanaged models are:

- `dea.LedgerBalance` -> `ledger_balances`
- `dea.AccountBalance` -> `account_balances`
- `product.StockBalance` -> `stock_balance`

Their underlying views must:

- project a physical `workspace_id` column;
- include Workspace in every grouping/join key;
- remain subject to source-table RLS;
- avoid `SECURITY DEFINER` unless separately reviewed;
- never use a Workspace-ambiguous one-to-one primary key;
- have cross-Workspace aggregate tests under the runtime role.

RLS cannot be enabled directly on an ordinary PostgreSQL view. Security follows
from invoker rights and RLS-protected base tables, so view ownership and role
configuration are part of the gate.

## Index Review Policy

RLS adds an implicit Workspace predicate to tenant reads. Index review should:

1. retain indexes supporting global immutable/public IDs where needed;
2. lead common tenant worklists with `workspace_id`;
3. include Workspace in unique indexes when uniqueness is Workspace-local;
4. avoid duplicating a composite unique index with an equivalent plain index;
5. validate actual query plans for accounting, loan, risk, notification, and
   inventory worklists.

Initial high-value families are:

- Party `(workspace_id, status, party_code/name)`;
- Pawn/Girvi loans `(workspace_id, state/release, date, borrower)`;
- obligations `(workspace_id, status, due_date)`;
- vouchers/journals/transactions by Workspace, status/date, period, ledger, and
  account;
- stock transactions by Workspace, stock/item, and date;
- notification jobs by Workspace, status, and schedule;
- risk snapshots/alerts by Workspace and state.

## Per-App Conversion Gate

An app's integrity conversion is complete only when:

- every concrete model has direct non-null ownership;
- every one of its existing uniqueness rules has an explicit disposition;
- all tenant FK edges have same-Workspace protection proportional to risk;
- all cross-app dependencies point only to already converted aggregates;
- generic links pass foreign-Workspace object tests;
- SQL views/triggers are Workspace-aware;
- indexes support verified common queries;
- RLS registry and database metadata agree.
