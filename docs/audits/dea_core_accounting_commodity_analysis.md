---
status: active
owner: project
updated: 2026-06-23
tags: [audit, dea, accounting, commodity, architecture]
related:
  - ../AGENT_MEMORY.md
  - ../STATUS.md
  - ../constitution.md
  - ../domain/accounting.md
  - ../implementation/girvi-posting-event-contract.md
  - girvi_deep_analysis.md
---

# DEA Core Accounting And Commodity Analysis

## 1. Executive Summary

This audit reviews the current `dea` app as the double-entry accounting core and evaluates how it should evolve for jewellery, bullion, gold-loan, and small-business ERP workflows.

The central finding is clear: DEA currently has a financial accounting engine that stores transaction values through `MoneyField`, `amount_currency`, `amount_base`, multi-currency `Balance`, and SQL balance views grouped by currency. That is acceptable for INR/USD/AUD-style monetary currencies, but it is the wrong model for gold, silver, or any metal quantity. A commodity position is not a financial currency balance. It needs metal, gross weight, purity/fineness, fine weight, rate, fixation state, valuation currency, and valuation amount as separate concepts.

The repo already contains useful pieces:

- DEA has vouchers, journal entries, ledger transactions, account transactions, posting rules, period controls, party account mappings, reports, and reconciliation tools.
- Girvi already models loan collateral with item type, weight, purity, pure weight, and current value selectors.
- Rates already models `metal`, `currency`, and `purity` separately.
- Product stock already tracks quantity and weight with inventory movements and optional `JournalEntry` linkage.

The missing piece is a clean commodity accounting layer. The recommended MVP direction is not to rename gold/silver currency codes. Instead, keep DEA financial ledgers base-currency-first, keep party accounts monetary, and add a side-by-side commodity movement/exposure model for metal balances, fixed/unfixed positions, and valuation.

Highest-risk current areas:

| Risk | Area | Why it matters |
|---|---|---|
| Critical | `dea/models/ledger.py` balance methods and `ledger_balances` SQL view | Trial balance can be polluted if metal quantities are represented as money currencies. |
| Critical | `dea/models/account.py` balance methods and `account_balances` SQL view | Party statements cannot distinguish INR receivable from gold receivable if both are currency balances. |
| High | `dea/utils/currency.py::Balance` | It is a multi-currency money balance, not a physical quantity balance. |
| High | `dea/posting/types.py`, `dea/posting/validate.py`, `dea/services/materialize_journal.py` | Posting contracts assume monetary amount, currency, and base amount. |
| High | `dea/services/reports.py` | Financial reports read base currency and assume all ledger values belong in normal financial statements. |
| Medium | Current business document UI | Sales/purchase/payment flows are accounting-form centric, not bullion/jewellery event centric. |

Important constraint: this document is an audit and target design only. No application code, migrations, templates, tests, or runtime files were changed.

## 2. Current App Structure

The current `dea` app is already a broad accounting module rather than a small ledger library. It contains master data, accounting documents, posting, reporting, UI, bank reconciliation, opening balances, party account mappings, and compatibility surfaces.

Current major folders and files:

| Area | Current paths | Current role | Belongs in accounting core? |
|---|---|---|---|
| Model package | `apps/tenant_apps/dea/models/*.py` | Chart of accounts, external accounts, vouchers, journal entries, documents, periods, bank/audit/prepaid/assets. | Yes for core accounting models; business-document models should remain thin event documents. |
| Posting package | `apps/tenant_apps/dea/posting/**` | Rule registry, posting context, bundle types, validators, command wrapper, concrete engine, posting rules. | Yes. This is the accounting engine boundary. |
| Services | `apps/tenant_apps/dea/services/*.py` | Voucher creation, journal materialization, reports, settlement, reconciliation, audit, account resolution, numbering, seeding. | Mostly yes; settlement/reporting should stay clearly separated from posting mutation. |
| Facade | `apps/tenant_apps/dea/facade.py`, `facades/*.py` | Public boundary for Girvi and other apps. | Yes. Other apps should use this, not DEA internals. |
| Views/UI | `apps/tenant_apps/dea/views/*.py`, `forms.py`, `forms_vouchers.py`, `templates/dea/**` | Admin/accountant-facing pages for ledgers, vouchers, reports, payments, invoices, periods. | UI belongs in DEA, but business workflows should be document/event centric. |
| SQL views/migrations | `migrations/0003_create_ledger_balance_view.py`, `0019_*`, `0020_*` | Ledger/account balance views and data repair for base amount fields. | Balance views belong only if they remain financial-currency-only. |
| Tests | `apps/tenant_apps/dea/test_*.py`, `tests/*.py` | Posting, reports, settlement, reconciliation, party mapping coverage. | Yes, but commodity regression coverage is missing. |
| Knowledge/archive files | `apps/tenant_apps/dea/know/**` | Historical notes and PDFs. | No runtime role; useful historical context only. |

Nearby related apps:

| App | Current role | DEA relationship |
|---|---|---|
| `girvi` | Given/Taken loan lifecycle, collateral, repayments, releases, custody, notices, reports. | Uses `apps/tenant_apps/girvi/integrations/dea_adapter.py` as the current DEA seam. |
| `party` | Long-term party/person/vendor/customer model and profiles. | DEA has `PartyAccountMapping` for role/purpose-specific subledger accounts. |
| `rates` | Metal rates by `metal`, `currency`, `purity`, source, timestamp. | Should support valuation and rate fixing, not financial currency configuration. |
| `product` | Stock, stock item, stock transaction, stock statement, quantity/weight inventory. | Inventory-like layer; optional journal linkage exists but not a DEA commodity ledger. |
| `contact` | Legacy `Customer` compatibility model. | DEA `Account.contact` still points to `contact.Customer`; Party migration is in progress. |

There is no `apps/tenant_apps/inventory` directory in this checkout. Current inventory analysis therefore refers to `apps/tenant_apps/product`.

## 3. Source Map

### 3.1 Models

| File | Important objects | Current responsibility | Classification | Audit note |
|---|---|---|---|---|
| `dea/models/account.py` | `Account`, `AccountStatement`, `AccountTransaction`, `AccountBalance`, `TransactionType_DE`, `TransactionType_Ext`, `AccountType_Ext`, `EntityType` | External/customer/vendor account accounting and account balance snapshots/views. | External/subledger accounting | Uses `MoneyField` and currency grouping. Correct for receivables/payables, wrong for metal receivable/payable if represented as currency. |
| `dea/models/ledger.py` | `AccountType`, `Ledger`, `LedgerTransaction`, `LedgerStatement`, `LedgerBalance` | Chart of accounts, GL transactions, statement snapshots, ledger balance SQL view model. | Financial accounting core | Core GL model. The balance methods and view are currency-based financial balances, not commodity balances. |
| `dea/models/journal.py` | `JournalEntry` | Posted accounting entry linking voucher to ledger/account transactions. | Financial accounting core | Should remain immutable after posting. Current validation derives posted state from voucher status. |
| `dea/models/voucher.py` | `VoucherType`, `VoucherStatus`, `Voucher`, `VoucherLine` | Accounting voucher and normalized voucher lines. | Financial accounting core | `VoucherLine.amount`, `amount_base`, `currency`, `exchange_rate` are monetary fields. Do not use for metal quantity. |
| `dea/models/doc.py` | `BusinessDoc` | Abstract source document base with audit fields and auto-post hook. | Business document/legacy compatibility | `save()` auto-posts and swallows exceptions. Risky for accounting correctness; newer paths mostly post explicitly. |
| `dea/models/payment.py` | `PaymentVoucher`, `CashFlowDirection`, `PaymentType`, `PaymentMethod` | Cash movement source document. | Business document plus financial posting source | Correctly monetary. Multi-currency support is for cash, not metals. |
| `dea/models/journal_entry.py` | `JournalEntryVoucher`, `JournalEntryLineItem` | Manual accountant journal adjustment document. | Business document/UI plus financial posting source | Useful for financial adjustments. Should not become a metal movement entry screen. |
| `dea/models/sales_invoice.py` | `SalesInvoiceVoucher`, `SalesInvoiceLineItem` | Accounting sales invoice document with AR/revenue/tax fields. | Business document/UI | Monetary-only; insufficient for bullion fixed/unfixed sale because there is no metal quantity/exposure/rate fixing model. |
| `dea/models/purchase_invoice.py` | `PurchaseInvoiceVoucher`, `PurchaseInvoiceLineItem`, `PurchaseType` | Accounting purchase invoice document with AP/cost/tax fields. | Business document/UI | Monetary-only; insufficient for bullion fixed/unfixed purchase. |
| `dea/models/currency.py` | `ExchangeRate`, `CurrencyConfiguration` | Monetary currency configuration and FX rates. | Financial accounting support | Correct for ISO currencies. Should not contain metals as currencies. |
| `dea/models/party_account.py` | `PartyAccountMapping`, `PartyAccountPurpose`, `PartyAccountMappingStatus` | Maps party + role + accounting purpose to DEA account/control ledger. | External/subledger accounting | Good direction. Add commodity account mapping separately later instead of overloading this. |
| `dea/models/period.py` | `AccountingPeriod` | Period lifecycle and lock controls. | Financial accounting core | Posting and reversal should always respect this. |
| `dea/models/bank.py` | Bank/reconciliation models | Bank account and statement reconciliation. | Financial accounting support | Monetary only. |
| `dea/models/audit.py` | `AccountingAuditEvent` | Audit trail for accounting actions. | Financial accounting core/support | Should be extended to commodity posting actions later. |
| `dea/models/expense.py` | `ExpenseVoucher`, `ExpenseLineItem` | Expense document and lines. | Business document/UI | Monetary expense flow. |
| `dea/models/asset.py` | Fixed asset/depreciation models | Fixed asset accounting. | Financial accounting support | Monetary and depreciation-specific. |
| `dea/models/prepaid.py` | Prepaid expense schedule models | Prepaid accounting. | Financial accounting support | Monetary and schedule-specific. |
| `dea/models/numbering.py`, `voucher_numbering.py` | Sequences | Ledger/voucher numbering support. | Financial accounting support | Should remain shared infra. |

