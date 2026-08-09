---
status: accepted
owner: project
updated: 2026-08-07
tags: [implementation, accounting, persistence, double-entry]
related:
  - ../adr/2026-08-07-standalone-accounting-transaction-kernel.md
  - ../plans/standalone-accounting-kernel-proof.md
  - ../constitution.md
---

# Standalone Accounting Persistence Design

## Purpose

Map the accepted standalone accounting kernel to a relational Django/PostgreSQL
design before creating models or tenant migrations. This document is the K4
persistence review. Current DEA remains the runtime accounting authority.

## Persistence Principles

1. One stored monetary fact has one `AccountingTransaction` base row and exactly
   one exclusive subtype: ledger-to-ledger or ledger-to-external-account.
2. Draft transactions become the posted truth; posting does not copy them into
   a second transaction table. A posted transaction is immutable.
3. A `TransactionBatch` is created atomically when an authorized voucher posts.
   Its existence marks the voucher's transactions as posted.
4. External-account classification versions are immutable and protected. Every
   account transaction references the exact version used for reporting.
5. Balances, conventional journal lines, trial balance, and statements are
   projections. No writable balance is authoritative.
6. Source identity, rule version, fingerprint, authorization, period, currency,
   reversal, and correction evidence are durable.
7. Database constraints and deferred constraint triggers enforce invariants
   that model validation alone cannot protect.

## Ownership Boundary

### `AccountingOrganization`

Standalone owner of accounting data.

| Field | Contract |
|---|---|
| `id` | UUID primary key. |
| `organization_key` | Stable unique public key. |
| `name` | Display name. |
| `external_tenant_key` | Nullable adapter identity for Rokkad workspace or another host. No cross-app FK. |
| `active` | Setup/lifecycle flag; never used to hide historical postings. |

Rokkad's future adapter maps one workspace to an accounting organization. The
accounting app does not import workspace models. Tenant-schema isolation may
remain during initial deployment, but explicit organization ownership is still
required to support auditing and a future shared-schema/RLS boundary.

### `AccountingBook`

| Field | Contract |
|---|---|
| `id` | UUID primary key. |
| `organization` | Protected FK. |
| `book_key` | Stable key unique per organization. |
| `name` | Display name. |
| `base_currency` | Three-letter allow-listed monetary code. |
| `decimal_places` | Currency finalization scale, bounded 0-8. |
| `active` | Blocks new activity only. |

Unique: `(organization, book_key)`.

## Periods And Ledger Master

### `AccountingPeriod`

Fields: `book`, `period_key`, `start_date`, `end_date`, `status`, `closed_at`,
`closed_by_id`, `locked_at`, and `locked_by_id`.

Statuses: `OPEN`, `ADJUSTMENT_ONLY`, `CLOSED`, `LOCKED`.

Constraints:

- start date is not after end date;
- `(book, period_key)` is unique;
- periods in one book may not overlap, enforced by a PostgreSQL exclusion
  constraint over a daterange;
- posting date and allowed purpose are checked while the period row is locked;
- locked periods cannot be reopened by ordinary application commands.

### `Ledger`

Fields: `book`, `ledger_key`, `code`, `name`, nullable protected `parent`,
`reporting_class`, `normal_side`, `node_kind`, `can_debit`, `can_credit`, and
`active`.

`node_kind` is `INTERMEDIATE` or `POSTING`. Only posting leaves may transact.

Constraints:

- `(book, ledger_key)` and `(book, code)` are unique;
- parent and child belong to the same book;
- a ledger cannot parent itself or form a cycle;
- posting ledgers cannot have children;
- intermediate ledgers cannot occur in transaction subtypes;
- a ledger transaction cannot use the same ledger on both sides;
- `can_debit`/`can_credit` are enforced on the respective transaction side.

Cycle, leaf, and debit/credit rules require database triggers or equivalent
transactional constraint functions in addition to model validation.

## External Accounts And Classification

### `ExternalAccount`

