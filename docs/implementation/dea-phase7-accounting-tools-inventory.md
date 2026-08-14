---
status: documentation
updated: 2026-06-26
phase: 7
scope: DEA legacy accounting surfaces
audience: architects, engineers planning Phase 8+
---

# DEA Phase 7 Accounting Tools Inventory

Complete catalog of legacy accounting tool surfaces in the DEA module, organized by business function with role-gating analysis and scope characterization for Phase 8+ planning.

## Document Purpose

This inventory characterizes all remaining legacy DEA accounting tool surfaces that are still exposed to users. It supports:

- **Phase 8 planning**: Understanding which surfaces to deprecate, relabel, or migrate to business-event workflows
- **Architecture decisions**: Identifying patterns for consistent role gating and navigation patterns
- **Risk assessment**: Knowing which surfaces are high-risk (e.g., period management, opening balance setup) vs. low-risk (e.g., read-only reports)
- **Stakeholder communication**: Clear scope definition for accountant-only tools vs. business-event-first workflows

**Phase 7 Status**: Phase 7 legacy-surface reduction is focused on dashboard and navigation gating (completed). This document captures remaining surfaces for Phase 8+ characterization work.

---

## 1. VOUCHER HUB & GENERIC VOUCHER SURFACES

### Voucher Hub Landing Page
- **File**: `apps/tenant_apps/dea/views/voucher_hub.py`
- **URL**: `/dea/create/` (name: `dea_voucher_hub`)
- **Role**: `@dea_accountant_required` ✅ (Owner, Admin, Accountant only)
- **Purpose**: Single landing page showing all voucher types with links to creation forms
- **Key Config**: `_VOUCHER_TYPES` defines available voucher categories
- **Business Workflow**: Manual accounting entry point

### Generic Voucher CRUD & Actions
- **File**: `apps/tenant_apps/dea/views/voucher.py`
- **Role**: All operations require `@dea_accountant_required` ✅

#### Operations:
| Operation | URL | Purpose | Risk Level |
|---|---|---|---|
| List | `/dea/vouchers/` | View all vouchers across types | Low |
| Detail | `/dea/vouchers/<int:pk>/` | Inspect single voucher | Low |
| Create | `/dea/vouchers/create/` | Manual voucher creation | Medium |
| Update | `/dea/vouchers/<int:pk>/edit/` | Modify draft voucher | Medium |
| Delete | `/dea/vouchers/<int:pk>/delete/` | Remove unposted voucher | Medium |
| Post | `/dea/vouchers/<int:pk>/post/` | Post voucher to ledger (accounting-deterministic) | **High** |
| Reverse | `/dea/vouchers/<int:pk>/reverse/` | Reverse posted voucher (creates correction entry) | **High** |
| Check Balance (AJAX) | `/dea/vouchers/<int:pk>/balance/` | Real-time balance validation | Low |
| Status Badge (AJAX) | `/dea/vouchers/<int:pk>/status/` | HTMX status refresh | Low |

**Key Models**: `Voucher`, `JournalEntry`, `JournalEntryLineItem`, `ContentType`

**Phase 7+ Consideration**: Generic voucher CRUD is foundational for all manual accounting entry. Candidates for **relabeling** (e.g., "Accounting Entries" vs. "Vouchers") rather than deprecation, as it serves as catch-all for custom/edge-case posting.

---

## 2. PAYMENT VOUCHER SURFACES

### Payment Voucher Management
- **File**: `apps/tenant_apps/dea/views/payment.py`
- **Role**: All operations require `DeaAccountantRequiredMixin` ✅
- **Purpose**: Record receipts and payments with cash flow direction control

#### Operations:
| Operation | URL | Form | Purpose | Risk |
|---|---|---|---|---|
| List (filtered) | `/dea/payments/` | PaymentFilter | View receipts/payments with date, method, loan filtering | Low |
| Detail | `/dea/payments/<int:pk>/` | — | View payment details + linked journal entries if posted | Low |
| Create | `/dea/payments/create/` | `PaymentVoucherForm` | Create new receipt/payment manually | Medium |
| Update | `/dea/payments/<int:pk>/edit/` | `PaymentVoucherForm` | Modify draft payment | Medium |
| Delete | `/dea/payments/<int:pk>/delete/` | — | Remove unposted payment | Medium |