### 3.2 Posting

| File | Current responsibility | Classification | Audit note |
|---|---|---|---|
| `dea/posting/types.py` | Defines `LedgerLine`, `DualLedgerLine`, `AccountLine`, `PostingBundle`, posting errors. | Financial posting engine | `currency`, `amount`, `amount_base` are monetary posting fields. No commodity line concept exists. |
| `dea/posting/validate.py` | Structural and balance validation for posting bundles. | Financial posting engine | Validates financial double-entry, not commodity position integrity. |
| `dea/posting/context.py` | Posting context and fingerprint helper. | Posting engine support | Correct place for idempotency payload construction. |
| `dea/posting/registry.py` | Rule registry. | Posting engine support | Correct pattern. Commodity posting rules should be separately typed or explicitly mixed bundles. |
| `dea/posting/commands.py` | Command wrapper for posting vouchers. | Posting engine support | Good boundary for UI/services. |
| `dea/posting/engine.py` | Locks vouchers, validates period, computes fingerprint, builds posting bundle, materializes journal, updates voucher status, reverses. | Financial posting engine | Main engine. Should not write commodity movements through `LedgerTransaction`; add a side-by-side commodity materialization step later. |
| `dea/posting/required_rules.py` | Required rule coverage. | Posting engine support | Should be extended when new business-event voucher types are added. |
| `dea/posting/resolver.py` | Posting resolution utilities. | Posting engine support | Needs review during rule cleanup. |
| `dea/posting/legacy_direct_write_engine.py` | Legacy direct write behavior. | Legacy/compatibility | Should be isolated and eventually removed after tests. |
| `dea/posting/rules/*.py` | Posting rules for loans, sales, purchase, expense, depreciation, prepaid, journal entry, party accounts. | Financial posting rules | Current rules create monetary ledger/account lines only. |

Posting rule inventory:

- `base.py`
- `depreciation.py`
- `expense.py`
- `givenloan_auction.py`
- `givenloan_payment.py`
- `givenloan_receipt.py`
- `givenloan_release.py`
- `givenloan_sold.py`
- `journal_entry.py`
- `loan_disbursement.py`
- `loan_repayment.py`
- `party_accounts.py`
- `prepaid.py`
- `purchase_invoice.py`
- `sales_invoice.py`
- `takenloan_payment.py`
- `takenloan_receipt.py`

### 3.3 Services And Facades

| File | Current responsibility | Classification | Audit note |
|---|---|---|---|
| `dea/services/post_doc.py` | Creates a `Voucher` for a source doc, computes fingerprint, posts through engine. | Posting engine support | Good core path. Needs stronger single source of truth versus older direct view posting. |
| `dea/services/materialize_journal.py` | Converts `PostingBundle`/`VoucherLine` into `JournalEntry`, `LedgerTransaction`, `AccountTransaction`. | Financial posting engine | Critical financial materializer. Do not use for commodity movements. |
| `dea/services/reports.py` | Trial balance, P&L, balance sheet, cash flow, AR/AP aging. | Reporting/read model | Assumes base currency INR and financial ledgers. Commodity reports should be separate. |
| `dea/services/settlement.py` | Settles invoice/payment amounts. | External/subledger support | Monetary settlement only. Commodity fixing/settlement needs separate service. |
| `dea/services/reconciliation.py` | Bank reconciliation service. | Financial support | Monetary only. |
| `dea/services/audit.py` | Accounting audit logging. | Core support | Should log commodity posting actions later. |
| `dea/services/account_resolution.py` | Party/customer account resolution. | External/subledger accounting | Good role/purpose pattern. |
| `dea/services/voucher_numbering.py`, `voucher_type_seed.py` | Voucher numbering and seed helpers. | Core support | Shared infra for document/voucher lifecycle. |
| `dea/services/pre_close.py` | Period close checks. | Financial accounting support | Should check commodity/financial consistency later but not mix balances. |
| `dea/services/prepaid.py`, `depreciation.py` | Schedule-driven financial postings. | Financial support | Monetary only. |
| `dea/facade.py`, `dea/facades/*.py` | Public imports for payments, accounts, journal reads/posting. | Integration boundary | Correct boundary for other apps. Keep Girvi and future sales/purchase behind this. |

### 3.4 Views, Forms, Templates, Admin, Filters, Tables

| Area | Files | Current responsibility | Classification | Audit note |
|---|---|---|---|---|
| Voucher UI | `views/voucher.py`, `templates/dea/voucher_*`, `forms.py`, `forms_vouchers.py` | Manual voucher creation, edit, post, reverse, line entry. | Business document/UI plus legacy posting | Contains direct post/reverse helpers separate from engine. Mark as legacy/confusing. |
| Voucher hub | `views/voucher_hub.py`, `templates/dea/voucher_hub.html` | Entry point for voucher creation. | Business document/UI | Should become accountant-facing, not normal staff business event entry. |
| Payment UI | `views/payment.py`, `templates/dea/paymentvoucher_*`, `PaymentVoucherForm` | Payment voucher CRUD. | Business document/UI | Monetary receipt/payment flow. |
| Journal voucher UI | `views/journal_entry_voucher.py`, `templates/dea/journalentryvoucher_*`, `forms_vouchers.py` | Manual journal adjustment flow. | Business document/UI | Accountant-only in target. |
| Journal/transaction UI | `views/journal_entry.py`, `views/transactions.py`, transaction templates | Lists/details for posted journal/account/ledger transactions. | Reporting/read model/UI | Inspection surface, not normal operational flow. |
| Ledger/account UI | `views/ledger.py`, `views/account.py`, templates | Chart of accounts and party account pages. | Financial/subledger UI | Accountant/admin surface. |
| Invoice UI | `views/sales_invoice.py`, `views/purchase_invoice.py`, invoice templates/forms | Monetary sales/purchase invoice flows. | Business document/UI | Not enough for bullion events. |
| Reports UI | `views/reports.py`, `views/reports_hub.py`, report templates | Financial reports and aging. | Reporting/read model | Should remain base-currency financial reporting. Add separate commodity reports. |
| Period UI | `views/period.py`, period templates | Period setup, close, lock, balances. | Financial accounting support | Should prevent posting into locked periods. |
| Opening balance UI | `views/opening_balance.py`, `templates/dea/opening_balance/**` | Opening balance wizard/import. | Financial/subledger UI | Needs future separate commodity opening balance flow. |
| Reconciliation UI | `views/reconciliation.py`, bank reconciliation templates | Bank statement import/match. | Financial support UI | Monetary only. |
| Dashboard UI | `views/dashboard.py`, `dashboard_enhanced.py`, dashboard templates | Accounting overview. | Reporting/UI | Should split financial and operational/event views. |
| Admin | `admin.py` | Admin registration for accounting models. | Admin/support | Useful for diagnostics, not primary workflow. |
| Filters/tables | `filters.py`, `tables.py` | List filtering/table helpers. | UI support | Fine. |

Template inventory includes `templates/dea/account_*`, `ledger_*`, `voucher_*`, `journalentry*`, `paymentvoucher_*`, `salesinvoicevoucher_*`, `purchaseinvoicevoucher_*`, `period_*`, `reports/**`, `reconciliation/**`, and opening balance templates.

### 3.5 SQL And Materialized/Database Views

The current DEA balance models are normal PostgreSQL views, not materialized views:

- `ledger_balances` exposed through `dea/models/ledger.py::LedgerBalance`
- `account_balances` exposed through `dea/models/account.py::AccountBalance`

`dea/migrations/0003_create_ledger_balance_view.py` creates both. It also contains migration repair logic for older `_money_value` array columns. This is a key historical sign that the accounting engine previously drifted through a custom/multi-currency balance representation.

Important details:

- `ledger_balances` normalizes `LedgerTransaction` credit/debit legs and `AccountTransaction` lines into one ledger balance by `amount_currency`.
- `account_balances` groups `AccountTransaction` by `amount_currency` and applies debtor/creditor side rules.
- Neither view has a concept of metal, UOM, gross weight, fine weight, purity, or fixed/unfixed exposure.
- If gold/silver ever appear as currencies in these views, they become financial statement balances by accident.

`dea/migrations/0019_repair_ledgertransaction_amount_base_currency.py` and `0020_repair_ledgertransaction_amount_base.py` add/repair `amount_base_currency` and `amount_base`. These support base-currency financial reporting, but do not solve commodity quantity accounting.

### 3.6 Integrations

