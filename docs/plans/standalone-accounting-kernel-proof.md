---
status: active
owner: project
updated: 2026-08-07
tags: [plan, accounting, dea, double-entry, proof]
related:
  - ../adr/2026-08-07-standalone-accounting-transaction-kernel.md
  - ../constitution.md
  - ../domain/accounting.md
---

# Standalone Accounting Kernel Proof

## Objective

Determine whether the normalized *Ledger - Double Entry* ontology can become
Rokkad's standalone accounting foundation without duplicating financial truth.
The proof must precede Django persistence, runtime registration, or cutover.

## Non-Goals

- No current DEA changes or data migration.
- No Django models, migrations, settings, routes, templates, or navigation.
- No Loans, Girvi, Party, Inventory, or Commodity integration.
- No claim that the proposed ADR is accepted before the reporting gate passes.

## Stage K0: Vocabulary And Pure Invariants

- [x] Define atomic ledger-to-ledger transactions.
- [x] Define atomic ledger-to-external-account transactions.
- [x] Define immutable external-account classification snapshots.
- [x] Define ordered compound transaction batches.
- [x] Define exact reversal behavior.
- [x] Test positive amounts, currency consistency, exclusive direction, distinct
  ledgers, classification requirement, non-empty batches, and reversal.

## Stage K1: Accounting Scenario Corpus

- [x] Cash sale.
- [x] Credit sale.
- [x] Customer receipt and partial allocation.
- [x] Supplier purchase and payment.
- [x] Loan disbursal.
- [x] Loan repayment split into principal, interest, and fees.
- [x] Many-sided manual journal represented by explicit atomic pairs.
- [x] Whole-batch reversal.

Each scenario must declare source facts, atomic transactions, expected external
balances, expected financial-statement effects, and reversal results.

K1 result: the corpus is executable in
`accounting.tests.test_accounting_scenarios`. It proves expected internal,
external-account, classification, and reversal effects with a deliberately
small independent fold oracle. Partial open-item allocation is separate
non-financial evidence over an existing account transaction; it cannot exceed
the monetary transaction or cross external accounts. Production projections
remain K2 work and must be compared against these expectations rather than
reusing the test fold.

## Stage K2: Pure Projections And Reconciliation

- [x] Conventional debit/credit journal-line projection.
- [x] Internal ledger statement.
- [x] External account statement.
- [x] Trial balance.
- [x] Balance sheet.
- [x] Profit and loss.
- [x] Classification reconciliation without duplicate GL effects.
- [x] Historical result remains stable after a new classification version.

K2 result: `accounting.domain.projections` independently projects every atomic
transaction into two conventional lines, folds internal and external statements,
and combines direct internal balances with frozen external classifications
exactly once. The trial balance balances; current profit/loss closes into a
derived current-period equity row for the balance sheet. Reconciliation proves
that external detail plus any direct internal activity at the same reporting
ledger equals the trial-balance row. A later classification version affects
only later transactions. Whole-batch reversal removes journal, statement,
financial-statement, and reconciliation effects. This clears the primary
no-double-counting concern, subject to K3 posting-control proof.

## Stage K3: Posting Contracts

- [x] Voucher draft and authorization vocabulary.
- [x] Book-scoped idempotency contract.
- [x] Period state and posting-date contract.
- [x] Transaction/base currency and rate provenance.
- [x] Append-only correction and reversal contract.
- [x] Source-event and posting-rule-version identity.

K3 result: immutable voucher authorization precedes posting; deterministic
fingerprints include source and rule versions; an exact book-scoped replay
returns the existing result while a changed payload fails. Period and book
boundaries fail closed, adjustment-only periods accept only adjustments, and
closed/locked periods reject posting. Currency policy verifies transaction-to-
base conversion and rate provenance. Reversal creates new opposite evidence;
correction preserves the original and produces reversal plus replacement.

## Architecture Gate

At the end of K3, review the proposed ADR. Accept it only if all scenarios and
reports derive from one transaction truth and the account-classification model
is historically stable and operationally understandable.