**Key Models**: `PaymentVoucher`, `PaymentMethod`, `CashFlowDirection`, `JournalEntry`

**Database Views**: Implicitly uses `LedgerBalance` for GL posting

**Posting Logic**: Integrated into `DjangoPostingEngine`; creates GL entries for cash/bank accounts

**Phase 7+ Consideration**: Payment workflow is **high-value** for Girvi module integration (loan payments → DEA posting). Business-event equivalent exists (Girvi payment event). **Medium-term strategy**: Evaluate if explicit payment voucher UI is still needed or if all payments should flow through business events + Girvi lifecycle.

---

## 3. EXPENSE VOUCHER SURFACES

### Expense Voucher Management
- **File**: `apps/tenant_apps/dea/views/expense.py`
- **Role**: All CRUD + post operations require `DeaAccountantRequiredMixin` + `@dea_accountant_required` ✅
- **Purpose**: Record business expenses with line items; supports materialization to GL

#### Operations:
| Operation | URL | Form/Formset | Purpose | Risk |
|---|---|---|---|---|
| List (filtered) | `/dea/expenses/` | ExpenseFilter | View expenses with source/payment status/date filtering | Low |
| Detail | `/dea/expenses/<int:pk>/` | — | View expense + line items + GL entries if posted | Low |
| Summary Stats | Context: `dea_expense_list` | — | Total, paid count, pending count calculated inline | Low |
| Create | `/dea/expenses/create/` | `ExpenseVoucherForm` + `ExpenseLineItemFormSet` | Manual expense entry with line items | Medium |
| Update | `/dea/expenses/<int:pk>/update/` | `ExpenseVoucherForm` + `ExpenseLineItemFormSet` | Modify draft expense | Medium |
| Delete | `/dea/expenses/<int:pk>/delete/` | — | Remove unposted expense | Medium |
| **Post** | `/dea/expenses/<int:pk>/post/` | — | Post expense to GL; uses `DjangoPostingEngine` | **High** |

**Key Models**: `ExpenseVoucher`, `ExpenseLineItem`, `Ledger`, `Account`

**Posting Behavior** (Phase 7 characterized):
- Idempotent: repeated posting of same expense produces same GL entries
- Duplicate prevention: checks if expense already posted before creating new entries
- Closed-period validation: does not materialize if period is locked/closed
- Creates `JournalEntry` + `JournalEntryLineItem` pairs for each line item

**Phase 7+ Consideration**: Expense posting is **fundamental** for multi-ledger accounting (e.g., expense ledgers by type/category). Business-event equivalent exists (business event expense posting). **Strategy**: Keep as fallback for ad-hoc/adjustment expenses; consider relabeling to "Adjustment Entries" or "Manual Expenses" to reduce perceived scope vs. business events.

---

## 4. MANUAL JOURNAL ENTRY VOUCHER SURFACES

### Journal Entry Voucher Management
- **File**: `apps/tenant_apps/dea/views/journal_entry_voucher.py`
- **Role**: All CRUD operations require `DeaAccountantRequiredMixin` ✅
- **Purpose**: Double-entry journalization with balance validation for adjustments, accruals, and corrections

#### Operations:
| Operation | URL | Form/Formset | Purpose | Risk |
|---|---|---|---|---|
| List (filtered) | `/dea/journal-entry-vouchers/` | JournalEntryVoucherFilter | View JEVs with entry type/date/memo filtering | Low |
| Detail | `/dea/journal-entry-vouchers/<int:pk>/` | — | View JEV + debit/credit pairs + balance check | Low |
| Summary Stats | Context: list | — | Total entries, balanced count, unbalanced count, reviewed status | Low |
| Create | `/dea/journal-entry-vouchers/create/` | `JournalEntryVoucherForm` + `JournalEntryPairFormSet` | Multi-pair journalization with balance validation | Medium |
| Update | `/dea/journal-entry-vouchers/<int:pk>/update/` | `JournalEntryVoucherForm` + `JournalEntryPairFormSet` | Modify draft JEV | Medium |
| Delete | `/dea/journal-entry-vouchers/<int:pk>/delete/` | — | Remove unposted JEV | Medium |

