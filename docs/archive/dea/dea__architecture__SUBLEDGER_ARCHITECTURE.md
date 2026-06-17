---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# DEA Subledger Architecture Guide

## Overview

The DEA (Double Entry Accounting) app implements a **two-tier accounting system**:

1. **General Ledger (GL)** - Category-level tracking (Ledger model)
2. **Subledger** - Individual customer/vendor tracking (Account model)

This document explains how the subledger system works, addressing common questions like:
- "What is ABC Corp's current balance?"
- "Who owes us money?"
- "Which invoices are overdue?"

---

## Conceptual Model

### General Ledger vs Subledger

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚             GENERAL LEDGER (Category Level)             â”‚
â”‚                                                          â”‚
â”‚  Question: "How much total money do customers owe us?" â”‚
â”‚  Answer: Check Accounts Receivable ledger = â‚¹50,000   â”‚
â”‚                                                          â”‚
â”‚  Ledger Model:                                          â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                  â”‚
â”‚  â”‚ Accounts Receivable (Asset)      â”‚                  â”‚
â”‚  â”‚ Balance: â‚¹50,000                 â”‚                  â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                       â†•ï¸
            MUST RECONCILE (DR = CR)
                       â†•ï¸
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚              SUBLEDGER (Individual Level)               â”‚
â”‚                                                          â”‚
â”‚  Question: "Which customers owe us? How much each?"    â”‚
â”‚  Answer:                                                â”‚
â”‚  - ABC Corp: â‚¹30,000                                   â”‚
â”‚  - XYZ Ltd:  â‚¹20,000                                   â”‚
â”‚  â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€                                   â”‚
â”‚  Total:      â‚¹50,000 âœ… (matches GL)                   â”‚
â”‚                                                          â”‚
â”‚  Account Model (per customer/vendor):                  â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                  â”‚
â”‚  â”‚ Account: ABC Corp                â”‚                  â”‚
â”‚  â”‚ Type: Debtor (Customer)          â”‚                  â”‚
â”‚  â”‚ Balance: â‚¹30,000 (DR)            â”‚                  â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Database Schema

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                     TRANSACTION FLOW                    â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

When you post a Sales Invoice:

1. SalesInvoiceVoucher created (amount: â‚¹10,000 to ABC Corp)
        â†“
2. PostingEngine executes SalesInvoiceRule
        â†“
3. Creates JournalEntry with BOTH GL and Subledger lines:

   LedgerTransaction (GL):
   â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
   â”‚ ledgerno_dr = Accounts Receivable      â”‚  (Asset â†‘)
   â”‚ ledgerno    = Sales Revenue            â”‚  (Income â†‘)
   â”‚ amount      = â‚¹10,000                  â”‚
   â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

   AccountTransaction (Subledger):
   â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
   â”‚ Account     = ABC Corp (account record)â”‚
   â”‚ XactType    = Dr (Debit)               â”‚
   â”‚ amount      = â‚¹10,000                  â”‚
   â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
        â†“
4. AccountBalance view automatically updates:
   - ABC Corp balance = â‚¹30,000 + â‚¹10,000 = â‚¹40,000
```

---

## Balance Tracking Methods

The Account model provides **two methods** for querying balances:

### Method 1: Snapshot + Incremental (`current_balance()`)

**How it works:**
1. Find last `AccountStatement` snapshot (if any)
2. Calculate all transactions SINCE that snapshot
3. Return: `snapshot_balance + transaction_changes`

**Code:**
```python
customer = Customer.objects.get(name='ABC Corp')
account = customer.account

# Get balance (may be slow if many transactions)
balance = account.current_balance()  # Returns Balance object
inr_balance = balance.get('INR')     # Returns Money(30000, 'INR')
```

**When to use:**
- For audit trail (shows checkpoint + subsequent changes)
- When verifying against database view
- When debugging balance calculations

**Performance:** O(n) where n = transactions since last snapshot

---

### Method 2: Database View (`get_current_balance()`) â­ RECOMMENDED

**How it works:**
1. Query pre-aggregated PostgreSQL view `account_balances`
2. View automatically calculates: `last_statement + (debits - credits)`
3. Returns instant result

**Code:**
```python
customer = Customer.objects.get(name='ABC Corp')
account = customer.account

