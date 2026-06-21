---
status: active
owner: project
updated: 2026-06-18
tags: [dea, models, accounting]
related: [README.md, architecture.md, workflows.md]
---

# DEA Domain Models

## Core Business Concepts

DEA separates business intent from accounting effects:

- Business documents: `PaymentVoucher`, `ExpenseVoucher`, `JournalEntryVoucher`, `SalesInvoiceVoucher`, `PurchaseInvoiceVoucher`, depreciation schedules, prepaid schedule lines.
- Accounting layer: `Voucher`, `VoucherLine`, `JournalEntry`.
- Ledger layer: `LedgerTransaction` and `AccountTransaction`.
- Snapshot/reporting layer: `LedgerStatement`, `AccountStatement`, `LedgerBalance`, `AccountBalance`.

## Chart Of Accounts

### `AccountType`

Defined in [models/ledger.py](../../../apps/tenant_apps/dea/models/ledger.py). Represents high-level GL classes such as Asset, Liability, Equity, Income, and Expense. `code_prefix` is used by ledger numbering.

### `Ledger`

Defined in [models/ledger.py](../../../apps/tenant_apps/dea/models/ledger.py). This is the chart-of-accounts node. It uses MPTT for hierarchy and has classification flags used by reports:

- `is_operating_revenue`
- `is_direct_expense`
- `is_operating_expense`
- `is_current_asset`
- `is_current_liability`

Important methods:

- `calculate_balance()`
- `calculate_period_balance()`
- `get_current_balance()`
- `set_opening_bal()`

`Ledger` is the GL account used by posting rules.

## Party / Subledger Accounts

### `TransactionType_DE`

Defined in [models/account.py](../../../apps/tenant_apps/dea/models/account.py). Stores debit/credit codes: `Dr` and `Cr`.

### `AccountType_Ext`

Defined in [models/account.py](../../../apps/tenant_apps/dea/models/account.py). Represents debtor/creditor subledger type.

### `EntityType`

Defined in [models/account.py](../../../apps/tenant_apps/dea/models/account.py). Person or organisation.

### `Account`

Defined in [models/account.py](../../../apps/tenant_apps/dea/models/account.py). Subledger account linked to the compatibility Contact `Customer`. This is now a foreign key so a bridged customer/party can have separate accounts for different accounting purposes. It tracks debtor/creditor type, account number, status, credit limit, credit days, and statements.

Important state:

- `status`: `ACTIVE`, `INACTIVE`, `SUSPENDED`, `CLOSED`.

Important methods:

- `current_balance()`
- `get_current_balance()`
- `calculate_period_balance()`
- `close_account()`
- `set_opening_bal()`

Boundary note: this model still imports `apps.tenant_apps.contact.models.Customer` for compatibility. New cross-app callers should use the public DEA facade resolver instead of importing DEA models directly.

### `PartyAccountMapping`

Defined in [models/party_account.py](../../../apps/tenant_apps/dea/models/party_account.py). Maps a Party role and accounting purpose to a DEA subledger account.

Key fields:

- `party`
- `role_key`
- `purpose`
- `account`
- `control_ledger`
- `event_type`
- `is_default`
- `status`

Supported purposes:

- `CUSTOMER_RECEIVABLE`
- `SUPPLIER_PAYABLE`
- `BORROWER_LOAN_RECEIVABLE`
- `LENDER_LOAN_PAYABLE`
- `CUSTOMER_ADVANCE`
- `SUPPLIER_ADVANCE`

Resolver entry points:

- `dea.facade.resolve_party_account()`
- `dea.facade.resolve_customer_account()`
- `dea.facade.ensure_customer_account()`

### `AccountTransaction`

Defined in [models/account.py](../../../apps/tenant_apps/dea/models/account.py). Subledger transaction connected to a `JournalEntry`, `Ledger`, `Account`, debit/credit code, and transaction extension code.

### `AccountStatement` and `AccountBalance`