| Integration | Files | Current responsibility | Audit note |
|---|---|---|---|
| Girvi to DEA | `apps/tenant_apps/girvi/integrations/dea_adapter.py` | Synchronous adapter and event-contract helpers for disbursal, repayment, release, accrual, auction, sale, renewal, write-off, reversal. | Good boundary. Current economic fields are monetary loan accounting fields, not commodity movement fields. |
| Girvi selectors | `apps/tenant_apps/girvi/selectors.py` | Loan settlement, collateral weight/purity summaries, accounting status, operational controls. | Has useful metal read models, but not an accounting-grade commodity ledger. |
| Party | `apps/tenant_apps/party/**`, `dea/models/party_account.py` | Party profile and DEA account mappings. | Good external account direction. Add commodity account mappings separately later. |
| Rates | `apps/tenant_apps/rates/models.py` | `Rate(metal, currency, purity, buying_rate, selling_rate, source)`. | Correctly separates metal from monetary currency. Should feed valuation/rate fixing. |
| Product stock | `apps/tenant_apps/product/models/stock.py`, `product/inventory/services/**` | Stock/StockItem quantity and weight movements, statements, optional journal entry link. | Inventory layer exists but is not a commodity accounting layer. |

## 4. Current Domain Model

### 4.1 Plain-English Model

DEA currently has two accounting transaction families:

1. Internal ledger transactions:
   - `Ledger` is the chart-of-accounts node.
   - `LedgerTransaction` is a dual-ledger posting row with `ledgerno_dr`, `ledgerno`, `amount`, and optional `amount_base`.
   - `LedgerStatement` is a checkpoint/snapshot.
   - `LedgerBalance` reads the `ledger_balances` view.

2. External account transactions:
   - `Account` is a party/customer/vendor subledger account.
   - `AccountTransaction` records a one-sided movement against an external account and associated control ledger.
   - `AccountStatement` is a checkpoint/snapshot.
   - `AccountBalance` reads the `account_balances` view.

Source documents include:

- `PaymentVoucher`: cash in/out event.
- `JournalEntryVoucher`: manual accountant adjustment.
- `SalesInvoiceVoucher`: monetary sales invoice.
- `PurchaseInvoiceVoucher`: monetary purchase invoice.
- `ExpenseVoucher`, prepaid/depreciation documents, and loan-related source documents from Girvi.

Accounting records include:

- `Voucher`: accounting intent tied to a source document through generic foreign key.
- `VoucherLine`: normalized debit/credit lines before posting or generated by posting rules.
- `JournalEntry`: immutable posted entry once voucher is posted.
- `LedgerTransaction` and `AccountTransaction`: materialized posting effects.

### 4.2 Important Model Assessment

| Model | Represents | Important fields | Category | Assessment |
|---|---|---|---|---|
| `BusinessDoc` | Abstract source-event base. | `created_at`, `created_by`, `updated_at`, `updated_by`, `auto_post_to_accounting`. | Business document base | Confusing/risky because `save()` auto-posts and catches failures. Keep only if explicit posting semantics are tightened. |
| `Voucher` | Accounting voucher for a business document. | `voucher_no`, `voucher_type`, `voucher_date`, `status`, generic doc link, `corrected_from`, `fingerprint`, `last_posted_at`. | Voucher/accounting intent | Correct core concept. Unique posted doc/type and fingerprint constraints help, but event granularity needs care. |
| `VoucherLine` | Normalized monetary debit/credit line. | `side`, `ledger`, optional `account`, `amount`, `amount_base`, `exchange_rate`. | Financial posting line | Good for financial postings, not commodity movements. |
| `JournalEntry` | Posted immutable accounting entry. | `voucher`, `period`, `posted_by`, `posted_at`, `is_reversal_of`. | Financial accounting | Correct core concept. Immutability should be enforced consistently through services and UI. |
| `LedgerTransaction` | GL debit/credit pair. | `ledgerno_dr`, `ledgerno`, `amount`, `amount_base`. | Financial accounting | Good for financial double-entry. Critical risk if metal quantities are stored in `amount_currency`. |
| `AccountTransaction` | External account movement. | `Account`, `ledgerno`, `XactTypeCode`, `XactTypeCode_ext`, `amount`. | External/subledger accounting | Good for AR/AP/loan accounts. Wrong for commodity receivable/payable if stored as money. |
| `LedgerStatement` | Ledger balance checkpoint. | `ClosingBalance`, `ClosingBalance_currency`, `period`, `is_opening_statement`. | Financial reporting support | Should remain monetary only. |
| `AccountStatement` | Account balance checkpoint. | `ClosingBalance`, `TotalCredit`, `TotalDebit`, currency columns, period. | External/subledger reporting | Should remain monetary only. |
| `PaymentVoucher` | One actual cash movement. | `total_amount`, component amounts, `direction`, `payment_method`, `source_document`, `posted`. | Business document/payment | Strong monetary document. It should not represent metal delivery. |
| `JournalEntryVoucher` | Manual accountant journal. | `je_number`, `entry_type`, `total_debit`, `total_credit`, line items. | Business document/accountant UI | Good for financial adjustments only. |
| `SalesInvoiceVoucher` | Monetary sales invoice. | customer/party, subtotal, tax, total, received/outstanding. | Business document | Not a bullion sale model. Needs separate sales event for metal quantities/fixing. |
| `PurchaseInvoiceVoucher` | Monetary purchase invoice. | vendor/party, type, subtotal, tax, net payable, paid/outstanding. | Business document | Not a bullion purchase model. |
| `ExchangeRate` | Monetary FX rate. | `base_currency`, `quote_currency`, `rate`, effective dates. | Financial currency support | Correct for fiat currency conversion. |
| `CurrencyConfiguration` | Tenant base/enabled currencies. | `base_currency`, `enabled_currencies`. | Financial currency support | Should enforce ISO monetary currencies eventually. |
| `PartyAccountMapping` | Role/purpose subledger mapping. | `party`, `role_key`, `purpose`, `account`, `control_ledger`, `event_type`. | External/subledger accounting | Good and should stay monetary. |

## 5. Current Business Document, Voucher, Journal Relationship

### 5.1 Current Implementation

Current intended chain:

```text
Business document
-> Voucher
-> VoucherLine
-> JournalEntry
-> LedgerTransaction / AccountTransaction
-> Reports and statements
```

Current actual implementation has multiple paths:

- Newer path: `services/post_doc.py::create_and_post_voucher_for_doc()` creates `Voucher`, then `PostVoucherCommand`, then `posting/engine.py`, then `services/materialize_journal.py`.
- Stored line path: `VoucherLine` rows can be materialized directly by `materialize_journal_from_voucher_lines()`.
- Older UI path: `views/voucher.py::post_voucher()` and `reverse_voucher()` contain direct posting/reversal helper logic, separate from the posting engine.
- Auto-post path: `BusinessDoc.save()` can call `_auto_post_to_accounting()` and swallow posting failures.

This creates conceptual duplication and makes it harder to reason about exactly which posting path is canonical.

### 5.2 Recommended Clean Model

| Concept | Recommended meaning |
|---|---|
| Business document | Operational/economic fact: purchase, sale, receipt, payment, rate fixing, karigar issue/receipt, loan disbursal, release, accrual. It can be draft/editable before posting. |
| Voucher | Accounting intent generated from one business event. It holds source identity, voucher type, date, status, fingerprint, and normalized financial lines. |
| Journal entry | Immutable posted accounting record created from the voucher. It is the legal/accounting effect. |
| Commodity movement | Immutable posted commodity effect created from the same source/voucher where metal changes hands or exposure changes. |

### 5.3 Relationship Rules

| Question | Recommendation |
|---|---|
| Should each business document have one voucher? | For MVP, each accounting-relevant business event should create one primary voucher. Long-lived aggregates such as loans should create one voucher per accounting event, not one voucher for the whole aggregate. |
| Can one voucher have multiple journal entries? | Usually one original `JournalEntry` plus optional reversal/correction entries linked to the voucher or correcting voucher. Do not treat multiple normal entries per voucher as default. |
| Can one journal entry support both internal ledger lines and external account lines? | Yes. GL lines are the financial double-entry basis; account lines are subledger attribution tied to control ledgers. |
| What should be editable? | Draft business documents and draft vouchers/lines. Posted financial and commodity effects should not be edited in place. |
| What becomes immutable after posting? | Journal entries, ledger transactions, account transactions, commodity movements, posting fingerprint payload, and source document accounting-impact fields. |
| How are posted documents corrected? | Reverse original effects and create a correction/amendment document or correcting voucher. |
| Should correction happen by editing? | No for posted economic fields. Editing is acceptable only for non-economic metadata if audited. |
| Where should idempotency live? | Posting request/voucher boundary: source app/model/pk, event type, voucher type/rule version, economic payload hash. Girvi adapter already points in this direction. |
| How prevent double submit/races? | Atomic transaction, row lock on source/voucher, unique active fingerprint/dedupe key, idempotent command endpoint, no direct write helpers bypassing engine. |

### 5.4 Lifecycle Table

| Layer | State | Meaning | Allowed changes | Next states |
|---|---|---|---|---|
| Business document | Draft | User is entering economic details. | Full economic edit. | Submitted, Cancelled |
| Business document | Submitted/Ready | Validated and ready to post. | Limited edit or return to draft. | Posted, Cancelled |
| Business document | Posted | Financial/commodity effects exist. | Non-economic metadata only, audited. | Corrected, Closed |
| Business document | Corrected | Original posted effects have been reversed and replaced. | No direct economic edit. | Closed |
| Business document | Cancelled | No posting should occur, or draft was abandoned. | No posting. | None |
| Business document | Closed | Operationally complete. | No economic edit. | None |
| Voucher | Draft | Accounting intent exists but not posted. | Lines/date/narration can change under permissions. | Posted, Cancelled/deleted if no effects |
| Voucher | Posted | Journal and optional commodity effects created. | Immutable economic fields. | Reversed, Corrected |
| Voucher | Reversed | Original effects are negated. | No direct edit. | None |
| Voucher | Corrected | Superseded by correction voucher/document. | No direct edit. | None |
| Journal entry | Posted | Immutable financial record. | None except audited metadata if needed. | Reversed by new entry |
| Commodity movement | Posted | Immutable commodity quantity/exposure record. | None. | Reversed by opposite movement |