# Get balance (FAST - uses database view)
balance = account.get_current_balance()  # Returns Balance object
inr_balance = balance.get('INR')         # Returns Money(30000, 'INR')
```

**When to use:**
- For ALL real-time queries (default choice)
- AR Aging reports
- Customer statements
- Credit limit checks
- Dashboard metrics

**Performance:** O(1) - View is maintained by PostgreSQL

---

### Method 3: Direct View Query (Most Performant)

For bulk queries (e.g., "Top 100 debtors"), query `AccountBalance` directly:

```python
from apps.tenant_apps.dea.models.account import AccountBalance

# Top 10 debtors in INR
top_debtors = AccountBalance.objects.filter(
    AccountType_Ext__XactTypeCode_id='Dr',  # Debtor accounts
    currency='INR',
    current_balance__gt=0  # Positive balance = they owe us
).select_related('account', 'contact').order_by('-current_balance')[:10]

for balance_record in top_debtors:
    print(f"{balance_record.contact.name}: {balance_record.get_balance()}")

# Example output:
# ABC Corp: â‚¹30,000.00
# XYZ Ltd: â‚¹20,000.00
# ...
```

---

## Common Queries

### 1. Get Customer Balance

```python
def get_customer_balance(customer_id, currency='INR'):
    """Get single customer's balance"""
    from apps.tenant_apps.dea.models.account import AccountBalance
    
    try:
        balance = AccountBalance.objects.get(
            account__contact_id=customer_id,
            currency=currency
        )
        return balance.get_balance()  # Returns Money object
    except AccountBalance.DoesNotExist:
        return Money(0, currency)

# Usage
abc_balance = get_customer_balance(customer_id=123, currency='INR')
print(f"ABC Corp owes: {abc_balance}")
```

### 2. AR Aging Report (Who owes money? How old?)

```python
from datetime import datetime, timedelta
from django.db.models import Sum, F
from apps.tenant_apps.dea.models.account import AccountBalance
from apps.tenant_apps.dea.models.sales_invoice import SalesInvoiceVoucher

def ar_aging_report():
    """Generate AR aging report (0-30, 31-60, 61-90, 90+ days)"""
    today = datetime.now().date()
    
    # Get all debtor accounts with positive balances
    debtors = AccountBalance.objects.filter(
        AccountType_Ext__XactTypeCode_id='Dr',
        current_balance__gt=0
    ).select_related('account', 'contact')
    
    aging_data = []
    
    for debtor_balance in debtors:
        account = debtor_balance.account
        
        # Get all unpaid invoices for this customer
        unpaid_invoices = SalesInvoiceVoucher.objects.filter(
            customer=account.contact,
            payment_status__in=['UNPAID', 'PARTIAL']
        )
        
        aging = {
            'customer': account.contact.name,
            'total_balance': debtor_balance.get_balance(),
            '0_30_days': Money(0, debtor_balance.currency),
            '31_60_days': Money(0, debtor_balance.currency),
            '61_90_days': Money(0, debtor_balance.currency),
            '90_plus_days': Money(0, debtor_balance.currency),
        }
        
        for invoice in unpaid_invoices:
            days_old = (today - invoice.invoice_date).days
            outstanding = invoice.total_amount - invoice.amount_paid
            
            if days_old <= 30:
                aging['0_30_days'] += outstanding
            elif days_old <= 60:
                aging['31_60_days'] += outstanding
            elif days_old <= 90:
                aging['61_90_days'] += outstanding
            else:
                aging['90_plus_days'] += outstanding
        
        aging_data.append(aging)
    
    return aging_data

# Usage
aging = ar_aging_report()
for row in aging:
    print(f"{row['customer']}: Total {row['total_balance']}")
    print(f"  0-30: {row['0_30_days']}")
    print(f"  31-60: {row['31_60_days']}")
    print(f"  61-90: {row['61_90_days']}")
    print(f"  90+: {row['90_plus_days']}")