**Key Helpers**:
- `build_journal_entry_pair_initial()`: Format existing pairs for form display
- `save_journal_entry_pairs()`: Persist debit/credit pair formset

**Key Models**: `JournalEntryVoucher`, `JournalEntryLineItem`, `VoucherType`

**Posting Behavior**: When posted, becomes `JournalEntry` + line items; double-entry constraint enforced at model level

**Phase 7+ Consideration**: Manual JEVs are **essential** for accruals, reversals, and auditor-requested corrections. Business-event system does not yet support arbitrary JEV creation. **Strategy**: Keep; possibly add "why is this needed?" guidance (e.g., "Use this only for auditor-required or non-standard entries") to dashboard/wizard.

---

## 5. OPENING BALANCE SETUP SURFACES

### Opening Balance Wizard (Multi-Step)
- **File**: `apps/tenant_apps/dea/views/opening_balance.py`
- **Role**: All steps require `@dea_accountant_required` ✅
- **Purpose**: Initialize opening balances for new fiscal period via guided wizard or bulk import
- **URL Base**: `/dea/opening-balance/`

#### Wizard Steps:
| Step | Function | URL | Purpose | Validation |
|---|---|---|---|---|
| 1. Period Selection | `_opening_balance_step1_period()` | `.../wizard/?step=1` | Select accounting period for OB | Checks if period already has OB |
| 2. Entry | `_opening_balance_step2_entry()` | `.../wizard/?step=2` | Enter opening balances for ledgers/accounts | Multi-currency support |
| 3. Review | `_opening_balance_step3_review()` | `.../wizard/?step=3` | Review entered balances before posting | Calculated totals |
| 4. Confirmation | `_opening_balance_step4_confirm()` | `.../wizard/?step=4` | Confirm and post OB to accounting | Final validation |

**Main Entry Point**: `opening_balance_wizard()` → `/dea/opening-balance/wizard/` (name: `dea_opening_balance_wizard`)

#### Supporting Operations:
| Operation | URL | Purpose | Risk |
|---|---|---|---|
| **Bulk Import** | `/dea/opening-balance/bulk-import/` | CSV-based mass OB entry | **High** |
| **Template Download** | `/dea/opening-balance/template/` | Download CSV template for import | Low |
| **Validation (AJAX)** | `/dea/opening-balance/validate/` | Real-time OB validation | Low |

**Key Models**: `Ledger`, `Account`, `LedgerStatement`, `AccountStatement`, `AccountingPeriod`, `LedgerBalance`, `AccountBalance`

**Posting Behavior**: Opening balances create special `LedgerStatement`/`AccountStatement` records (not full journal entries) to initialize carry-forward balances

**Critical Risk**: Opening balance setup is **high-stakes**. Incorrect OB cascades to all downstream reports. Bulk import amplifies risk for data entry error.

**Phase 7+ Consideration**: Opening balance workflow is **foundational** for fiscal period initialization. **No deprecation candidate**. **Strategy**: Enhance wizard UX with pre-close validation checklist that reminds users to verify OB before locking period.

---

## 6. ACCOUNTING PERIOD MANAGEMENT SURFACES

### Period Lifecycle Management
- **File**: `apps/tenant_apps/dea/views/period.py`
- **Role Gating**: Mixed (see table below)
- **Purpose**: Create, manage, adjust, close, and lock fiscal periods with pre-close checklist

#### Period CRUD (LoginRequired):
| Operation | URL | Role | Purpose |
|---|---|---|---|
| List | `/dea/periods/` | `@login_required` | View all periods with filter | 
| Detail | `/dea/period/<int:pk>/` | `@login_required` | View period summary + pre-close checklist |
| Create | `/dea/period/create/` | `@login_required` | Create new period |
| Update | `/dea/period/<int:pk>/update/` | `@login_required` | Modify period dates/name |
| Delete | `/dea/period/<int:pk>/delete/` | `@login_required` | Remove period (if no vouchers) |

