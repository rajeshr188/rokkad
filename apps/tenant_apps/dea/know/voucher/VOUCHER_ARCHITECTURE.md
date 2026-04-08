# Voucher Architecture - Confirmed Design

**Status:** ✅ Aligned Architecture  
**Date:** February 20, 2026

---

## Core Principle: Separation of Concerns

```
┌─────────────────────────────────────────────────────────┐
│         BUSINESS LAYER (Domain Documents)               │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  Sales Invoice, Purchase Order, Loan Slip, Payment,    │
│  Bank Transfer, Stock Movement, Expense, Loan Repay    │
│                                                           │
│  • Contains business logic (quantities, rates, taxes)    │
│  • Stores business context (customer, vendor, items)    │
│  • Validates business rules                             │
│  • Has its own lifecycle (draft, approved, cancelled)   │
│                                                           │
└─────────────────────────────────────────────────────────┘
                            ↓
                    (Triggers Creation)
                            ↓
┌─────────────────────────────────────────────────────────┐
│       ACCOUNTING LAYER (Voucher + Journal Entries)      │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  VOUCHER (Accounting Representation of Business Doc)   │
│  ├─ Header: date, type, reference to business doc      │
│  ├─ Line Items: debit/credit transactions              │
│  ├─ Totals: DR = CR validation                         │
│  └─ Status: DRAFT → POSTED → REVERSED                  │
│                                                           │
│  When POSTED:                                           │
│  └─ Creates JOURNAL ENTRY #1 (Original posting)        │
│     ├─ LedgerTransactions (GL postings)                │
│     └─ AccountTransactions (Subledger postings)        │
│                                                           │
│  When REVERSED:                                         │
│  └─ Creates JOURNAL ENTRY #2 (Reversal posting)        │
│     ├─ Opposite of original (DR becomes CR)            │
│     └─ Links back to original via is_reversal_of       │
│                                                           │
└─────────────────────────────────────────────────────────┘
                            ↓
                    (Creates Postings)
                            ↓
┌─────────────────────────────────────────────────────────┐
│              GL & SUBLEDGER (Updated Balances)          │
├─────────────────────────────────────────────────────────┤
│  LedgerBalance, AccountBalance                          │
│  (Automatically updated by transactions)                │
└─────────────────────────────────────────────────────────┘
```

---

## Your Architecture is CORRECT ✅

### **Business Layer** (Sales Invoice, Purchase Order, Loan, etc.)
**Responsibilities:**
- ✅ Contains business details (quantities, rates, taxes, parties)
- ✅ Validates business rules (credit limits, stock levels)
- ✅ Has own lifecycle (draft, approved, cancelled)
- ✅ May have line items (products on invoice)
- ✅ Stores header info (supplier, customer, date)

**What it does NOT do:**
- ❌ Does NOT create accounting postings directly
- ❌ Does NOT know about ledgers or accounts
- ❌ Does NOT manage journal entries

### **Accounting Layer** (Voucher)
**Responsibilities:**
- ✅ Represents the ACCOUNTING VIEW of the business document
- ✅ Maps business event to GL accounts (dr/cr logic)
- ✅ Has strict accounting lifecycle: DRAFT → POSTED → REVERSED
- ✅ Balancing logic (total debits = total credits)
- ✅ References back to business document

**Structure:**
```
Voucher
├─ Header
│  ├─ voucher_number (auto-generated)
│  ├─ voucher_type (Invoice, Payment, LoanGiven, etc.)
│  ├─ voucher_date
│  ├─ description/memo
│  ├─ reference_doc (FK to Sales Invoice, Purchase Order, etc.)
│  ├─ status (DRAFT, POSTED, REVERSED)
│  └─ created_by, created_at, posted_by, posted_at
│
├─ Line Items (Debit/Credit transactions)
│  ├─ Ledger lines (GL account postings)
│  │  └─ LedgerTransaction (ledger_dr, ledger_cr, amount)
│  │
│  └─ Account lines (Subledger postings)
│     └─ AccountTransaction (account, dr/cr, amount)
│
└─ Totals
   ├─ total_debit (sum of all debits)
   ├─ total_credit (sum of all credits)
   └─ is_balanced (total_debit == total_credit)
```