```

### 3. Reconcile Subledger to GL

```python
from django.db.models import Sum
from apps.tenant_apps.dea.models.ledger import Ledger
from apps.tenant_apps.dea.models.account import AccountBalance

def reconcile_ar():
    """Verify subledger AR balances equal GL Accounts Receivable"""
    
    # Get GL Accounts Receivable balance
    ar_ledger = Ledger.objects.get(code='1200')  # Assuming 1200 = AR
    gl_balance = ar_ledger.balance
    
    # Get sum of all customer balances
    subledger_total = AccountBalance.objects.filter(
        AccountType_Ext__XactTypeCode_id='Dr',
        currency='INR'
    ).aggregate(total=Sum('current_balance'))['total'] or Decimal('0')
    
    # Compare
    difference = abs(gl_balance.amount - subledger_total)
    
    if difference < Decimal('0.01'):  # Allow rounding tolerance
        return {
            'status': 'BALANCED',
            'gl_balance': gl_balance,
            'subledger_total': Money(subledger_total, 'INR'),
            'difference': Money(0, 'INR')
        }
    else:
        return {
            'status': 'IMBALANCED',
            'gl_balance': gl_balance,
            'subledger_total': Money(subledger_total, 'INR'),
            'difference': Money(difference, 'INR'),
            'error': 'Subledger does not match GL! Investigate.'
        }

# Usage
result = reconcile_ar()
if result['status'] == 'IMBALANCED':
    print(f"âš ï¸ ALERT: AR out of balance by {result['difference']}")
else:
    print(f"âœ… AR reconciled: GL = Subledger = {result['gl_balance']}")
```

### 4. Customer Statement (All Invoices + Payments)

```python
def customer_statement(customer_id, start_date=None, end_date=None):
    """Generate customer statement showing all transactions"""
    from apps.tenant_apps.dea.models.account import Account, AccountTransaction
    from apps.tenant_apps.dea.models.sales_invoice import SalesInvoiceVoucher
    
    account = Account.objects.get(contact_id=customer_id)
    
    # Get opening balance
    opening_balance = Money(0, 'INR')
    if start_date:
        opening_balance = account.get_current_balance().get('INR')
        # TODO: Calculate balance AS OF start_date
    
    # Get all transactions in period
    transactions = AccountTransaction.objects.filter(
        Account=account,
        created__gte=start_date,
        created__lte=end_date
    ).select_related('JournalEntry', 'JournalEntry__voucher').order_by('created')
    
    statement = {
        'customer': account.contact.name,
        'opening_balance': opening_balance,
        'transactions': [],
        'closing_balance': Money(0, 'INR')
    }
    
    running_balance = opening_balance
    
    for txn in transactions:
        # Get source document
        source_doc = None
        if txn.JournalEntry.voucher:
            source_doc = txn.JournalEntry.voucher.content_object
        
        # Determine debit/credit
        if txn.XactTypeCode.XactTypeCode == 'Dr':
            running_balance += txn.amount
            dr_amount = txn.amount
            cr_amount = Money(0, 'INR')
        else:
            running_balance -= txn.amount
            dr_amount = Money(0, 'INR')
            cr_amount = txn.amount
        
        statement['transactions'].append({
            'date': txn.created.date(),
            'document': f"{source_doc.__class__.__name__} {source_doc.get_display_number()}" if source_doc else "Journal Entry",
            'debit': dr_amount,
            'credit': cr_amount,
            'balance': running_balance
        })
    
    statement['closing_balance'] = running_balance
    
    return statement

# Usage
stmt = customer_statement(customer_id=123, start_date='2026-01-01', end_date='2026-02-28')
print(f"Customer: {stmt['customer']}")
print(f"Opening Balance: {stmt['opening_balance']}")
for txn in stmt['transactions']:
    print(f"{txn['date']} | {txn['document']} | DR {txn['debit']} | CR {txn['credit']} | Bal {txn['balance']}")
