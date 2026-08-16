---
status: active
owner: project
updated: 2026-08-14
tags: [plan, tenancy, django-tenants, rls, migration]
related: [../adr/2026-08-14-shared-schema-workspace-rls-tenancy.md, ../implementation/tenancy-architecture-audit-rls-vs-django-tenants.md, ../STATUS.md]
---

# Django-Tenants Removal And Shared-Schema Migration

## Objective

Remove `django-tenants` and every schema-per-tenant runtime assumption. Preserve
Workspace, Membership, RBAC, subscriptions, domain routing, archive semantics,
and domain/accounting evidence as ordinary SaaS concepts. Replace schema
isolation with explicit Workspace ownership and PostgreSQL RLS.

Runtime implementation is authorized by the accepted related ADR.

## Definition Of Done

- one shared application schema;
- ordinary global Workspace and WorkspaceDomain models;
- direct `workspace_id NOT NULL` on every tenant-owned concrete table;
- forced RLS and restricted runtime role;
- same-Workspace relational integrity on critical aggregates;
- explicit HTTP/task/command context;
- standard Django PostgreSQL backend, migrations, and test runner;
- no schema creation, cloning, switching, iteration, or deletion;
- clean development database build and complete adversarial isolation proof;
- `django-tenants` removed from requirements and runtime.

## Phase 0: Decision, Inventory, And Baseline

### Work

1. Accept the related ADR.
2. Freeze `Workspace.id` as bigint and adopt `Workspace.slug` as the routing key.
3. Generate machine-readable inventories of registered models, tenant tables,
   uniqueness, indexes, raw SQL objects, tasks, commands, files, caches, and
   schema references.
4. Identify seed/reference data that must survive a database rebuild.
5. Record current focused test baselines without treating schema isolation as
   proof of the target.

### Gate

- inventory accounts for every concrete tenant model and SQL object;
- no unresolved required development data;
- ADR accepted.

## Phase 1: Isolation Foundation

### Work

1. Add a deliberately small `apps.tenancy` infrastructure package.
2. Add abstract `WorkspaceOwnedModel`.
3. Add transaction-owning `workspace_context(workspace_id)`.
4. Add RLS and composite-constraint migration operations.
5. Add tenant-model registry and PostgreSQL system checks.
6. Define migration-owner and restricted runtime roles for development and CI.
7. Prove context and RLS behavior on a disposable/simple tenant model.

### Tests

- missing/invalid context;
- all four DML operations across two Workspaces;
- nested conflicting context;
- reused connection;
- exception and rollback;
- raw SQL and bulk ORM operations;
- owner/runtime role metadata.

### Gate

The proof passes under the actual restricted runtime role.

## Phase 2: Global SaaS Foundation

### Work

1. Replace `Company(TenantMixin)` with ordinary Workspace model state.
2. Replace `DomainMixin` with ordinary WorkspaceDomain.
3. Separate immutable slug from legacy schema name.
4. Preserve Membership, Role, invitations, subscriptions, onboarding, and
   selected-Workspace preference.
5. Replace schema provisioning/archive/delete behavior with row lifecycle.
6. Preserve domain and `/w/<slug>/` routing without schema switching.

### Gate

Global authentication, Workspace creation/selection/archive/restore,
Membership, invitation, and subscription tests pass without schema operations
in the target test setup.

## Phase 3: Party And Contact Proof Aggregate

### Work

Convert Party and Contact together, including children, relationships, portal
grants, identifiers, documents, and number sequences. Add direct ownership,
Workspace uniqueness, composite constraints, RLS, explicit file paths, and
two-Workspace tests.

### Gate

No Party/Contact query or relationship can cross Workspace boundaries through
ORM, raw SQL, bulk operations, portal paths, admin, or imports.

## Phase 4: Simple Workspace Configuration

Convert Terms, Rates, and tenant-owned configuration/seeding. Keep global
control-plane preferences global and application-authorized.

### Gate

No schema argument or connection-schema read remains in these apps.

## Phase 5: Product And Inventory

Convert the product catalog, pricing, attributes, stock, stock items,
transactions, statements, and balance views as one dependency unit.

### Gate

- inventory SQL views project/group by Workspace;
- cross-Workspace stock/product references fail at the database;
- accounting-linked stock movements share Workspace;
- reconciliation totals remain correct.

## Phase 6: Accounting

### DEA unit

Convert periods, ledgers, accounts, vouchers, lines, journals, transactions,
statements, numbering, party mappings, commodities, assets, prepaids, banking,
audit, generic source links, and SQL balance views.

### Standalone accounting unit

