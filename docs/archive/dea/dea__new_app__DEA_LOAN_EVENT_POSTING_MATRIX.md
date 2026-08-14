---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# DEA Loan Event Posting Matrix

Purpose: implementation-ready mapping for all loan events from business action to voucher type, posting lines, subledger attribution, controls, and idempotency.

Date: 2026-05-10

---

## 1) Key conventions

This matrix follows current DEA posting key conventions already used in rules:
- CASH
- LOAN_PRINCIPAL_CTRL
- BORROWER_LOAN_CTRL
- INTEREST_RECEIVABLE
- INTEREST_INCOME
- BORROWING_PRINCIPAL_CTRL
- LENDER_ACCOUNT_CTRL
- INTEREST_EXPENSE

New keys required for full lifecycle coverage:
- FEE_RECEIVABLE
- FEE_INCOME
- PENALTY_RECEIVABLE
- PENALTY_INCOME
- EXCESS_COLLECTION_LIABILITY
- ECL_ALLOWANCE
- ECL_EXPENSE
- WRITEOFF_EXPENSE
- RECOVERY_INCOME
- FORECLOSURE_CHARGE_INCOME
- WAIVER_EXPENSE
- AUCTION_GAIN
- AUCTION_LOSS
- TRANSFER_GAIN
- TRANSFER_LOSS
- LOAN_TRANSFER_RECEIVABLE

---

## 2) Voucher type map

| Loan Event | Voucher Type Key | Rule Mode |
|---|---|---|
| Loan contract created | LOAN_CONTRACT_CREATED | Memo / optional accounting |
| Given loan disbursal | GIVENLOAN_PAYMENT | Existing rule |
| Given loan receipt | GIVENLOAN_RECEIPT | Existing rule |
| Given loan release settlement | GIVENLOAN_RELEASE | Existing rule |
| Taken loan receipt | TAKENLOAN_RECEIPT | Existing rule |
| Taken loan repayment | TAKENLOAN_PAYMENT | Existing rule |
| Interest accrual (asset-side) | LOAN_INTEREST_ACCRUAL | New rule |
| Fee accrual | LOAN_FEE_ACCRUAL | New rule |
| Penalty accrual | LOAN_PENALTY_ACCRUAL | New rule |
| Loan receipt allocation | LOAN_RECEIPT_ALLOCATION | New rule |
| Excess receipt refund | LOAN_EXCESS_REFUND | New rule |
| Foreclosure / prepayment | LOAN_FORECLOSURE | New rule |
| Restructure adjustment | LOAN_RESTRUCTURE_ADJ | New rule |
| NPA stage migration | LOAN_NPA_STAGE_CHANGE | New rule |
| ECL provisioning | LOAN_ECL_PROVISION | New rule |
| Loan write-off | LOAN_WRITEOFF | New rule |
| Recovery after write-off | LOAN_WRITEOFF_RECOVERY | New rule |
| Waiver / concession | LOAN_WAIVER | New rule |
| Collateral auction realization | LOAN_AUCTION_REALIZATION | New rule |
| Transfer out | LOAN_TRANSFER_OUT | New rule |
| Transfer in | LOAN_TRANSFER_IN | New rule |
| Generic event reversal | LOAN_EVENT_REVERSAL | Framework rule |

---

## 3) Posting matrix (double-entry)

### 3.1 Lending side: Given loan events

| Event | Debit | Credit | AccountTransaction attribution |
|---|---|---|---|
| Given loan disbursal principal | LOAN_PRINCIPAL_CTRL | CASH | BORROWER_LOAN_CTRL side Dr, xact LG |
| Given loan receipt principal | CASH | LOAN_PRINCIPAL_CTRL | BORROWER_LOAN_CTRL side Cr, xact RP |
| Given loan receipt interest with receivable available | CASH | INTEREST_RECEIVABLE | none |
| Given loan receipt interest without receivable | CASH | INTEREST_INCOME | none |
| Interest accrual | INTEREST_RECEIVABLE | INTEREST_INCOME | optional borrower analytic tag |
| Fee accrual | FEE_RECEIVABLE | FEE_INCOME | optional borrower analytic tag |
| Penalty accrual | PENALTY_RECEIVABLE | PENALTY_INCOME | optional borrower analytic tag |
| Foreclosure charge collected | CASH | FORECLOSURE_CHARGE_INCOME | none |
| Excess collection recognized | CASH | EXCESS_COLLECTION_LIABILITY | borrower account optional |
| Excess collection refund | EXCESS_COLLECTION_LIABILITY | CASH | borrower account optional |
| Waiver of principal/interest/fee/penalty | WAIVER_EXPENSE | respective receivable bucket | borrower account optional |
| Write-off (allowance route) | ECL_ALLOWANCE | receivable bucket | borrower account optional |
| Write-off (expense route fallback) | WRITEOFF_EXPENSE | receivable bucket | borrower account optional |
| Recovery after write-off | CASH | RECOVERY_INCOME | borrower account optional |
| Collateral auction receipt (covered amount) | CASH | LOAN_PRINCIPAL_CTRL or receivable bucket | borrower account optional |
| Collateral auction surplus gain | CASH | AUCTION_GAIN | none |
| Collateral auction shortfall loss | AUCTION_LOSS | LOAN_PRINCIPAL_CTRL or receivable bucket | none |

