# DEA From-Scratch System Architecture Plan

Branch context: dea-kiss  
Date: 2026-05-10

---

## 1) Vision and design principles

Build an accounting core that is:
- Correct first: no silent imbalance, no mutable posted data.
- Explainable: every number in reports can be traced to source events.
- Operationally safe: period controls, approvals, audit evidence, rollback strategy.
- Tenant-safe by default under django-tenants schema isolation.
- Extensible: new business docs can plug into posting without rewriting core engine.

Core principles:
- Source of truth chain: Business Event -> Accounting Document -> Journal Entry -> Reports.
- Reversal, never mutation: corrections are new documents linked to originals.
- Deterministic posting: same input produces same output.
- Idempotent processing: retries do not duplicate accounting impact.
- Explicit lifecycle states: draft, approved, posted, reversed, corrected.

---

## 2) Target capability scope

### 2.1 Day-1 mandatory scope
- Chart of accounts and subledgers.
- Voucher lifecycle with line-level accounting intent.
- Journal posting engine with balance validation.
- Period open/close/lock workflows.
- Trial balance, P and L, balance sheet, GL ledger report.
- Audit trail and role-based permissions.
- Bank reconciliation basic workflow.

### 2.2 Phase-2 scope
- Depreciation, prepaid amortization, accrual scheduler.
- FX revaluation and multi-currency reporting.
- Approval matrix by amount and voucher type.
- API for posting and reporting integrations.

### 2.3 Deferred scope
- Full inventory costing.
- Forecasting and analytics.
- Advanced consolidation.

---

## 3) Domain model (from scratch)

### 3.1 Layer A: Business event models
Purpose: capture economic events in business language.

Examples:
- SalesInvoice
- PurchaseInvoice
- PaymentReceipt
- PaymentDisbursement
- LoanDisbursal
- LoanRepayment
- ExpenseClaim
- ManualAdjustmentRequest

Rules:
- Business model save never directly mutates ledger balances.
- Business models carry operational fields, not GL pairing logic.
- Business models emit accounting-intent requests to accounting layer.

### 3.2 Layer B: Accounting document models
Purpose: persistent accounting intent before posting.

Models:
- VoucherHeader
  - voucher_no, voucher_type, voucher_date, status
  - source_object reference
  - fingerprint and posting metadata
- VoucherLine
  - voucher FK, line_no
  - side (Dr/Cr)
  - ledger FK
  - optional account FK
  - amount, amount_base, currency, fx rate
  - tax tags and narration

Rules:
- Voucher lines are editable only while draft.
- Posting always consumes VoucherLine as source of truth.
- Validation requires Dr equals Cr by currency and base amount.

### 3.3 Layer C: Posted accounting models
Purpose: immutable accounting record.

Models:
- JournalEntry
  - voucher FK, period FK, posted_by, posted_at
  - reversal linkage
- LedgerTransaction
  - dual-leg row: debit ledger, credit ledger, amount
- AccountTransaction
  - subledger attribution row from voucher lines with account

Rules:
- Posted rows are immutable.
- Any correction uses reversal and replacement voucher.

### 3.4 Control and governance models
- AccountingPeriod: OPEN, CLOSED, LOCKED
- ApprovalPolicy and ApprovalRequest
- AccountingAuditEvent
- PostingErrorQueue for failed/blocked jobs
- Reconciliation models for bank statement matching

### 3.5 Loan domain model set (comprehensive)
Purpose: model the complete loan lifecycle with explicit accounting events.

Core loan entities:
- LoanContract
  - contract_no, product, borrower, principal, rate model, tenure
  - disbursal_date, maturity_date, status
- LoanScheduleLine
  - due_date, principal_due, interest_due, fee_due, penalty_due
- LoanCollateral
  - asset details, valuation snapshots, custody status
- LoanSettlement
  - payoff quote, settlement date, write-off/waiver components
- LoanRestructure
  - old terms, new terms, effective date, approval linkage

Accounting event entities (source for voucher generation):
- LoanDisbursalEvent
- LoanAccrualEvent (interest/fee accrual)
- LoanReceiptEvent (cash collection)
- LoanAllocationEvent (how receipt split to interest/principal/fees/penalty)
- LoanRefundEvent (excess receipt returned)
- LoanPrepaymentEvent
- LoanRescheduleEvent
- LoanNPAEvent (stage migration and recognition switch)
- LoanWriteOffEvent
- LoanRecoveryAfterWriteOffEvent
- LoanClosureEvent
- CollateralReleaseEvent
- CollateralAuctionEvent
- LoanTransferInEvent / LoanTransferOutEvent

