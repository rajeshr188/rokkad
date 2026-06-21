---
status: active
owner: project
updated: 2026-06-18
tags: [dea, workflows, posting]
related: [README.md, architecture.md, models.md, userflows.md]
---

# DEA Workflows

## Business Event To Voucher To JournalEntry

A business event is a business fact with possible accounting meaning:

- cash paid
- cash received
- sale invoice issued
- purchase invoice received
- expense incurred
- interest accrued
- loan released
- stock moved
- period closed

DEA translates accounting-relevant facts like this:

```text
Business event
-> BusinessDoc model or explicit event payload
-> DEA facade / command service
-> Voucher
-> VoucherLine rows
-> DjangoPostingEngine
-> JournalEntry
-> LedgerTransaction / AccountTransaction
```

`Voucher` is the accounting wrapper around the source document or event. `VoucherLine` is the normalized debit/credit representation. `JournalEntry` is the immutable posted accounting effect.

Example: Girvi `GivenLoan` disbursal:

```text
GivenLoan created
-> no accounting effect yet; this is a loan agreement

Loan disbursed
-> accounting-relevant business event: cash moved out
-> DEA creates/uses PaymentVoucher
-> DEA creates Voucher for that PaymentVoucher
-> posting rule creates VoucherLine rows:
   Dr LOAN_RECEIVABLE
   Cr CASH
-> engine posts JournalEntry
-> LedgerTransaction and AccountTransaction rows record the effect
```

`GivenLoan` itself is not the DEA business document because one loan can produce many accounting facts over time. The disbursal, repayment, release, auction, sale, and accrual events are the accounting-relevant units.

## Preferred Posting Flow

Entry points:

- [facades/payments.py](../../../apps/tenant_apps/dea/facades/payments.py)
- [facades/journals.py](../../../apps/tenant_apps/dea/facades/journals.py)
- [services/post_doc.py](../../../apps/tenant_apps/dea/services/post_doc.py)

Steps:

1. Caller passes a business document and user.
2. `create_and_post_voucher_for_doc()` resolves `VoucherType`.
3. It computes a fingerprint from the posting rule or document payload.
4. If an existing posted voucher has the same fingerprint, it returns it.
5. Otherwise it creates a draft `Voucher`.
6. `PostVoucherCommand` calls `DjangoPostingEngine`.
7. Engine validates tenant schema and period openness.
8. Engine resolves the posting rule from `PostingRuleRegistry`.
9. Rule builds a `PostingBundle`.
10. `sync_voucher_lines_from_bundle()` creates canonical `VoucherLine` rows.
11. `materialize_journal_from_voucher_lines()` creates `JournalEntry`, `LedgerTransaction`, and `AccountTransaction`.
12. Voucher gets `POSTED`, `fingerprint`, and `last_posted_at`.

## Party Account Resolution Flow

Current status: active for DEA facade callers, current Girvi borrower/lender posting rules, and DEA sales/purchase invoice posting rules; other operational posting rules are migrated gradually.

Purpose:

- Choose the correct subledger account from business context.
- Avoid treating one person or organization as one accounting account.
- Preserve separate gross balances for receivables, payables, loans, and advances.

Flow:

```text
Business event
-> identify party
-> identify role_key, such as CUSTOMER, SUPPLIER, BORROWER, LENDER
-> identify purpose, such as CUSTOMER_RECEIVABLE or BORROWER_LOAN_RECEIVABLE
-> dea.facade.resolve_party_account()
-> PartyAccountMapping
-> DEA Account
-> AccountTransaction during posting
```

Compatibility:

- `resolve_customer_account()` accepts the current Contact `Customer` model.
- Bridged customers use `Customer.party` and `PartyAccountMapping`.
- Unbridged customers fall back to `ensure_customer_account()`.
- `Customer.account` remains a read compatibility alias, but new posting code should not depend on it.

Examples:

- Sale to customer: role `CUSTOMER`, purpose `CUSTOMER_RECEIVABLE`.
- Purchase from supplier: role `SUPPLIER`, purpose `SUPPLIER_PAYABLE`.
- GivenLoan disbursal: role `BORROWER`, purpose `BORROWER_LOAN_RECEIVABLE`.
- TakenLoan receipt: role `LENDER`, purpose `LENDER_LOAN_PAYABLE`.
13. Audit event is recorded.

Primary files:

- [services/post_doc.py](../../../apps/tenant_apps/dea/services/post_doc.py)
- [posting/engine.py](../../../apps/tenant_apps/dea/posting/engine.py)
- [services/materialize_journal.py](../../../apps/tenant_apps/dea/services/materialize_journal.py)

## Payment Flow

Used for cash movements, especially Girvi disbursal/repayment/release.

Main facade:

- [facades/payments.py](../../../apps/tenant_apps/dea/facades/payments.py)

Steps:

1. Caller invokes `create_and_post_payment()`.
2. Existing payment is looked up by source document and `reference_number`.
3. If existing and unposted, it is posted.
4. If existing and posted, it is returned as idempotent retry.
5. If new, a `PaymentVoucher` is created.
6. `PaymentVoucher.get_voucher_type()` derives rule key from source model and direction.
7. `create_and_post_voucher_for_doc()` posts the accounting voucher.
8. `payment.posted=True`.
9. If source is an invoice, `SettlementService` may settle invoice balances.