`AccountStatement` is a stored balance snapshot. `AccountBalance` is a read-only database view for live account balances.

## Voucher Layer

### `VoucherType`

Defined in [models/voucher.py](../../../apps/tenant_apps/dea/models/voucher.py). Symbolic posting type such as `GIVENLOAN_PAYMENT`, `GIVENLOAN_RELEASE`, `EXPENSE_VENDOR_BILL`, or `JOURNAL_ENTRY_ACCRUAL`.

### `VoucherStatus`

Defined in [models/voucher.py](../../../apps/tenant_apps/dea/models/voucher.py):

- `DRAFT`
- `POSTED`
- `CORRECTED`
- `REVERSED`

### `Voucher`

Defined in [models/voucher.py](../../../apps/tenant_apps/dea/models/voucher.py). Accounting representation of a business document. It links to source documents through `doc_content_type` and `doc_object_id`.

Important fields:

- `voucher_no`
- `voucher_type`
- `voucher_date`
- `status`
- `corrected_from`
- `fingerprint`
- `last_posted_at`
- `narration`

Constraints:

- One posted voucher per document/type: `unique_posted_voucher_per_doc_type`.
- One active fingerprint among posted/corrected vouchers: `unique_fingerprint_active`.

### `VoucherLine`

Defined in [models/voucher.py](../../../apps/tenant_apps/dea/models/voucher.py). Canonical pre-journal debit/credit row.

Important fields:

- `voucher`
- `line_no`
- `side`: `Dr` or `Cr`
- `ledger`
- optional `account`
- `amount`
- `amount_base`
- `exchange_rate`
- `xact_type_ext`

`VoucherLine.clean()` prevents line changes for posted/reversed vouchers.

## Journal Layer

### `JournalEntry`

Defined in [models/journal.py](../../../apps/tenant_apps/dea/models/journal.py). Immutable accounting entry created from a voucher. It is linked to:

- `voucher`
- `period`
- `posted_by`
- optional `is_reversal_of`

Important behavior:

- `save()` auto-assigns the period based on voucher date.
- `clean()` prevents modification when the original voucher is posted.
- `delete()` prevents deleting posted entries.
- `validate_balanced()` checks ledger/account transactions.

## Business Documents

### `BusinessDoc`

Defined in [models/doc.py](../../../apps/tenant_apps/dea/models/doc.py). Abstract base for business documents. It has `created_by`, `updated_by`, and `auto_post_to_accounting`.

Important warning: `BusinessDoc.save()` can call `_auto_post_to_accounting()` and swallow errors. Newer workflows often set `auto_post_to_accounting=False` and post explicitly through services.

### What Classifies As A BusinessDoc

A `BusinessDoc` is a source document that DEA can translate into an accounting `Voucher`. It should represent one accounting-relevant fact, not a whole long-lived business object.

A model is a good `BusinessDoc` candidate when:

- It represents one economic/accounting fact.
- It has an effective accounting date.
- It has a clear amount, currency, party, direction, tax, or other economic payload.
- It can map to one voucher type.
- It can be independently audited.
- It has stable identity for idempotency and fingerprinting.
- It may need review, approval, correction, or reporting before/after posting.

Good examples:

- `PaymentVoucher`: one cash movement.
- `ExpenseVoucher`: one expense document.
- `JournalEntryVoucher`: one manual adjustment.
- `SalesInvoiceVoucher`: one sales accounting document.
- `PurchaseInvoiceVoucher`: one purchase accounting document.
- `DepreciationSchedule`: one asset depreciation posting for one period.
- `PrepaidScheduleLine`: one prepaid amortization posting for one period.

Poor examples:

- `Customer`: master data, not an accounting event.
- `Ledger`: setup/master data, not a business event.
- `Rate`: valuation input, not an accounting event by itself.
- `LoanItem`: collateral detail, not usually an accounting event by itself.
- Girvi `GivenLoan`: loan aggregate/lifecycle object, not one accounting event.

