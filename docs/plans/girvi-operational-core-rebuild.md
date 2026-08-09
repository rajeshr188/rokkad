---
status: on-hold
owner: project
updated: 2026-08-08
tags: [girvi, architecture, rebuild, execution-plan]
related:
  - ../adr/2026-08-08-girvi-operational-core-rebuild.md
  - ../domain/girvi.md
  - ../constitution.md
  - girvi-audit-followup-plan.md
---

# Girvi Operational Core Rebuild Plan

> On hold while `loans-girvi-consolidation-fit-gap.md` evaluates Loans as the
> single operational loan platform. This plan remains the fallback only if the
> consolidation gates expose a fundamental product or architecture mismatch.

## Goal

Replace the current Girvi implementation with a clean pawn-loan origination
and servicing system whose operational workflows are complete without any
accounting integration. Add accounting later as an outbound consumer of
immutable Girvi business events.

This is a destructive rebuild. Preserving Girvi rows, migration history,
compatibility routes, legacy imports, and DEA document identity is out of
scope. Girvi and Loans remain separate products with separate ownership.

## Planning Principles

1. Domain behavior before ORM schema.
2. Operational truth before accounting delivery.
3. Two explicit aggregates, not an inheritance-heavy generic loan model.
4. Immutable event/document evidence and compensating corrections.
5. Party-only identity and tenant-safe ownership.
6. One writer per workflow; no signals or model-save side effects.
7. Projections derive balances and queues; they do not become writable truth.
8. Build vertical workflows and prove each through the public application API.
9. Delete unused code instead of wrapping it for compatibility.
10. Do not copy Loans implementation wholesale. Reuse tested business decisions
    and pure concepts only when they fit Girvi.

## Scope Decisions Required Before Schema

Resolve these in the architecture baseline. Defaults are recommendations, not
silent assumptions.

| Decision | Recommended baseline |
| --- | --- |
| Customer loan lifecycle | Draft, Pending Approval, Approved, Active, Closed, Cancelled, Rejected, Written Off. Derive overdue/NPA and recovery queues. |
| Funding loan lifecycle | Draft, Active, Closed, Cancelled. Derive settlement readiness. |
| Repayment allocation | Fees, overdue interest, current interest, principal; no staff override initially. |
| Interest | Monthly simple interest first, explicit partial-month slab, immutable terms snapshot at activation. Compound/capitalization only after simple lifecycle passes. |
| Partial release | Exclude from first operational kernel; full release first. Add later only with retained-collateral LTV evidence. |
| Renewal | Close source plus create successor; never mutate active terms. |
| Repledge | FundingLoan owns pledges of individual collateral items from one or more active CustomerLoans. |
| Auction/sale | Require first-class `RecoveryCase` and `CollateralDisposition`; do not represent recovery as a status plus amount. |
| Backdating | Disallow initially except explicit administrator correction workflows. |
| Documents | Fixed loan ticket, repayment receipt, release document, funding pledge document, and custody receipt first. Configurable layouts later. |
| Accounting | Null adapter through operational completion; outbox adapter only after Gate 8. |

## Target Domain

### Aggregates

`CustomerLoan`

- Party borrower, regulatory license/series, official number, terms snapshot,
  activation evidence, collateral, and terminal outcome.
- Draft collateral/terms are editable through commands.
- Approval freezes the reviewed draft fingerprint.
- Activation freezes the final economic terms and principal.
- Active economics change only through repayment, accrual, release, renewal,
  recovery, write-off, or compensating correction events.

`FundingLoan`

- Party lender, workspace number, terms snapshot, activation evidence, selected
  collateral pledges, repayments, returns, and closure.
- One funding loan may hold collateral from several customer loans.
- Collateral cannot be released to a borrower while an active funding pledge
  exists.

`CollateralItem`

- Belongs permanently to its originating CustomerLoan.
- Stores description, metal, quantity, gross/non-metal/net weight, purity,
  appraisal, and principal allocation snapshot.
- Current custody is projected from immutable `CustodyMovement` rows.
- Valid locations initially: customer, branch vault, and lender through an
  active funding pledge.

### Immutable Operational Evidence

- `LoanActivation`
- `LoanRepayment` and exact `LoanRepaymentReversal`
- `InterestAccrual` and compensating reversal
- `CustodyMovement`
- `LoanRelease` with item and settlement snapshots
- `LoanRenewal` linking source and successor
- `FundingPledge` and `FundingReturn`
- `RecoveryCase`, notices, valuations, sale/auction disposition, and proceeds
- `LoanWriteOff`
- `DomainEvent` plus optional outbound-delivery rows

Events carry stable source IDs, effective date, actor snapshot, request key,
reason where applicable, and schema version. Monetary events retain exact
principal/interest/fee allocation.

### Projections

- Customer loan balance and settlement quote
- Funding loan balance
- Collateral current custody and availability
- Loan timeline
- Overdue/NPA/recovery queues
- Release readiness
- Funding settlement readiness
- Party exposure
- Operations dashboard and reconciliation

## Target Package Shape