---

## Voucher Lifecycle & Journal Entry Generation

### **State 1: DRAFT**
```
Voucher Status: DRAFT
├─ Can be edited
├─ No journal entries yet
├─ No GL impact
└─ Ready for posting
```

### **State 2: POSTED**
```
Voucher Status: POSTED (triggered by user clicking "Post")
├─ Cannot be edited
├─ Posting Engine runs:
│  ├─ Validates balanced (DR = CR)
│  ├─ Validates period is OPEN
│  ├─ Validates all amounts are positive
│  └─ Creates JOURNAL ENTRY #1
│     ├─ posted_by = current user
│     ├─ posted_at = now
│     ├─ period = auto-assigned or specified
│     ├─ LedgerTransactions (from voucher lines)
│     │  └─ DR Ledger → CR Ledger mapping
│     ├─ AccountTransactions (from voucher lines)
│     │  └─ Account DR/CR as specified
│     └─ Snapshot: is_reversal_of = NULL
│
├─ GL Balances UPDATED
│  ├─ Ledger balances change
│  └─ Account balances change
│
└─ marked: is_posted = TRUE (or derived from voucher.status)
```

### **State 3: REVERSED** (Optional)
```
Voucher Status: REVERSED (triggered by user clicking "Reverse")
├─ Original voucher CANNOT be edited
├─ New voucher created (alternative: flag same voucher)
├─ Posting Engine runs:
│  ├─ Creates JOURNAL ENTRY #2 (Reversal entry)
│  ├─ Reversal entry:
│  │  ├─ posted_by = current user who reversed
│  │  ├─ posted_at = now
│  │  ├─ period = same as original (can be different period? policy choice)
│  │  ├─ LedgerTransactions (OPPOSITE of original)
│  │  │  └─ DR Ledger → CR Ledger SWAPPED
│  │  ├─ AccountTransactions (OPPOSITE of original)
│  │  │  └─ All DR/CR reversed
│  │  └─ Snapshot: is_reversal_of = [Original JournalEntry ID]
│  │
│  └─ Links: JournalEntry#2.is_reversal_of = JournalEntry#1.id
│
├─ GL Balances REVERTED
│  └─ Back to state before original posting
│
└─ marked: is_posted = FALSE (voucher back to draft-like state)
```

---

## Example: Sales Invoice Flow

### **Business Layer: Sales Invoice Created**
```
SalesInvoice
├─ invoice_number: INV-2024-001
├─ customer: XYZ Corp
├─ amount: 100,000
├─ line items: [Product A qty 5 @ 10k, Product B qty 2 @ 25k]
├─ date: 2024-02-20
├─ status: APPROVED
└─ payment_terms: Net 30 days
```

### **Accounting Layer: Voucher Created (Manually or Auto)**
```
Voucher
├─ voucher_number: V-2024-001 (auto-generated)
├─ voucher_type: INVOICE
├─ voucher_date: 2024-02-20
├─ description: "Sales to XYZ Corp - INV-2024-001"
├─ reference: SalesInvoice ID
├─ status: DRAFT
│
├─ Line Items:
│  ├─ LedgerTransaction
│  │  ├─ ledger_dr: Accounts Receivable (1.01)
│  │  ├─ ledger_cr: Sales Revenue (4.01)
│  │  └─ amount: 100,000
│  │
│  └─ AccountTransaction
│     ├─ account: XYZ Corp (Customer Account)
│     ├─ dr/cr: DEBIT
│     └─ amount: 100,000
│
└─ Totals:
   ├─ total_debit: 100,000
   ├─ total_credit: 100,000
   └─ is_balanced: TRUE
```