## 6. Current Materialized Views And Balance Logic

### 6.1 Ledger Balance Logic

Current ledger balance sources:

- `Ledger.current_balance()` scans `credit_txns`, `debit_txns`, and external-account `aleg` rows by active currency.
- `Ledger.get_current_balance()` reads `LedgerBalance.objects.filter(ledgerno=self)`.
- `LedgerBalance` maps to SQL view `ledger_balances`.
- `ReportsService._get_ledger_balance_for_period()` sums `LedgerTransaction.amount_base` by period and returns `Money(amount, "INR")`.

Risk:

- Ledger balances mix internal GL rows and external account rows in the SQL view.
- Active balances are grouped by `amount_currency`.
- Base reports assume all relevant financial effects are in `amount_base`.
- None of this supports physical metal quantity.

### 6.2 Account Balance Logic

Current account balance sources:

- `Account.current_balance()` scans `AccountTransaction` by `amount_currency`, using `AccountStatement` snapshots.
- `Account.get_current_balance()` reads SQL view `account_balances`.
- `Account.calculate_balance()` applies debtor/creditor rules by transaction side.
- `AccountStatement` stores closing balance, total debit, and total credit as `MoneyField`.

Risk:

- Party account statements are monetary. If metal receivable/payable is forced into `amount_currency`, statements will display metal as money.
- Credit limit logic compares monetary `credit_limit` to current balance. A metal currency code would break or mislead credit controls.

### 6.3 Voucher Line And Posting Balance Logic

`services/materialize_journal.py` validates:

- At least one debit and credit line.
- Per-currency voucher line totals.
- Per-currency base totals.
- Ledger-only line fallback if account-attributed lines exist.

This is a financial double-entry validation. It does not validate:

- Metal gross/fine weight conservation.
- Purity/fineness.
- Fixed versus unfixed exposure.
- Commodity receivable/payable settlement.
- Rate fixing allocation.
- Inventory quantity and commodity movement consistency.

## 7. Commodity-As-Currency Mistake Analysis

The current codebase does not expose a dedicated DEA commodity model. The conceptual problem is that existing financial balance mechanisms are capable of accepting arbitrary three-character or moneyed currency codes. If gold/silver were represented through those paths, they would be treated as currencies.

| Risk | File / object | Current behavior | Why conceptually wrong for commodities | Impact | Correction direction |
|---|---|---|---|---|---|
| High | `dea/utils/currency.py::Balance` | Stores a tuple of `Money` values keyed by currency and supports multi-currency arithmetic/comparison. | Metal balances are not money values. They require metal, UOM, gross weight, purity, and fine weight. | Balance APIs, account/ledger methods, UI display. | Keep for monetary balances only. Add `CommodityBalance` value object separately. |
| Critical | `dea/models/ledger.py::Ledger.get_active_currencies`, `current_balance`, `get_current_balance` | Detects currencies from transaction rows and returns `Balance(Money(...))`. | A gold quantity balance would become a GL currency balance and could appear in trial balance. | Trial balance, ledger detail, reports. | Restrict GL currency to monetary currencies; add commodity movement/position selectors. |
| Critical | `dea/models/account.py::Account.current_balance`, `get_current_balance` | Computes party account balances by `amount_currency`. | Metal receivable/payable is a commodity obligation, not customer INR receivable. | Party statements, credit limit, AR/AP. | Add `CommodityAccount` and `CommodityMovement`; keep `Account` monetary. |
| Critical | `dea/migrations/0003_create_ledger_balance_view.py` | SQL views group transaction amounts by currency and aggregate financial balances. | SQL cannot know whether a value is USD or an accidental metal code. | Ledger/account balances, dashboards, reports. | Keep views for financial currencies only; add separate commodity balance view/query. |
| High | `dea/posting/types.py` | Posting bundle lines contain `currency`, `amount`, `amount_base`. | Commodity quantity cannot be represented by amount/currency/base amount. | Posting rule contracts. | Add explicit commodity posting bundle or event sidecar lines. |
| High | `dea/posting/validate.py` | Validates monetary bundle shape and financial balance. | Does not validate metal balance, exposure, rate fixing, or purity. | Posting correctness. | Add separate commodity validators. |
| High | `dea/services/materialize_journal.py` | Converts voucher lines into financial `JournalEntry`, `LedgerTransaction`, `AccountTransaction`. | Commodity movements should not become GL transactions unless valued into financial accounting. | Posting, statements, reports. | Add `materialize_commodity_movements()` separate from journal materialization. |
| High | `dea/services/reports.py` | Trial balance, P&L, balance sheet read financial ledger balances in INR. | Metal quantities must not appear in financial statements except through valuation policy. | Financial reporting. | Keep reports base currency only; add metal balance/exposure reports separately. |
| Medium | `dea/forms.py`, `dea/forms_vouchers.py` | Manual entry forms expose `MoneyField` and currency widgets for ledger/account/voucher lines. | Users could try to enter commodity-like balances in monetary fields. | UI/data capture. | Staff business flows should collect metal fields separately; accountant forms remain monetary. |
| Medium | `dea/models/currency.py::CurrencyConfiguration` | Enabled currency list is arbitrary JSON of codes. | No explicit guard that enabled currencies are monetary ISO currencies. | Setup/configuration risk. | Validate monetary currencies; commodity master data elsewhere. |
| Low/Medium | `rates/models.py::Rate` | Tracks `metal`, `currency`, `purity`, rates. | This is mostly correct, but rates are valuation inputs, not accounting currencies. | Valuation/rate UI. | Keep rates separate and integrate into commodity valuation/fixing. |
| Medium | `product/models/stock.py` and Girvi weight selectors | Track weights, purity/touch, quantities, and values outside DEA. | Useful domain data but not immutable commodity accounting entries. | Inventory/Girvi consistency. | Feed commodity posting events from these domains into a DEA commodity layer. |

Needs verification:

- Whether production/tenant data currently contains `amount_currency`, `ClosingBalance_currency`, `TotalCredit_currency`, or `TotalDebit_currency` values like `GLD`, `SLV`, `XAU`, `XAG`, `GOLD`, `SILVER`, or local metal codes.
- Whether older imports used PostgreSQL `_money_value` arrays to store multiple monetary/metal values.

## 8. Logical Gaps

| Rank | Gap | Current evidence | Risk | MVP correction |
|---|---|---|---|---|
| Critical | Financial currency and commodity quantity can be confused if metals enter `MoneyField` currency paths. | `MoneyField`, `Balance`, SQL views grouped by currency. | Financial reports and statements become invalid. | Enforce monetary-only currencies and add commodity models. |
| Critical | Trial balance has no explicit guard against metal-as-currency balances. | `ReportsService` reads `amount_base`; ledger views group currency. | Trial balance polluted or silently misvalued. | Trial balance only from base-currency financial postings; commodity report separate. |
| Critical | Commodity receivable/payable is missing. | Only `Account` monetary subledger exists. | Unfixed metal obligations cannot be tracked properly. | Add `CommodityAccount`/`CommodityMovement`/`ExposureLine`. |
| High | Unfixed purchase/sale is not modeled. | Sales/purchase invoice vouchers are monetary only. | Cannot represent price-unfixed bullion trades. | Add document fields and exposure/rate fixing flow. |
| High | Rate fixing is not modeled in DEA. | Rates exist, but no `RateFixing` document or settlement allocation. | Cannot close unfixed exposure correctly. | Add `RateFixing` business document and posting rule. |
| High | Commodity exposure missing. | No exposure model. | No risk/position view for unfixed trades. | Add `ExposureLine` with open/closed/fixed status. |
| High | Metal balances missing in accounting core. | Product/Girvi track weight, DEA does not. | Inventory/loan collateral cannot reconcile with commodity accounting. | Add `CommodityMovement` and metal balance report. |
| High | Business rules split across documents, views, posting rules, and services. | Direct posting helpers in views plus engine/services. | Duplicate behavior and inconsistent controls. | Canonicalize posting through engine/services only. |
| High | Auto-post save hook can hide failed accounting effects. | `BusinessDoc._auto_post_to_accounting()` catches exceptions and logs. | Source doc may save without accounting. | Disable/remove implicit auto-post for meaningful documents; use explicit commands. |
| High | Reversal/correction semantics are inconsistent. | Engine has reversal; view has separate reversal; voucher statuses include corrected/reversed. | Audit trail confusion. | One reversal/correction service with lifecycle contract. |
| High | Duplicate posting risk across paths. | `post_doc`, engine, direct views, `PaymentVoucher.posted` boolean. | Race or mismatch between source doc and voucher status. | Lock source/voucher, dedupe keys, one posting command. |
| Medium | Account and ledger statement snapshots are monetary-only but not named that way. | `AccountStatement`, `LedgerStatement` use `MoneyField`. | Future developers may use them for metals. | Document and enforce monetary naming/validators. |
| Medium | Materialized/database views hide business meaning. | SQL aggregates account and ledger transaction rows by currency. | Hard to diagnose conceptual errors. | Keep for performance after semantic constraints; create explicit selectors. |
| Medium | Permission boundaries need accounting-specific hardening. | Many DEA UI routes exist; exact permission coverage needs verification. | Staff may access accountant-only surfaces. | Restrict manual voucher/journal/reversal to accountant/admin. |
| Medium | Tenant isolation needs continued tests. | Engine blocks public schema posting; broader UI/report tenant tests need verification. | Cross-tenant accounting leakage. | Add tenant isolation regression tests. |
| Low | Rates include `Bronze`. | `rates.Rate.Metal` includes bronze. | May be valid inventory metadata, but not MVP bullion accounting priority. | MVP commodity accounting starts with Gold/Silver. |