Make AccountingOrganization explicitly Workspace-owned and convert its Book,
Period, Ledger, Voucher, transaction, source delivery, sequence, and open-item
aggregates. `external_tenant_key` may remain an integration key, never an
isolation boundary.

### Gate

- mixed-Workspace posting cannot construct or persist evidence;
- reversals cannot cross Workspace;
- period close is Workspace/Book local;
- SQL reports never aggregate Workspaces;
- accounting immutability and reconciliation suites pass.

## Phase 7: Girvi

Convert in aggregate order: license/series/numbering; Given/Taken loans and
collateral; repayment/accrual/release/renewal; custody/statements; outbox/audit;
templates and files. Rewrite triggers and scheduled entrypoints.

### Gate

All Girvi runtime, commands, and tasks use explicit Workspace identity and pass
cross-Workspace financial/custody tests.

## Phase 8: Loans

Convert in aggregate order:

1. license/series/policies/numbering;
2. PawnLoan origination and immutable evidence;
3. events/outboxes/accruals/schedules/obligations;
4. release/auction/renewal/custody/verification;
5. layouts/profiles/assets/issues;
6. FundingLoan and pledge/return aggregates;
7. monitoring/risk/communication.

Add a physical Workspace column to every child/evidence table; Python
properties that derive ownership do not satisfy the gate. Rewrite every Loans
trigger with Workspace validation.

### Gate

Every Loans table is registered and forced-RLS protected, all aggregate
relationships are same-Workspace, and accounting/Notify adapters preserve the
same Workspace.

## Phase 9: Notify, Jobs, Commands, Admin, Files, And Caches

1. Convert Notify v2 policies, recipients, templates, events, jobs, artifacts,
   attempts, receipts, and Workspace provider integration.
2. Keep legacy Notify only under its accepted retirement plan, but make its
   surviving rows explicitly Workspace-owned and RLS protected.
3. Require `workspace_id` for tenant tasks and commands.
4. Replace tenant storage with `workspaces/<id>/...` paths.
5. Replace schema cache keys and logging context with Workspace identity.
6. Separate global admin from explicit Workspace admin; introduce an audited
   privileged platform database path only for proven cross-Workspace needs.

### Gate

No worker, command, admin, provider callback, file, or cache path relies on
ambient schema state.

## Phase 10: Clean Migration Baseline And Database Rebuild

1. Confirm all required reference data is deterministic.
2. Remove/replace selected schema-era project migration files on this branch.
3. Generate clean initial migrations with ownership, constraints, SQL objects,
   and RLS operations.
4. Initialize migration/runtime roles.
5. Recreate the development and test databases.
6. Load reviewed seed data and adversarial Workspace fixtures.

### Gate

A fresh checkout builds the complete database using ordinary Django migrations
and the restricted runtime role can run the application.

## Phase 11: Remove Django-Tenants

Remove the package, backend, router, mixins, app split, settings, schema
middleware/context, test runner, storage/finder, cache/log helpers, provisioning,
cloning, deletion, `migrate_schemas`, schema commands, compatibility aliases,
and obsolete tests/docs.

### Gate

Repository search and import checks find no unintended live dependency.

## Phase 12: Completion Audit

Run requirement-by-requirement evidence checks:

- every registered tenant model matches PostgreSQL RLS metadata;
- no context means no data;
- SELECT/INSERT/UPDATE/DELETE isolation;
- raw SQL, bulk ORM, related loading, aggregates, annotations and subqueries;
- signals, admin, imports, tasks, commands, reused connections and rollback;
- composite relationship rejection;
- accounting and inventory reconciliation;
- clean database build and full relevant test suite;
- current documentation contains no schema-tenancy runtime guidance.

The goal is complete only when all evidence passes and `django-tenants` is
absent from runtime and dependencies.

## Explicit Non-Goals

- preserving production or development tenant rows;
- maintaining dual schema/shared runtimes;
- rewriting domain applications unrelated to ownership;
- merging DEA and standalone accounting;
- merging Party and legacy Contact;
- retiring Girvi or legacy Notify outside their accepted plans;
- encoding RBAC or subscription rules into RLS policies.

## Current State

Execution is active on `no-tenants-no-acc`. The first authoritative Phase 0 registry/coupling
baseline is recorded in
`docs/implementation/django-tenants-removal-phase0-inventory.md`: 212 tenant-app
models are registered, 35 have direct Workspace ownership, and 177 still depend
on schema or parent-derived ownership. The companion integrity inventory records
252 uniqueness rules, 358 tenant foreign-key edges, 28 cross-app edges, 10
generic relation surfaces, and three unmanaged balance views.