```text
girvi/
  domain/
    customer_loans.py
    funding_loans.py
    collateral.py
    interest.py
    repayment.py
    release.py
    renewal.py
    recovery.py
    numbering.py
    errors.py
  application/
    commands.py
    handlers/
      customer_loans.py
      funding_loans.py
      repayments.py
      releases.py
      renewals.py
      recovery.py
    ports/
      repositories.py
      clock.py
      rates.py
      notifications.py
      documents.py
      accounting.py
    results.py
  models/
    setup.py
    customer_loan.py
    funding_loan.py
    collateral.py
    servicing.py
    custody.py
    recovery.py
    events.py
  infrastructure/
    repositories.py
    rates.py
    notifications.py
    documents.py
    accounting/
      null.py
      outbox.py
  selectors/
    loans.py
    balances.py
    custody.py
    operations.py
    parties.py
  interfaces/
    web/
      forms/
      views/
      urls.py
    jobs/
    management/
  tests/
    domain/
    application/
    persistence/
    web/
    tenant/
```

No wildcard exports, generic `services.py`, monolithic `forms.py`, monolithic
`selectors.py`, transition registry, model payment wrappers, or direct DEA
imports are allowed.

## Current Code Disposition

Retain only after redesign:

- license/series numbering business rules;
- Party-based identity intention;
- item valuation inputs and custody invariants;
- release owns physical handoff;
- accrual is separate from release but may be finalized before settlement;
- repayment principal/interest split and idempotency;
- renewal creates a successor rather than changing active terms;
- notices, statements, storage, and documents as operational capabilities;
- public facade use cases required by orgs, contact, party, and period-close.

Delete and replace:

- `BaseLoan`, `GivenLoan`, `TakenLoan`, model calculation/payment helpers;
- `flows.py`, `lifecycle.py`, `transition_registry.py`, `transitions/`, and
  `loan_transtitions/`;
- `service_modules/`, broad `services.py`, `payment_service.py`;
- wildcard `models` and `views` exports;
- monolithic forms/selectors and compatibility tables/filters;
- generic relations to DEA payment models and all DEA IDs as operational truth;
- Customer shadow fields and bridge writes;
- signals that update domain state or aggregates;
- duplicate routes, aliases, archives, legacy reports, import/export resources,
  and old template administration unless separately re-approved;
- the current 33-step Girvi migration chain after the clean baseline is ready.

## Execution Sequence

### Phase 0: Freeze And Decide

Deliverables:

- Accept the rebuild ADR and this plan.
- Decide every item in the scope-decision table.
- Freeze feature work on current Girvi except critical fixes.
- Inventory external callers and define the minimal replacement facade.
- Tag the last pre-rebuild commit and create schema backups.

Gate 0:

- No unresolved MVP domain decision.
- Explicit owner approval for data loss and migration-history replacement.
- Exact target schemas and rollback artifacts identified.

### Phase 1: Executable Domain Specification

Build pure Python value objects, policies, transition functions, repayment
allocation, interest periods, release eligibility, funding pledge eligibility,
custody transitions, and correction ordering. Use scenario tests only; no ORM.

Required scenario corpus:

1. Draft, approve, reject, reopen, cancel, and activate customer loan.
2. Partial and full repayment with deterministic allocation.
3. Interest accrual and settlement as of a date.
4. Full release with every item returned and loan closed.
5. Renewal closing source and opening successor.
6. Funding loan activation with items from multiple customer loans.
7. Funding repayment, item return, and closure.
8. Release blocked while collateral is lender-held.
9. Recovery and write-off outcomes.
10. Newest-first compensating corrections.

Gate 1: domain tests run without Django and contain no accounting vocabulary
except neutral `DomainEvent` facts.

### Phase 2: New Schema Design

Design the fresh model graph and database invariants from the domain tests.
Use Party only. Add explicit workspace ownership where tenant schema alone is
not enough for authorization/audit.

Database protections must cover:

- numbering uniqueness and non-reuse;
- positive monetary/weight/rate values;
- approved and activated snapshot immutability;
- immutable operational events;
- exactly one reversal per eligible original;
- exact repayment/accrual compensation;
- valid custody movement lineage;
- one active funding pledge per collateral item;
- release item/loan agreement and terminal closure invariants;
- request-key idempotency scoped by aggregate and operation.

Gate 2: reviewed model diagram, constraint table, and migration baseline draft;
no views or accounting adapter.

### Phase 3: Application Core And Null Adapters

Implement repositories, unit-of-work transaction boundaries, commands, and
handlers for setup, drafting, approval, activation, repayment, accrual, custody,
release, renewal, funding, and correction. Inject clock, rate, notification,
document, and accounting ports. Default accounting port is a no-op recorder
that never imports DEA.

Gate 3: every scenario passes through application handlers and real database
repositories in a tenant schema with accounting disabled.

### Phase 4: Destructive Schema Baseline

Before changing migration history:

1. Narrow or remove external runtime imports of Girvi models.
2. Replace them with the approved facade/selectors.
3. Confirm no external app migration depends on a named Girvi migration.
4. Remove current Girvi migration files and generate one clean `0001_initial`.
5. Drop `girvi_%` tables and Girvi migration rows only in approved schemas.
6. Apply the new baseline with `migrate_schemas --tenant --schema ...`.
7. Verify no non-Girvi table or FK was removed by cascade. Do not use CASCADE.