Rules:
- Every loan accounting event maps to exactly one voucher type and one posting rule version.
- Loan operational state changes are blocked until accounting event reaches POSTED status.
- Allocation (principal vs interest vs fees vs penalty) is explicit and immutable once posted.

---

## 4A) Loan event handling architecture (all events)

### 4A.1 Canonical loan event catalog and accounting intent

1. Origination only (no cash movement)
- Event: LoanContractCreated
- Typical accounting: none (memo only), unless policy requires processing fee recognition.

2. Disbursal
- Event: LoanDisbursalEvent
- Posting: Dr Loan Receivable / Cr Cash-Bank

3. Periodic interest accrual
- Event: LoanAccrualEvent
- Posting: Dr Interest Receivable / Cr Interest Income

4. Fee accrual (processing/admin/renewal)
- Event: LoanFeeAccrualEvent
- Posting: Dr Fee Receivable / Cr Fee Income

5. Penalty accrual
- Event: LoanPenaltyAccrualEvent
- Posting: Dr Penalty Receivable / Cr Penalty Income

6. Receipt against loan
- Event: LoanReceiptEvent + LoanAllocationEvent
- Posting sequence by policy order:
  - Dr Cash-Bank / Cr Interest Receivable (first)
  - Dr Cash-Bank / Cr Penalty Receivable
  - Dr Cash-Bank / Cr Fee Receivable
  - Dr Cash-Bank / Cr Loan Receivable (principal)

7. Excess receipt refund
- Event: LoanRefundEvent
- Posting: Dr Liability-Excess Collection / Cr Cash-Bank (or reverse prior excess)

8. Prepayment/foreclosure
- Event: LoanPrepaymentEvent
- Posting: Dr Cash-Bank / Cr Loan Receivable (+ charges as applicable)
- Trigger closure checks and residual writeback if needed.

9. Restructure/reschedule
- Event: LoanRescheduleEvent
- Posting: usually no immediate GL principal movement; may require
  deferred fee recognition adjustment entries.

10. NPA/stage migration
- Event: LoanNPAEvent
- Posting: recognition policy switch; may stop income accrual and move to
  suspense/unrealized buckets based on policy.

11. Provisioning
- Event: LoanProvisionEvent
- Posting: Dr Provision Expense / Cr Expected Credit Loss Allowance

12. Write-off
- Event: LoanWriteOffEvent
- Posting: Dr Allowance (or Write-off Expense) / Cr Loan Receivable

13. Recovery after write-off
- Event: LoanRecoveryAfterWriteOffEvent
- Posting: Dr Cash-Bank / Cr Recovery Income

14. Collateral auction realization
- Event: CollateralAuctionEvent
- Posting:
  - Dr Cash-Bank / Cr Loan Receivable (to covered amount)
  - residual gain/loss to auction gain-loss ledger per policy

15. Collateral release on closure
- Event: CollateralReleaseEvent
- Posting: generally no GL movement; mandatory custody audit event.

16. Loan transfer out (assignment/securitization)
- Event: LoanTransferOutEvent
- Posting: derecognize receivable; recognize proceeds and gain/loss.

17. Loan transfer in
- Event: LoanTransferInEvent
- Posting: Dr Loan Receivable / Cr Cash-Bank (plus premium/discount handling).

18. Waiver/discount granted
- Event: LoanWaiverEvent
- Posting: Dr Waiver Expense / Cr Receivable bucket waived.

19. Reversal/correction for any event
- Event: LoanEventReversal
- Posting: exact mirror via reversal voucher linked to original event.

### 4A.2 Loan lifecycle state machine (operational + accounting)

States:
- DRAFT -> APPROVED -> ACTIVE -> DELINQUENT -> NPA -> RESTRUCTURED -> CLOSED -> WRITTEN_OFF

Guardrails:
- ACTIVE requires posted disbursal.
- CLOSED requires receivable and accrued components to be zero (or explicitly waived/write-off posted).
- WRITTEN_OFF requires provisioning/write-off approval and posted voucher.
- Any backward transition requires reversal chain and approval.

### 4A.3 Loan posting orchestration

Command handlers:
- CreateLoanDisbursalVoucher
- AccrueLoanInterestCommand
- PostLoanReceiptAndAllocateCommand
- ForeclosureSettlementCommand
- WriteOffLoanCommand
- RecoverWrittenOffLoanCommand

All handlers must:
- lock loan row + open loan events for update
- ensure idempotency by event fingerprint
- generate VoucherHeader + VoucherLine
- call common materialization service
- append domain + audit events

### 4A.4 Allocation policy engine