### 3.2 Borrowing side: Taken loan events

| Event | Debit | Credit | AccountTransaction attribution |
|---|---|---|---|
| Taken loan receipt principal | CASH | BORROWING_PRINCIPAL_CTRL | LENDER_ACCOUNT_CTRL side Cr, xact LR |
| Taken loan repayment principal | BORROWING_PRINCIPAL_CTRL | CASH | LENDER_ACCOUNT_CTRL side Dr, xact LP |
| Taken loan interest payment | INTEREST_EXPENSE | CASH | none |
| Taken loan accrued interest (if policy accrues) | INTEREST_EXPENSE | INTEREST_PAYABLE | lender account optional |
| Taken loan fee/charge accrual | BORROWING_COST_EXPENSE | BORROWING_COST_PAYABLE | lender account optional |

### 3.3 Transfer and restructure events

| Event | Debit | Credit | Notes |
|---|---|---|---|
| Transfer out at gain | CASH | LOAN_TRANSFER_RECEIVABLE then TRANSFER_GAIN | two-step allowed |
| Transfer out at loss | CASH and TRANSFER_LOSS | LOAN_TRANSFER_RECEIVABLE | two-line voucher |
| Transfer in | LOAN_TRANSFER_RECEIVABLE or LOAN_PRINCIPAL_CTRL | CASH | premium/discount policy applies |
| Restructure fee capitalization | LOAN_PRINCIPAL_CTRL | FEE_INCOME deferred or liability | product policy driven |
| Stage migration to NPA | no direct mandatory GL | no direct mandatory GL | accounting policy switch event |

---

## 4) Receipt allocation policy

Allocation order is product-configurable and must be persisted at posting time.

Supported policies:
- PRIORITY_INTEREST_FIRST
- PRIORITY_PENALTY_FIRST
- PRO_RATA
- PRINCIPAL_FIRST

For every LoanReceiptEvent, the engine must produce LoanAllocationEvent rows:
- allocated_to_component: principal, interest_receivable, penalty_receivable, fee_receivable, income
- allocated_amount
- currency
- sequence_no

Posting must consume these persisted allocation rows, not recompute later.

---

## 5) State guards by event

| Guard | Required posted events |
|---|---|
| Move to ACTIVE | disbursal posted |
| Move to DELINQUENT | schedule breach detected, no posting required |
| Move to NPA | stage-change event posted if policy requires |
| Move to RESTRUCTURED | restructure approval and adjustment posting complete |
| Move to CLOSED | principal and all receivable buckets zero, or waiver/write-off posted |
| Move to WRITTEN_OFF | provision and write-off posted |

Any blocked guard must leave loan state unchanged and create a queue item with actionable reason.

---

## 6) Idempotency and reversal rules

Idempotency key for loan events should include:
- tenant schema
- source loan id
- event type
- event effective date-time
- economic payload hash (principal, interest, fees, penalty, currency)
- allocation hash (for receipt events)

Reversal policy:
- Never mutate posted loan event voucher lines.
- Create reversal voucher with mirrored lines.
- Link reversal to original voucher and original loan event id.
- If business correction is needed, post a replacement event after reversal.

---

## 7) Validation checklist per loan voucher before posting

1. Voucher lines balanced by currency and base currency.
2. Loan status allows event type.
3. Event effective date belongs to open period.
4. Allocation rows exist and sum equals receipt amount for receipt events.
5. Required ledger keys resolve in tenant schema.
6. Required borrower/lender account exists where subledger attribution is mandatory.
7. Idempotency fingerprint not already posted.

---

## 8) Minimum test matrix

1. Given loan disbursal posts principal correctly with borrower subledger Dr.
2. Given loan receipt splits principal and interest and clears receivable first.
3. Taken loan receipt and repayment correctly move lender liability subledger.
4. Interest accrual then receipt clears receivable, not income double-count.
5. Foreclosure with excess amount creates excess liability and refund clears it.
6. Write-off and recovery entries reconcile net exposure correctly.
7. Reversal reproduces exact opposite effect of original event.
8. Duplicate event payload returns same posted result (idempotent).
9. Cross-tenant run attempts fail without active tenant schema context.

---

## 9) Implementation notes for this repository

1. Keep existing voucher type keys for implemented rules to avoid breaking compatibility:
- GIVENLOAN_PAYMENT
- GIVENLOAN_RECEIPT
- GIVENLOAN_RELEASE
- TAKENLOAN_RECEIPT
- TAKENLOAN_PAYMENT

2. Introduce new keys incrementally and seed required ledgers before enabling rule registration.

3. For all new loan rules, persist allocation and event metadata in business event tables, then generate VoucherLine and materialize JournalEntry from those lines.

4. Ensure period close checks include loan accrual and closure integrity checks before marking CLOSED.

