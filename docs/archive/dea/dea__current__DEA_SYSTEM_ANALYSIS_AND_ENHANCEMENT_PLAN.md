---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# DEA (Double Entry Accounting) System - Comprehensive Analysis & Enhancement Plan

**Date**: March 27, 2026 (Updated from March 25)  
**Status**: âœ… Phase 1 Complete â€” Phase 2 Ready to Start  
**Project**: Unified UX/UI for DEA System with Enhanced Reporting

> ðŸ“Œ **UPDATE (Mar 27):** The dashboard has been implemented. Phase 1 sections are marked complete below. See [DEA_DASHBOARD_GUIDE.md](../DEA_DASHBOARD_GUIDE.md) for the full feature reference. Enhancement work now begins at Phase 2.

---

## EXECUTIVE SUMMARY

The DEA (Double Entry Accounting) application is a sophisticated accounting system built on Django with robust backend models and business logic. However, **critical functionality is hidden from users** and the **user experience is fragmented**:

### Current Problems
1. **Hidden Functionality**: Vouchers, transactions, reports exist but are not discoverable
2. **Ambiguous User Flow**: Users don't know:
   - Where to start creating vouchers
   - Which vouchers they can create
   - How to record income/expense/customer transactions
   - What the chart of accounts contains
3. **No Unified Dashboard**: Dashboard shows alerts but no actionable entry points
4. **Scattered Templates**: Functionality spread across unconnected views/pages
5. **Missing Guidance**: No educational guidance on accounting concepts

### Proposed Solution
Create a **unified, intuitive accounting dashboard** that:
- Centralizes account discovery and voucher creation
- Provides clear walkthroughs for different transaction types
- Integrates critical financial reports
- Reduces cognitive load on users
- Makes accounting workflow discoverable and self-explanatory

---

## CURRENT SYSTEM ARCHITECTURE

### Backend Structure (Well-Designed)

#### Core Models
```
Account System:
â”œâ”€â”€ EntityType                 (Person, Company, etc.)
â”œâ”€â”€ TransactionType_DE         (DR/CR base types)
â”œâ”€â”€ AccountType_Ext            (Sundry Debtor, Creditor, etc.)
â”œâ”€â”€ Account                    (Customer/Vendor accounts with credit limits)
â”œâ”€â”€ AccountTransaction         (Individual account-level transactions)

Ledger System:
â”œâ”€â”€ Ledger                      (GL accounts in hierarchical tree - MPPT)
â”œâ”€â”€ LedgerTransaction           (Debit/Credit entries per ledger)
â”œâ”€â”€ LedgerBalance               (Cached running balance)

Voucher System:
â”œâ”€â”€ VoucherType                 (Classification: Journal, Invoice, Payment, etc.)
â”œâ”€â”€ Voucher                     (Master record linking doc to journal entry)
â”œâ”€â”€ VoucherStatus               (DRAFT â†’ POSTED â†’ REVERSED/CORRECTED)

Document Types (Business):
â”œâ”€â”€ SalesInvoice                (Revenue document)
â”œâ”€â”€ PurchaseInvoice             (Cost document)
â”œâ”€â”€ Expense                     (Operating expense document)
â”œâ”€â”€ Payment                     (Cash/Bank transaction)
â”œâ”€â”€ JournalEntryVoucher         (Manual GL adjustment)
â”œâ”€â”€ TakenLoan, GivenLoan        (Loan management)

Journal Entry System:
â”œâ”€â”€ JournalEntry                (Posted GL entries per voucher)
â”œâ”€â”€ LineItems                   (DR/CR lines with amounts)

Reporting:
â”œâ”€â”€ LedgerStatement             (GL account history)
â”œâ”€â”€ AccountStatement            (Customer account history)
â”œâ”€â”€ Balance Sheet, P&L, Trial Balance
```

#### Voucher Types Available
1. **SalesInvoiceVoucher** - Revenue transactions (customer invoices)
2. **PurchaseInvoiceVoucher** - Cost transactions (supplier invoices)
3. **PaymentVoucher** - Cash/bank payments and receipts
4. **ExpenseVoucher** - Operating expenses with line items
5. **JournalEntryVoucher** - Manual GL adjustments
6. **LoanDisbursementVoucher** - Loan disbursement
7. **LoanRepaymentVoucher** - Loan repayment
8. **TakenLoanVoucher** - Loan taken from lender
9. **GivenLoanVoucher** - Loan given to borrower
10. **OpeningBalanceVoucher** - Initial account setup

### Posting Engine (Sophisticated)
```
Posting Rules:
â”œâ”€â”€ sales_invoice.py             â†’ DR: Receivable, CR: Revenue
â”œâ”€â”€ purchase_invoice.py          â†’ DR: Expense/Inventory, CR: Payable
â”œâ”€â”€ expense.py                   â†’ DR: Various Expense, CR: Cash/Payable
â”œâ”€â”€ payment.py                   â†’ DR: Cash, CR: Receivable/Payable
â”œâ”€â”€ journal_entry.py             â†’ User-defined DR/CR
â”œâ”€â”€ loan_disbursement.py         â†’ DR: Loan (asset), CR: Cash
â”œâ”€â”€ loan_repayment.py            â†’ DR: Cash, CR: Loan
â”œâ”€â”€ givenloan_*.py               â†’ Loan given to borrower
â”œâ”€â”€ takenloan_*.py               â†’ Loan taken from lender

Key Features:
- Idempotent fingerprinting (edit-repost pattern)
- Automatic reversal on changes
- Multi-currency support
- Balanced validation
- Atomic transactions
```

### Views & Template Structure *(Updated Mar 27)*

