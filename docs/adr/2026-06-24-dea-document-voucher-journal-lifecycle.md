---
status: accepted
owner: dea
updated: 2026-06-24
tags: [adr, dea, accounting, posting, lifecycle, reversal, idempotency]
related:
  - ../constitution.md
  - ../domain/accounting.md
  - ../audits/dea_core_accounting_commodity_analysis.md
  - ../roadmaps/dea_commodity_accounting_refactor_plan.md
  - ../implementation/dea-monetary-currency-guardrails.md
---

# ADR: DEA Document, Voucher, Journal Lifecycle

Date: 2026-06-24
Status: Accepted
Owners: DEA Team, Platform Architecture

## Summary

DEA will use an explicit business-document -> voucher -> journal lifecycle.

Business documents capture business facts. Vouchers capture accounting intent for those facts. Posted vouchers create immutable financial journal entries and, in the future commodity layer, immutable commodity movements. Corrections happen through reversal and new corrected postings, not by editing posted accounting records in place.

This ADR is the Phase 2 anchor for the DEA commodity-accounting refactor. It must be implemented before large posting, commodity, or UI refactors.

## Context

Rokkad's constitution says:

1. Business events become source documents or explicit domain events.
2. Source documents and domain events become vouchers.
3. Posted vouchers create immutable journal entries.
4. Corrections happen through reversals.
5. Posted journal entries are not edited in place.
6. Every accounting effect must be traceable to its source document or domain event.

The current DEA implementation mostly follows this direction, but the contract is spread across models, services, posting engine code, views, and comments.

Current evidence:

- `apps/tenant_apps/dea/models/doc.py::BusinessDoc.save()` can auto-post after save and logs/swallow failures.
- `apps/tenant_apps/dea/models/voucher.py::VoucherStatus` has `DRAFT`, `POSTED`, `CORRECTED`, and `REVERSED`.
- `apps/tenant_apps/dea/models/voucher.py::Voucher` links to a source document through `doc_content_type`, `doc_object_id`, and `business_doc`.
- `apps/tenant_apps/dea/models/voucher.py::Voucher.fingerprint` is already used for idempotency.
- `apps/tenant_apps/dea/models/voucher.py` has active uniqueness constraints for one posted voucher per document/type and active fingerprint uniqueness.
- `apps/tenant_apps/dea/models/voucher.py::VoucherLine.clean()` blocks line edits when the voucher is posted or reversed.
- `apps/tenant_apps/dea/models/journal.py::JournalEntry.clean()` and `delete()` block modification/deletion when the owning voucher is posted.
- `apps/tenant_apps/dea/posting/engine.py::BasePostingEngine.post()` locks the voucher row, validates period openness, computes a fingerprint, materializes journal rows, and updates voucher status.
- `apps/tenant_apps/dea/posting/engine.py::BasePostingEngine.reverse_voucher()` creates a reversal journal entry and marks the voucher reversed.
- `apps/tenant_apps/dea/views/voucher.py` still contains direct post/reverse helper logic that duplicates newer posting-engine responsibilities.
- `apps/tenant_apps/dea/models/payment.py::PaymentVoucher.posted` is a separate boolean state that overlaps with accounting voucher status.

The DEA commodity audit also found that commodity effects must not be represented as financial journal currencies. Future commodity postings need their own immutable movement/exposure records that are created side-by-side with financial journal entries.

## Decision

### 1. Business Documents Are Source Facts

A business document is the source record for an accounting-relevant business fact.

Examples:

- Fixed purchase.
- Unfixed purchase.
- Rate fixing.
- Fixed sale.
- Receipt from customer.
- Payment to supplier.
- Karigar metal issue.
- Karigar metal receipt.
- Financial journal voucher.
- Girvi disbursal or repayment event.

Long-lived operational aggregates are not automatically one accounting document. For example, a loan aggregate can create multiple accounting-relevant events: disbursal, repayment, release, auction, sale, interest accrual, and correction.