## 9. Functional Gaps

### MVP-Critical

| Gap | Why critical |
|---|---|
| Fixed purchase flow | Needed for jeweller/bullion purchases with metal quantity and monetary payable. |
| Unfixed purchase flow | Needed for bullion-style price-unfixed transactions and exposure. |
| Purchase rate fixing | Needed to convert exposure into monetary payable/valuation. |
| Fixed sale flow | Needed for metal sold with monetary receivable/revenue. |
| Unfixed sale flow | Needed for price-unfixed customer transactions. |
| Sale rate fixing | Needed to close sales exposure. |
| Receipt/payment flow tied to documents | Needed for settlement and party balances. |
| Metal balance report | Needed to prove physical/commodity position. |
| Financial trial balance | Already exists but must be protected from commodity pollution. |
| Party account statement | Exists for monetary accounts; needs clearer role/purpose usage. |
| Ledger statement | Exists for financial ledgers; must stay monetary. |
| Opening balance setup | Exists for financial balances; needs separate commodity opening balance. |
| Posting/reversal/correction tools | Exist partially; need canonical engine path. |
| Tests for commodity-as-currency prevention | Missing. |

### Future Enhancements

| Gap | Defer until |
|---|---|
| Commodity lots and costing policy | Inventory costing/lot traceability is required. |
| Valuation snapshots and unrealized gain/loss policy | Periodic mark-to-market reporting is required. |
| Advanced hedging/risk metrics | Business needs exposure/risk beyond basic open unfixed quantity. |
| Partial settlement allocation model | Partial fixing/payment complexity appears. |
| Broker/commission settlement | Broker workflows are introduced. |
| Automated inventory accounting integration | Product/inventory flows are stabilized around business documents. |

## 10. Over-Engineered Or Legacy Areas

| Area | Current issue | Recommendation |
|---|---|---|
| Multi-currency `Balance` used as general balance abstraction | Good for money, misleading for commodities. | Keep for monetary balances; introduce explicit commodity balance. |
| SQL balance views | Useful performance optimization but hides ledger/account aggregation semantics. | Keep with monetary guardrails; add clear selectors/tests. |
| Direct voucher post/reverse in `views/voucher.py` | Duplicates posting engine behavior. | Replace with engine/service calls after characterization tests. |
| `BusinessDoc.save()` auto-post | Side effect on save, failures swallowed. | Remove or disable for meaningful docs in future refactor. |
| `PaymentVoucher.posted` boolean plus accounting `Voucher.status` | Duplicate state. | Keep temporarily, then derive or synchronize through one posting status model. |
| Sales/purchase invoice vouchers in DEA | Useful accounting documents but look like operational sales/purchase modules. | Keep as accounting docs; rebuild business-event commerce/procurement outside or above DEA. |
| AccountTransaction and LedgerTransaction duality | Needed for GL plus subledger, but confusing when both feed ledger balance view. | Keep but document GL versus subledger attribution and reconcile control accounts explicitly. |
| Legacy direct write engine | Old posting artifact. | Delete after tests prove no runtime callers. |
| Generic voucher creation hub | Database-table-centric rather than workflow-centric. | Keep for accountant tools; normal users use business event screens. |

## 11. Target Accounting Architecture

### 11.1 Layered Model

```text
Business Event Document
  -> Posting Command
    -> Voucher
      -> Financial Journal Entry
      -> External Account Lines
      -> Commodity Movement / Exposure Lines
      -> Inventory Movement Adapter
    -> Reports
```

### 11.2 Financial Accounting Layer

Responsible for:

- Chart of accounts and ledger hierarchy.
- Voucher and voucher type lifecycle.
- Journal entries.
- Debit/credit ledger lines.
- Base-currency financial balances.
- Trial balance.
- Profit and loss.
- Balance sheet readiness.
- Receipts/payments.
- Sales/purchases in monetary value.
- Period locks and closing controls.

Suggested implementation direction:

- Keep `Ledger`, `Voucher`, `VoucherLine`, `JournalEntry`, `LedgerTransaction`, `AccountingPeriod`, financial reports in DEA.
- Make `amount_base` mandatory for financial postings when non-base monetary currency is used.
- Enforce that financial currency codes are monetary ISO-style currencies.

### 11.3 External Account/Subsidiary Layer

Responsible for:

- Customer/vendor/party account balances.
- Receivables/payables.
- Loan receivables/payables.
- Party-wise outstanding.
- Control account reconciliation.
- Account statements.

Suggested implementation direction:

- Keep `Account`, `AccountTransaction`, `AccountStatement`, `PartyAccountMapping`.
- Continue role/purpose mapping such as `CUSTOMER_RECEIVABLE`, `SUPPLIER_PAYABLE`, `BORROWER_LOAN_RECEIVABLE`, `LENDER_LOAN_PAYABLE`.
- Do not store metal receivable/payable in `AccountTransaction`.
- Add separate commodity account mappings later if party metal balances are needed.

### 11.4 Commodity Accounting Layer

Responsible for:

- Metal quantity balances.
- Gold/silver positions.
- Gross weight and fine weight.
- Purity/fineness.
- Fixed/unfixed exposure.
- Rate fixing.
- Commodity receivable/payable.
- Metal balance report.
- Valuation in base currency.
- Later realized/unrealized gain/loss policy.

Suggested files:

- `dea/models/commodity.py`
- `dea/services/commodity_posting.py`
- `dea/services/valuation.py`
- `dea/selectors/commodity.py` or `dea/selectors.py`
- `dea/reports/commodity.py` or `dea/services/commodity_reports.py`
- `dea/posting/commodity_types.py` if financial and commodity bundles are separate.

### 11.5 Business Document Layer

Responsible for:

- Purchase document.
- Sale document.
- Receipt/payment document.
- Rate fixing document.
- Issue to karigar.
- Receive from karigar.
- Loan/girvi events later.
- Inventory movement documents later.

Suggested implementation direction:

- Keep normal staff workflows document-centric.
- DEA may own accounting documents, but operational purchase/sale/karigar workflows can live in domain apps and call DEA facade.
- Each document should expose a deterministic economic payload for fingerprinting.

### 11.6 Posting Engine Layer

Responsible for:

- Converting business events into postings.
- Validating debit equals credit for financial effects.
- Creating immutable journal entries.
- Creating account transaction lines.
- Creating commodity movement/exposure lines where needed.
- Preventing duplicate postings.
- Reversal/correction.

Suggested implementation direction:

- Keep current posting engine for financial postings.
- Add a commodity posting sidecar that runs inside the same atomic posting command for documents with commodity effects.
- Do not materialize commodity quantity through `LedgerTransaction`.

## 12. Target Commodity Accounting Model

Use explicit fields:

- `money_amount`
- `currency`
- `metal`
- `uom`
- `gross_weight`
- `purity`
- `fine_weight`
- `rate`
- `valuation_currency`
- `valuation_amount`
- `fixed_status`

Do not use:

- `amount_currency = "GLD"` for metal quantity.
- `Money(10, "XAU")` for physical gold.
- Financial `AccountStatement` for metal receivable/payable.

### 12.1 Recommended Models

| Model | MVP? | Purpose | Key fields | Relationship to voucher/journal |
|---|---|---|---|---|
| `Commodity` or `Metal` | MVP | Master data for Gold/Silver. | `code`, `name`, `default_uom`, `is_active`. | Referenced by commodity documents and movements. |
| `CommodityAccount` | MVP | Balance bucket for owned metal, party metal receivable/payable, karigar custody, location/vault. | `account_type`, `party`, `location`, `metal`, `purpose`, `status`. | Referenced by commodity movement debit/credit sides. |
| `CommodityMovement` | MVP | Immutable metal movement or obligation movement. | `voucher`, `source_ref`, `metal`, `gross_weight`, `purity`, `fine_weight`, `uom`, `from_account`, `to_account`, `movement_type`, `fixed_status`. | Created during posting alongside financial journal entry. |
| `ExposureLine` | MVP | Open fixed/unfixed commodity exposure. | `source_doc`, `metal`, `fine_weight`, `side`, `fixed_status`, `open_weight`, `rate_basis`, `valuation_currency`. | Created/updated by purchase/sale/rate fixing posting. |
| `RateFixing` | MVP | Document that fixes rate for an open unfixed exposure. | `fixing_no`, `date`, `party`, `metal`, `fine_weight`, `rate`, `currency`, `linked_exposure`. | Posts financial payable/receivable adjustment and closes exposure. |
| `CommodityPosition` | MVP as selector | Current balance/position by metal/account/fixed status. | Derived `gross_weight`, `fine_weight`, valuation. | Read from movements/exposures; persist later only if needed. |
| `CommodityLot` | Deferred | Inventory/costing lot tracking. | `lot_no`, source, metal, weights, cost, location, status. | Link to inventory and commodity movement when lot traceability matters. |
| `ValuationSnapshot` | Deferred | Periodic mark-to-market values. | `as_of`, `metal`, `position`, `rate`, `valuation_amount`, policy. | Linked to period close/report, not initial posting. |
| `SettlementLine` | Deferred | Partial fixing/payment allocation. | `source`, `settled_weight`, `settled_amount`, references. | Useful after partial settlement complexity appears. |