#### Available Views
```
Dashboard: âœ… IMPLEMENTED (see DEA_DASHBOARD_GUIDE.md)
â”œâ”€â”€ dashboard/                    - âœ… Main dashboard (650 lines, full metrics + alerts)
â”œâ”€â”€ dashboard/enhanced/           - âœ… Enhanced skeleton (quick actions, workflows, COA preview)
â”œâ”€â”€ dashboard/metrics/ajax/       - âœ… AJAX metrics refresh (JSON)
â”œâ”€â”€ reports/receivables/aging/    - âœ… AR Aging (4 buckets, card + table)
â”œâ”€â”€ reports/payables/aging/       - âœ… AP Aging (same layout)
â””â”€â”€ reports/ratios/               - âœ… Financial Ratios (liquidity + leverage)

Accounts:
â”œâ”€â”€ account/                      - List customer/vendor accounts
â”œâ”€â”€ account/<id>/                 - Account detail & transactions
â”œâ”€â”€ account/<id>/set-ob/          - Set opening balance
â”œâ”€â”€ accountstatement/             - Account aging/statement

Ledgers:
â”œâ”€â”€ ledger/                       - GL accounts list
â”œâ”€â”€ ledger/<id>/                  - Ledger detail
â”œâ”€â”€ ledger/add/                   - Create ledger
â”œâ”€â”€ ledger/<id>/update/           - Update ledger
â”œâ”€â”€ ledger/<id>/set-ob/           - Set opening balance

Vouchers & Documents:
â”œâ”€â”€ voucher/                      - All vouchers list
â”œâ”€â”€ voucher/add/                  - Create manual voucher
â”œâ”€â”€ sales-invoice/                - Sales invoice list
â”œâ”€â”€ purchase-invoice/             - Purchase invoice list
â”œâ”€â”€ expense/                      - Expense voucher list
â”œâ”€â”€ payment/                      - Payment voucher list
â”œâ”€â”€ journal-entry/                - Manual journal entry creation
â”œâ”€â”€ opening-balance/              - Opening balance setup

Financial Reports:
â”œâ”€â”€ trial-balance/                - Trial balance report
â”œâ”€â”€ balance-sheet/                - Balance sheet
â”œâ”€â”€ profit-and-loss/              - P&L statement
â”œâ”€â”€ income-statement/             - Income statement
â”œâ”€â”€ cash-flow/                    - Cash flow statement
â”œâ”€â”€ reports/receivables/aging/    - AR aging
â”œâ”€â”€ reports/payables/aging/       - AP aging
â”œâ”€â”€ reports/ratios/               - Financial ratios

Miscellaneous:
â”œâ”€â”€ daybook/                      - Full transaction log
â”œâ”€â”€ gl/                           - General ledger detail
â”œâ”€â”€ period/                       - Accounting periods
â”œâ”€â”€ tally/                        - Tally import
```

#### Dashboard Features *(Updated: Mar 27 â€” see DEA_DASHBOARD_GUIDE.md for full detail)*
- âœ… Key financial metrics: Cash, Receivables, Payables, Working Capital
- âœ… Period P&L summary: Revenue â†’ COGS â†’ Gross Profit â†’ Net Profit â†’ Margin %
- âœ… Smart alert system: credit limit, draft vouchers, unbalanced JE, old periods
- âœ… Top 5 Debtors / Top 5 Creditors tables
- âœ… Recent Activity: 10 vouchers + 10 journal entries
- âœ… Quick Actions (placeholders â€” wired to `/dea/dashboard/enhanced/`)
- âœ… AR/AP Aging, Financial Ratios â€” separate report pages

---

## IDENTIFIED PROBLEMS & GAPS *(Updated Mar 27)*

### Problem 1: Discovery & Navigation â¬œ NOT YET FIXED
**Issue**: Users have no idea where to find/create specific vouchers

| Voucher Type | Current Status | Discoverability |
|---|---|---|
| Sales Invoice | âœ… Exists | âš ï¸ Hidden in deep URL |
| Purchase Invoice | âœ… Exists | âš ï¸ Hidden in deep URL |
| Expense | âœ… Exists | âš ï¸ Hidden in deep URL |
| Payment | âœ… Exists | âš ï¸ Hidden in deep URL |
| Journal Entry | âœ… Exists | âš ï¸ Hidden in deep URL |
| Opening Balance | âœ… Exists | âš ï¸ Hidden in deep URL |
| Loan Transactions | âœ… Exists | âš ï¸ Completely hidden |
| Manual Voucher | âœ… Exists | âš ï¸ Hidden in deep URL |

**Fix (Phase 2)**: Voucher Creation Hub at `/dea/create/`

### Problem 2: No Chart of Accounts Navigation â¬œ NOT YET FIXED
**Issue**: Users don't know what GL accounts exist for transactions

**What's Missing**:
- Visual hierarchy with balance overlay
- Account search with drill-down
- Account class (Asset/Liability/Equity/Revenue/Expense) grouping
- Account status indicators

**Fix (Phase 2)**: Chart of Accounts Navigator at `/dea/chart-of-accounts/`

### Problem 3: No Transaction Flow Guidance ðŸ”¶ PARTIALLY FIXED
**Original Issue**: No guided workflows or help texts

**What's Done**: `/dea/dashboard/enhanced/` has 5 guided workflow accordions (Set Up Accounts, Customer Transactions, Supplier Transactions, Expenses, Period-End) â€” but the flows point to pages that aren't themed yet with help text

**Remaining**: Wire help text and contextual guidance into individual voucher creation forms (Phase 4)

### Problem 4: Fragmented Dashboard âœ… RESOLVED
**Original Complaint**: Dashboard shows metrics only, no action buttons

**What Was Implemented** (per DEA_DASHBOARD_GUIDE.md):
- âœ… Main dashboard: full metrics, alerts, top debtors/creditors, recent activity
- âœ… Enhanced dashboard: quick actions (4 types) + 5 guided workflows + COA preview slot
- âœ… AR/AP aging separate pages
- âœ… Financial ratios page
- âœ… AJAX refresh endpoint

**Remaining (1-2 days)**: Wire real balance data into enhanced dashboard placeholder functions

### Problem 5: Reporting is Disconnected â¬œ NOT YET FIXED
**Current State**:
- AR/AP Aging âœ… exists at separate URLs
- Financial Ratios âœ… exists at separate URL
- Trial Balance, Balance Sheet, P&L â€” in reports but no hub page
- No centralized "Reports" landing page