print(f"Closing Balance: {stmt['closing_balance']}")
```

---

## AccountStatement Snapshots

### Purpose

`AccountStatement` records are **checkpoint snapshots** of account balances at specific points in time.

**Benefits:**
1. **Performance**: `current_balance()` only scans transactions SINCE last snapshot
2. **Audit Trail**: Official balance records for compliance
3. **Historical Reporting**: "What was ABC Corp's balance on Dec 31, 2025?"

### When to Create Snapshots

```python
# 1. Manual audit (creates snapshot NOW)
account.audit()

# 2. Period close (bulk create for all accounts)
from apps.tenant_apps.dea.models.account import Account

def close_period_accounts():
    """Create balance snapshots for all accounts at period close"""
    for account in Account.objects.filter(status='ACTIVE'):
        account.audit()
    print("All account balances snapshotted")

# 3. Scheduled task (nightly/weekly via Celery)
from celery import shared_task

@shared_task
def nightly_account_audit():
    """Create balance snapshots for accounts with >1000 transactions"""
    from django.db.models import Count
    
    busy_accounts = Account.objects.annotate(
        txn_count=Count('debit_transactions') + Count('credit_transactions')
    ).filter(txn_count__gt=1000)
    
    for account in busy_accounts:
        account.audit()
```

---

## Database View Definition

The `account_balances` view is created in migration `0003_create_ledger_balance_view.py`:

```sql
CREATE OR REPLACE VIEW account_balances AS
WITH latest_statements AS (
    -- Get most recent AccountStatement per account+currency
    SELECT DISTINCT ON ("AccountNo_id", "ClosingBalance_currency")
        "AccountNo_id",
        created,
        "ClosingBalance",
        "ClosingBalance_currency"
    FROM dea_accountstatement
    ORDER BY "AccountNo_id", "ClosingBalance_currency", created DESC
),
credit_sums AS (
    -- Sum CR transactions SINCE last statement
    SELECT 
        at."Account_id",
        at.amount_currency,
        COALESCE(SUM(
            CASE
                WHEN (ls.created IS NULL OR at.created > ls.created) 
                AND at."XactTypeCode_id" = 'Cr'
                THEN at.amount
                ELSE 0
            END), 0) AS credit_sum
    FROM dea_accounttransaction at
    LEFT JOIN latest_statements ls 
        ON at."Account_id" = ls."AccountNo_id" 
        AND at.amount_currency = ls."ClosingBalance_currency"
    GROUP BY at."Account_id", at.amount_currency
),
debit_sums AS (
    -- Sum DR transactions SINCE last statement
    SELECT 
        at."Account_id",
        at.amount_currency,
        COALESCE(SUM(
            CASE
                WHEN (ls.created IS NULL OR at.created > ls.created) 
                AND at."XactTypeCode_id" = 'Dr'
                THEN at.amount
                ELSE 0
            END), 0) AS debit_sum
    FROM dea_accounttransaction at
    LEFT JOIN latest_statements ls 
        ON at."Account_id" = ls."AccountNo_id" 
        AND at.amount_currency = ls."ClosingBalance_currency"
    GROUP BY at."Account_id", at.amount_currency
)
SELECT 
    a.id as account_id,
    a.contact_id,
    a."AccountType_Ext_id",
    COALESCE(ls."ClosingBalance_currency", 'INR') as currency,
    ls.created as last_statement_date,
    COALESCE(ls."ClosingBalance", 0) as last_statement_balance,
    COALESCE(cs.credit_sum, 0) as credit_sum,
    COALESCE(ds.debit_sum, 0) as debit_sum,
    -- Calculate current_balance based on account type
    CASE 
        WHEN a."AccountType_Ext_id" IN (SELECT id FROM dea_accounttype_ext WHERE "XactTypeCode_id" = 'Dr')
        THEN COALESCE(ls."ClosingBalance", 0) + COALESCE(ds.debit_sum, 0) - COALESCE(cs.credit_sum, 0)
        ELSE COALESCE(ls."ClosingBalance", 0) + COALESCE(cs.credit_sum, 0) - COALESCE(ds.debit_sum, 0)
    END as current_balance
