---
status: active
owner: project
updated: 2026-08-14
tags: [implementation, tenancy, inventory, django-tenants, rls]
related: [../adr/2026-08-14-shared-schema-workspace-rls-tenancy.md, ../plans/django-tenants-removal.md, ../STATUS.md]
---

# Django-Tenants Removal Phase 0 Inventory

## Purpose And Method

This is the authoritative pre-implementation inventory for the `no-tenants`
branch. It was generated from Django's live app registry under
`django_project.settings.dev`, then cross-checked with repository searches for
package imports, connection/request context, schema commands, SQL migrations,
and tenant test bases.

No model, migration, setting, dependency, or database state changed while
creating this inventory.

## Registered Tenant Model Baseline

| App label | Concrete models | Direct non-null `workspace` | Missing direct `workspace` |
|---|---:|---:|---:|
| contact | 6 | 0 | 6 |
| dea | 46 | 0 | 46 |
| girvi | 21 | 0 | 21 |
| loans | 73 | 34 | 39 |
| notify | 5 | 0 | 5 |
| notify_v2 | 11 | 1 | 10 |
| party | 10 | 0 | 10 |
| product | 21 | 0 | 21 |
| rates | 2 | 0 | 2 |
| standalone_accounting | 16 | 0 | 16 |
| terms | 1 | 0 | 1 |
| **Total** | **212** | **35** | **177** |

All 212 models are currently installed through `TENANT_APPS`. Even the 35
models with a Workspace FK still live in separate schemas and have no RLS.
Therefore none is complete under the target architecture.

## Models Missing Direct Ownership

### Contact

`Customer`, `CustomerPic`, `CustomerRelationship`, `Address`, `Contact`, and
`Proof`.

### Party

`Party`, `PartyAddress`, `PartyContactMethod`, `PartyIdentifier`,
`PartyDocument`, `PartyCodeSequence`, `PartyPortalAccess`, `PartyRelationship`,
`PartyRoleType`, and `PartyRole`.

### Girvi

`License`, `LicenseDocument`, `Series`, `LoanChangeLog`, `Release`,
`LoanTemplate`, `TemplateFrame`, `RepledgeHistory`, `GivenLoan`, `TakenLoan`,
`LoanItem`, `RepledgedLoanItem`, `LoanItemPic`, `LoanItemStorageBox`, `Statement`,
`StatementItem`, `LoanInterestAccrual`, `LoanRenewal`, `GirviNumberSequence`,
`LoanRepayment`, and `GirviPostingOutboxEvent`.

### DEA

All 46 registered DEA models lack direct ownership: accounting audit, account
and ledger types, accounts, ledgers, statements and balance-view models,
vouchers and lines, journal entries, ledger/account transactions, periods,
currency configuration and exchange rates, payment/expense/journal/sales/
purchase documents and lines, numbering, assets, prepaids, banking and
reconciliation, party mappings, commodities, movements, exposure, rate fixing,
and business-event drafts.

### Standalone accounting

`AccountingOrganization`, `AccountingBook`, `AccountingPeriod`,
`AccountingPeriodTransition`, `Ledger`, `ExternalAccount`,
`ExternalAccountClassification`, `Voucher`, `AccountingTransaction`,
`LedgerTransaction`, `AccountTransaction`, `TransactionBatch`,
`VoucherNumberSequence`, `AccountingSourceDelivery`, `OpenItem`, and
`OpenItemAllocation`.

### Product and inventory

All catalog, pricing, category/type, product/variant, attribute/assignment,
image, stock, movement, transaction, statement, item, and balance models.

### Rates, terms, and notifications

- `RateSource`, `Rate`, and `PaymentTerm`.
- Legacy Notify's five models.
- Notify v2's event type, policy, recipient, template, batch, event, job,
  artifact, attempt log, and webhook receipt. Only
  `WhatsAppCloudIntegration` has direct Workspace ownership.

### Loans children missing ownership

The 39 missing Loans models are primarily child/evidence rows:

- `LoanSeries`, `LoanNumberSequence`, `LoanPolicySnapshot`, `LoanChangeLog`,
  `LoanLicenseRevision`, and `LoanProductVersion`;
- Pawn collateral items, photos, labels, custody/storage movements;
- approval/disbursal snapshots, accounting events/outboxes, interest accruals
  and their lines, repayment allocation and principal opening/closing lines;
- release items/reversals, auction items/reversals, renewal reversals;
- document layout/profile revisions;
- Funding draft terms/collateral, cancellation, terms snapshot, event,
  pledge/return items and reversals;
- physical verification expectation, observation, and resolution rows.

Direct Workspace properties derived in Python from a parent are not physical
columns and do not satisfy RLS or composite-integrity requirements.

## Global And Control-Plane Boundary

