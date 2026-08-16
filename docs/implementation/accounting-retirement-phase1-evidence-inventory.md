---
status: active
owner: project
updated: 2026-08-16
tags: [implementation, loans, accounting, retirement]
related: [../adr/2026-08-16-retire-accounting.md, ../plans/accounting-retirement.md]
---

# Accounting Retirement Phase 1 Evidence Inventory

## Finding

`PawnLoanAccountingEvent` is misnamed for the target architecture but is not
disposable accounting integration state. It is the canonical economic event
stream folded by Loans to calculate principal, interest, fees, settlement,
closure readiness, tranche allocation, renewal transfer, auction recovery, and
reversal effects. Its removal must follow a Loans-owned replacement or rename.

`PawnLoanAccountingOutbox` is different: it exists to deliver those events to
DEA and can be retired once workflow idempotency and result contracts no longer
depend on it.

## Field Classification

### Preserve As Loans Operational Evidence

From `PawnLoanAccountingEvent`:

- `loan`: aggregate ownership and workspace reachability.
- `event_kind`: economic transition vocabulary.
- `effective_date`: as-of balance ordering.
- `payload`: frozen principal, interest, fee, allocation, and reversal values.
- `payload_fingerprint`: reproducibility and tamper evidence.
- `idempotency_key`: duplicate-command protection.
- `reversal_of`: explicit compensation chain.
- `created_by`, `created_at`: actor and audit chronology.

Preserve related immutable evidence:

- disbursal and policy snapshots;
- interest accruals and accrual lines;
- repayment allocation lines;
- principal opening and closing allocation lines;
- releases, release items, and release reversals;
- auctions, auction items, and auction reversals;
- renewals, successor evidence, and renewal reversals;
- collateral custody events and immutable change logs.

### Retire As Accounting Delivery State

From `PawnLoanAccountingOutbox`:

- delivery payload and contract version;
- pending/processing/posted/failed delivery status;
- claim, retry, availability, delivery, and error fields;
- `dea_voucher_id` and `dea_journal_entry_id`.

The outbox row and its relationship are removable only after Loans workflows no
longer return it, wait on it, or use its state as a balance/closure blocker.

### Rename Or Remove As Obsolete Terminology

- `PawnLoanAccountingEvent` -> Loans operational/economic event.
- `accounting_events` relations -> operational/economic events.
- `accounting_event` foreign-key field names -> operational/economic event.
- `accounting_recognition` policy -> remove after interest behavior is expressed
  solely as a Loans calculation policy.
- `posting_ready`, `posting_blockers`, and accounting-health UI -> remove.
- document `accounting.delivery` and `accounting.references` -> remove.

## Current Direct DEA Import Boundary

Loans runtime DEA imports are confined to:

- `integrations/dea_delivery.py`
- `integrations/dea_payloads.py`
- `services/accounting_readiness.py`
- `services/borrower_accounting.py`
- `selectors/accounting_reconciliation.py`
- `selectors/reports.py`

Party runtime DEA imports are confined to portal invoice/payment reads and
Party account-mapping merge behavior. These are Phase 5 removal targets.

No target runtime app currently imports Standalone Accounting directly.

## Sequencing Constraint

First remove DEA readiness and delivery as workflow requirements. Next remove
the outbox and delivery-only result fields. Only then rename the preserved event
spine and its related fields. This keeps balances and reversals continuously
testable throughout retirement.