### **User Posts Voucher**
```
POST /dea/vouchers/1/post/

Posting Engine:
├─ Validates: is_balanced ✓
├─ Validates: period is OPEN ✓
├─ Creates JournalEntry #1:
│  ├─ voucher: this voucher
│  ├─ posted_by: current_user
│  ├─ posted_at: 2024-02-20 14:30:00
│  ├─ period: Feb 2024
│  ├─ LedgerTransactions: [as above]
│  ├─ AccountTransactions: [as above]
│  └─ is_reversal_of: NULL
│
├─ Updates Balances:
│  ├─ AR Ledger: +100,000
│  ├─ Revenue Ledger: +100,000
│  └─ XYZ Corp Account: +100,000 (DR side)
│
└─ Voucher.status: DRAFT → POSTED
```

### **GL Now Shows:**
```
Accounts Receivable Ledger
├─ Opening: 0
├─ V-2024-001 DR: 100,000
└─ Closing: 100,000

Sales Revenue Ledger
├─ Opening: 0
├─ V-2024-001 CR: 100,000
└─ Closing: 100,000

Customer XYZ Account
├─ Opening: 0
├─ Invoice INV-2024-001: 100,000 (due)
└─ Closing: 100,000
```

### **User Later Reverses Voucher (e.g., return or cancellation)**
```
POST /dea/vouchers/1/reverse/  (or creates new Reversal Voucher)

Posting Engine:
├─ Creates NEW JournalEntry #2 (Reversal):
│  ├─ voucher: original voucher (or new Reversal Voucher)
│  ├─ posted_by: current_user
│  ├─ posted_at: 2024-02-21 09:00:00
│  ├─ period: Feb 2024 (or Mar 2024, policy choice)
│  ├─ LedgerTransactions: OPPOSITE
│  │  ├─ ledger_dr: Sales Revenue (was CR)
│  │  ├─ ledger_cr: Accounts Receivable (was DR)
│  │  └─ amount: 100,000
│  │
│  ├─ AccountTransactions: OPPOSITE
│  │  ├─ account: XYZ Corp
│  │  ├─ dr/cr: CREDIT (was DEBIT)
│  │  └─ amount: 100,000
│  │
│  └─ is_reversal_of: JournalEntry #1 ID
│
├─ Updates Balances (reverts):
│  ├─ AR Ledger: 100,000 - 100,000 = 0
│  ├─ Revenue Ledger: 100,000 - 100,000 = 0
│  └─ XYZ Corp Account: 100,000 - 100,000 = 0
│
└─ Voucher.status: POSTED → REVERSED
```

### **GL Now Shows:**
```
Accounts Receivable Ledger
├─ Opening: 0
├─ V-2024-001 DR: 100,000
├─ V-2024-001-REV CR: 100,000
└─ Closing: 0

Sales Revenue Ledger
├─ Opening: 0
├─ V-2024-001 CR: 100,000
├─ V-2024-001-REV DR: 100,000
└─ Closing: 0

Customer XYZ Account
├─ Opening: 0
├─ Invoice INV-2024-001: 100,000 (due)
├─ Reversal: -100,000
└─ Closing: 0
```

---

## Valid Scenarios - Does Your Model Fit?

### ✅ **Scenario 1: One Business Doc = One Voucher**
```
Sales Invoice → One Voucher with multiple line items
Payment Received → One Voucher
Loan Given → One Voucher
```

### ✅ **Scenario 2: Multiple Business Docs = One Voucher** (if needed)
```
Batch Payment → One Voucher with multiple payee lines
Allocation Entry → One Voucher with multiple customer allocations
```

### ✅ **Scenario 3: Business Doc Can Create Multiple Vouchers** (if needed)
```
Complex Sales with tax, discount, freight → Multiple vouchers?
Or all in one Voucher with multiple line items?
```

### ❓ **Question for You:**
- Usually: 1 business doc = 1 voucher (recommended for simplicity)
- But: 1 voucher can have multiple line items (for complex transactions)

---

## Journal Entry Generation Summary

### **Rule #1: One Voucher = At Most 2 Journal Entries**
```
JournalEntry #1: When posted (original transaction)
JournalEntry #2: When reversed (reversal transaction)
```