**Fix (Phase 3)**: Reports Hub at `/dea/reports/`

### Problem 6: No Visual COA Representation â¬œ NOT YET FIXED
**Current State**:
- Ledger list exists at `/dea/ledger/` (flat list only)
- No account type hierarchy
- No balance overlay

**Fix (Phase 2)**: Chart of Accounts Navigator

### Problem 7: Missing Entry Points for Common Tasks
**Users Need Easy Access To**:
- Create customer invoice â†’ List of customers â†’ Pre-filled form
- Create supplier invoice â†’ List of suppliers â†’ Pre-filled form
- Record expense â†’ Expense type selection â†’ Form with suggestions
- View customer balance â†’ Account list with balances
- View outstanding AR/AP â†’ Aging reports with drill-down

---

## CURRENT VIEWS AVAILABLE (SCATTERED)

### Account Management
- Account list (flat, no balance view)
- Account detail (basic)
- Account statement (aging view exists)

### Ledger Management
- Ledger list (deep tree not visible)
- Ledger detail
- Trial balance
- General ledger

### Voucher Creation
- Manual voucher form (generic)
- Sales invoice form (specific)
- Purchase invoice form (specific)
- Expense voucher form (specific)
- Payment voucher form (specific)
- Journal entry form (specific)

### Reports
- Trial balance
- Balance sheet
- P&L
- Income statement
- Cash flow
- AR aging
- AP aging
- Financial ratios
- Daybook
- Account statements

**Problem**: All scattered, no unified navigation or context

---

## PROPOSED UNIFIED SOLUTION *(Updated Mar 27 â€” Phase 1 is DONE)*

### 1. Enhanced Dashboard - Central Hub âœ… PHASE 1 COMPLETE

**What Exists** (DO NOT reinvent â€” see DEA_DASHBOARD_GUIDE.md):
- `/dea/dashboard/` â€” full metrics, P&L, alerts, top debtors/creditors, recent activity (650-line `dashboard.py`)
- `/dea/dashboard/enhanced/` â€” quick actions + 5 guided workflow accordions + COA preview slot + report links (skeleton in `dashboard_enhanced.py`)
- `/dea/reports/receivables/aging/` + `/dea/reports/payables/aging/` â€” 4-bucket aging (0-30, 31-60, 61-90, 90+)
- `/dea/reports/ratios/` â€” Liquidity + Leverage ratios
- `/dea/dashboard/metrics/ajax/` â€” JSON refresh endpoint

**Remaining Gap** (implement in `dashboard_enhanced.py`):
Replace these 5 placeholder functions with real DB queries:
```python
calculate_ar_balance()   # currently returns 0
calculate_ap_balance()   # currently returns 0
calculate_cash_balance() # currently returns 0
calculate_period_pl()    # currently returns 0
get_coa_preview()        # currently returns []
```
Mirror patterns already in `dashboard.py` functions `_calculate_key_metrics()` and `_get_top_debtors()`.

**Phase 2 Layout Target** (wire enhanced dashboard as primary):

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  ACCOUNTING DASHBOARD - Unified Control Center                  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ QUICK ACTIONS (Top Section)                                     â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                                 â”‚
â”‚  [+ Invoice]  [+ Expense]  [+ Payment]  [+ Journal]  [Reports] â”‚
â”‚    Create      Create       Create       Entry        View All  â”‚
â”‚   Customer     Operating    Cash/Bank    GL Adjust             â”‚
â”‚    Invoice     Expense      Movement     Entry                 â”‚
â”‚                                                                 â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ KEY METRICS & ALERTS (Three Column Section)                     â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ Current Period:      â”‚ Financial Health     â”‚ Period Status    â”‚
â”‚ (Name & Dates)       â”‚                      â”‚                  â”‚
â”‚                      â”‚ â€¢ AR Balance         â”‚ â€¢ Open           â”‚
â”‚ Open Period Action   â”‚ â€¢ AP Balance         â”‚ â€¢ Days Left      â”‚
â”‚ Button (if exists)   â”‚ â€¢ Cash Position      â”‚ â€¢ Month/Quarter  â”‚
â”‚                      â”‚ â€¢ Net P&L            â”‚   View           â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ Volume Metrics       â”‚ Account Status       â”‚ Alert Summary    â”‚
â”‚                      â”‚                      â”‚                  â”‚
â”‚ â€¢ Vouchers (Posted)  â”‚ â€¢ Active Accounts    â”‚ â€¢ Unbalanced JE  â”‚
â”‚ â€¢ Draft Vouchers     â”‚ â€¢ Over-limit Debtors â”‚ â€¢ Over Credit    â”‚
â”‚ â€¢ Active Ledgers     â”‚ â€¢ Inactive Accounts  â”‚ â€¢ Inactive Accts â”‚
â”‚                      â”‚                      â”‚ â€¢ Overdue AP     â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ GUIDED WORKFLOW SECTION (Collapsible Cards)                    â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                                 â”‚
â”‚ â–¼ 1. Set Up Account Structure (Initial Setup)                  â”‚
â”‚   â””â”€ Chart of Accounts â†’ Opening Balances â†’ Bank Setup          â”‚
â”‚                                                                 â”‚
â”‚ â–¼ 2. Record Customer Transactions                              â”‚
â”‚   â””â”€ View Customers â†’ Create Invoice â†’ Record Payment          â”‚
â”‚                                                                 â”‚
â”‚ â–¼ 3. Record Supplier Transactions                              â”‚
â”‚   â””â”€ View Suppliers â†’ Create Bill â†’ Record Payment             â”‚
â”‚                                                                 â”‚
â”‚ â–¼ 4. Record Operating Expenses                                 â”‚
â”‚   â””â”€ Create Expense Entry â†’ Categorize â†’ Post                  â”‚
â”‚                                                                 â”‚
â”‚ â–¼ 5. Period-End Activities                                     â”‚
â”‚   â””â”€ Review GL â†’ Generate Reports â†’ Close Period               â”‚
â”‚                                                                 â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ RECENT ACTIVITY & CHART OF ACCOUNTS (Three Column)              â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ Recent Vouchers (10) â”‚ Chart of Accounts   â”‚ Key Balances     â”‚
â”‚                      â”‚ (Hierarchical)       â”‚                  â”‚
â”‚ â€¢ Type              â”‚  â”œâ”€ Assets          â”‚ â€¢ Receivables    â”‚
â”‚ â€¢ Date              â”‚  â”‚  â”œâ”€ Cash         â”‚ â€¢ Payables       â”‚
â”‚ â€¢ Amount            â”‚  â”‚  â”œâ”€ Bank         â”‚ â€¢ Inventory      â”‚
â”‚ â€¢ Status            â”‚  â”‚  â””â”€ Receivables  â”‚ â€¢ Fixed Assets   â”‚
â”‚                      â”‚  â”œâ”€ Liabilities     â”‚ â€¢ Equity         â”‚
â”‚ [View All Vouchers] â”‚  â”‚  â”œâ”€ Payables     â”‚ â€¢ Revenue        â”‚
â”‚                      â”‚  â”‚  â””â”€ Bank Loans   â”‚                  â”‚
â”‚                      â”‚  â”œâ”€ Equity          â”‚ [View Full COA]  â”‚
â”‚                      â”‚  â”œâ”€ Revenue         â”‚                  â”‚
â”‚                      â”‚  â””â”€ Expenses        â”‚                  â”‚
â”‚                      â”‚                      â”‚                  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ FINANCIAL REPORTS (Quick Links)                                 â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                                 â”‚
â”‚ [Trial Balance]  [Balance Sheet]  [P&L]  [Cash Flow]  [More...] â”‚
â”‚                                                                 â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### 2. Chart of Accounts Navigator (New Page)