Important side effects:

- Creates `PaymentVoucher`.
- Creates/updates `Voucher`.
- Creates `VoucherLine`.
- Creates `JournalEntry`, `LedgerTransaction`, and optionally `AccountTransaction`.
- May settle invoices.

## Manual Journal Entry Voucher Flow

URL family:

- `/dea/journal-entry-vouchers/`
- `/dea/journal-entry-vouchers/create/`

View:

- [views/journal_entry_voucher.py](../../../apps/tenant_apps/dea/views/journal_entry_voucher.py)

Forms:

- `JournalEntryVoucherForm`
- `JournalEntryPairFormSet`
- `save_journal_entry_pairs()`

Steps:

1. User enters journal header and debit/credit pair rows.
2. Pair formset validates at least one pair and one currency.
3. `JournalEntryVoucher` is saved with `auto_post_to_accounting=False`.
4. Pair rows are expanded into `JournalEntryLineItem` records.
5. Totals are updated.
6. `VoucherType` is ensured.
7. `create_and_post_voucher_for_doc()` posts through the engine.

## Generic Voucher CRUD Flow

URL family:

- `/dea/vouchers/`
- `/dea/vouchers/create/`
- `/dea/vouchers/<pk>/post/`
- `/dea/vouchers/<pk>/reverse/`

View:

- [views/voucher.py](../../../apps/tenant_apps/dea/views/voucher.py)

Important warning: `VoucherCreateView` and `VoucherUpdateView` use `VoucherLineFormSet`, which matches the new canonical voucher-line model. However, `post_voucher()` and `reverse_voucher()` in the same file are legacy view-level posting paths and should be refactored to call the posting engine. See [refactor plan](refactor-plan.md).

## Expense Flow

URL family:

- `/dea/expenses/`
- `/dea/expenses/create/`
- `/dea/expenses/<pk>/post/`

Files:

- [models/expense.py](../../../apps/tenant_apps/dea/models/expense.py)
- [views/expense.py](../../../apps/tenant_apps/dea/views/expense.py)
- [posting/rules/expense.py](../../../apps/tenant_apps/dea/posting/rules/expense.py)

Expected flow:

1. Create expense voucher and lines.
2. Calculate gross, tax, TDS, and net payable.
3. Post via expense posting rule.
4. Later payment can clear the payable through `PaymentVoucher`.

## Period Close Flow

URL family:

- `/dea/periods/`
- `/dea/period/<pk>/adjustments/`
- `/dea/period/<pk>/close/`
- `/dea/period/<pk>/lock/`
- `/dea/period/<pk>/unlock/`

Files:

- [views/period.py](../../../apps/tenant_apps/dea/views/period.py)
- [models/period.py](../../../apps/tenant_apps/dea/models/period.py)
- [services/pre_close.py](../../../apps/tenant_apps/dea/services/pre_close.py)

Steps:

1. User reviews period detail.
2. Pre-close checklist checks draft vouchers, depreciation, prepaids, and Girvi interest accrual readiness.
3. User can post pre-close adjustments from `period_adjustments`.
4. `period_close` optionally runs Girvi interest accrual through Girvi facade.
5. `AccountingPeriod.close_period()` blocks draft vouchers, posts retained earnings close, creates closing statements, marks period `CLOSED`.
6. User can lock a closed period if they have `dea.can_lock_period`.

## Opening Balance Flow

URL family:

- `/dea/opening-balance/wizard/`
- `/dea/opening-balance/bulk-import/`
- `/dea/opening-balance/template/`
- `/dea/opening-balance/validate/`

File:

- [views/opening_balance.py](../../../apps/tenant_apps/dea/views/opening_balance.py)

Steps:

1. Select accounting period.
2. Enter ledger/account opening balances.
3. Review balanced debit/credit totals.
4. Confirm and create/update opening `LedgerStatement` and `AccountStatement` rows.

## Reports And Dashboard Flow

Files:

- [views/dashboard.py](../../../apps/tenant_apps/dea/views/dashboard.py)
- [views/reports.py](../../../apps/tenant_apps/dea/views/reports.py)
- [services/reports.py](../../../apps/tenant_apps/dea/services/reports.py)

Reports use ledgers, accounts, periods, statements, and read-only balance views to build trial balance, income statement, balance sheet, cash flow, aging, and ratios.

## Depreciation And Prepaid Posting

Files:

- [services/depreciation.py](../../../apps/tenant_apps/dea/services/depreciation.py)
- [services/prepaid.py](../../../apps/tenant_apps/dea/services/prepaid.py)
- [posting/rules/depreciation.py](../../../apps/tenant_apps/dea/posting/rules/depreciation.py)
- [posting/rules/prepaid.py](../../../apps/tenant_apps/dea/posting/rules/prepaid.py)

These are explicit service calls, not background tasks. They create schedule rows and post vouchers for a period.

## Background Jobs / Signals

No active DEA Celery tasks or signal module is currently wired. [apps.py](../../../apps/tenant_apps/dea/apps.py) only auto-imports posting rules.