Business document states are:

| State | Meaning | Editable? | Posting allowed? |
|---|---|---:|---:|
| `DRAFT` | Incomplete or still being edited. | Yes | No |
| `SUBMITTED` / `READY` | Business payload is complete and ready for accounting validation. | Limited metadata only | Yes |
| `POSTED` | Accounting effects have been created successfully. | No economic edits | No duplicate post |
| `CORRECTED` | Superseded by a corrected document/posting. | No | No |
| `CANCELLED` | Abandoned before posting or voided by policy before effects exist. | No | No |
| `CLOSED` | Operationally complete after settlement/fixing/fulfilment. | No economic edits | No |

Not every existing DEA `BusinessDoc` subclass currently has this state field. This ADR defines the target lifecycle contract; implementation may use compatibility adapters during migration.

### 2. Vouchers Are Accounting Intent

A voucher represents the accounting intent generated from one source event.

Target voucher states are:

| State | Meaning | Allowed next states |
|---|---|---|
| `DRAFT` | Accounting impact has been prepared but not posted. | `POSTED`, abandoned/deleted if no effects exist |
| `POSTED` | Financial journal rows and any sidecar effects were created. | `REVERSED`, `CORRECTED`, `CLOSED` through source workflow |
| `REVERSED` | The posted effects have been negated by a reversal entry. | Terminal for that voucher |
| `CORRECTED` | The posted effects were superseded by a corrected voucher/document. | Terminal for that voucher |

`CANCELLED` is a source-document state unless a later migration explicitly adds a voucher cancellation state for unposted draft vouchers. Posted vouchers are not cancelled; they are reversed or corrected.

One source event should have at most one active posted voucher per voucher type. A long-lived aggregate can have multiple source events, each with its own voucher identity.

### 3. Journal Entries Are Immutable After Posting

A posted financial journal entry is an immutable accounting record.

Allowed behavior:

- Create journal entries only through the posting engine or a canonical posting service.
- Link each journal entry to its voucher.
- Link reversal journal entries to the original journal entry through `is_reversal_of`.
- Correct mistakes by reversing the old effects and creating a new corrected voucher/journal entry.

Forbidden behavior:

- Editing posted journal entries in place.
- Deleting posted journal entries.
- Editing ledger/account transaction rows under a posted journal entry.
- Treating commodity quantity movements as financial journal currency lines.

Existing model-level protections cover `JournalEntry` and `VoucherLine` in supported save/delete paths. Follow-up work must add tests for `LedgerTransaction` and `AccountTransaction` immutability and close any gaps.

### 4. Commodity Movements Will Follow The Same Immutability Rule

When DEA introduces the commodity layer, commodity movements and exposure lines must be created side-by-side with financial postings, but they must not be materialized into `LedgerTransaction`.

Future commodity records:

- `CommodityMovement`
- `ExposureLine`
- `RateFixing`
- derived `CommodityPosition`

Target rule:

- Posted commodity movement rows are immutable.
- Corrections create an opposite commodity movement and, when needed, a corrected source document.
- Financial valuation entries are separate financial journal entries in monetary currency.

### 5. Posting Fingerprints Live At The Voucher/Posting Boundary

The posting fingerprint is the idempotency key for accounting effects.

The fingerprint payload must include:

- Source document identity or source event identity.
- Voucher type.
- Rule version.
- Business-effective date.
- Economic payload fields only.
- Monetary fields as monetary amounts/currencies.
- Future commodity fields as explicit metal, UOM, gross weight, purity, fine weight, rate/fixed-status fields.

The fingerprint payload must not include incidental UI-only fields or mutable display metadata unless those fields change accounting effects.

The current `Voucher.fingerprint` and active uniqueness constraint are the right location for MVP. If future posting requests become first-class records, they may hold the incoming idempotency key, but the voucher must still retain the effective posting fingerprint that created accounting effects.