**Page: `/dea/chart-of-accounts/`**

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  CHART OF ACCOUNTS - Full Hierarchical View                    â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ Search & Filter                                                 â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ [Search: ________]  [Filter: Class â–¼] [Status: â–¼]  [Drill: >] â”‚
â”‚                                          Active/All   Details   â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  ACCOUNT HIERARCHY (Tree View with Details)                    â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                                 â”‚
â”‚  â–¼ ASSETS (Class)                              Balance          â”‚
â”‚    â–¼ Current Assets                                            â”‚
â”‚      â€¢ Cash on Hand              ACC-001      50,000 DR        â”‚
â”‚      â€¢ Bank Account              ACC-002      1,25,000 DR      â”‚
â”‚      â€¢ Accounts Receivable       ACC-003      3,75,000 DR      â”‚
â”‚    â–¼ Fixed Assets                                              â”‚
â”‚      â€¢ Plant & Machinery         ACC-004      10,00,000 DR     â”‚
â”‚      â€¢ Office Equipment          ACC-005      2,50,000 DR      â”‚
â”‚      â€¢ Accumulated Depreciation  ACC-006      (3,00,000) CR    â”‚
â”‚                                                                 â”‚
â”‚  â–¼ LIABILITIES (Class)                        Balance          â”‚
â”‚    â–¼ Current Liabilities                                       â”‚
â”‚      â€¢ Accounts Payable          ACC-007      (2,00,000) CR    â”‚
â”‚      â€¢ Short-term Loan          ACC-008      (1,50,000) CR    â”‚
â”‚    â–¼ Long-term Liabilities                                     â”‚
â”‚      â€¢ Long-term Loan           ACC-009      (5,00,000) CR    â”‚
â”‚                                                                 â”‚
â”‚  â–¼ EQUITY (Class)                             Balance          â”‚
â”‚      â€¢ Capital (Owner)          ACC-010      (8,00,000) CR    â”‚
â”‚      â€¢ Retained Earnings        ACC-011      (2,00,000) CR    â”‚
â”‚                                                                 â”‚
â”‚  â–¼ REVENUE (Class)                            Balance          â”‚
â”‚    â–¼ Operating Revenue                                         â”‚
â”‚      â€¢ Sales - Product          ACC-012      (5,00,000) CR    â”‚
â”‚      â€¢ Sales - Service          ACC-013      (1,50,000) CR    â”‚
â”‚    â–¼ Other Revenue                                             â”‚
â”‚      â€¢ Interest Income          ACC-014      (20,000) CR      â”‚
â”‚                                                                 â”‚
â”‚  â–¼ EXPENSES (Class)                           Balance          â”‚
â”‚    â–¼ Operating Expenses                                        â”‚
â”‚      â€¢ Salaries & Wages         ACC-015      3,00,000 DR      â”‚
â”‚      â€¢ Rent Expense             ACC-016      60,000 DR        â”‚
â”‚      â€¢ Utilities                 ACC-017      25,000 DR       â”‚
â”‚    â–¼ Cost of Goods Sold                                        â”‚
â”‚      â€¢ Raw Material             ACC-018      2,00,000 DR      â”‚
â”‚                                                                 â”‚
â”‚                                               [More Accounts]  â”‚
â”‚                                                                 â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