#### Period Actions (AccountantRequired):
| Operation | URL | Role | Purpose | Risk |
|---|---|---|---|---|
| **Close** | `/dea/period/<int:pk>/close/` | `@dea_accountant_required` | Close period with pre-close validations | **High** |
| **Lock** | `/dea/period/<int:pk>/lock/` | `@dea_accountant_required` | Lock period; prevent posting | **High** |
| **Unlock** | `/dea/period/<int:pk>/unlock/` | `@dea_accountant_required` | Unlock period; allow posting | **High** |

#### Period Adjustments (AccountantRequired):
| Operation | URL | Adjustment Types | Purpose | Risk |
|---|---|---|---|---|
| Adjustments Hub | `/dea/period/<int:pk>/adjustments/` | ACCRUAL, PREPAID_EXPENSE, DEPRECIATION, INTEREST_ACCRUAL, CUSTOM | Add pre-close adjusting entries | **High** |

**Adjustment Behavior**: Creates `JournalEntryVoucher` with memo prefix `PRE_CLOSE:{type}` to track source

#### Period Reports/Analytics (Mostly LoginRequired):
| Operation | URL | Purpose | Role |
|---|---|---|---|
| Transactions | `/dea/period/<int:pk>/transactions/` | View all vouchers in period | `@login_required` |
| Balances | `/dea/period/<int:pk>/balances/` | View GL balances at period close | `@login_required` |
| Report | `/dea/period/<int:pk>/report/` | Period summary report | `@login_required` |
| Status (AJAX) | `/dea/period/status/` | Period state/progress refresh | `@login_required` |

**Pre-Close Checklist** (validates before close):
- Accruals recorded
- Prepaid expenses amortized
- Fixed assets depreciated
- Interest accrued
- Draft vouchers resolved
- Custom checks (via `PreCloseChecklist` validator)

**Key Models**: `AccountingPeriod`, `Voucher`, `VoucherStatus`, `JournalEntry`, `JournalEntryVoucher`

**Phase 7+ Consideration**: Period management is **architectural foundation** for all posting. The **LoginRequired vs. AccountantRequired mismatch** is a Phase 8 candidate for hardening:
- Currently, anyone can create/modify periods (LoginRequired)
- Only accountants can close/lock periods
- **Recommendation**: Restrict period CRUD to `@dea_accountant_required` to prevent non-accountants from creating invalid periods

---

## 7. DIAGNOSTIC, AUDIT & REPORT SURFACES

### Dashboard Views (Mixed Role Gating)

#### Legacy Dashboard
- **File**: `apps/tenant_apps/dea/views/dashboard.py`
- **URL**: `/dea/dashboard/` and `/dea/dashboard/legacy/` (names: `dea_dashboard`, `dea_dashboard_legacy`)
- **Role**: `@dea_accountant_required` (recently gated in Phase 7)
- **Purpose**: Overview of accounting status, key metrics, debtors/creditors

**Helper Functions**:
- `_calculate_key_metrics()`: Profit, revenue, expense, balance sheet totals
- `_get_dashboard_alerts()`: Outstanding invoices, overdue payments, closed periods
- `_get_top_debtors()`: AR analysis
- `_get_top_creditors()`: AP analysis

**AJAX Refresh**: `dashboard_metrics_ajax()` → `/dea/dashboard/metrics/ajax/` (name: `dashboard_metrics_ajax`)

#### Enhanced Dashboard
- **File**: `apps/tenant_apps/dea/views/dashboard_enhanced.py`
- **URL**: `/dea/dashboard/enhanced/` (name: `dea_dashboard_enhanced`)
- **Role**: `@dea_accountant_required` (recently gated in Phase 7)
- **Purpose**: Modern enhanced dashboard with better visualization + COA preview
- **Phase 7 Change**: COA preview now hidden for non-accountant roles; voucher drilldowns redirected to business events

**Phase 7+ Consideration**: Dashboard gating completed in Phase 7. Both variants are **accountant-only** (correct). **Next**: Consider renaming "Dashboard" to "Accounting Dashboard" to clarify scope.