The rule of thumb is:

```text
If this object is posted, can we name the exact debit/credit effect, effective date,
amount, source identity, and idempotency key?
```

If yes, it can be a `BusinessDoc` or an explicit event payload. If the answer depends on which lifecycle action happened, the object is likely a domain aggregate rather than a `BusinessDoc`.

### Why Girvi GivenLoan Is Not A BusinessDoc

`GivenLoan` belongs to Girvi and represents the whole loan lifecycle. It can produce several separate accounting events:

- loan disbursal
- repayment receipt
- interest accrual
- release receipt
- auction
- sale
- correction or reversal

Treating `GivenLoan` itself as a DEA `BusinessDoc` would make the whole loan look like one accounting document and would couple Girvi runtime models to DEA posting internals. The better boundary is:

```text
GivenLoan lifecycle action
-> explicit business event or DEA document such as PaymentVoucher
-> Voucher
-> VoucherLine
-> JournalEntry
```

### `PaymentVoucher`

Defined in [models/payment.py](../../../apps/tenant_apps/dea/models/payment.py). Represents actual cash movement.

Key state:

- `payment_type`: `DISBURSAL`, `RECEIPT`, `REFUND`, `OTHER`.
- `direction`: `RECEIPT` or `PAYMENT`.
- `payment_method`: `CASH`, `BANK`, `CHEQUE`, `UPI`, `CARD`, `OTHER`.
- `posted`: whether accounting posting is complete.
- `create_release`: makes a GivenLoan receipt use `GIVENLOAN_RELEASE`.

`get_voucher_type()` derives rule key from source model and direction.

### `ExpenseVoucher` and `ExpenseLineItem`

Defined in [models/expense.py](../../../apps/tenant_apps/dea/models/expense.py). Expense header and itemized expense lines. `ExpenseVoucher.get_voucher_type()` returns `EXPENSE_{source_type}`.

### `JournalEntryVoucher` and `JournalEntryLineItem`

Defined in [models/journal_entry.py](../../../apps/tenant_apps/dea/models/journal_entry.py). Manual GL adjustment document. It stores user-entered debit/credit line items and posts through the journal-entry posting rule.

Entry types include:

- `CLOSING`
- `ACCRUAL`
- `CORRECTION`
- `ADJUSTMENT`
- `INTERCORP`
- `EXCHANGE`
- `OTHER`

### Sales And Purchase Invoice Vouchers

Defined in [models/sales_invoice.py](../../../apps/tenant_apps/dea/models/sales_invoice.py) and [models/purchase_invoice.py](../../../apps/tenant_apps/dea/models/purchase_invoice.py). They model accounting documents for sales/purchase workflows and have line items, totals, payment status, and posting rule mapping.

During Party Phase 9 they also carry nullable `party -> party.Party` shadow links. These are populated from `customer.party` / `vendor.party` when the compatibility bridge exists. Posting account resolution prefers the explicit Party link and falls back to the legacy Customer link.

## Periods And Statements

### `AccountingPeriod`

Defined in [models/period.py](../../../apps/tenant_apps/dea/models/period.py). Tracks date ranges and period status.

Status:

- `OPEN`
- `CLOSED`
- `LOCKED`

Important methods:

- `get_period_for_date()`
- `can_modify_transactions()`
- `close_period()`
- `lock_period()`
- `unlock_period()`

`close_period()` blocks if draft vouchers exist, creates closing entries/statements, and logs audit events.

## Fixed Assets, Prepaids, Bank, Audit

- [models/asset.py](../../../apps/tenant_apps/dea/models/asset.py): fixed assets and depreciation schedules.
- [models/prepaid.py](../../../apps/tenant_apps/dea/models/prepaid.py): prepaid expenses and schedule lines.
- [models/bank.py](../../../apps/tenant_apps/dea/models/bank.py): bank reconciliation records.
- [models/audit.py](../../../apps/tenant_apps/dea/models/audit.py): immutable audit events.