Features:
- Click account â†’ Drill to detail â†’ Open Ledger/Statement
- Hover account â†’ Show 30-day movement sparkline
- Balance shown in account's natural position (DR/CR)
- Status badges: Active (green), Inactive (gray), Suspended (red)
- Quick navigation: Jump to account class
```

### 3. Voucher Creation Hub (New Page)

**Page: `/dea/vouchers/create/`**

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  CREATE TRANSACTION - Choose Your Type                          â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ CUSTOMER & SUPPLIER TRANSACTIONS                                â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                                  â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”   â”‚
â”‚  â”‚ CUSTOMER INVOICE   â”‚  â”‚ SUPPLIER INVOICE   â”‚  â”‚PAYMENT â”‚   â”‚
â”‚  â”‚   (Revenue)        â”‚  â”‚   (Expense/Cost)   â”‚  â”‚Records â”‚   â”‚
â”‚  â”‚                    â”‚  â”‚                    â”‚  â”‚Cash In â”‚   â”‚
â”‚  â”‚ For: Sales to      â”‚  â”‚ For: Purchases     â”‚  â”‚   &    â”‚   â”‚
â”‚  â”‚      Customers     â”‚  â”‚      from Vendors  â”‚  â”‚   Out  â”‚   â”‚
â”‚  â”‚                    â”‚  â”‚                    â”‚  â”‚        â”‚   â”‚
â”‚  â”‚ GL Impact:         â”‚  â”‚ GL Impact:         â”‚  â”‚GL Impactâ”‚  â”‚
â”‚  â”‚ DR: Receivable     â”‚  â”‚ DR: Inventory/Exp  â”‚  â”‚DR: Cashâ”‚   â”‚
â”‚  â”‚ CR: Revenue        â”‚  â”‚ CR: Payable        â”‚  â”‚CR: A/R â”‚   â”‚
â”‚  â”‚                    â”‚  â”‚                    â”‚  â”‚or A/P  â”‚   â”‚
â”‚  â”‚  [Create Invoice] â–¶â”‚  â”‚ [Create Bill]     â–¶â”‚  â”‚[Record]â–¶   â”‚
â”‚  â”‚                    â”‚  â”‚                    â”‚  â”‚        â”‚   â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”€â”€â”˜   â”‚
â”‚                                                                  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ OPERATING EXPENSES & MANUAL ENTRIES                             â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                                  â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                 â”‚
â”‚  â”‚ EXPENSE ENTRY      â”‚  â”‚ JOURNAL ENTRY      â”‚                 â”‚
â”‚  â”‚   (Operational)    â”‚  â”‚   (GL Adjustments) â”‚                 â”‚
â”‚  â”‚                    â”‚  â”‚                    â”‚                 â”‚
â”‚  â”‚ For: Operating     â”‚  â”‚ For: Corrections,  â”‚                 â”‚
â”‚  â”‚      Expenses      â”‚  â”‚      Accruals,     â”‚                 â”‚
â”‚  â”‚      (Rent,        â”‚  â”‚      Adjustments   â”‚                 â”‚
â”‚  â”‚       Utilities,   â”‚  â”‚                    â”‚                 â”‚
â”‚  â”‚       etc.)        â”‚  â”‚ GL Impact:         â”‚                 â”‚
â”‚  â”‚                    â”‚  â”‚ DR: User Selected  â”‚                 â”‚
â”‚  â”‚ GL Impact:         â”‚  â”‚ CR: User Selected  â”‚                 â”‚
â”‚  â”‚ DR: Expense        â”‚  â”‚                    â”‚                 â”‚
â”‚  â”‚ CR: Cash/Payable   â”‚  â”‚  [Entry Form]     â–¶                 â”‚
â”‚  â”‚                    â”‚  â”‚                    â”‚                 â”‚
â”‚  â”‚  [Create Expense] â–¶â”‚  â”‚                    â”‚                 â”‚
â”‚  â”‚                    â”‚  â”‚                    â”‚                 â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                 â”‚
â”‚                                                                  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ INITIALIZATION & SPECIAL ENTRIES                                â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                                  â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                 â”‚
â”‚  â”‚ OPENING BALANCE    â”‚  â”‚ LOAN TRANSACTIONS  â”‚                 â”‚
â”‚  â”‚   (Period Setup)   â”‚  â”‚   (Borrowing)      â”‚                 â”‚
â”‚  â”‚                    â”‚  â”‚                    â”‚                 â”‚
â”‚  â”‚ For: Initial       â”‚  â”‚ For: Loan given    â”‚                 â”‚
â”‚  â”‚      GL Balances   â”‚  â”‚      or received   â”‚                 â”‚
â”‚  â”‚      at period     â”‚  â”‚                    â”‚                 â”‚
â”‚  â”‚      start         â”‚  â”‚ Types:             â”‚                 â”‚
â”‚  â”‚                    â”‚  â”‚ â€¢ Loan Disbursed   â”‚                 â”‚
â”‚  â”‚ GL Impact:         â”‚  â”‚ â€¢ Loan Repaid      â”‚                 â”‚
â”‚  â”‚ DR/CR: Balance     â”‚  â”‚ â€¢ Taken Loan       â”‚                 â”‚
â”‚  â”‚        Account     â”‚  â”‚ â€¢ Given Loan       â”‚                 â”‚
â”‚  â”‚                    â”‚  â”‚                    â”‚                 â”‚
â”‚  â”‚ [Set Opening Bal] â–¶â”‚  â”‚  [Loan Options]   â–¶                 â”‚
â”‚  â”‚                    â”‚  â”‚                    â”‚                 â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                 â”‚
â”‚                                                                  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

Help Section:
"â“ Don't know which to choose?" [Show Flowchart]
- Are you selling products/services? â†’ Customer Invoice
- Are you receiving a bill? â†’ Supplier Invoice
- Are you paying someone? â†’ Payment Entry
- Is this a regular business expense? â†’ Expense Entry
- Making GL adjustments? â†’ Journal Entry
```

### 4. Unified Transaction List (Enhanced)

