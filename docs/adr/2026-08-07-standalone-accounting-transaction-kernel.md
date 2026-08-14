---
status: accepted
owner: project
updated: 2026-08-07
tags: [adr, accounting, dea, double-entry, rewrite]
related:
  - ../constitution.md
  - ../domain/accounting.md
  - ../plans/standalone-accounting-kernel-proof.md
  - 2026-06-24-dea-document-voucher-journal-lifecycle.md
---

# ADR: Standalone Accounting Transaction Kernel

Date: 2026-08-07
Status: Accepted after the K0-K3 accounting-kernel proof gate

## Context

DEA currently combines business documents, conventional one-sided voucher
lines, paired general-ledger transactions, account/subledger transactions, and
compatibility dependencies on other Rokkad apps. Reworking those structures in
place would make it difficult to tell whether a new accounting ontology is
sound or merely compatible with the existing implementation.

The supplied *Alex Account TA* and *Ledger - Double Entry* schemas describe a
different relational foundation. A monetary transaction is one atomic
movement, represented either between two internal ledgers or between an
internal ledger and an external account. Compound economic events are batches
of atomic transactions. Debit and credit are reciprocal views of one stored
fact, not independently stored facts that must later be reconciled.

The fuller schema also distinguishes the organization's internal ledger
hierarchy from external personal accounts and uses exclusive base/subtype
relationships. Rokkad needs to test that ontology against modern requirements
such as immutable posting, source traceability, periods, currencies, party
purposes, historical classification, and tenant isolation before adopting it.

## Decision

### Side-by-side proof

1. Build a new package at `apps.tenant_apps.accounting`.
2. Keep it unregistered, model-free, migration-free, URL-free, and disconnected
   from current DEA during the proof phase.
3. Treat current DEA as a reference implementation, not as the persistence
   foundation of the new package.
4. Do not replace current DEA or change an operational posting path until this
   ADR passes its review gate and is accepted explicitly.

### Atomic transaction ontology

1. A transaction is one positive monetary movement with exactly one exclusive
   form:
   - `LEDGER`: internal debit ledger to internal credit ledger.
   - `ACCOUNT`: one internal ledger side and the reciprocal side belonging to
     an external account.
2. A transaction must never have neither form or both forms.
3. An internal ledger-to-ledger transaction must use distinct ledgers.
4. An account transaction must freeze the versioned accounting classification
   that applied to the external account when the transaction was posted.
5. A compound business event is an ordered transaction batch. Atomic pairing
   is explicit before authorization; the posting engine must not invent an
   undisclosed pairing afterward.
6. Reversal creates a new batch whose transactions reverse direction in reverse
   order. It does not edit or delete the original batch.

### External-account meaning

An external account is a genuine transaction side, not a sidecar attached to a
separate complete GL transaction. It represents a Party plus an accounting
purpose, for example customer receivable, supplier payable, borrower loan
receivable, lender loan payable, customer advance, or supplier advance.

The classification version frozen by an account transaction supplies its
financial-statement placement. Historical reports must not depend on a mutable
current classification.

### Durable layers

The target durable flow is:

```text
Source event or business document
  -> Voucher (editable intent until authorization)
    -> Transaction batch
      -> Atomic ledger/account transactions
        -> immutable posted accounting truth
```

Conventional one-sided debit/credit rows may be exposed as an entry aid, import
format, database view, or reporting projection. They are not a second writable
accounting truth.

### Modern controls surrounding the PDF kernel

The eventual Django schema must add organization/book ownership, tenant
isolation, fiscal periods, immutable posting state, idempotency, source-event
identity, rule version, transaction and base currencies, exchange-rate
provenance, authorization, audit data, reversal links, open-item settlement,
and optional analytical dimensions.

Commodity quantities remain outside the monetary transaction kernel.

## Invariants To Prove

1. Every atomic transaction is positive and self-balancing.
2. Ledger transactions cannot use the same ledger on both sides.
3. Account transactions expose reciprocal internal and external sides.
4. Every account transaction carries an immutable classification version.
5. Every batch is non-empty and ordered deterministically.
6. Reversing twice reproduces the original economic directions and amounts.
7. Posted records will be append-only; correction is reversal plus replacement.
8. An idempotency key identifies one economic posting request per book.
9. Transaction currency, base amount, and conversion provenance remain
   explainable without using commodity codes as monetary currencies.
10. Financial-statement projections count each economic side once.

## Proof Gate

This ADR may become `accepted` only after the proof package demonstrates and
documents:

- cash sale and credit sale;
- customer receipt and partial open-item allocation;
- supplier purchase and payment;
- loan disbursal and repayment split into principal, interest, and fees;
- a compound many-sided event as a batch of explicit pairs;
- exact whole-batch reversal;
- conventional journal-line projection without double-counting;
- external-account statements;
- trial balance, balance sheet, and profit-and-loss derivation;
- reconciliation of external classifications to financial statements;
- period-lock and idempotency contracts;
- transaction/base currency behavior; and
- historical stability after an external account is reclassified.

The gate must reject the proposal if external-account transactions require an
independent duplicate GL posting to produce correct financial statements.

### Gate Result: Passed 2026-08-07

The database-free K0-K3 proof passes all 40 focused tests:

- K0 enforces positive atomic pairs, exclusive transaction forms, frozen
  external classifications, ordered batches, currency evidence, and reversal.
- K1 expresses all required cash/credit, customer/supplier, loan, compound, and
  reversal scenarios without duplicate control-ledger postings.
- K2 independently derives conventional journal lines, internal/external
  statements, a balanced trial balance, P&L, balance sheet, classification
  reconciliation, historical classification, and reversal effects.
- K3 proves immutable voucher authorization, source/rule identity, book-scoped
  idempotency and conflict detection, period policy, currency conversion,
  append-only reversal, and correction as reversal plus replacement.

The decisive K2 equation holds:

```text
external-account detail
+ direct internal activity at the reporting ledger
= trial-balance reporting-ledger balance
```

No independent duplicate GL posting is required. The architecture is accepted
for persistence design. This acceptance does not register the app, introduce a
schema, migrate current DEA data, or authorize a runtime cutover.

## Consequences

- The proof can challenge the accounting ontology without risking current DEA.
- Atomic paired transactions become explicit at the voucher boundary.
- Reporting is more demanding because internal ledgers and classified external
  accounts jointly contribute to financial statements.
- Effective-dated classification is foundational rather than optional.
- Existing DEA integrations cannot be copied directly; they will eventually
  submit immutable facts to a new posting boundary.

## Rejected Alternatives

- Rewrite DEA in place: rejected for the proof phase because compatibility
  behavior would obscure architectural correctness.
- Store independent debit and credit rows as the canonical truth: rejected for
  the proof because it abandons the relational premise being evaluated.
- Store a complete GL pair plus an account sidecar for every party transaction:
  rejected as the target because it creates two representations of one amount.
- Copy the PDF literally: rejected because it does not specify all SaaS,
  lifecycle, currency, audit, tax, and source-integration requirements.

## Review Triggers

Review this ADR at the proof gate and before adding Django models, migrations,
app registration, operational posting integration, or any current-DEA cutover.