### Chart of Accounts
- **File**: `apps/tenant_apps/dea/views/chart_of_accounts.py`
- **URL**: `/dea/chart-of-accounts/` (name: `dea_chart_of_accounts`)
- **Role**: `@dea_accountant_required` (gated in Phase 7)
- **Purpose**: COA navigator grouped by account type showing current balances
- **Key Models**: `Ledger`, `Account`, `AccountType`, `LedgerBalance` (DB view)

**Phase 7+ Consideration**: COA access is now restricted to accountants. **Previously exposed**: non-accountants could view COA. Phase 7 restricted this to reduce "surface noise" in user navigation.

### Audit & Ledger Trails
- **Ledger Audit**: `audit_ledger()` → `/dea/ledger/audit/` (name: `dea_ledger_audit`)
- **Account Audit**: `audit_acc()` → `/dea/account/<int:pk>/audit/` (name: `dea_account_audit`)
- **Account Transaction Detail**: `accounttransaction_detail()` → `/dea/dea/accounttransaction/<int:pk>/detail/`
- **Ledger Transaction Detail**: `ledger_transaction_detail()` → `/dea/dea/ledgertransaction/<int:pk>/detail/`

**Role**: `@dea_accountant_required`

**Purpose**: Immutable audit trail for GL changes; used for forensic accounting and compliance

**Phase 7+ Consideration**: Audit trails are **governance-critical**. **No deprecation candidate**. Keep as accountant-only.

### Financial Reports Hub
- **File**: `apps/tenant_apps/dea/views/reports_hub.py`
- **URL**: `/dea/reports/` (name: `dea_reports_hub`)
- **Role**: `@login_required` (open to all authenticated users)
- **Purpose**: Landing page for all financial and diagnostic reports

**Phase 7+ Consideration**: Reports hub is accessible to all users (business-event-first design). **Recommended**: Audit which reports are actually used by non-accountants; hide specialized reports (e.g., detailed ledger, trial balance) from non-accountant navigation.

### Financial Reports (Period-Aware)
- **File**: `apps/tenant_apps/dea/views/reports.py`
- **Base Class**: `BaseReportView(LoginRequiredMixin, TemplateView)`

#### Standard Reports:
| Report | URL | CSV Export | Role | Purpose |
|---|---|---|---|---|
| Trial Balance | `/dea/reports/period/<period_id>/trial-balance/` | ✅ Yes | LoginRequired | GL balance verification |
| Income Statement | `/dea/reports/period/<period_id>/income-statement/` | ✅ Yes | LoginRequired | P&L by period |
| Balance Sheet | `/dea/reports/period/<period_id>/balance-sheet/` | ✅ Yes | LoginRequired | Assets/Liabilities/Equity snapshot |
| Cash Flow | `/dea/reports/period/<period_id>/cash-flow/` | ✅ Yes | LoginRequired | Cash movements |
| AR Aging | `/dea/reports/period/<period_id>/ar-aging/` | ✅ Yes | LoginRequired | Customer receivables age |
| AP Aging | `/dea/reports/period/<period_id>/ap-aging/` | ✅ Yes | LoginRequired | Vendor payables age |

#### Ledger-Based Reports:
| Report | URL | Role | Purpose |
|---|---|---|---|
| Trial Balance | `/dea/trial-balance/` | LoginRequired | Current GL state |
| Balance Sheet | `/dea/balance-sheet/` | LoginRequired | Current position |
| Income Statement | `/dea/income-statement/` | LoginRequired | Current P&L |
| Profit & Loss | `/dea/profit-and-loss/` | LoginRequired | Alternate P&L |
| Cash Flow | `/dea/cash-flow/` | LoginRequired | Cash projection |
| Financial Ratios | `/dea/reports/ratios/` | LoginRequired | Liquidity, profitability metrics |

**Phase 7+ Consideration**: Financial reports are **business-facing** (not accountant-only); currently exposed to all users. **Correct design**. **Future**: Enhance with role-based filtering (e.g., non-accountants see revenue/expense summary; accountants see detailed GL).

### Commodity Reports
- **File**: `apps/tenant_apps/dea/views/commodity_reports.py`