**Page: `/dea/transactions/`** (New consolidated view)

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  ALL TRANSACTIONS - Integrated View                             â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ Filters & Search                                                 â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ [Search: ________]  [Type: â–¼]   [Status: â–¼]   [Date: â–¼]        â”‚
â”‚                     All Types    All            All Time        â”‚
â”‚                     â€¢ Invoice                   â€¢ Last 30 Days  â”‚
â”‚                     â€¢ Expense                   â€¢ Last Quarter  â”‚
â”‚                     â€¢ Payment                   â€¢ Date Range    â”‚
â”‚                     â€¢ Journal Entry                             â”‚
â”‚                                                                  â”‚
â”‚ [Account: â–¼]  [Posted By: â–¼]  [Amount Range: â–¼]               â”‚
â”‚ All Accounts  All Users       All Amounts                      â”‚
â”‚                                                                  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  TRANSACTION TABLE (with Summary)                               â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ Date    â”‚ Type        â”‚ Ref #    â”‚ Party/Account â”‚ Amount  â”‚Status â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ 25-Mar  â”‚ Invoice     â”‚ INV-001  â”‚ ABC Corp      â”‚ 50,000  â”‚Posted â”‚
â”‚ 24-Mar  â”‚ Expense     â”‚ EXP-056  â”‚ Rent Expense  â”‚ 15,000  â”‚Posted â”‚
â”‚ 23-Mar  â”‚ Payment     â”‚ PAY-032  â”‚ Supplier X    â”‚ 30,000  â”‚Posted â”‚
â”‚ 22-Mar  â”‚ Journal     â”‚ JE-015   â”‚ Bank Reconcil â”‚ 5,000   â”‚Draft  â”‚
â”‚ ...     â”‚ ...         â”‚ ...      â”‚ ...           â”‚ ...     â”‚ ...   â”‚
â”‚                                                   Total:   â”‚ 95,000â”‚
â”‚                                                                  â”‚
â”‚ [Back] [Previous] [Page 1 of 5] [Next] [Last] [Show 10/25/50]  â”‚
â”‚                                                                  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

Key Features:
- Click transaction â†’ View full details
- Color-coded by type
- Status badges
- Batch actions (Mark Posted, Reverse, Delete Draft)
```

### 5. Reporting Hub (New Page)

**Page: `/dea/reports/`** (Centralized)

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  FINANCIAL REPORTS - Central Hub                                â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ Period & Date Selector                                           â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ Period: [Current Period â–¼]   As of: [25-Mar-2026]  [Refresh]   â”‚
â”‚ [View by: Current Month] [Current Quarter] [Current Year] [MTD] â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ FINANCIAL STATEMENTS (Primary Reports)                          â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                                  â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â” â”‚
â”‚  â”‚  BALANCE SHEET  â”‚  â”‚  PROFIT & LOSS  â”‚  â”‚   CASH FLOW      â”‚ â”‚
â”‚  â”‚                 â”‚  â”‚                 â”‚  â”‚                  â”‚ â”‚
â”‚  â”‚ Position at     â”‚  â”‚ Performance for â”‚  â”‚ Liquidity for    â”‚ â”‚
â”‚  â”‚ specific date   â”‚  â”‚ date range      â”‚  â”‚ date range       â”‚ â”‚
â”‚  â”‚                 â”‚  â”‚                 â”‚  â”‚                  â”‚ â”‚
â”‚  â”‚ Shows:          â”‚  â”‚ Shows:          â”‚  â”‚ Shows:           â”‚ â”‚
â”‚  â”‚ â€¢ Assets        â”‚  â”‚ â€¢ Revenue       â”‚  â”‚ â€¢ Operations     â”‚ â”‚
â”‚  â”‚ â€¢ Liabilities   â”‚  â”‚ â€¢ Expenses      â”‚  â”‚ â€¢ Investing      â”‚ â”‚
â”‚  â”‚ â€¢ Equity        â”‚  â”‚ â€¢ Net Income    â”‚  â”‚ â€¢ Financing      â”‚ â”‚
â”‚  â”‚                 â”‚  â”‚                 â”‚  â”‚ â€¢ Net Change     â”‚ â”‚
â”‚  â”‚  [View Report]  â”‚  â”‚  [View Report]  â”‚  â”‚  [View Report]   â”‚ â”‚
â”‚  â”‚                 â”‚  â”‚                 â”‚  â”‚                  â”‚ â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜ â”‚
â”‚                                                                  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ TRANSACTION & ANALYSIS REPORTS                                  â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                                  â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â” â”‚
â”‚  â”‚   TRIAL BALANCE  â”‚  â”‚  LEDGER DETAIL   â”‚  â”‚  ACCOUNT STMT  â”‚ â”‚
â”‚  â”‚                  â”‚  â”‚                  â”‚  â”‚                â”‚ â”‚
â”‚  â”‚ Pre-closing      â”‚  â”‚ General ledger   â”‚  â”‚ Individual     â”‚ â”‚
â”‚  â”‚ balance check    â”‚  â”‚ account detail   â”‚  â”‚ customer/      â”‚ â”‚
â”‚  â”‚                  â”‚  â”‚                  â”‚  â”‚ vendor account â”‚ â”‚
â”‚  â”‚ [Generate]       â”‚  â”‚ [Generate]       â”‚  â”‚ [Generate]     â”‚ â”‚
â”‚  â”‚                  â”‚  â”‚                  â”‚  â”‚                â”‚ â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜ â”‚
â”‚                                                                  â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â” â”‚
â”‚  â”‚  AR AGING        â”‚  â”‚  AP AGING        â”‚  â”‚ FINANCIAL      â”‚ â”‚
â”‚  â”‚                  â”‚  â”‚                  â”‚  â”‚ RATIOS         â”‚ â”‚
â”‚  â”‚ Customer payment â”‚  â”‚ Supplier payment â”‚  â”‚                â”‚ â”‚
â”‚  â”‚ aging analysis   â”‚  â”‚ aging analysis   â”‚  â”‚ Liquidity,     â”‚ â”‚
â”‚  â”‚                  â”‚  â”‚                  â”‚  â”‚ Profitability, â”‚ â”‚
â”‚  â”‚ [Generate]       â”‚  â”‚ [Generate]       â”‚  â”‚ Solvency       â”‚ â”‚
â”‚  â”‚                  â”‚  â”‚                  â”‚  â”‚ [Generate]     â”‚ â”‚
â”‚  â”‚                  â”‚  â”‚                  â”‚  â”‚                â”‚ â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜ â”‚
â”‚                                                                  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ UTILITY REPORTS                                                  â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ [Day Book - Full Log]  [General Ledger Detail]  [More Options] â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### 6. Account Hub (Enhanced)

**Page: `/dea/accounts/`** (Redesigned)

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ ACCOUNTS - Customers & Vendors                                  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ Search & Quick Actions                                           â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ [Search by Name/Number: ___________]  [Type: â–¼]  [Status: â–¼]   â”‚
â”‚                                       All Types  All/Active      â”‚
â”‚                                                                  â”‚
â”‚ [+ New Customer] [+ New Supplier] [View Aging Report] [Export]  â”‚
â”‚                                                                  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ ACCOUNT SUMMARY (Card View / Table View)                         â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                                   â”‚
â”‚ ACCOUNT                        BALANCE    CREDIT LIMIT    STATUS  â”‚
â”‚ John Smith (Customer)          50,000 DR  100,000         ðŸŸ¢ Active
â”‚ ABC Corp (Customer)            (5,000) CR 250,000         ðŸŸ¢ Active
â”‚ Supplier X (Vendor)            (75,000) CR Unlimited      ðŸŸ¡ Watch
â”‚ Retailer Ltd (Customer)        120,000 DR 100,000         ðŸ”´ Over
â”‚ ...                                                               â”‚
â”‚                                                                   â”‚
â”‚ Outstanding AR: 170,000  â”‚  Outstanding AP: 80,000  â”‚  Net: 90k â”‚
â”‚                                                                   â”‚
â”‚ [Previous] [Page 1 of 3] [Next] [View by Type] [View Aging]     â”‚
â”‚                                                                   â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

Click Account â†’ Opens:
â”œâ”€ Account Overview
â”‚  â”œâ”€ Contact Details
â”‚  â”œâ”€ Current Balance
â”‚  â”œâ”€ Credit Limit & Usage
â”‚  â”œâ”€ Status
â”‚  â””â”€ Recent Transactions (5)
â”‚
â”œâ”€ Quick Actions
â”‚  â”œâ”€ [Create Invoice] (for customer)
â”‚  â”œâ”€ [Create Bill] (for vendor)
â”‚  â”œâ”€ [Record Payment]
â”‚  â””â”€ [View Aging Report]
â”‚
â”œâ”€ Complete Transaction History
â”‚  â””â”€ (Searchable, filterable, sortable)
â”‚
â””â”€ Account Details & Settings
   â”œâ”€ Edit Contact
   â”œâ”€ Update Credit Limit
   â”œâ”€ Change Status
   â””â”€ Account Activity Log
```