**Gate result: PASS on 2026-08-07.** All 40 K0-K3 tests pass. Reports derive
from one transaction truth, frozen classification is historically stable, and
the architecture does not require duplicate control-ledger postings. ADR
`2026-08-07-standalone-accounting-transaction-kernel.md` is accepted.

## Stage K4: App Skeleton And Persistence Design

- [x] Add an import-safe `AccountingConfig` with stable app identity.
- [x] Keep the app absent from `TENANT_APPS` and `INSTALLED_APPS`.
- [x] Keep models, migrations, URLs, admin, and runtime integrations absent.
- [x] Map organization/book, periods, ledger hierarchy, external accounts,
  immutable classification versions, vouchers, atomic transactions, exclusive
  subtypes, posting batches, reversals, corrections, and allocations.
- [x] Specify database constraints/triggers and reporting views.
- [x] Prove structural boundaries with tests.

K4 result: [the persistence design](../implementation/standalone-accounting-persistence-design.md)
is accepted for the first schema slice. Draft atomic transactions will become
the immutable posted truth when their batch is created; posting will not copy
them into a duplicate transaction table. Cross-table exclusivity and posted
immutability require PostgreSQL constraint triggers. All 44 K0-K4 tests pass,
and the app remains unregistered with no model or migration surface.

The next stage is K5.1: model the organization/book, period, and ledger master
slice, review its generated tenant migration, and only then register/apply it
using `migrate_schemas`. External accounts and monetary transaction tables stay
out of K5.1 so ownership and hierarchy constraints are proven first.

## Stage K5.1: Accounting Master Schema

- [x] Add `AccountingOrganization` without a workspace-model FK.
- [x] Add organization-scoped `AccountingBook` and currency policy fields.
- [x] Add non-overlapping book periods and lifecycle evidence constraints.
- [x] Add hierarchical ledgers with reporting class, normal side, node kind,
  debit/credit permission, uniqueness, and cycle/parent/leaf guards.
- [x] Register `AccountingConfig` in `TENANT_APPS`.
- [x] Generate and review `standalone_accounting.0001_initial`.
- [x] Add tenant/model/database-bypass tests.
- [x] Apply through `migrate_schemas --tenant`.

K5.1 result: all 52 focused tests pass. PostgreSQL exclusion prevents period
overlap per book, and a trigger prevents cross-book/invalid parents, children
under posting ledgers, and cycles even through bulk/update bypass paths. The
tables exist only in tenant schemas. Migration `0001_initial` is applied and
verified in local tenants `jcl1`, `jsk`, and `test`. No rows were seeded and no
current DEA table or posting path changed.

The next stage is K5.2: external accounts and immutable effective-dated
classification versions only. Vouchers and monetary transactions remain a
later slice until account-purpose, range-exclusion, protection, and historical
classification constraints pass tenant tests.

## Stage K5.2: External Accounts And Classification Versions

- [x] Add book-owned `ExternalAccount` with adapter `party_key` and explicit
  accounting purpose.
- [x] Permit one party identity to hold separate gross-purpose accounts.
- [x] Add effective-dated `ExternalAccountClassification` versions.
- [x] Require the reporting ledger to be a same-book posting ledger with
  matching reporting class and normal side.
- [x] Exclude overlapping classification ranges per external account.
- [x] Protect classification core fields and deletion in the database.
- [x] Permit only one-time closure of an open version when appending a successor.
- [x] Add an atomic append service and date-aware fail-closed selector.
- [x] Apply and verify tenant migration `0002`.

K5.2 result: all 57 focused tests pass. Database-bypass tests cover overlapping
ranges, cross-book ledgers, reporting mismatch, core mutation, and deletion.
The append service locks versions, closes the current open range at the day
before its successor, and creates the new immutable version atomically. The
selector resolves exactly one version for the posting date or fails. Migration
`0002_externalaccount_externalaccountclassification_and_more` is applied and
verified in `jcl1`, `jsk`, and `test`; no account rows were seeded.

The next stage is K5.3: voucher headers and draft atomic transaction base plus
exclusive ledger/account subtypes. Posting batches and runtime posting remain
K5.4, so K5.3 must prove draft ownership, currency fields, classification
freezing, same-book consistency, and deferred subtype cardinality first.

