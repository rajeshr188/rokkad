---
status: active
owner: project
updated: 2026-08-07
tags: [accounting, dea, mvp, readiness, pilot]
related:
  - standalone-accounting-kernel-proof.md
  - ../adr/2026-08-07-standalone-accounting-transaction-kernel.md
  - ../implementation/standalone-accounting-persistence-design.md
  - ../domain/accounting.md
  - ../constitution.md
---

# Standalone Accounting MVP Readiness Review

## Decision

**GO for an isolated non-production acceptance pilot.**

**NO-GO for production posting, production shadow integration, data migration,
or replacement of DEA.**

The transaction ontology and persisted accounting kernel are sufficiently
proved for controlled sandbox evaluation. They are not yet an operable product
boundary: callers currently pass untrusted actor IDs and timestamps directly,
there is no authenticated facade or source adapter, setup is not reproducible,
and operational reconciliation/recovery controls do not exist.

## Evidence Reviewed

- The accepted paired transaction ADR and persistence design.
- K0-K5.8 domain, lifecycle, database-bypass, tenant, and report tests.
- All 76 focused accounting tests pass on PostgreSQL.
- Django system checks, compilation, migration drift, and diff checks pass.
- Tenant schemas `jcl1`, `jsk`, and `test` each record all seven
  `standalone_accounting` migrations.
- Core successor tables exist only in tenant schemas, not `public`.
- All successor master, voucher, transaction, batch, open-item, and allocation
  tables contain zero rows in the three local tenants.
- The app has no URL, admin, business-module caller, runtime source adapter, or
  seeded accounting configuration.

Plain `showmigrations standalone_accounting` reflects the public schema and
therefore displays tenant-only migrations as unchecked. Tenant-schema migration
records are the authoritative verification for this app.

## Readiness Matrix

| Area | Result | Evidence / gap |
|---|---|---|
| Transaction correctness | Ready | Paired transactions, currency provenance, posting, reversal, correction, and settlement invariants are tested. |
| Immutability | Ready | PostgreSQL protects authorized/posted intent, batches, classifications, open items, and allocations. |
| Financial reporting | Ready for small pilot | Journal, statements, trial balance, P&L, balance sheet, and reconciliation derive read-only from posted truth. |
| Tenant isolation | Ready | Tenant-only registration/tables and public-schema absence are verified. |
| Period enforcement | Kernel ready; operations missing | Posting enforces period status, but controlled close/lock/reopen operations and permissions are absent. |
| Idempotency | Kernel ready | Book-scoped voucher identity and exact posting/reversal replay exist; no external delivery adapter exercises them. |
| Authorization | Blocked for production | Services accept numeric actor IDs; no authenticated permission facade, separation-of-duties rule, or trusted clock exists. |
| Audit identity | Blocked for production | Actor IDs are evidence but not durable identity snapshots; voucher-number policy is not defined. |
| Bootstrap/configuration | Blocked for production | No idempotent organization/book/chart/period/classification bootstrap path exists. |
| Runtime integration | Blocked | No public facade DTO, source adapter, delivery/outbox boundary, or DEA comparison path exists. |
| Operations | Blocked for production | No health/integrity command, monitoring, backup/restore rehearsal, or incident runbook exists. |
| Concurrency assurance | Needs pilot gate | Locks and constraints exist, but separate-connection race tests for replay and allocation capacity are still required. |
| Scale | Not evaluated | Reports materialize batches in memory; acceptable only for the deliberately small acceptance dataset. |

## Smallest Safe Pilot

Use one dedicated non-production tenant with no imported or production data.

Scope:

1. one active organization and INR book with two decimal places;
2. one open accounting period;
3. the minimum posting ledgers for cash, sales revenue, inventory, cost of
   sales, and accounts receivable;
4. one customer receivable external account and one classification version;
5. scripted cash sale, credit sale, partial customer receipt/allocation,
   reversal, and corrected replacement;
6. verification of journal lines, customer balance, trial balance, P&L,
   balance sheet, classification reconciliation, and open-item outstanding;
7. teardown by deleting the dedicated tenant, not by mutating posted rows.

The pilot must use synthetic values and a test-only harness or management
command. It must not write DEA, accept production events, expose browser routes,
or claim accounting authority.

## Production Entry Gates

All gates below are required before any production or production-shadow caller:

1. **Authenticated facade:** tenant-bound principals, explicit create/authorize/
   post/reverse permissions, trusted server timestamps, and a documented
   separation-of-duties decision.
2. **Durable audit identity:** stable actor snapshot/reference and an explicit
   voucher-number uniqueness/allocation policy.
3. **Controlled period lifecycle:** authorized open, adjustment-only, close,
   lock, and exceptional reopen commands with database protections and audit.
4. **Idempotent bootstrap:** repeatable creation/validation of book, ledger,
   period, external-account, and classification configuration without guessing.
5. **One narrow source adapter:** versioned DTO, book/source identity,
   idempotent delivery, failure state, and no direct model imports by callers.
6. **Operational diagnostics:** integrity/reconciliation command covering
   posted-state/batch cardinality, subtype cardinality, fingerprints, reversal
   shape, classification, settlement capacity, and report balance.
7. **Recovery rehearsal:** tenant migration from clean schema, backup/restore,
   failed-post rollback, and documented response to diagnostic failure.
8. **Concurrency tests:** separate database connections racing identical post,
   changed-payload reuse, reversal, and allocation capacity.
9. **Pilot sign-off:** accountant review of the scripted evidence and explicit
   approval of the paired external-account presentation.

## Explicitly Deferred Beyond MVP

- Tax engines and statutory returns
- Bank feeds and reconciliation automation
- Budgets, forecasting, consolidation, and multi-entity elimination
- Recurring journals and approval workflow builders
- Configurable allocation strategies and aging caches
- Materialized reporting balances or a second writable journal
- Browser UI, admin CRUD, public API, and customer-facing reports
- Legacy DEA data migration or production cutover

## Recommended Next Action

Implement only the isolated acceptance harness and its deterministic bootstrap,
then execute the scripted pilot. Do not begin a source adapter or production
facade until the sandbox evidence is reviewed. If that review passes, open a
separately approved K7 production-boundary plan containing the nine entry gates.

Implementation status: the guarded, idempotent bootstrap/harness exists as
`run_accounting_acceptance_pilot` and has a 77-test accounting suite. The
disposable `accounting_pilot_mvp` tenant was provisioned through the normal
tenant flow on 2026-08-07; two identical command runs passed all accounting and
DEA-isolation checks. The internal accountant-style review passed with an
unapplied-receipt presentation observation; that observation is resolved and
all 77 tests pass. K7 production-boundary work may now begin, while independent
user/professional sign-off remains a production-entry gate. See
`docs/implementation/standalone-accounting-acceptance-pilot.md`.