---

## IMPLEMENTATION ROADMAP *(Updated Mar 27)*

### Phase 1: Foundation & Dashboard âœ… COMPLETE (as of Mar 27)
**Deliverables Done**:
- âœ… Main dashboard with full metrics, alerts, top debtors/creditors, recent activity
- âœ… Enhanced dashboard skeleton (quick actions, 5 guided workflows, COA preview slot)
- âœ… AR/AP Aging report pages
- âœ… Financial Ratios page
- âœ… AJAX metrics refresh endpoint
- âœ… Payment Voucher (all variants) + Opening Balance wizard

**Remaining gap (1-2 days)**: Wire 5 placeholder functions in `dashboard_enhanced.py` with real queries

### Phase 2: Navigation & Discovery (Weeks 1-2 from now)
**Goal**: Wire enhanced dashboard + build Chart of Accounts and Voucher Creation UIs

1. **Wire Enhanced Dashboard data** â¬… START HERE
   - [x] Quick Actions section â€” done (links need real views)
   - [x] Guided workflow cards â€” done (content done)
   - [ ] `calculate_ar_balance()` â†’ real query (mirror AR aging logic)
   - [ ] `calculate_ap_balance()` â†’ real query (mirror AP aging logic)
   - [ ] `calculate_cash_balance()` â†’ real query
   - [ ] `calculate_period_pl()` â†’ real query (mirror dashboard.py `_get_period_summary`)
   - [ ] `get_coa_preview()` â†’ real query (top 10 accounts by class)

2. **Chart of Accounts Navigator**
   - [ ] `/dea/chart-of-accounts/` â€” hierarchical tree view
   - [ ] Account balance display
   - [ ] Status indicators
   - [ ] Search & filter

3. **Voucher Creation Hub**
   - [ ] `/dea/vouchers/create/` â€” decision tree UI
   - [ ] Workflow guidance cards
   - [ ] Quick links to existing forms
   - [ ] Help documentation

4. **Consolidated Transaction List**
   - [ ] Multi-type transaction table
   - [ ] Advanced filtering
   - [ ] Batch operations

### Phase 3: Accounts & Reporting (Weeks 3-4)
**Goal**: Enhance account management and create Reports Hub landing page

1. **Enhanced Accounts Page**
   - [ ] Account card view with balances
   - [ ] Status indicators & credit limit usage
   - [ ] Quick action buttons
   - [ ] Aging analysis integration

2. **Reports Hub** at `/dea/reports/`
   - [ ] Centralized report navigation (AR/AP aging, ratios already exist â€” need hub page)
   - [ ] Report generation interface with period/date selectors

3. **Add Missing Navigation Links**
   - [ ] Dashboard â†’ COA
   - [ ] Dashboard â†’ Create Voucher Hub
   - [ ] Dashboard â†’ Reports Hub

### Phase 4: UX Polish & Documentation (Weeks 5-6)
**Goal**: Refine UI, add help, test workflows

1. **Improve Form UX**
   - [ ] Better form layouts
   - [ ] Field descriptions & inline validation
   - [ ] Smart defaults

2. **Add Help System**
   - [ ] Contextual tooltips
   - [ ] Workflow guides
   - [ ] FAQ section

3. **Testing & Refinement**
   - [ ] User flow testing
   - [ ] Performance optimization
   - [ ] Mobile responsiveness

1. **Enhanced Accounts Page**
   - [ ] Account card view with balances
   - [ ] Status indicators
   - [ ] Quick action buttons
   - [ ] Aging analysis integration

2. **Reports Hub**
   - [ ] Centralized report navigation
   - [ ] Report generation interface
   - [ ] Period/date selectors
   - [ ] Report caching

3. **Add Missing Navigation Links**
   - [ ] Dashboard â†’ COA Navigator
   - [ ] Dashboard â†’ Voucher Creation Hub
   - [ ] Dashboard â†’ Reports Hub

---