The following remain outside tenant RLS because they are needed to resolve and
authorize Workspace context:

- `accounts.CustomUser` and authentication/allauth records;
- ordinary `Workspace`/current `Company`, WorkspaceDomain/current `Domain`,
  Membership, Role, invitations, and control-plane audit;
- subscriptions, billing, onboarding, and Workspace setup state;
- global/user preferences, sessions, sites, permissions, and content types.

Workspace-related global rows still require centralized Django authorization;
their exclusion from tenant RLS is deliberate, not missing ownership.

## Direct Package Coupling

Foundational live modules importing `django_tenants` include:

- Django settings and custom test runner;
- orgs models, middleware, admin, context, control-plane services, views, tests,
  and seed/parity/sequence commands;
- onboarding schema cloning;
- subscriptions services;
- accounting facade, pilot commands, and tests;
- DEA seeds/audits/tests;
- Girvi commands and tests;
- Loans services and tests;
- Party services/commands/tests;
- Product tests/commands;
- Rates middleware;
- tenant storage helper.

The package cannot be uninstalled until all live imports and settings are gone.

## Connection And Request Context Coupling

High-impact production modules reading or mutating ambient tenancy include:

- `apps.orgs.middleware_v2`: `set_schema_to_public`, `set_tenant`,
  `request.tenant`;
- `apps.orgs.tenant_context`: `request.tenant` authority;
- `apps.orgs.context_processors` and Django/template permission processors;
- DEA period, posting engine, reversal, audit/seed and access code;
- standalone accounting facade, feature flags, and pilot;
- Girvi loan views and access boundaries;
- Loans core context helper and services;
- Notify v2 delivery, readiness, admin, and callback views;
- Rates middleware;
- Party/Product/Notify access boundaries.

Test coupling is much broader than production coupling and must be removed as
part of each app conversion rather than in one final mechanical rewrite.

## Commands And Jobs

### Schema/control-plane commands

- `seed_public_defaults`
- `seed_tenant_defaults`
- `seed_all_tenants`
- `check_tenant_seed_parity`
- `reset_sequences`
- `check_saas_foundation`

### Tenant-domain commands requiring conversion

- standalone accounting evidence, integrity, recovery, and acceptance commands;
- DEA currency audit, core-ledger seed, and commodity seed;
- Girvi accrual, backup, statement import, sequence sync/reset, and legacy update;
- Loans readiness, risk, notice dispatch, product seed, and document diagnostics;
- Notify v2 WhatsApp readiness;
- Party backfill and role seed;
- Product inventory diagnostics and attribute migration.

Every surviving tenant command must require or deterministically enumerate
Workspace IDs and enter `workspace_context` for each bounded unit.

### Async task surfaces

- `apps.tenant_apps.contact.tasks.add` is a non-domain sample and should be
  deleted or excluded from tenancy design.
- Girvi export/reminder/accrual tasks currently rely on schema locality or a
  schema argument.
- Product price-update `.delay()` calls must carry Workspace identity.

No asynchronous caller may rely on the producer connection's context.

## Raw SQL Object Migration Inventory

The clean baseline must re-express and inspect SQL from:

### DEA

- `0003_create_ledger_balance_view`
- `0004_accountingperiod_currencyconfiguration_exchangerate_and_more`
- journal-column repair migrations `0018`-`0020`
- `0031_partyaccountmapping_and_more`

The balance views must project and group by Workspace.

### Product

- `0004_auto_views`
- `0011_pr6_unified_balance_views`

Inventory/stock projections and balances must be Workspace-partitioned.

### Girvi

- legacy statement bridge migrations `0018` and `0019`
- `0033_loanrepayment_immutability_guard`

Bridge SQL is a clean-baseline deletion candidate; the repayment invariant must
be re-expressed with Workspace checks.

### Loans

- funding guards in `0020`, `0025`, and `0026`;
- license and revision guards in `0027` and `0029`;
- collateral media/label guards in `0030` and `0049`;
- storage and verification guards in `0031` and `0032`;
- operational notice guard in `0033`;
- intake guards in `0051`.

Every retained trigger function must validate the new row's Workspace and all
referenced rows. Historical Collateral Intake SQL may be deleted only after the
removed model/runtime state is confirmed in the clean baseline.

### Standalone accounting and Contact

Standalone accounting migrations contain substantial `RunSQL` constraint and
immutability enforcement that must be preserved in the new initial migration.
Contact `0002` contains schema-era repair SQL and is a baseline deletion
candidate after its intended final state is modeled directly.

## Test Conversion Baseline

Exactly 76 currently discovered test modules directly use `TenantTestCase` or another
`django-tenants` test helper. Additional tests patch schema state or construct
`request.tenant` without inheriting a tenant test class.

Conversion rules:

1. rewrite tests with two ordinary Workspace fixtures;
2. use the real restricted runtime role for RLS security tests;
3. retain domain assertions but replace schema setup with `workspace_context`;
4. delete tests whose only contract is tenant-app registration or schema
   creation;
5. add direct SQL and cross-Workspace mutation tests for every converted
   aggregate.

## Seed And Development Data Dependencies

Repository-visible deterministic seed entrypoints exist for:

- public defaults;
- tenant defaults;
- core DEA ledgers and commodities;
- Party role types;
- default Loan products;
- subscription plans.

Before resetting migrations/database, Phase 0 must still inspect:

- what `seed_tenant_defaults` transitively invokes;
- fixture files and import/export resources;
- database dumps and rehearsal SQL in the repository root;
- dynamic preference defaults and any data encoded only in migrations;
- template-schema cloning assumptions in onboarding.

No dump is presumed required merely because it exists.

### Verified tenant seed closure

`seed_tenant_defaults` currently performs one transaction inside
`schema_context(schema_name)` and owns these baseline categories:

1. DEA core account types/ledgers through `seed_core_ledgers`;
2. DEA voucher types through `seed_voucher_types`;
3. Terms from `apps/tenant_apps/terms/fixtures/data.json`;
4. Rates from `apps/tenant_apps/rates/fixtures/metal_rates.json`;
5. Product movement types, Gold/Silver categories, product types, and attributes;
6. Party role types through `seed_party_roles`;
7. legacy Notify notice types and default templates;
8. Notify v2 Girvi event, policy, and template defaults.

The shared-schema replacement should be one idempotent
`seed_workspace_defaults(workspace_id)` service/command using
`workspace_context`. Fixture rows that become tenant-owned must receive the
target Workspace explicitly; ordinary `loaddata` without context/ownership is
not acceptable.

### Verified public seed closure

`seed_public_defaults` only calls `setup_permissions` inside the public schema.
Its replacement is an ordinary global idempotent seed without database context.

### Data encoded in migration history

The clean baseline must preserve only intended final reference state from:

- default org roles;
- DEA initial fixtures and later Girvi/expense voucher types and ledgers;
- Product initial reference fixtures;
- legacy Notify default notice types;
- Rate and Terms fixtures;
- later Party-link, lifecycle-normalization, regulatory, collateral, product,
  pricing, and opening-balance data migrations only where their final state is
  still required for a fresh development database.

Bridge/backfill migrations for old rows are not copied into the clean baseline.
Their desired final schema constraints belong in new initial migrations.

### Repository data artifacts

The repository root contains database dumps and rehearsal SQL. They remain
historical unless the owner explicitly identifies business/reference rows to
retain. Product contains several older JSON fixture sets in addition to the
current programmatic baseline; these require a KEEP/ARCHIVE/DELETE disposition
before migration reset to prevent accidental duplicate or stale seeding.

## Database Role Baseline

Current development configuration uses `DB_USER=postgres`, and Docker enables
trust authentication. No migration-owner/runtime role split, `BYPASSRLS` check,
or role bootstrap SQL exists.

This is a critical RLS blocker. Passing isolation tests as `postgres` would not
prove the production security boundary. The accepted implementation design must
introduce:

- `rokkad_migration_owner`: object owner and migration identity;
- `rokkad_app_runtime`: DML-only, non-owner, non-superuser, `NOBYPASSRLS`;
- separate settings/environment variables for migration and runtime execution;
- development/CI bootstrap and metadata assertions;
- no trust-auth assumption in the security acceptance environment.

## Quantified Blockers

| Blocker | Current evidence | Removal gate |
|---|---|---|
| Tenant model ownership | 177/212 models lack direct Workspace | 0 missing |
| Existing direct ownership | 35/212 models have Workspace but no RLS | all registered and protected |
| Tenant test base | 76 discovered modules | 0 live tenant-test dependencies |
| Raw SQL | 35 identified migration files | every retained object Workspace-aware |
| Runtime package imports | settings plus many control/domain modules | 0 unintended imports |
| Runtime DB role | development uses PostgreSQL superuser | restricted role proven |
| Context | schema/search-path based | transaction-local Workspace context |

## Phase 0 Remaining Work

1. Owner acceptance of the proposed ADR.
2. Owner disposition for historical local dumps and older Product fixtures.
3. Exact credentials/bootstrap commands belong to Phase 1 implementation after
   ADR acceptance; the required role contract is now recorded above.

The uniqueness and relationship graph is now recorded in
`docs/implementation/django-tenants-removal-integrity-inventory.md`: 252
uniqueness rules, 358 tenant FK edges, 28 cross-app edges, 10 generic relation
surfaces, and three unmanaged balance views.

Runtime implementation remains blocked until item 1 is complete.