### 12.2 MVP Commodity Posting Principles

- Fine weight is the primary metal balance quantity.
- Gross weight and purity are retained for operational traceability.
- Rate is valuation/fixing input, not the commodity itself.
- Financial accounting posts monetary value in base currency or transaction currency.
- Commodity accounting posts physical/obligation movement in metal units.
- Fixed transaction creates both monetary and commodity effects immediately.
- Unfixed transaction creates commodity movement/exposure and defers final monetary price until fixing.

## 13. Business Operations Analysis

### 13.1 Fixed Purchase

| Aspect | Recommendation |
|---|---|
| Business meaning | Business receives metal/goods at agreed fixed rate and owes/pays supplier. |
| Required document | `PurchaseDocument` with `fixed_status=FIXED`. |
| Validations | Active supplier, metal, gross weight > 0, purity valid, fine weight computed, rate > 0, tax/charges valid, period open. |
| Financial effect | Dr inventory/metal purchase asset or expense, Dr input tax if applicable, Cr supplier payable/cash/bank. |
| External account effect | Supplier payable increases unless paid immediately. |
| Commodity effect | Metal/stock commodity account increases by fine weight. |
| Inventory effect | Stock lot/item may be created if inventory tracking applies. |
| Rate/valuation effect | Valuation amount fixed at transaction rate. |
| Lifecycle | Draft -> Submitted -> Posted -> Corrected/Reversed/Closed. |
| Edit/cancel/reversal | Draft editable; posted corrected by reversal and corrected purchase document. |
| Reports | Trial balance, AP, inventory/metal balance, purchase register. |
| MVP priority | Critical. |

### 13.2 Unfixed Purchase

| Aspect | Recommendation |
|---|---|
| Business meaning | Business receives or commits to receive metal before final price is fixed. |
| Required document | `PurchaseDocument` with `fixed_status=UNFIXED`. |
| Validations | Supplier, metal, fine weight, rate basis or reference source, unfixed terms. |
| Financial effect | Depending policy: no final payable except advances/estimated accrual if required; avoid false fixed payable. |
| External account effect | Commodity payable/receivable tracked in commodity account, not monetary AP unless advance exists. |
| Commodity effect | Metal received increases owned/custody stock and creates open unfixed exposure/payable. |
| Inventory effect | Stock movement if physical receipt occurs. |
| Rate/valuation effect | Exposure valued for reporting using market rate; not final settlement. |
| Lifecycle | Draft -> Posted as unfixed -> Partially/fully fixed -> Closed. |
| Edit/cancel/reversal | Posted receipt/exposure reversed by reversal document. |
| Reports | Metal balance, exposure report, valuation report, supplier outstanding commodity report. |
| MVP priority | Critical. |

### 13.3 Rate Fixing For Purchase

| Aspect | Recommendation |
|---|---|
| Business meaning | Agrees price for all/part of an open unfixed purchase exposure. |
| Required document | `RateFixing` linked to purchase exposure. |
| Validations | Open exposure exists, fixing weight <= open fine weight, rate > 0, currency monetary, period open. |
| Financial effect | Cr supplier payable and Dr inventory/purchase/valuation account based on fixed amount, or adjust provisional entry. |
| External account effect | Monetary supplier payable created/increased. |
| Commodity effect | Open unfixed exposure reduced; fixed exposure/settlement recorded. |
| Inventory effect | No physical movement unless fixing also triggers receipt. |
| Rate/valuation effect | Fixing rate becomes settlement rate. |
| Lifecycle | Draft -> Posted -> Corrected/Reversed. |
| Reports | AP, exposure report, valuation/fixing register. |
| MVP priority | Critical. |

### 13.4 Fixed Sale

| Aspect | Recommendation |
|---|---|
| Business meaning | Business sells metal/goods at fixed rate. |
| Required document | `SaleDocument` with `fixed_status=FIXED`. |
| Validations | Customer, metal/stock availability, fine weight, rate, tax, period open. |
| Financial effect | Dr customer receivable/cash, Cr sales revenue, Cr output tax; COGS/inventory as policy matures. |
| External account effect | Customer receivable increases unless paid. |
| Commodity effect | Owned metal decreases or delivery obligation closes. |
| Inventory effect | Stock issue/sale movement. |
| Rate/valuation effect | Sale value fixed at rate. |
| Reports | Trial balance, AR, sales register, metal balance. |
| MVP priority | Critical. |

### 13.5 Unfixed Sale

| Aspect | Recommendation |
|---|---|
| Business meaning | Business delivers/sells metal before final price is fixed. |
| Required document | `SaleDocument` with `fixed_status=UNFIXED`. |
| Validations | Customer, metal availability, fine weight, unfixed terms. |
| Financial effect | Avoid final revenue/receivable until fixing except advances/provisional policy. |
| External account effect | Commodity receivable/payable or customer metal obligation tracked separately. |
| Commodity effect | Owned metal decreases and open unfixed sale exposure created. |
| Inventory effect | Stock movement if physical delivery occurs. |
| Rate/valuation effect | Exposure valued at market for management reporting. |
| Reports | Metal balance, exposure report, customer commodity statement. |
| MVP priority | High/Critical depending business launch scope. |

### 13.6 Rate Fixing For Sale

| Aspect | Recommendation |
|---|---|
| Business meaning | Agrees final price for open unfixed sale exposure. |
| Required document | `RateFixing` linked to sale exposure. |
| Validations | Open sale exposure, fixing weight <= open fine weight, rate > 0. |
| Financial effect | Dr customer receivable/cash, Cr sales revenue/tax as applicable. |
| External account effect | Monetary customer receivable created/increased. |
| Commodity effect | Open unfixed exposure reduced/closed. |
| Inventory effect | Usually none if delivery already posted. |
| Reports | AR, sales register, exposure/fixing report. |
| MVP priority | High/Critical. |

### 13.7 Receipt From Customer

| Aspect | Recommendation |
|---|---|
| Business meaning | Cash/bank received from customer. |
| Required document | `PaymentVoucher` or receipt document. |
| Validations | Customer account, amount > 0, method/reference, period open, settlement target optional/valid. |
| Financial effect | Dr cash/bank, Cr customer receivable/advance. |
| External account effect | Customer receivable decreases or advance increases. |
| Commodity effect | None unless receipt is metal-in-kind, which should be a commodity receipt document. |
| Inventory effect | None for monetary receipt. |
| Reports | Cash/bank, AR aging, party statement. |
| MVP priority | Critical. |

### 13.8 Payment To Supplier

| Aspect | Recommendation |
|---|---|
| Business meaning | Cash/bank paid to supplier. |
| Required document | `PaymentVoucher` or payment document. |
| Validations | Supplier account, amount > 0, payment method/reference, period open. |
| Financial effect | Dr supplier payable/advance, Cr cash/bank. |
| External account effect | Supplier payable decreases or advance increases. |
| Commodity effect | None unless payment is metal-in-kind. |
| Reports | Cash/bank, AP aging, party statement. |
| MVP priority | Critical. |

### 13.9 Issue Metal To Karigar

| Aspect | Recommendation |
|---|---|
| Business meaning | Business sends metal to artisan/karigar for work. |
| Required document | `KarigarIssueDocument`. |
| Validations | Karigar party, metal, fine weight, stock availability, expected return/wastage terms. |
| Financial effect | Usually no P&L at issue; may reclassify inventory custody account if needed. |
| External account effect | No monetary AR/AP unless charges/advance exist. |
| Commodity effect | Move metal from own vault account to karigar custody account. |
| Inventory effect | Stock custody/location movement. |
| Rate/valuation effect | Retain carrying value; valuation optional. |
| Reports | Metal balance by location/custody, karigar outstanding. |
| MVP priority | High. |

### 13.10 Receive Metal From Karigar

| Aspect | Recommendation |
|---|---|
| Business meaning | Business receives finished/processed metal/goods back from karigar. |
| Required document | `KarigarReceiptDocument`. |
| Validations | Open issue exists, received fine weight, wastage/loss within policy, making charges if any. |
| Financial effect | Making charges payable/expense if billed; inventory reclassification if needed. |
| External account effect | Karigar payable for labor/charges if any. |
| Commodity effect | Reduce karigar custody balance; increase vault/finished goods balance; record loss/wastage if applicable. |
| Inventory effect | Receive stock item/lot or transform input into finished stock. |
| Reports | Metal balance, karigar outstanding, inventory. |
| MVP priority | High. |

### 13.11 Metal Balance Adjustment

| Aspect | Recommendation |
|---|---|
| Business meaning | Correct physical/commodity balance after audit, loss, gain, or data correction. |
| Required document | `MetalAdjustmentDocument`. |
| Validations | Permission, reason, audit reference, metal, fine weight, period open. |
| Financial effect | Optional valuation gain/loss if policy requires. |
| External account effect | Usually none. |
| Commodity effect | Increase/decrease commodity account with adjustment reason. |
| Inventory effect | Stock adjustment if inventory tracked. |
| Reports | Metal balance, adjustment register, audit trail. |
| MVP priority | Medium/High. |