Receipt allocation policy should be configurable per product:
- PRIORITY_INTEREST_FIRST
- PRIORITY_PENALTY_FIRST
- PRO_RATA
- PRINCIPAL_FIRST (rare, explicit override)

Allocation output is persisted in LoanAllocationEvent and cannot be recomputed after posting.

### 4A.5 Loan event failure handling

- Failed posting moves event to PostingErrorQueue with reason and retry token.
- Loan state transition remains blocked until retry success or approved override.
- Overrides require maker-checker and mandatory justification.

---

## 4) Posting architecture

### 4.1 Pipeline
1. Accept request to post a voucher.
2. Lock voucher header and lines.
3. Verify status and approvals.
4. Recompute fingerprint from economic payload + lines.
5. Validate balance and mandatory dimensions.
6. Resolve accounting period from voucher date.
7. Materialize JournalEntry and transactions.
8. Update voucher status and posted metadata.
9. Emit audit event and outbox integration event.

### 4.2 Idempotency strategy
- Unique fingerprint constraint for active posted/corrected states.
- Unique posted voucher per source business object.
- Retry-safe engine that returns existing JournalEntry on duplicate intent.

### 4.3 Deterministic pairing strategy
Since ledger transaction table is dual-leg, generate rows by pairing debit lines with credit lines sorted by line_no.

Algorithm:
- Separate Dr and Cr lines by currency.
- Pair greedily with min(remaining_dr, remaining_cr).
- Emit stable row order.

This guarantees stable posted output for the same voucher lines.

---

## 5) Multi-tenant architecture under django-tenants

### 5.1 Boundary model
- Tenant data isolation lives in schema separation.
- No cross-tenant joins for DEA transactional tables.

### 5.2 Hardening points
- Assert tenant schema context at every mutation entrypoint:
  - posting
  - period close/lock
  - scheduled accrual/depreciation jobs
  - management commands
- Tenant-aware logging fields on every audit event.
- Tenant-prefixed cache keys and file storage paths.

### 5.3 Operational safeguards
- Background jobs iterate tenants explicitly and switch schema per tenant.
- Any command run without tenant context fails fast.

---

## 6) Period-end architecture

### 6.1 Pre-close checklist service
Checks:
- unposted drafts
- unresolved reconciliation exceptions
- missing accrual/depreciation/prepaid entries
- trial balance sanity checks
- FX revaluation pending
- loan accrual catch-up complete for all active loans
- no orphan loan allocation events (receipt without posted allocation)
- no loan in CLOSED status with non-zero receivable/accrual balances

### 6.2 Close process
1. Soft-close validation pass.
2. Auto-post scheduled period-end entries if enabled.
3. Post closing entries to retained earnings.
4. Generate signed period snapshots.
5. Mark CLOSED.
6. Optional hard lock to LOCKED.

### 6.3 Reopen policy
- Reopen only with elevated role and mandatory reason.
- Full audit event required.

---

## 7) Reporting architecture

### 7.1 Data strategy
- Closed periods use snapshot tables.
- Open periods use incremental balance materialization.
- Drill-down path always available:
  report line -> ledger/account -> journal entry -> voucher line -> business source.

### 7.2 Core report pack
- Trial Balance
- Profit and Loss
- Balance Sheet
- Cash Flow (indirect)
- General Ledger
- AR and AP aging
- Loan Portfolio Register (active, delinquent, NPA, written-off)
- Loan Accrual vs Collection report
- Loan Stage Migration and Provision movement report
- Loan Recovery after Write-off report

### 7.3 Performance targets
- Trial balance for medium tenant under 200 ms using materialized balances.
- All reports filterable by period and exportable.

---

## 8) Security and controls

- RBAC with accountant roles.
- Approval matrix for high-value and sensitive voucher types.
- Immutable audit event stream.
- Reversal-only corrections.
- Constraint-first data integrity at DB layer.
- Explicit anti-tamper checks for posted documents.

---

## 9) Integration architecture

### 9.1 Internal integration pattern
- Use application services and command handlers.
- Domain events persisted in outbox table.
- Asynchronous consumers for non-critical side effects.

### 9.2 External API surface
- Post voucher endpoint
- Voucher status endpoint
- Trial balance and ledger transaction endpoints
- Period metadata endpoint
- Loan event ingestion endpoint (disbursal, receipt, accrual, write-off)
- Loan allocation query endpoint (receipt split transparency)

All endpoints are authenticated, rate-limited, and tenant-context validated.

---

## 10) Build and rollout plan (from scratch)

### Phase A: Core ledger engine (4-6 weeks)
- Implement layer B and C models first.
- Build posting materialization service.
- Build period model and close guardrails.
- Ship minimal report pack.