| Report | URL | Role | Purpose |
|---|---|---|---|
| Metal Balance | `/dea/reports/commodity/metal-balance/` | LoginRequired | Commodity inventory by type |
| Exposure | `/dea/reports/commodity/exposure/` | LoginRequired | Commodity price exposure (hedging analysis) |
| Valuation | `/dea/reports/commodity/valuation/` | LoginRequired | Mark-to-market commodity value |

**Phase 7+ Consideration**: Commodity reports are **integrated with DEA** (via business-event rates). Open to all users. **Correct for commodity-heavy businesses**.

### General Ledger & Daybook
- **File**: `apps/tenant_apps/dea/views/common.py`

| View | URL | Role | Purpose |
|---|---|---|---|
| General Ledger | `/dea/dea/gl/` (name: `dea_general_ledger`) | LoginRequired | Full GL transaction log |
| Daybook | `/dea/daybook/` (name: `dea_daybook`) | LoginRequired | Daily transaction summary |

**Phase 7+ Consideration**: GL and daybook are **foundational diagnostic tools**. Open to all users. **Correct**.

### Transaction List (Unified)
- **File**: `apps/tenant_apps/dea/views/transactions.py`
- **URL**: `/dea/transactions/` (name: `dea_transaction_list`)
- **Role**: LoginRequired
- **Purpose**: All-in-one transaction view across all voucher types

**Phase 7+ Consideration**: Transaction list is **high-value** for non-accountants to see history. **Correct design**.

---

## 8. LEDGER & ACCOUNT MANAGEMENT SURFACES

### Ledger Management
- **File**: `apps/tenant_apps/dea/views/ledger.py`

| Operation | URL | Role | Purpose | Risk |
|---|---|---|---|---|
| List | `/dea/ledger/` | `@dea_accountant_required` | View all ledgers with balance | Low |
| Detail | `/dea/ledger/<int:pk>/` | `@dea_accountant_required` | Ledger details + statements + transactions | Low |
| Create | `/dea/ledger/add/` | `@dea_accountant_required` | Create new ledger | Medium |
| Update | `/dea/ledger/<int:pk>/update/` | `@dea_accountant_required` | Modify ledger properties | Medium |
| Set Opening Balance | `/dea/ledger/<int:pk>/set-ob/` | `@dea_accountant_required` | Manually set ledger OB | **High** |
| Statements | `/dea/ledger/statement/` | `@dea_accountant_required` | View ledger statements (OB, activity, closing) | Low |
| Transactions | `/dea/ledger/transaction/` | `@dea_accountant_required` | View all ledger transactions | Low |

**Key Models**: `Ledger`, `LedgerStatement`, `LedgerTransaction`, `LedgerBalance` (view)

**Phase 7+ Consideration**: Ledger management is **foundational** for multi-ledger accounting (e.g., separate commodity/AR ledgers). **No deprecation candidate**. **Strategy**: Audit whether non-accountants need read-only ledger access (e.g., commodity balance queries).

### Account Management
- **File**: `apps/tenant_apps/dea/views/account.py`

| Operation | URL | Role | Purpose | Risk |
|---|---|---|---|---|
| List | `/dea/account/` | `@dea_accountant_required` | View all accounts grouped by ledger | Low |
| Detail | `/dea/account/<int:pk>/` | `@dea_accountant_required` | Account details + balance + statements | Low |
| Set Opening Balance | `/dea/account/<int:pk>/set-ob/` | `@dea_accountant_required` | Manually set account OB | **High** |
| Statements | `/dea/account/accountstatement/` | `@dea_accountant_required` | View account statements | Low |
| Statement Delete | `/dea/account/accountstatement/<int:pk>/delete` | `@dea_accountant_required` | Remove account statement | **High** |
| Balance (AJAX) | `/dea/customer_balance/` | `@dea_accountant_required` | Fetch customer/party account balance | Low |

**Key Models**: `Account`, `AccountStatement`, `AccountBalance` (view)

**Phase 7+ Consideration**: Account management similar to ledger management. **No deprecation candidate**.

---