FROM dea_account a
LEFT JOIN latest_statements ls ON a.id = ls."AccountNo_id"
LEFT JOIN credit_sums cs ON a.id = cs."Account_id"
LEFT JOIN debit_sums ds ON a.id = ds."Account_id";
```

---

## Testing Balance Calculations

### Example Test Suite

```python
# apps/tenant_apps/dea/tests/test_subledger_balance.py

from decimal import Decimal
from django.test import TestCase
from moneyed import Money
from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.dea.models.account import Account, AccountBalance
from apps.tenant_apps.dea.models.sales_invoice import SalesInvoiceVoucher

class SubledgerBalanceTestCase(TestCase):
    def setUp(self):
        """Create test data"""
        self.customer = Customer.objects.create(
            name='Test Corp',
            email='test@example.com'
        )
        self.account = Account.objects.create(
            contact=self.customer,
            AccountType_Ext=...,  # Setup debtor account type
        )
    
    def test_initial_balance_is_zero(self):
        """New account should have zero balance"""
        balance = self.account.get_current_balance()
        self.assertEqual(balance.get('INR'), Money(0, 'INR'))
    
    def test_invoice_increases_balance(self):
        """Posting invoice should increase customer balance"""
        # Create and post invoice
        invoice = SalesInvoiceVoucher.objects.create(
            customer=self.customer,
            total_amount=Money(10000, 'INR'),
            # ... other fields
        )
        
        # Check balance increased
        balance = self.account.get_current_balance()
        self.assertEqual(balance.get('INR'), Money(10000, 'INR'))
    
    def test_payment_decreases_balance(self):
        """Posting payment should decrease customer balance"""
        # Create invoice
        invoice = SalesInvoiceVoucher.objects.create(
            customer=self.customer,
            total_amount=Money(10000, 'INR')
        )
        
        # Create payment (when PaymentVoucher is implemented)
        # payment = ReceiptVoucher.objects.create(...)
        
        # Check balance decreased
        # balance = self.account.get_current_balance()
        # self.assertEqual(balance.get('INR'), Money(0, 'INR'))
    
    def test_balance_reconciles_with_view(self):
        """current_balance() should match get_current_balance()"""
        # Create multiple transactions
        for i in range(5):
            SalesInvoiceVoucher.objects.create(
                customer=self.customer,
                total_amount=Money(1000 * (i+1), 'INR')
            )
        
        # Compare methods
        incremental_balance = self.account.current_balance().get('INR')
        view_balance = self.account.get_current_balance().get('INR')
        
        # Should match within rounding tolerance
        self.assertAlmostEqual(
            incremental_balance.amount,
            view_balance.amount,
            places=2
        )
    
    def test_audit_creates_snapshot(self):
        """audit() should create AccountStatement"""
        # Create transactions
        SalesInvoiceVoucher.objects.create(
            customer=self.customer,
            total_amount=Money(5000, 'INR')
        )
        
        # Create snapshot
        statements = self.account.audit()
        
        # Verify statement created
        self.assertEqual(len(statements), 1)
        self.assertEqual(
            statements[0].ClosingBalance,
            Money(5000, 'INR')
        )
```

---

## Summary

### Key Takeaways

1. **Two-tier system**: GL (Ledger) + Subledger (Account)
2. **Always use `get_current_balance()`** for real-time queries
3. **AccountBalance view** provides O(1) performance for bulk queries
4. **AccountStatement snapshots** improve incremental calculation performance
5. **Reconciliation required**: SUM(subledger) must equal GL control ledger

### Architecture Benefits

âœ… **Performance**: Database view provides instant balance lookups  
âœ… **Accuracy**: Two-sided journal entry design prevents imbalances  
âœ… **Auditability**: AccountStatement snapshots create audit trail  
âœ… **Scalability**: Supports multi-currency, millions of transactions  
âœ… **Flexibility**: Both incremental and view-based calculations available  

### Next Steps

- [ ] Implement Receipt/Payment vouchers (closes invoices)
- [ ] Create AR Aging Report view
- [ ] Build Customer Statement generator
- [ ] Add reconciliation dashboard
- [ ] Implement automated balance snapshot scheduling

---

**Document Version**: 1.0  
**Last Updated**: February 27, 2026  
**Author**: DEA Development Team