This phase is intentionally destructive and must use a revised runbook. The old
reset runbook cannot be reused unchanged because the target migration history
and table set are different.

Gate 4: fresh tenant replay and approved schema rebuild produce identical table,
constraint, trigger, and seed inventories.

### Phase 5: Operational Web Workflows

Build the actual work surfaces, not generic transition forms:

- Setup: licenses, series, policies, numbering health.
- Dashboard: drafts, approvals, due work, custody exceptions, release-ready,
  funding settlement, recovery work.
- Customer loan: create/edit draft, approve, activate, repay, release, renew,
  recover, correct, timeline, documents.
- Funding loan: create, select collateral, activate, repay, return items, close.
- Collateral: custody history, vault/storage assignment, verification.
- Party history and operational reports.

Views bind forms, call one handler, and render one selector contract. Major
workflows get dedicated pages. No generic transition endpoint returns.

Gate 5: browser and tenant tests prove the complete customer-loan and
funding-loan happy paths with accounting disabled.

### Phase 6: Documents, Notifications, Jobs, And Reports

Add fixed versioned documents first. Notification adapters consume committed
domain events. Scheduled jobs call application commands and are idempotent.
Reports use selectors only.

Gate 6: document hashes/source links, reminder idempotency, accrual reruns,
custody verification, and operational reports are tenant-tested.

### Phase 7: Corrections And Integrity

Complete compensating correction workflows before integrations:

- activation cancellation/reversal;
- repayment reversal;
- accrual reversal;
- release reversal with custody restoration checks;
- renewal reversal across source/successor;
- funding pledge/return correction;
- recovery/write-off correction.

Add an integrity command checking aggregate/event/custody/projection invariants.

Gate 7: originals remain immutable, dependencies enforce newest-first reversal,
and the integrity command reports zero findings on the scenario corpus.

### Phase 8: Accounting Event Contract

Only now define versioned accounting DTOs from committed operational events.
The adapter may target DEA, standalone accounting, or remain deferred. Delivery
uses a dedicated outbox with status and retries; delivery rows never determine
loan balances, custody, lifecycle, or correction eligibility.

Required events initially:

- customer loan activation/disbursal;
- customer repayment;
- funding activation/receipt;
- funding repayment;
- accrual recognition when policy requires it;
- release settlement;
- recovery/write-off;
- compensating accounting reversals.

Gate 8: null-adapter tests remain unchanged; contract tests prove exact payload,
idempotency, retries, and reconciliation without importing accounting models
into domain/application modules.

### Phase 9: Cutover And Removal

- Enable rebuilt Girvi only after Gates 0-8 pass.
- Remove all old Girvi runtime, templates, tests, migrations, and documentation
  not explicitly retained.
- Update orgs/contact/party/notify/DEA callers to the new facade contracts.
- Run full tenant, cross-app, route, permission, and migration-replay gates.
- Record schema reset evidence and accepted residual scope.

## Testing Strategy

Use a test pyramid based on behavior, not current file parity:

| Layer | Required proof |
| --- | --- |
| Pure domain | Transition matrix, allocations, interest, custody, release, funding, reversal ordering. |
| Application | Command authorization, idempotency, atomicity, error contracts, null adapters. |
| Persistence | Constraints, triggers, concurrency, tenant isolation, immutable bypass resistance. |
| Selectors | Balances, custody, queues, timelines, party exposure, no writes. |
| Web | Permissions, form binding, redirects/HTMX, dedicated workflow usability. |
| Tenant E2E | Customer create-to-release and funding create-to-close with accounting disabled. |
| Contract | Notifications, documents, rates, and later accounting DTOs. |
| Migration | Fresh replay and approved destructive schema reset. |

The current 418 Girvi tests are a knowledge source, not a mandatory compatibility
suite. Classify each as retain concept, rewrite behavior, or delete. Do not make
new architecture imitate obsolete tests.

## Cross-App Contracts To Preserve Or Replace First

- Orgs dashboard summary.
- Contact/Party active-loan checks and Party loan history.
- DEA/standalone period-close accrual hook, later moved to a neutral facade.
- Notify reminder source selector and document payload.
- Tenant navigation route names intentionally retained.

No cross-app caller may import new Girvi models directly. Architecture tests
must enforce facade-only access outside Girvi.

## Definition Of Done

- Girvi runs its complete approved customer and funding loan workflows with
  accounting disabled.
- Domain/application modules import neither Django views/forms nor accounting.
- Party is the only counterparty identity.
- Every monetary/custody correction is compensating evidence.
- No generic DEA payment relation participates in operational reads.
- No wildcard exports, compatibility aliases, generic transition registry,
  model side effects, or domain-mutating signals remain.
- Fresh and reset tenant schemas use one clean Girvi migration baseline plus
  only post-rebuild migrations.
- Cross-app access is facade-only and tenant-safe.
- Accounting integration is a replaceable outbound adapter over immutable
  Girvi events.
