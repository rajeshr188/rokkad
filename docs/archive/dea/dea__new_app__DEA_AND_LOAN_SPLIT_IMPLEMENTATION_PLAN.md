---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# DEA and Loan App Split Implementation Plan

Date: 2026-05-10  
Branch context: dea-kiss

---

## 1) Objective

Implement a clean two-app architecture:
- Loan app (girvi): business lifecycle and event production.
- DEA app: accounting processing, controls, and reporting.

This plan defines what each app owns, how they integrate, and how to execute migration without service disruption.

---

## 2) Ownership split

### 2.1 Loan app ownership

Owns:
- LoanContract, LoanScheduleLine, LoanCollateral, LoanRestructure, LoanSettlement.
- Status transitions: DRAFT, APPROVED, ACTIVE, DELINQUENT, NPA, RESTRUCTURED, CLOSED, WRITTEN_OFF.
- Business events:
  - LoanDisbursalEvent
  - LoanAccrualEvent
  - LoanReceiptEvent
  - LoanAllocationEvent
  - LoanRefundEvent
  - LoanPrepaymentEvent
  - LoanRescheduleEvent
  - LoanNPAEvent
  - LoanWriteOffEvent
  - LoanRecoveryAfterWriteOffEvent
  - LoanClosureEvent
  - CollateralReleaseEvent
  - CollateralAuctionEvent
  - LoanTransferInEvent / LoanTransferOutEvent

Does not own:
- VoucherHeader, VoucherLine, JournalEntry, LedgerTransaction, AccountTransaction.

### 2.2 DEA app ownership

Owns:
- VoucherHeader and VoucherLine model lifecycle.
- Posting engine and materialization service.
- Period open/close/lock and controls.
- Audit event stream and approval matrix.
- Financial reporting and reconciliation.

Does not own:
- Loan business policy decisions unrelated to accounting amounts.

---

## 3) Integration contract

### 3.1 Command interface (loan -> DEA)

Single integration command shape:
- tenant_schema
- source_app = "loan"
- source_event_type
- source_event_id
- source_entity_type = "loan"
- source_entity_id
- effective_at
- voucher_type
- economic_payload
- allocation_payload (optional)
- idempotency_key
- requested_by

### 3.2 Response contract (DEA -> loan)

- accepted: bool
- posting_status: DRAFT | POSTED | REJECTED
- voucher_id
- voucher_no
- journal_entry_id
- fingerprint
- error_code
- error_message

### 3.3 Asynchronous reliability

- Use outbox in loan app for event publication.
- DEA consumes and posts idempotently.
- DEA emits posting outcome event; loan app consumes and updates state.

---

## 4) State coupling rules

1. Loan may enter ACTIVE only after disbursal event is POSTED in DEA.
2. Loan may enter CLOSED only after principal and accrual buckets are zeroed (or waiver/write-off posted).
3. Loan may enter WRITTEN_OFF only after write-off voucher is POSTED.
4. Any correction requires reversal event chain and DEA confirmation.

---

## 5) App-level module structure

### 5.1 Loan app modules

- service_modules/loan_events.py
  - CreateLoanDisbursalEvent
  - CreateLoanAccrualEvent
  - CreateLoanReceiptEvent
  - CreateLoanWriteOffEvent
- service_modules/loan_accounting_adapter.py
  - dispatch_to_dea(event)
  - handle_dea_posting_result(result)

### 5.2 DEA app modules

- services/post_doc.py (entry)
- services/materialize_journal.py (core materialization)
- posting/rules/loan_*.py (loan-specific accounting mapping)
- models/voucher.py (VoucherHeader + VoucherLine)
- models/journal.py, models/ledger.py, models/account.py

---

## 6) Security and tenancy

- All integration commands must include and validate active tenant schema.
- Reject commands without schema context.
- Include tenant metadata in audit events and logs.
- Cache keys and retries are tenant-prefixed.

---

## 7) Migration plan

### Stage 1: Introduce contract in parallel

- Keep current direct calls working.
- Add adapter interfaces in loan app.
- Route a small subset of loan events through adapter in shadow mode.

Exit criteria:
- Shadow-posted voucher outputs match current postings for sampled events.

### Stage 2: Cut over loan events

- Move all loan accounting triggers to adapter.
- Disable direct posting writes from loan code paths.

Exit criteria:
- No loan module creates JournalEntry/LedgerTransaction directly.

### Stage 3: Harden and enforce

- Add lint/test guard to block cross-app write violations.
- Add contractual schema checks and idempotency enforcement.

Exit criteria:
- Contract tests and tenant isolation tests pass in CI.

---

## 8) Test strategy for split architecture

### 8.1 Contract tests

- Loan event payload schema validation.
- Idempotency key duplicate behavior.
- Error mapping and retry semantics.

### 8.2 End-to-end tests

- Disbursal -> posted voucher -> loan ACTIVE transition.
- Receipt + allocation -> posted -> balances update.
- Write-off -> posted -> state change.
- Recovery -> posted -> income recognized.

### 8.3 Regression tests

- Ensure existing voucher types still post correctly.
- Ensure period close catches unresolved loan accounting items.

---

## 9) Non-negotiable boundaries

1. Loan app cannot mutate DEA posted tables.
2. DEA app cannot own loan business lifecycle states.
3. Every accounting-impacting loan state transition requires DEA POSTED confirmation.
4. Reversals happen in DEA, then loan consumes resulting status.

---

## 10) Execution backlog (high-level)

1. Create LoanAccountingService adapter in loan app.
2. Define integration DTO schema and validators.
3. Introduce DEA command endpoint/service for external app posting requests.
4. Move disbursal and receipt first.
5. Move accrual and allocation next.
6. Move write-off/recovery and closure last.
7. Enforce boundaries with tests and static checks.

This sequence minimizes risk by migrating highest-volume, lowest-complexity events first.