Fields: `book`, `account_key`, protected nullable `party` FK, `party_key`,
`purpose`, `name`, `active`, and optional operational metadata. `party_key`
remains adapter/source identity. Migration `0013` adds the direct tenant Party
link for new visual accounts; null remains only for earlier synthetic evidence.

Purposes initially include customer receivable, supplier payable, borrower loan
receivable, lender loan payable, customer advance, and supplier advance.

Unique: `(book, account_key)` and, when Party is linked, `(book, party,
purpose)`. A Party may own multiple external accounts for different purposes;
gross economic relationships are not netted by identity.

### `ExternalAccountClassification`

Fields: `external_account`, `version_key`, `effective_from`, nullable
`effective_to`, `reporting_ledger`, `reporting_class`, `normal_side`, and
`created_at`.

Constraints:

- `(external_account, version_key)` is unique;
- effective ranges do not overlap;
- reporting ledger belongs to the same book;
- classification reporting class and normal side agree with the reporting
  ledger definition;
- classification core fields cannot be updated and versions cannot be deleted;
- the only permitted update is closing an open `effective_to` once while its
  successor is appended atomically. A future transaction reference will also
  prevent closure before any posting that already uses the version.

New classification creates a new version. It never rewrites a posted account
transaction's financial-statement meaning.

## Voucher And Source Identity

### `Voucher`

Fields:

- `book`, `voucher_key`, `voucher_number`, `effective_date`, and `purpose`;
- state: `DRAFT`, `AUTHORIZED`, `POSTED`, or `CANCELLED`;
- `idempotency_key`;
- `source_system`, `source_type`, `source_id`, `source_version`;
- `rule_key`, `rule_version`;
- nullable `fingerprint` until posting;
- authorization actor/time;
- narration and non-economic display metadata;
- optional `correction_group_key`.

Constraints:

- `(book, voucher_key)` is unique;
- `(book, idempotency_key)` is unique;
- source/rule identity is indexed and cannot change after authorization;
- an authorized voucher requires authorization actor/time;
- a posted voucher requires a fingerprint and one posting batch;
- a cancelled voucher cannot have a posting batch;
- economic fields and transactions cannot change after authorization without an
  explicit reopen-to-draft command and audit event; after posting they can never
  change.

## Atomic Transactions

### `AccountingTransaction`

Base fields:

- UUID primary key;
- protected FK to `Voucher`;
- positive `sequence` unique within voucher;
- discriminator `LEDGER` or `ACCOUNT`;
- positive `amount`, `currency`, `base_amount`, `base_currency`;
- positive `exchange_rate`, nonblank `rate_source`;
- narration.

Unique: `(voucher, sequence)`. Transaction and voucher books are required to
match. Currency/base values are checked against the book policy at posting.

### `LedgerTransaction`

One-to-one primary-key subtype of `AccountingTransaction`, containing protected
`debit_ledger` and `credit_ledger` FKs.

### `AccountTransaction`

One-to-one primary-key subtype containing protected `ledger`,
`external_account`, `ledger_side`, and `classification` FKs.

The external side is always the reciprocal of `ledger_side`; it is not stored.
Account, classification, internal ledger, voucher, and book must agree.

### Exclusive subtype enforcement

Normal Django checks cannot enforce cross-table subtype cardinality. A deferred
PostgreSQL constraint trigger will enforce at transaction commit:

```text
discriminator = LEDGER
  => exactly one LedgerTransaction and no AccountTransaction

discriminator = ACCOUNT
  => exactly one AccountTransaction and no LedgerTransaction
```

Subtype rows cannot exist without their base row. Bulk-write paths must remain
inside the canonical posting repository so the deferred constraint sees a
complete transaction by commit.

## Posting Batch, Reversal, And Correction

### `TransactionBatch`

Fields: one-to-one protected `voucher`, protected `period`, `posted_at`,
`posted_by_id`, `fingerprint`, nullable protected `reversal_of`, and nullable
`correction_group_key`.

Constraints:

- one batch per posted voucher;
- `(book, fingerprint)` is unique for posted economic effects;
- a reversal points to an earlier batch in the same book and cannot reverse a
  reversal unless a future explicit policy permits it;
- one active reversal per original batch;
- reversal transactions must be an exact opposite, reverse-order image of the
  original, verified by the posting service and a stored verification digest;
- correction consists of an untouched original, its reversal batch, and a new
  replacement voucher/batch sharing a correction group.

No status update substitutes for reversal evidence. Original transaction rows
remain posted and unchanged.

## Open Items And Allocation

### `OpenItem`

References the originating `AccountTransaction`; records due date and immutable
original transaction/base amounts. Outstanding value is derived from active
allocations.

### `OpenItemAllocation`

References one settlement `AccountTransaction` and one `OpenItem`; stores
transaction/base allocated amounts and allocation sequence.

Constraints:

- settlement and open item use the same external account and book;
- allocation currencies agree with the relevant monetary facts;
- allocations cannot exceed the settlement or open-item outstanding amount;
- reversal creates compensating allocation evidence; it does not delete the
  original allocation.

Allocation is explanatory settlement evidence. It never creates a financial
transaction.

## Immutability And Write Boundary

Database triggers will reject update/delete of:

- any transaction or subtype belonging to a posted voucher;
- any posting batch;
- referenced classification versions;
- posted voucher economic/source/rule/idempotency fields;
- original open-item allocations after finalization.

The application exposes one posting repository/service that locks, validates,
fingerprints, writes, and posts atomically. Admin, forms, fixtures, bulk APIs,
and integrations must not write posted tables directly.

## Reporting Views

Initial read-only PostgreSQL views or selectors:

1. conventional journal lines: two projected rows per atomic transaction;
2. internal ledger movements;
3. external account movements;
4. combined trial-balance movements, where external sides map through their
   frozen classification exactly once;
5. classification reconciliation:

```text
external detail
+ direct internal reporting-ledger activity
= trial-balance reporting-ledger value
```

Cached/materialized reports may be added later, but are disposable projections.

## Migration Sequence After K4

Schema work requires a new explicit implementation slice:

1. organization, book, period, and ledger master;
2. external account and classification versions;
3. voucher, base transaction, and exclusive subtypes;
4. one-to-one posting batch and posted-state guards;
5. remaining immutability database functions and triggers;
6. open items and allocations;
7. projection selectors/views and tenant isolation tests.

These are tenant app changes and must use `migrate_schemas`. K5.1 has registered
the app and introduced sequence item 1 plus ledger hierarchy guards. K5.2 and
K5.3 now implement sequence items 2 and 3; later items remain unimplemented.

## K4 Review Result

The accepted pure domain contracts map without requiring a second writable GL
or subledger representation. The persistence design is approved as the basis
for the first model/schema slice, subject to model-level review of every
constraint before migration generation.

## K5.1 Implementation Result

`standalone_accounting.0001_initial` implements organization/book, period, and
ledger master tables. It includes a per-book PostgreSQL daterange exclusion for
overlapping periods and a ledger trigger that protects same-book parenting,
intermediate-only parents, cycle prevention, and posting-leaf integrity even
when model validation is bypassed. It is applied to local tenant schemas
`jcl1`, `jsk`, and `test`; no master rows were seeded. External accounts,
classifications, vouchers, transactions, batches, and allocations do not exist
yet.

## K5.2 Implementation Result

Migration `0002_externalaccount_externalaccountclassification_and_more` adds
book-owned external accounts and their effective-dated classification versions.
PostgreSQL exclusion prevents overlapping ranges; triggers enforce same-book
posting-ledger/reporting agreement, protect all core fields, and prohibit
deletion. A version may only move from open-ended to one closed end date, and
only the atomic append service uses that transition before creating a successor.
A date-aware selector fails unless exactly one version applies. The migration is
applied in `jcl1`, `jsk`, and `test`; no rows were seeded.

## K5.3 Implementation Result