### 6. Posting Must Be Atomic And Race-Safe

Posting must run in one database transaction.

Required controls:

- Lock the voucher row with `select_for_update()`.
- When posting from a source document/event, lock the source or source-event row when practical.
- Validate accounting period openness inside the posting path.
- Compute the fingerprint from the locked payload.
- Enforce a unique active fingerprint.
- Enforce one active posted voucher per source event/type.
- Materialize voucher lines, journal entry, ledger transactions, account transactions, future commodity movements, and future exposure rows atomically.
- Fail the whole post if any required accounting/commodity effect fails.

Direct view-level posting paths should become thin wrappers around the canonical posting command/service.

### 7. Corrections Use Reversal, Not In-Place Edit

Draft documents and draft vouchers are editable.

Posted documents and posted vouchers are not economically editable. Corrections must use one of these patterns:

| Situation | Required pattern |
|---|---|
| Typo or metadata that has no economic effect | Metadata amendment with audit trail, no new posting |
| Wrong amount, ledger, party, currency, metal, purity, rate, date, or tax | Reverse old effects and create corrected document/voucher |
| Duplicate posted document | Reverse duplicate effects and mark duplicate as corrected/reversed |
| Cancel before posting | Cancel/delete draft according to permission policy |
| Cancel after posting | Reverse accounting and commodity effects; source document becomes corrected/reversed, not silently deleted |

Reversal should preserve traceability to the original voucher, original journal entry, source document, actor, timestamp, reason, and period.

## Canonical Lifecycle

```text
Business Document
  DRAFT
    -> SUBMITTED/READY
      -> Posting Command
        -> Voucher DRAFT
          -> Voucher POSTED
            -> JournalEntry + LedgerTransaction + AccountTransaction
            -> Future CommodityMovement + ExposureLine
              -> CLOSED
              -> REVERSED
              -> CORRECTED -> new corrected document/voucher
```

## Implementation Direction

Near-term implementation order:

1. Add posted immutability tests for `JournalEntry`, `VoucherLine`, `LedgerTransaction`, and `AccountTransaction`.
2. Add posting idempotency and double-submit tests around existing `Voucher.fingerprint`, `unique_fingerprint_active`, and `select_for_update()` behavior.
3. Document the canonical posting path and mark `views/voucher.py` direct materialization as legacy.
4. Introduce one reversal/correction service contract and route UI commands through it.
5. Disable or replace `BusinessDoc.save()` implicit auto-post behavior for meaningful runtime documents.
6. Reconcile duplicate state such as `PaymentVoucher.posted` with voucher status.
7. Only after these controls are covered, introduce commodity movement/exposure models side-by-side.

## Consequences

Positive:

- Clear source-of-truth boundaries.
- Better protection against duplicate postings.
- Easier commodity sidecar introduction without polluting financial journals.
- Better audit trail for corrections and reversals.
- UI can become business-event centric while accountants still inspect vouchers and journal entries.

Costs:

- Existing direct view posting paths need migration.
- Existing documents without explicit lifecycle states need compatibility handling.
- Some model-level immutability gaps may require migrations or validation changes.
- Historical data may need verification before enforcing stricter uniqueness and currency/commodity guards.

## Open Questions

1. Whether every operational document should store an explicit lifecycle field or whether some domain events should remain event-table records only.
2. Whether reversal vouchers should be separate voucher records in all cases, or whether the current same-voucher reversal journal pattern is retained temporarily for compatibility.
3. Whether `CORRECTED` should mean "original was superseded" or "new corrected voucher" in all UI labels. The target meaning in this ADR is "original was superseded."
4. How far back production data needs to be normalized before strict fingerprint/currency enforcement is enabled.

## Review Trigger

Review this ADR when:

1. Commodity movement models are introduced.
2. Posting requests become first-class durable records.
3. Direct view-level posting paths are removed.
4. Production data verification finds existing metal-like values in financial currency columns.