### 13.12 Basic Financial Journal Voucher

| Aspect | Recommendation |
|---|---|
| Business meaning | Accountant posts manual financial adjustment. |
| Required document | `JournalEntryVoucher`. |
| Validations | Balanced financial debit/credit, monetary currency, period open, accountant permission. |
| Financial effect | User-selected GL postings. |
| External account effect | Optional if subledger line is explicitly selected. |
| Commodity effect | None. Manual metal adjustment should use commodity adjustment document. |
| Reports | Trial balance, P&L, balance sheet. |
| MVP priority | Critical for accountants. |

### 13.13 Opening Balances

| Aspect | Recommendation |
|---|---|
| Business meaning | Initial balances at system start. |
| Required document | Financial opening balance document and separate commodity opening balance document. |
| Validations | First/open period, no prior postings for account/commodity account, approval. |
| Financial effect | Opening GL/account balances in base or monetary currencies. |
| External account effect | Party monetary opening balances. |
| Commodity effect | Opening metal balances by account/location/party if separate commodity opening. |
| Inventory effect | Optional stock lots/items seeded. |
| Reports | Trial balance and metal balance. |
| MVP priority | Critical. |

### 13.14 Basic Metal Balance Report

| Aspect | Recommendation |
|---|---|
| Business meaning | Shows metal quantity position by metal/account/location/party/fixed status. |
| Required document | No document; report over commodity movements/exposures. |
| Validations | As-of date, tenant isolation, permission. |
| Financial effect | None. |
| External account effect | None. |
| Commodity effect | Reads commodity movements. |
| Inventory effect | Optional reconciliation against stock. |
| Reports | Metal balance, exposure, karigar outstanding. |
| MVP priority | Critical. |

### 13.15 Basic Financial Trial Balance

| Aspect | Recommendation |
|---|---|
| Business meaning | Financial debit/credit balances in base currency. |
| Required document | No document; report over posted financial journal entries. |
| Validations | Period/as-of date, base currency, posted entries only. |
| Financial effect | None. |
| External account effect | Reconciles control account balances. |
| Commodity effect | None except valued adjustments already posted as financial entries. |
| Inventory effect | None. |
| Reports | Trial balance. |
| MVP priority | Critical. |

## 14. Recommended Business Event Workflows

Current UI is mostly accounting table/form centric. Target workflow should be business-event centric:

```text
Choose event
-> Enter business facts
-> Preview accounting, commodity, inventory effects
-> Submit/post
-> View document detail with effects and timeline
-> Correct by reversal/amendment if needed
```

Workflow principles:

- Normal users create purchase/sale/receipt/payment/karigar/rate-fixing documents.
- They should not manually choose debit/credit ledgers in routine business flows.
- Accountants can inspect and adjust vouchers/journal entries.
- Every posted document detail page should show links to voucher, journal entry, commodity movements, inventory movements, and timeline.
- Posting preview should show warnings before effects are created.
- Reversal/correction should be explicit, permissioned, and reasoned.

## 15. Recommended UI/Page Hierarchy

| Screen | Purpose | Main actions | Data shown | User decisions | Visibility |
|---|---|---|---|---|---|
| Accounting dashboard | Financial control center. | View trial balance, periods, unposted vouchers, reconciliation, reports. | Period status, cash/bank, AR/AP, posting exceptions. | What needs review/close/reconcile. | Accountant/admin. |
| Business events dashboard | Operational event entry. | New purchase, sale, receipt, payment, rate fixing, karigar issue/receipt. | Recent documents, draft/posting status, exceptions. | Which business event to record. | Staff/accountant/admin. |
| Purchases | Purchase document list and create flow. | Create fixed/unfixed purchase, post, correct. | Supplier, metal, weights, fixed status, amount, posting status. | Fixed vs unfixed, supplier, metal/rate. | Staff plus accountant review. |
| Sales | Sale document list and create flow. | Create fixed/unfixed sale, post, correct. | Customer, metal, weights, fixed status, amount, delivery/payment status. | Fixed vs unfixed, customer, rate. | Staff plus accountant review. |
| Receipts/payments | Monetary settlement flow. | Receive, pay, allocate, post. | Party, amount, method, invoices/advances. | Settlement target and method. | Staff/accountant. |
| Rate fixing | Close unfixed exposure. | Fix purchase/sale exposure, post. | Open exposure by party/metal, market rates, fixing quantity/rate. | Which exposure and weight to fix. | Accountant/authorized staff. |
| Karigar issue/receipt | Metal custody workflow. | Issue metal, receive metal, record wastage/charges. | Karigar balances, open issues, weights, purity. | Quantity to issue/receive, wastage policy. | Staff/accountant. |
| Ledger accounts | Chart and GL inspection. | View/edit chart, inspect postings. | Ledger balances and transactions. | Account setup decisions. | Accountant/admin. |
| Party accounts | Monetary subledger. | View account mappings/statements. | AR/AP/loan receivable/payable by purpose. | Account resolution/setup. | Accountant/admin, limited staff view. |
| Commodity positions | Metal accounting overview. | View position/exposure by metal/account/location/party. | Gross/fine weight, fixed/unfixed, valuation. | Which exposure needs fixing/review. | Accountant/admin, limited operations. |
| Trial balance | Financial report. | Run/export. | Base-currency debit/credit by ledger. | Period/as-of date. | Accountant/admin. |
| Metal balance report | Commodity report. | Run/export/reconcile. | Metal, gross/fine weight, account/location/party. | As-of date, filters. | Operations/accountant/admin. |
| Voucher list | Accounting intent audit. | Inspect, post draft, reverse posted. | Voucher no/type/status/source/fingerprint. | Accounting review. | Accountant/admin. |
| Journal entry list | Immutable financial postings. | Inspect/export. | JE, voucher, period, lines. | None except reversal request. | Accountant/admin. |
| Document detail | Single source-of-truth page. | Post, reverse, correct, print. | Overview, Accounting Impact, Commodity Impact, Inventory Impact, attachments, history. | Whether to post/correct. | Staff sees business and status; accountant sees details. |
| Posting/reversal/correction | Controlled mutation screens. | Confirm post/reverse/correct. | Preview, warnings, reason fields, effects. | Approval and reason. | Accountant/admin or permissioned role. |

## 16. Editing, Posting, Reversal, Correction Lifecycle

### 16.1 Edit Rules

| Record | Draft | Posted |
|---|---|---|
| Business document | Economic fields editable with validation. | Economic fields locked. Non-economic metadata only if audited. |
| Voucher | Lines/date/narration editable while draft. | Locked. |
| VoucherLine | Editable while voucher draft. | Locked. |
| JournalEntry | Not manually edited after posting. | Immutable. |
| LedgerTransaction | Created only by posting engine. | Immutable. |
| AccountTransaction | Created only by posting engine. | Immutable. |
| CommodityMovement | Created only by commodity posting service. | Immutable. |
| ExposureLine | Created/closed by posting/fixing services. | No direct edit; adjustments through documents. |

### 16.2 Reversal And Correction

| Scenario | Recommended behavior |
|---|---|
| Wrong draft | Edit draft or cancel/delete draft. |
| Duplicate draft | Cancel/delete draft. |
| Wrong posted amount/rate/weight | Reverse posted effects, then create corrected document/voucher. |
| Wrong non-economic note | Allow audited metadata correction. |
| Wrong party/metal after posting | Reverse and correct. |
| Partial fixing error | Reverse fixing document and re-fix with correct details. |
| Physical stock discrepancy | Metal balance adjustment with reason and audit reference. |

### 16.3 Idempotency And Race Controls

Required controls:

- Source/event dedupe key: app, model, pk, event type, contract version.
- Economic payload hash/fingerprint.
- Row lock on source document and voucher during posting.
- Unique active fingerprint or event key for posted/corrected effects.
- Atomic creation of voucher, journal entry, ledger/account transactions, and commodity movements.
- No direct view-level materialization bypassing the posting engine in final architecture.
- Duplicate submit should return existing posted result when economic payload is unchanged.

## 17. Migration Strategy

No migrations should be written yet. Recommended staged migration:

### Phase A: Audit And Tests

- Add characterization tests around current financial postings, trial balance, account balances, and voucher reversal.
- Add data-detection queries for suspicious currency codes.
- Prove current financial reports remain base-currency only.

Suggested verification queries:

```sql
SELECT DISTINCT amount_currency FROM dea_ledgertransaction ORDER BY amount_currency;
SELECT DISTINCT amount_base_currency FROM dea_ledgertransaction ORDER BY amount_base_currency;
SELECT DISTINCT amount_currency FROM dea_accounttransaction ORDER BY amount_currency;
SELECT DISTINCT "ClosingBalance_currency" FROM dea_ledgerstatement ORDER BY "ClosingBalance_currency";
SELECT DISTINCT "ClosingBalance_currency" FROM dea_accountstatement ORDER BY "ClosingBalance_currency";
SELECT DISTINCT "TotalCredit_currency" FROM dea_accountstatement ORDER BY "TotalCredit_currency";
SELECT DISTINCT "TotalDebit_currency" FROM dea_accountstatement ORDER BY "TotalDebit_currency";
```

Suspicious examples to investigate manually:

- `GOLD`
- `SILVER`
- `GLD`
- `SLV`
- `XAU`
- `XAG`
- `AU`
- `AG`
- local metal aliases