## KEY FEATURES TO IMPLEMENT *(Updated â€” Phase 1 items already done)*

### 1. Dashboard Enhancements âœ… PHASE 1 DONE
- âœ… Quick action buttons (Invoice, Expense, Payment, Journal Entry) â€” wired in enhanced dashboard
- âœ… Key financial metrics â€” in `dashboard.py`
- âœ… Guided workflow section â€” in `dashboard_enhanced.py`
- âœ… Alert system (5 types) â€” in `dashboard.py`
- âœ… Customer/vendor top 5 â€” in `dashboard.py`
- â¬œ Wire real data into `dashboard_enhanced.py` placeholder functions (5 items, ~2 days)

### 2. Chart of Accounts â¬œ Phase 2
- [ ] Hierarchical tree visualization
- [ ] Account balance display
- [ ] Status indicators (Active/Inactive/Suspended)
- [ ] Class grouping (Asset/Liability/Equity/Revenue/Expense)
- [ ] Search and filtering
- [ ] Quick drill-down to ledger/statement

### 3. Voucher Creation Hub â¬œ Phase 2
- [ ] Decision tree UI for voucher type selection
- [ ] Guided workflows per transaction type
- [ ] Help documentation per voucher type

### 4. Reports Hub â¬œ Phase 3
- [ ] Centralized report navigation page (individual reports already exist)
- [ ] Report generation with parameters
- [ ] Period selectors across reports

### 5. Unified Transaction List â¬œ Phase 2
- [ ] All transaction types in one view
- [ ] Advanced filtering
- [ ] Batch operations (Mark Posted, Reverse, Delete)
- [ ] Color-coded by type
- [ ] Status visibility

### 6. Account Management
- [ ] Card view with balances visible
- [ ] Status indicators & credit limit usage
- [ ] Quick transaction creation
- [ ] Aging analysis integration
- [ ] Account activity timeline

### 7. Help & Guidance
- [ ] Contextual tooltips
- [ ] Workflow guides
- [ ] Accounting concepts primer
- [ ] Video tutorials
- [ ] FAQ section
- [ ] Link to documentation

---

## TECHNICAL IMPLEMENTATION NOTES

### Database Queries to Optimize
1. Account balance calculations (cache in LedgerBalance)
2. Receivables/Payables totals
3. Period P&L summary
4. Account aging calculations
5. Transaction counts by type

### Views to Create/Modify
```
New Views:
- ChartOfAccountsView (GET)
- VoucherCreationHubView (GET)
- ReportsHubView (GET)
- TransactionListView (GET)
- EnhancedAccountsView (GET)

Modified Views:
- DashboardView (add metrics, quick actions, COA preview)
- AccountDetailView (add quick actions, context)
- LedgerDetailView (improve presentation)
```

### Templates to Create
```
New Templates:
- dea/chart_of_accounts.html
- dea/voucher_creation_hub.html
- dea/reports_hub.html
- dea/transaction_list.html
- dea/accounts_enhanced.html
- dea/components/quick_actions.html
- dea/components/metrics_cards.html
- dea/components/guided_workflows.html

Modified Templates:
- dea/dashboard.html
- dea/account_detail.html
```

### Frontend Components
- Account card component
- Metrics card component
- Status badge component
- Alert card component
- Tree view component for COA
- Transaction table component
- Quick action button group
- Workflow card component

### API Endpoints (Optional AJAX)
- `/api/dea/coa/` - COA with balances
- `/api/dea/accounts/balances/` - Account balances
- `/api/dea/metrics/` - Dashboard metrics
- `/api/dea/transactions/` - Transaction list

---

## EXPECTED OUTCOMES

### For Users
1. âœ… Clear entry points to all features
2. âœ… Self-explanatory workflows
3. âœ… Easy discovery of acceptable transactions
4. âœ… Better understanding of account structure
5. âœ… Centralized access to critical reports
6. âœ… Reduced clicks to complete tasks
7. âœ… Educational interface for accounting learners

### For System
1. âœ… Reduced support questions
2. âœ… Higher feature adoption
3. âœ… Better data quality (less confusion)
4. âœ… Improved user retention
5. âœ… Foundation for future enhancements

---

## SUCCESS METRICS

- Page load time < 1.5 seconds
- User task completion rate > 85%
- Support questions reduced by 50%
- Feature adoption increased by 60%
- User satisfaction score > 4.0/5
- Mobile responsiveness score > 90

---

## NEXT STEPS

1. **Validate Design** - Get stakeholder feedback on proposed layouts
2. **Create Wireframes** - Low-fidelity mockups of new pages
3. **Plan Development** - Break into sprints/tasks
4. **Set Up Feature Branch** - Create `dea-ui-enhancement` branch
5. **Begin Phase 1 Implementation** - Start with dashboard

---

## APPENDIX: VOUCHER TYPE REFERENCE

| Voucher Type | Purpose | Key GL Impact | When to Use |
|---|---|---|---|
| Sales Invoice | Revenue transactions | DR: AR, CR: Revenue | Selling products/services |
| Purchase Invoice | Cost transactions | DR: Expense/Inventory, CR: AP | Buying goods/services |
| Payment | Cash movements | DR: Cash, CR: AR/AP | Receiving/making payments |
| Expense | Operating expenses | DR: Expense, CR: Cash/AP | Recording business expenses |
| Journal Entry | GL adjustments | User-defined | Corrections, accruals, adjustments |
| Opening Balance | Initial GL setup | DR/CR: Various | Starting new period |
| Loan Disbursement | Loan given out | DR: Loan (Asset), CR: Cash | Giving loan to someone |
| Loan Repayment | Loan repaid | DR: Cash, CR: Loan | Receiving loan payment |
| Taken Loan | Loan borrowed | DR: Cash, CR: Loan (Liability) | Taking loan from lender |
| Given Loan | Loan tracking | DR: Loan (Asset), CR: Receivable | Tracking given loans |

---

**Document Version**: 1.0  
**Last Updated**: March 25, 2026  
**Status**: Ready for Implementation Planning Phase

