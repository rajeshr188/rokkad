---
status: accepted
owner: project
updated: 2026-08-16
tags: [adr, loans, accounting, retirement]
related: [../constitution.md, ../plans/accounting-retirement.md]
---

# Retire Accounting And Make Loans Operationally Independent

## Context

Rokkad is being narrowed to Party, Loans, Notify v2, and Rates as its supported
tenant business applications. DEA, tenant Accounting, and Standalone Accounting
are outside that target. Loans currently emits immutable `PawnLoanAccountingEvent`
rows and optional delivery outbox rows to DEA. Those event rows also drive Loans'
own balances, allocations, tranches, releases, renewals, auctions, reports, and
reversals, so they are not merely an integration artifact.

## Decision

Retire DEA, tenant Accounting, and Standalone Accounting completely. Loans will
not create vouchers, journals, ledger accounts, account mappings, trial balances,
or financial statements.

Loans will retain immutable operational evidence for every completed financial
lifecycle action. Existing accounting-event concepts will first be separated
from external delivery, then renamed or replaced by Loans-owned operational event
terminology without losing identifiers, frozen payloads, allocation lines,
reversal links, or balance reproducibility.

Party portal and merge behavior will use only Party and Loans data. Notify v2
will consume Loans-owned notice intents. Rates remains a reference-data source.

Loans uses cash-only interest recognition. Monthly accrual rows remain
operational calculations of borrower amounts due, and contractual compound
capitalization remains a Loans-domain operation, but ACCRUAL is not a selectable
recognition basis. Existing development rows are normalized to CASH.

Because the project is in development, the final migration history will be
rewritten and databases rebuilt from empty after runtime decoupling. Historical
production accounting data migration is not required.

## Consequences

- The product will have no double-entry ledger, vouchers, journals, accounting
  periods, trial balance, or general financial statements.
- Loan balances remain auditable within the Loans domain through immutable event
  evidence and explicit reversals.
- DEA delivery retries, readiness checks, reconciliation, ledger configuration,
  and accounting reports are removed rather than replaced.
- Economic policy screens do not expose a recognition-basis choice; CASH is the
  sole supported value.
- UI and documents must use operational terms such as event, transaction,
  receipt, balance, and reversal rather than voucher or journal.
- A fresh database must create no DEA, tenant-Accounting, or
  Standalone-Accounting tables, permissions, ContentTypes, routes, or seed data.

## Rejected Alternatives

- Keeping DEA behind a new adapter: rejected because DEA is itself retiring.
- Migrating Loans to Standalone Accounting: rejected because all accounting is
  intentionally outside the target product.
- Deleting Loans accounting-event rows immediately: rejected because they are
  currently canonical inputs to balances and lifecycle invariants.