Migration `0003_voucher_accountingtransaction_accounttransaction_and_more`
adds voucher headers, the common positive monetary transaction row, and its
exclusive ledger/account subtypes. Deferred PostgreSQL constraint triggers
require exactly one matching subtype at commit. Immediate guards enforce book,
posting-ledger, side, effective classification, and base-currency consistency;
they also prevent a referenced classification from being shortened across a
voucher date. Draft services construct complete pairs atomically. Authorization
freezes the voucher and all transaction intent, but does not post it. All 63
focused tests pass, and the migration/four tables are verified in `jcl1`, `jsk`,
and `test` with no seeded rows. Posting batches and runtime integration remain
K5.4.

## K5.4 Implementation Result

Migration `0004_transactionbatch_and_more` adds the one-to-one posting batch,
the `POSTED` voucher state, fingerprint state constraints, one-reversal-per-
original structure, and database guards. The canonical repository locks the
voucher and covering period, enforces period purpose, fingerprints the frozen
intent, updates voucher state, and creates the batch in one transaction. A
deferred constraint requires posted state and exactly one batch to appear at
the same commit boundary. Batch rows and posted vouchers are immutable, while
an exact repeated call returns the existing batch. All 67 focused tests pass;
migration/table verification passed in `jcl1`, `jsk`, and `test`. Reversal and
correction execution, open items, projections, and runtime wiring remain later
slices.

## K5.5 Implementation Result

Migration `0005_transactionbatch_reversal_reason_and_more` adds mandatory
reversal-reason evidence and database exactness verification. The reversal
service locks the original, creates a new adjustment voucher, copies monetary
facts in reverse sequence, swaps ledger debit/credit or the internal account
side, retains the original classification FK, authorizes, and posts in one
transaction. PostgreSQL verifies the new batch is an exact reverse-order
opposite, permits only one reversal per original, and rejects reversing a
reversal. Correction composes that reversal with an already authorized
replacement under one correction group. All 71 focused tests pass, and the
migration/trigger are verified in `jcl1`, `jsk`, and `test`; no rows were seeded.

## K5.6 Implementation Result

Migration `0006_openitem_openitemallocation_and_more` adds immutable `OpenItem`
and `OpenItemAllocation` evidence. An open item freezes the exact book, external
account, and transaction/base money of one posted account transaction. An
allocation points to a posted opposite-side account transaction on that same
book/account, carries no ledger effect, and cannot exceed either the settlement
capacity or open-item outstanding capacity. The service locks both capacity
owners; PostgreSQL repeats ownership/currency/side/capacity checks and rejects
update/delete bypasses. A selector derives remaining transaction and base
amounts. All 74 focused tests pass, and migration/tables/triggers are verified
in `jcl1`, `jsk`, and `test`. Compensating allocation evidence for reversed
settlements remains K5.7; original allocation rows will not be mutated.

## K5.7 Implementation Result

Migration `0007_openitemallocation_reversal_of_and_more` adds only the minimum
compensation link required by immutable settlement lifecycle. When reversal
posts, allocations attached to the original settlement transactions are copied
as exact compensations tied to the corresponding reversed transaction. The
database requires original item/money/currencies and financial reversal lineage;
selectors subtract compensations from original allocation totals. All 75 tests
pass, and the migration, column, and revised trigger are verified in `jcl1`,
`jsk`, and `test`. This slice intentionally adds no allocation strategies, UI,
cached balances, reporting tables, or runtime integration.

## K5.8 Implementation Result

No migration or reporting persistence was added. Read-only selectors load only
posted batches for one book and optional effective-date bounds, adapt their
frozen rows to the already-proven pure contracts, and reuse the K2 projection
engine for journal lines, internal/external statements, trial balance, P&L,
balance sheet, and classification reconciliation. A persisted scenario proves
balanced results, draft exclusion, and no writes. All 76 focused tests pass.
This completes the intended persisted MVP kernel proof; further feature work
requires an explicit readiness/pilot decision rather than automatic expansion.