## 9. BANK RECONCILIATION SURFACES

### Bank Reconciliation Workflow
- **File**: `apps/tenant_apps/dea/views/reconciliation.py`
- **Role**: All operations open to `@login_required` (not accountant-restricted)

| Operation | URL | Purpose | Risk |
|---|---|---|---|
| Accounts List | `/dea/reconciliation/` | View bank accounts with reconciliation status | Low |
| Reconciliation Detail | `/dea/reconciliation/<int:pk>/` | View reconciliation in-progress for account | Medium |
| Import Statement | `/dea/reconciliation/import/` | Upload bank statement file (CSV/OFX) | Medium |
| Auto Match | `/dea/reconciliation/auto-match/<int:bank_account_id>/` | Automated transaction matching | Medium |
| Manual Match | `/dea/reconciliation/manual-match/` | Manually match statement lines to GL entries | Medium |
| Unmatch | `/dea/reconciliation/unmatch/` | Reverse a match | Medium |

**Key Models**: `BankAccount`, `BankReconciliation`, `BankStatement`, `BankTransaction`

**Phase 7+ Consideration**: Bank reconciliation is **business-facing** (not accountant-exclusive) in current design. **Recommendation**: Audit whether non-accountants should be creating reconciliations (currently allowed). Consider restricting to `@dea_accountant_required`.

---

## 10. SALES & PURCHASE INVOICE SURFACES

### Sales Invoice
- **File**: `apps/tenant_apps/dea/views/sales_invoice.py`
- **Role**: `@dea_accountant_required` (if manual entry); business-event-driven elsewhere

| Operation | URL | Purpose |
|---|---|---|
| List | `/dea/sales-invoices/` | View all sales invoices |
| Detail | `/dea/sales-invoices/<int:pk>/` | View invoice + items + GL entries if posted |
| Create | `/dea/sales-invoices/create/` | Manual sales invoice entry |
| Update | `/dea/sales-invoices/<int:pk>/update/` | Modify invoice |
| Delete | `/dea/sales-invoices/<int:pk>/delete/` | Remove unposted invoice |

### Purchase Invoice
- **File**: `apps/tenant_apps/dea/views/purchase_invoice.py`
- **Role**: `@dea_accountant_required` (if manual entry); business-event-driven elsewhere

| Operation | URL | Purpose |
|---|---|---|
| List | `/dea/purchase-invoices/` | View all purchase invoices |
| Detail | `/dea/purchase-invoices/<int:pk>/` | View invoice + items + GL entries if posted |
| Create | `/dea/purchase-invoices/create/` | Manual purchase invoice entry |
| Update | `/dea/purchase-invoices/<int:pk>/update/` | Modify invoice |
| Delete | `/dea/purchase-invoices/<int:pk>/delete/` | Remove unposted invoice |

**Phase 7+ Consideration**: Sales/Purchase invoice manual UIs are **mostly superseded by business-event workflows** (Fixed Sale, Fixed Purchase events). These are fallback surfaces for edge cases. **Strategy**: Mark as "legacy fallback" in navigation and reduce discoverability; encourage business-event routing instead.

---

## 11. LEGACY JOURNAL ENTRY VIEWS

### Legacy Journal Entry Direct Views
- **File**: `apps/tenant_apps/dea/views/journal_entry.py`
- **Role**: Varies; some `@dea_accountant_required`, some `@login_required`

| Operation | URL | Purpose | Role |
|---|---|---|---|
| List | `/dea/journal_entries/` | View JEs (legacy) | LoginRequired |
| Detail | `/dea/journal_entry/<int:pk>/detail` | JE detail | `@dea_accountant_required` |
| Create | `/dea/journal_entry/create/` | Manual JE creation (legacy) | `@dea_accountant_required` |
| Delete | `/dea/journal_entry/<int:pk>/delete` | Delete JE | `@dea_accountant_required` |
| Account Transaction (CRUD) | `/dea/dea/accounttransaction/*` | AT lifecycle | `@dea_accountant_required` |
| Ledger Transaction (CRUD) | `/dea/dea/ledgertransaction/*` | LT lifecycle | `@dea_accountant_required` |