### Phase B: Introduce Commodity Concepts Side-By-Side

- Add commodity master/account/movement/exposure models without changing financial postings.
- Add commodity opening balances.
- Add basic selectors and metal balance report.

### Phase C: Create Adapters/Selectors

- Add selectors that explicitly return financial balances or commodity balances.
- Add facade methods for commodity posting events.
- Keep existing financial facade APIs stable.

### Phase D: Migrate Reports

- Ensure trial balance, P&L, balance sheet, cash flow use only monetary base amounts.
- Add separate metal balance and exposure reports.
- Add reconciliation views between commodity movements and inventory stock where applicable.

### Phase E: Migrate Business Documents

- Build fixed/unfixed purchase and sale documents.
- Build rate fixing documents.
- Build karigar issue/receipt documents.
- Integrate Girvi later through explicit commodity events for collateral/custody if needed.

### Phase F: Deprecate Old Currency-Based Commodity Logic

- Add validators blocking metal-like codes in financial currency fields.
- Add warnings/migration checks for old data.
- Stop exposing generic multi-currency balance as commodity-capable.

### Phase G: Remove Legacy Logic After Verification

- Remove direct view posting helpers.
- Remove legacy direct write engine if unused.
- Remove compatibility paths only after tests and data checks pass.

## 18. Risk-Ranked Action Plan

| Priority | Action | Why |
|---|---|---|
| P0 | Add tests proving financial trial balance excludes commodity quantities. | Prevents the known conceptual bug from returning. |
| P0 | Add data audit for metal-like currency codes in DEA transaction/statement tables. | Determines whether production data conversion is needed. |
| P0 | Canonicalize posting through `services/post_doc.py` + `posting/engine.py`; mark direct view posting legacy. | Reduces duplicate posting/reversal behavior. |
| P1 | Introduce commodity master/account/movement/exposure model design ADR. | Architecture change needs explicit decision. |
| P1 | Add MVP metal balance report from commodity movements. | Core bullion/jeweller operational need. |
| P1 | Add fixed/unfixed purchase and rate-fixing workflow specs. | Required for bullion purchasing. |
| P1 | Add fixed/unfixed sale and rate-fixing workflow specs. | Required for bullion sales. |
| P1 | Add validators that financial currency config is monetary. | Prevents gold/silver-as-currency. |
| P2 | Add karigar issue/receipt commodity documents. | Important jewellery workflow. |
| P2 | Reconcile commodity movements with product stock movements. | Keeps inventory and commodity accounting consistent. |
| P2 | Add valuation snapshots and unrealized gain/loss policy. | Needed later for period-end valuation. |

## 19. Suggested Test Plan

### Financial Accounting Tests

- Posting bundle with valid ledger lines creates one `JournalEntry`.
- `LedgerTransaction` rows balance debit/credit in base currency.
- `AccountTransaction` rows are subledger attribution and do not double-count GL.
- Voucher cannot post into closed/locked period.
- Posted journal entry cannot be edited/deleted directly.
- Trial balance reads `amount_base` and returns INR/base-currency values only.
- P&L and balance sheet ignore commodity movement tables.

### Voucher Posting, Reversal, Correction

- Draft voucher posts once.
- Duplicate submit with same fingerprint returns existing posted result.
- Changed economic payload reverses/supersedes previous posted voucher according to lifecycle policy.
- Reversal creates opposite ledger/account transactions.
- Correction links to original through `corrected_from` or explicit correction metadata.
- View endpoints call canonical posting services after refactor.

### Ledger And Account Tests

- Ledger current balance works for monetary INR.
- Account current balance works for customer receivable/payable.
- Control account reconciliation matches account subledger totals.
- Credit limit logic works only with monetary currencies.
- Regression: metal-like currency codes are rejected or flagged.

### Commodity Tests

- Fixed purchase posts financial payable and commodity movement.
- Unfixed purchase posts commodity movement and exposure without false fixed monetary payable.
- Purchase rate fixing closes exposure and creates monetary payable.
- Fixed sale posts receivable/revenue and commodity outflow.
- Unfixed sale posts commodity outflow/exposure without false fixed revenue.
- Sale rate fixing closes exposure and posts monetary receivable/revenue.
- Metal balance report sums fine weight by metal/account/location.
- Commodity receivable/payable report separates metal obligations from monetary AR/AP.
- Commodity reversal creates opposite commodity movement.
- Commodity opening balance initializes metal balance without financial trial balance pollution.

### Receipt/Payment Tests

- Customer receipt reduces monetary receivable.
- Supplier payment reduces monetary payable.
- Receipt/payment cannot settle commodity exposure unless a rate fixing or metal receipt/payment document exists.
- Payment idempotency prevents duplicate accounting.

### Karigar Tests

- Issue metal moves fine weight from vault to karigar custody.
- Receive metal moves fine weight back to vault/finished goods.
- Wastage/loss is recorded as explicit adjustment.
- Karigar commodity balance report shows outstanding metal by karigar.

### Integration Tests

- Girvi disbursal/repayment/release remain monetary DEA events.
- Girvi collateral weight/purity remains separate from financial `MoneyField` balances.
- Product stock movement can link to journal entry but does not become commodity accounting by itself.
- Rates feed valuation/fixing but do not create financial currency codes.
- Party account mapping remains monetary by purpose.

### Tenant Isolation Tests

- Posting in public schema fails.
- Tenant A cannot see Tenant B vouchers, ledgers, party accounts, commodity movements, or reports.
- Currency/commodity master data seeding respects tenant schema strategy.

## 20. Suggested Next Codex Tasks

1. Add a focused characterization test suite for current DEA posting and trial balance behavior.
2. Add a data-audit management command or documented SQL check for metal-like currency codes in DEA tables.
3. Draft an ADR for separating financial currency accounting from commodity accounting.
4. Design the MVP commodity model schema in a plan document without migrations.
5. Refactor voucher UI posting actions to call the canonical posting engine after tests are in place.
6. Specify fixed/unfixed purchase and rate-fixing document contracts.
7. Specify fixed/unfixed sale and rate-fixing document contracts.
8. Specify basic metal balance report selectors and acceptance tests.
9. Specify karigar issue/receipt workflows and commodity movement rules.
10. Add permission matrix for staff, accountant, owner/admin on business event, voucher, journal, and reversal screens.

## Appendix A: Current Business Document To Posting Map

| Source document/event | Current source | Current DEA voucher type direction | Current limitation |
|---|---|---|---|
| Given loan disbursal | Girvi via `dea_adapter`/`PaymentVoucher` | Loan disbursement/payment rules | Monetary only; collateral metal not DEA commodity movement. |
| Given loan repayment | Girvi via `PaymentVoucher` | Given loan receipt rules | Monetary only. |
| Given loan release | Girvi release/payment paths | Given loan release rules | Release/collateral custody is operational; no DEA commodity ledger. |
| Taken loan activation/repayment | Girvi via DEA adapter | Taken loan receipt/payment rules | Monetary loan accounting only. |
| Interest accrual | Girvi accrual to `JournalEntryVoucher` | Interest accrual journal | Monetary only. |
| Sales invoice | `SalesInvoiceVoucher` | `SALES_INVOICE` | Monetary invoice, no metal/fixing. |
| Purchase invoice | `PurchaseInvoiceVoucher` | `PURCHASE_*` | Monetary invoice, no metal/fixing. |
| Payment/receipt | `PaymentVoucher` | Source model + direction | Cash movement only. |
| Expense | `ExpenseVoucher` | Expense rules | Monetary expense. |
| Manual adjustment | `JournalEntryVoucher` | `JOURNAL_ENTRY_*` | Financial adjustment only. |

## Appendix B: Current Versus Target Responsibility

| Responsibility | Current owner | Target owner |
|---|---|---|
| Chart of accounts | DEA | DEA financial layer |
| Financial vouchers | DEA | DEA financial layer |
| Journal entries | DEA | DEA financial layer |
| Party monetary accounts | DEA + Party bridge | DEA subledger layer with Party integration |
| Metal rates | Rates app | Rates/valuation service feeding commodity layer |
| Metal inventory quantity | Product stock | Product inventory plus commodity integration |
| Girvi collateral weight | Girvi | Girvi operational model plus optional commodity posting events |
| Metal balances | Product/Girvi read models only | DEA commodity accounting layer |
| Fixed/unfixed exposure | Missing | DEA commodity accounting layer |
| Rate fixing | Missing | Business document plus DEA commodity/financial posting |
| Trial balance | DEA reports | DEA financial reports, base currency only |
| Metal balance report | Missing | DEA commodity reports |

## Appendix C: Terms

| Term | Meaning |
|---|---|
| Monetary currency | Legal/financial currency such as INR, USD, AUD. |
| Commodity/metal | Physical or contractual metal such as gold/silver. Not a financial currency in this architecture. |
| Gross weight | Physical total weight. |
| Purity/fineness | Metal content ratio, for example 916/1000 or 22k equivalent. |
| Fine weight | Metal content weight after applying purity. |
| Fixed transaction | Transaction whose price/rate is agreed at posting time. |
| Unfixed transaction | Transaction whose quantity is known but final price/rate is not yet fixed. |
| Rate fixing | Event that assigns final rate to all or part of an unfixed exposure. |
| Exposure | Open quantity/value risk from unfixed purchase/sale. |
| Commodity receivable/payable | Metal quantity owed to/by a party, tracked separately from monetary receivable/payable. |