## Stage K5.3: Voucher And Draft Atomic Transactions

- [x] Add source/rule/idempotency-aware voucher headers with draft authorization.
- [x] Add positive monetary transaction bases with explicit book/base currency.
- [x] Add exclusive ledger-to-ledger and ledger-to-account transaction subtypes.
- [x] Freeze the effective external classification on account transactions.
- [x] Enforce same-book, posting-ledger, side, currency, and subtype invariants
  in PostgreSQL, including deferred exact subtype cardinality.
- [x] Freeze voucher intent and its transactions at authorization.
- [x] Apply and verify tenant migration `0003`.

K5.3 result: all 63 focused tests pass. Draft construction services create each
base/subtype pair atomically, account transactions resolve and retain the exact
classification version effective on the voucher date, and authorization makes
the complete intent immutable. Database-bypass tests cover missing/wrong
subtypes, cross-book ledgers, invalid base conversion, post-authorization
mutation, and retroactive classification closure. Migration `0003` is applied
and its four tables verified in `jcl1`, `jsk`, and `test`; no rows were seeded.

The next stage is K5.4: one-to-one posting batches and the repository/service
that validates, fingerprints, locks, and posts authorized vouchers atomically.
DEA remains runtime authority until a separately approved integration/cutover.

## Stage K5.4: Atomic Posting Batch

- [x] Add one immutable `TransactionBatch` per posted voucher.
- [x] Resolve and lock exactly one date-covering accounting period.
- [x] Enforce open and adjustment-only period policy.
- [x] Derive a deterministic SHA-256 fingerprint from frozen economic, source,
  rule, currency, ledger, account, and classification facts.
- [x] Transition authorized intent to posted state and create its batch in one
  atomic repository operation.
- [x] Return the original batch on exact repeated posting of that voucher.
- [x] Enforce posted-state/batch cardinality and batch immutability in PostgreSQL.
- [x] Apply and verify tenant migration `0004`.

K5.4 result: all 67 focused tests pass. A posted voucher and its batch cannot
commit independently, and neither posted intent nor batch evidence can be
updated or deleted through ORM-bypass paths. Closed/locked periods reject all
posting; adjustment-only periods admit adjustment vouchers only. Migration
`0004_transactionbatch_and_more` is applied and the batch table verified in
`jcl1`, `jsk`, and `test`; no rows were seeded and no runtime caller was wired.

The next coherent slice is K5.5: append-only reversal and correction services,
including exact opposite/reverse-order verification. Runtime DEA cutover remains
a separate later decision.

## Stage K5.5: Reversal And Correction Execution

- [x] Create reversal as a new adjustment voucher and posting batch.
- [x] Require actor, timestamp, reason, source identity, and idempotency identity.
- [x] Reverse transaction order and swap every monetary side exactly.
- [x] Preserve the original external-account classification version.
- [x] Permit only one reversal per original and prohibit reversal-of-reversal.
- [x] Verify exact opposite/reverse-order shape in PostgreSQL before batch insert.
- [x] Orchestrate correction as original plus reversal plus authorized replacement.
- [x] Apply and verify tenant migration `0005`.

K5.5 result: all 71 focused tests pass. Original vouchers and transactions are
never edited. Reversal replay returns the original reversal for the same
idempotency identity, while a second distinct reversal fails. Historical
account classification remains frozen even when reversal occurs after a new
classification version becomes effective. Correction posts the compensating
reversal and replacement atomically under one correction group. Migration
`0005_transactionbatch_reversal_reason_and_more` and its exact-reversal trigger
are verified in `jcl1`, `jsk`, and `test`; no rows were seeded.

The next coherent slice is K5.6: persisted open items and non-financial
allocation evidence over account transactions. DEA remains runtime authority.

## Stage K5.6: Open Items And Allocation Evidence

- [x] Add an immutable open item over one posted account transaction.
- [x] Freeze its book, external account, transaction/base money, and due date.
- [x] Add immutable allocation evidence over a posted opposite-side settlement.
- [x] Require the same book, external account, and currencies.
- [x] Prevent settlement and open-item over-allocation under row locks.
- [x] Enforce ownership, capacity, and immutability through PostgreSQL triggers.
- [x] Add an outstanding selector without creating financial movements.
- [x] Apply and verify tenant migration `0006`.