**Phase 7+ Consideration**: Legacy JE views are **superseded by JournalEntryVoucher**. **Candidates for deprecation in Phase 8** after verification that all workflows use JEV instead.

---

## Phase 8+ Recommendations by Surface Category

### 🔴 High-Risk (Keep, Harden Role Gating)
- **Opening Balance Setup**: Critical initialization; restrict to `@dea_accountant_required` (already done)
- **Period Management**: Architectural foundation; restrict period CRUD to `@dea_accountant_required` (currently `@login_required` — **Phase 8 task**)
- **Posting Operations** (vouchers, JEV): High-stakes GL materialization; keep `@dea_accountant_required` (currently correct)
- **Bank Reconciliation**: Currently `@login_required`; consider restricting to `@dea_accountant_required` (audit needed)

### 🟡 Medium-Risk (Keep, Relabel or Reduce Discoverability)
- **Payment Vouchers**: Keep as fallback; integrate with Girvi events; relabel to "Payment Records" or "Cash Receipts/Disbursements"
- **Expense Vouchers**: Keep as fallback; relabel to "Adjustment Entries" or "Manual Expenses"
- **Journal Entry Vouchers**: Keep for auditor-requested entries; add guidance (e.g., "Use for non-standard entries only")
- **Sales/Purchase Invoices**: Keep as fallback; relabel to "Manual Invoice Entry (Legacy)" and reduce navigation visibility
- **Legacy JE Views**: Phase 8 deprecation candidates if JEV is confirmed as sole JE creation path

### 🟢 Low-Risk (Keep, Consider Expanding Access)
- **Financial Reports**: Correct design (all users); consider enhancing with role-based filtering
- **Commodity Reports**: Correct design; keep open to business users
- **Audit Trails**: Keep as accountant-only; governance-critical
- **GL & Daybook**: Correct design (all users); business-facing

### ⚫ Deprecation Candidates (Phase 8+)
- **Legacy Journal Entry Views** (if JEV fully adopted)
- **Duplicate Report Endpoints** (if unified period-aware reporting is standardized)
- **Manual Sales/Purchase Invoice UIs** (if business-event routing is enforced)

---

## Role-Gating Audit Summary

### Inconsistencies Identified (Phase 8 work)

| Surface | Current Role-Gating | Issue | Phase 8 Action |
|---|---|---|---|
| Period CRUD | `@login_required` | Non-accountants can create periods | Restrict to `@dea_accountant_required` |
| Bank Reconciliation | `@login_required` | Non-accountants can reconcile | Audit + consider restricting |
| Period Reports | `@login_required` | Mix of open/restricted reports | Audit + standardize |
| Dashboard (Post-Phase7) | `@dea_accountant_required` | Correct | Keep |
| Voucher Hub | `@dea_accountant_required` | Correct | Keep |
| Opening Balance | `@dea_accountant_required` | Correct | Keep |
| Generic Voucher Posting | `@dea_accountant_required` | Correct | Keep |

---

## Document Maintenance

- **Last Updated**: 2026-06-26 (Phase 7 legacy-surface gating completion)
- **Next Review**: Before Phase 8 planning begins
- **Owner**: Architecture/Phase 8 planner
- **Related Documents**:
  - [docs/STATUS.md](../STATUS.md) — Project status and current focus
  - [docs/roadmaps/dea_commodity_accounting_refactor_plan.md](../roadmaps/dea_commodity_accounting_refactor_plan.md) — Phase roadmap
  - [docs/AGENTS.md](../AGENTS.md) — Project contract + rules

---

## Glossary

- **Accountant Required**: Restricted to workspace members with `Owner`, `Admin`, or `Accountant` roles
- **LoginRequired**: Open to all authenticated users (members of workspace)
- **JEV**: Journal Entry Voucher (modern manual journalization surface)
- **OB**: Opening Balance
- **GL**: General Ledger
- **AR**: Accounts Receivable
- **AP**: Accounts Payable
- **PRE_CLOSE**: Pre-closing adjustment entry prefix
- **DEA**: Domain-driven Enterprise Accounting (Rokkad's core accounting module)