Exit criteria:
- Can post manual and sales/payment vouchers.
- Can close a period safely.
- Trial balance and GL report reconcile.

### Phase B: Business adapters (4-6 weeks)
- Connect loan, sales, purchase, expense business models.
- Add idempotent posting commands and queue retries.
- Add reconciliation MVP.
- Implement full loan event command set and allocation policy engine.

Exit criteria:
- End-to-end cash in/cash out and invoice lifecycle complete.
- End-to-end loan lifecycle complete from disbursal to closure/write-off/recovery.

### Phase C: Controls and automation (4-6 weeks)
- Approval matrix and audit event model.
- Depreciation, prepaid, accrual services.
- FX revaluation.

Exit criteria:
- Accountant-grade period-end workflow complete.

### Phase D: Scale and operations (3-4 weeks)
- Materialized balances and performance tuning.
- API hardening and observability dashboards.
- Runbooks and failure drills.

Exit criteria:
- SLOs met, incident playbooks validated.

---

## 11) Testing strategy

### 11.1 Unit tests
- VoucherLine validation and balancing.
- Pairing algorithm determinism.
- Idempotency/fingerprint behavior.

### 11.2 Integration tests
- Business event to posted journal path.
- Reversal/correction workflows.
- Period close and reopen policy.
- Loan lifecycle path tests for all loan events (disbursal, accrual, receipt allocation, prepayment, write-off, recovery, closure).
- Loan state guardrail tests (no closure with residual balances, no state advance without posted event).

### 11.3 Tenant safety tests
- Schema context guards in jobs and commands.
- Cross-tenant leakage negative tests.

### 11.4 Performance tests
- High-volume posting throughput.
- Report latency thresholds.

---

## 12) Migration and cutover approach

If replacing an existing DEA:
1. Freeze legacy posting for a cutover window.
2. Migrate open documents into VoucherHeader and VoucherLine.
3. Rebuild posted snapshots from immutable journal tables.
4. Parallel run and reconcile trial balance for at least one period.
5. Switch write traffic to new engine.
6. Keep legacy system read-only for audit lookup.

---

## 13) Non-negotiable invariants

- No posted voucher without lines.
- No journal entry without balanced voucher lines.
- No mutation of posted lines or journal transactions.
- No period close with unresolved critical checks.
- No accounting mutation without tenant schema context.
- No integration event without durable outbox record.

---

## 14) Recommended first implementation order in this repository

1. VoucherLine model and migration in [apps/tenant_apps/dea/models/voucher.py](apps/tenant_apps/dea/models/voucher.py).
2. Materialization service in [apps/tenant_apps/dea/services](apps/tenant_apps/dea/services).
3. Engine cutover in [apps/tenant_apps/dea/posting/engine.py](apps/tenant_apps/dea/posting/engine.py).
4. Draft UI formset in [apps/tenant_apps/dea/forms_vouchers.py](apps/tenant_apps/dea/forms_vouchers.py) and voucher views/templates.
5. Period-close checklist and controls in DEA period views/services.
6. Snapshot-backed reports and reconciliation module.

This order minimizes refactor churn and establishes the accounting core correctly before feature expansion.

---

## 15) App boundary decision (Loan app vs DEA app)

Decision: keep loan and DEA as separate apps with a strict integration contract.

App ownership:
- Loan app (girvi domain):
  - Loan contract lifecycle, schedules, collateral, delinquency/NPA logic, restructure, closure intent.
  - Emits accounting events and allocation payloads.
  - Never writes JournalEntry, LedgerTransaction, or AccountTransaction directly.
- DEA app (accounting core):
  - VoucherHeader and VoucherLine lifecycle.
  - Posting engine and materialization to immutable journal tables.
  - Period controls, audit, reporting, reconciliation.

Integration contract:
- Input from loan app to DEA:
  - event_type
  - event_id
  - loan_id
  - effective_at
  - economic payload (principal, interest, fees, penalty, currency)
  - allocation payload (if receipt)
  - idempotency key
- Output from DEA back to loan app:
  - voucher_id, voucher_no, status
  - journal_entry_id
  - posted_at
  - failure reason if rejected

Guardrails:
- Loan state transitions that require accounting cannot complete until DEA returns POSTED.
- Reversal/correction follows reversal voucher chain in DEA; loan app updates status only after reversal posting succeeds.
- Cross-app calls must run with active tenant schema context.

Repository implementation implication:
- Keep loan event models and command handlers in girvi.
- Keep posting rules, voucher models, and period/report modules in DEA.
- Introduce a thin adapter layer (LoanAccountingService) at app boundary; avoid model-level cross-coupling.