K5.6 result: all 74 focused tests pass. Creating and allocating an open item
does not add an `AccountingTransaction`; outstanding values are derived from
immutable allocation rows. Model-bypass tests cover cross-account allocation,
capacity, and mutation/deletion. Migration `0006_openitem_openitemallocation_and_more`,
both tables, and both guards are verified in `jcl1`, `jsk`, and `test`; no rows
were seeded.

The next coherent slice is K5.7: compensating allocation evidence for reversed
settlements, followed by persisted reporting projections. Existing allocations
must never be deleted or edited to represent reversal.

## Stage K5.7: Settlement Allocation Compensation

- [x] Add one optional immutable `reversal_of` link to allocation evidence.
- [x] Automatically mirror affected allocations when their settlement batch is
  reversed.
- [x] Require exact item, transaction/base money, currency, and financial
  reversal lineage.
- [x] Derive outstanding from original allocations less compensations.
- [x] Preserve all original allocation rows unchanged.
- [x] Apply and verify tenant migration `0007`.

K5.7 result: all 75 focused tests pass. Reversing an allocated receipt creates
the financial reversal plus exact compensating allocation evidence in the same
atomic operation, restoring open-item outstanding without adding another
financial effect or deleting history. Migration `0007_openitemallocation_reversal_of_and_more`,
its column, and the revised database guard are verified in `jcl1`, `jsk`, and
`test`; no rows were seeded.

MVP scope remains deliberate: K5.7 adds no UI, allocation strategy engine,
aging dashboard, materialized view, runtime adapter, or DEA cutover. The next
slice should be K5.8 read-only ORM reporting projections needed to demonstrate
the persisted kernel (journal, statements, trial balance, P&L, balance sheet,
and reconciliation), without adding another writable accounting representation.

## Stage K5.8: Persisted Read-Only Reports

- [x] Adapt posted persisted batches into the proven pure transaction contracts.
- [x] Project exactly two conventional journal lines per atomic transaction.
- [x] Expose internal-ledger and external-account balances separately.
- [x] Produce a balanced combined trial balance without duplicate control rows.
- [x] Produce P&L and a balance sheet closed through current-period result.
- [x] Reconcile frozen external classifications to trial-balance reporting rows.
- [x] Exclude draft/authorized vouchers and support effective-date bounds.
- [x] Create no reporting table, cached balance, migration, or write path.

K5.8 result: all 76 focused tests pass. A persisted credit sale plus partial
receipt produces six conventional lines, the expected separate internal and
external balances, a balanced trial balance, ₹300 current-period result,
balanced balance sheet, and zero classification-reconciliation difference.
Draft transactions are excluded and projection does not change transaction
row counts. No schema migration was needed.

## MVP Boundary Review

The standalone kernel now covers the MVP accounting spine: masters, periods,
external classifications, authorized paired transactions, atomic posting,
reversal/correction, open-item settlement evidence, and core financial reports.
Do not continue adding accounting features by default. The next stage should be
a K6 MVP readiness review that identifies the smallest safe runtime pilot and
explicitly chooses whether to integrate, defer, or stop. UI, tax, bank feeds,
budgets, consolidation, recurring entries, configurable allocation strategies,
report caches, and legacy migration remain outside this architecture proof.

## Stage K6: MVP Readiness Review

The formal review is recorded in
[standalone-accounting-mvp-readiness.md](standalone-accounting-mvp-readiness.md).

Decision: **GO for one isolated synthetic non-production acceptance pilot;
NO-GO for production posting, production shadow traffic, data migration, or DEA
replacement.** The kernel is correct enough to evaluate, but production safety
requires an authenticated facade, durable audit identity, controlled period
lifecycle, deterministic bootstrap, a narrow source adapter, diagnostics,
recovery and concurrency rehearsals, and accountant sign-off.

K6 is a review gate, not permission for further features. The only immediate
implementation allowed by this result is the deterministic sandbox bootstrap
and scripted acceptance harness described in the readiness review.