### **Rule #2: JournalEntry #2 is Complete Reversal of #1**
```
#1 → DR 100 / CR 100
#2 → CR 100 / DR 100 (complete opposite)

Result: Net effect = 0
```

### **Rule #3: Audit Trail Preserved**
```
JournalEntry #1
├─ id: 1
├─ amount: 100
└─ is_reversal_of: NULL (original)

JournalEntry #2
├─ id: 2
├─ amount: 100
└─ is_reversal_of: 1 (links to original)
```

---

## Implementation Implications

### **Voucher Table Should Have:**
```python
class Voucher(models.Model):
    # Header
    voucher_number = CharField()  # Auto-generated
    voucher_type = ForeignKey(VoucherType)  # Invoice, Payment, etc.
    voucher_date = DateField()
    description = TextField()
    
    # Reference to business doc
    content_type = ForeignKey(ContentType)  # Generic FK
    object_id = PositiveIntegerField()
    business_doc = GenericForeignKey()  # Points to SalesInvoice, Loan, etc.
    
    # Accounting state
    status = CharField(choices=DRAFT/POSTED/REVERSED)
    
    # Audit
    created_by = ForeignKey(User)
    created_at = DateTimeField()
    posted_by = ForeignKey(User, null=True)
    posted_at = DateTimeField(null=True)
```

### **Line Items (In Voucher or Separate Table?)**
```
Option A: Store in Voucher.line_items (JSON field)
├─ Pro: Immutable snapshot
├─ Con: Not queryable

Option B: Separate VoucherLineItem table
├─ Pro: Queryable, flexible
├─ Con: More tables

Current code uses: Option B via Transactions
```

### **Journal Entry Creation Trigger:**
```
When Voucher.status changes to POSTED:
1. Validate voucher.is_balanced()
2. Create JournalEntry with:
   - voucher FK
   - posted_by = request.user
   - posted_at = now()
   - period = auto-detect or from voucher
3. Create LedgerTransactions from voucher lines
4. Create AccountTransactions from voucher lines
```

---

## Summary: Your Architecture is SOUND ✅

| Aspect | Your Model | Status |
|--------|-----------|--------|
| Business docs separate from accounting | ✅ Correct | GOOD |
| Each voucher type represents business doc | ✅ Correct | GOOD |
| Voucher = accounting view of business doc | ✅ Correct | GOOD |
| One voucher can have multiple line items | ✅ Correct | GOOD |
| Voucher lifecycle: DRAFT → POSTED → REVERSED | ✅ Correct | GOOD |
| Posted voucher creates JE #1 | ✅ Correct | GOOD |
| Reversed voucher creates JE #2 (opposite) | ✅ Correct | GOOD |
| JE #2 links to JE #1 via is_reversal_of | ✅ Correct | GOOD |
| Line items validate balanced (DR = CR) | ✅ Correct | GOOD |

---

## Ready for CRUD Implementation? ✅

With this architecture crystal clear, I can now build:

### **Voucher CRUD Operations:**
1. **List** - Filter by type, date, status
2. **Create** - New voucher for specific type
3. **Edit** - Modify draft vouchers only
4. **Post** - Trigger JE creation
5. **Reverse** - Create reversal JE
6. **View** - Show voucher + linked JEs + audit trail

### **Voucher Line Item CRUD:**
1. Add line (DR/CR transaction)
2. Edit line (before posting)
3. Delete line (before posting)
4. View all lines with running totals

### **Key Constraints:**
- ✅ Can only edit DRAFT vouchers
- ✅ Posting requires balanced entries
- ✅ Reversing creates new JE (doesn't modify original)
- ✅ Auto-generate voucher numbers per type/period
- ✅ Track who posted/reversed and when

---

## Questions Before I Code?

1. Should reversal create a NEW voucher or flag the same one?
2. Can you reverse a reversed voucher? (un-reverse?)
3. Which period should reversal JE go to? (same or different?)
4. Should vouchers auto-detect period from date, or require manual selection?
5. Any approval workflow before posting?

Let me know, and I'll build the Voucher CRUD views! 🚀
