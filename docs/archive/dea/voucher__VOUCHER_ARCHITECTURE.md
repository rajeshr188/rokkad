---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Voucher Architecture - Confirmed Design

**Status:** âœ… Aligned Architecture  
**Date:** February 20, 2026

---

## Core Principle: Separation of Concerns

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚         BUSINESS LAYER (Domain Documents)               â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                           â”‚
â”‚  Sales Invoice, Purchase Order, Loan Slip, Payment,    â”‚
â”‚  Bank Transfer, Stock Movement, Expense, Loan Repay    â”‚
â”‚                                                           â”‚
â”‚  â€¢ Contains business logic (quantities, rates, taxes)    â”‚
â”‚  â€¢ Stores business context (customer, vendor, items)    â”‚
â”‚  â€¢ Validates business rules                             â”‚
â”‚  â€¢ Has its own lifecycle (draft, approved, cancelled)   â”‚
â”‚                                                           â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                            â†“
                    (Triggers Creation)
                            â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚       ACCOUNTING LAYER (Voucher + Journal Entries)      â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                           â”‚
â”‚  VOUCHER (Accounting Representation of Business Doc)   â”‚
â”‚  â”œâ”€ Header: date, type, reference to business doc      â”‚
â”‚  â”œâ”€ Line Items: debit/credit transactions              â”‚
â”‚  â”œâ”€ Totals: DR = CR validation                         â”‚
â”‚  â””â”€ Status: DRAFT â†’ POSTED â†’ REVERSED                  â”‚
â”‚                                                           â”‚
â”‚  When POSTED:                                           â”‚
â”‚  â””â”€ Creates JOURNAL ENTRY #1 (Original posting)        â”‚
â”‚     â”œâ”€ LedgerTransactions (GL postings)                â”‚
â”‚     â””â”€ AccountTransactions (Subledger postings)        â”‚
â”‚                                                           â”‚
â”‚  When REVERSED:                                         â”‚
â”‚  â””â”€ Creates JOURNAL ENTRY #2 (Reversal posting)        â”‚
â”‚     â”œâ”€ Opposite of original (DR becomes CR)            â”‚
â”‚     â””â”€ Links back to original via is_reversal_of       â”‚
â”‚                                                           â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                            â†“
                    (Creates Postings)
                            â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚              GL & SUBLEDGER (Updated Balances)          â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚  LedgerBalance, AccountBalance                          â”‚
â”‚  (Automatically updated by transactions)                â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

---

## Your Architecture is CORRECT âœ…

### **Business Layer** (Sales Invoice, Purchase Order, Loan, etc.)
**Responsibilities:**
- âœ… Contains business details (quantities, rates, taxes, parties)
- âœ… Validates business rules (credit limits, stock levels)
- âœ… Has own lifecycle (draft, approved, cancelled)
- âœ… May have line items (products on invoice)
- âœ… Stores header info (supplier, customer, date)

**What it does NOT do:**
- âŒ Does NOT create accounting postings directly
- âŒ Does NOT know about ledgers or accounts
- âŒ Does NOT manage journal entries

### **Accounting Layer** (Voucher)
**Responsibilities:**
- âœ… Represents the ACCOUNTING VIEW of the business document
- âœ… Maps business event to GL accounts (dr/cr logic)
- âœ… Has strict accounting lifecycle: DRAFT â†’ POSTED â†’ REVERSED
- âœ… Balancing logic (total debits = total credits)
- âœ… References back to business document

**Structure:**
```
Voucher
â”œâ”€ Header
â”‚  â”œâ”€ voucher_number (auto-generated)
â”‚  â”œâ”€ voucher_type (Invoice, Payment, LoanGiven, etc.)
â”‚  â”œâ”€ voucher_date
â”‚  â”œâ”€ description/memo
â”‚  â”œâ”€ reference_doc (FK to Sales Invoice, Purchase Order, etc.)
â”‚  â”œâ”€ status (DRAFT, POSTED, REVERSED)
â”‚  â””â”€ created_by, created_at, posted_by, posted_at
â”‚
â”œâ”€ Line Items (Debit/Credit transactions)
â”‚  â”œâ”€ Ledger lines (GL account postings)
â”‚  â”‚  â””â”€ LedgerTransaction (ledger_dr, ledger_cr, amount)
â”‚  â”‚
â”‚  â””â”€ Account lines (Subledger postings)
â”‚     â””â”€ AccountTransaction (account, dr/cr, amount)
â”‚
â””â”€ Totals
   â”œâ”€ total_debit (sum of all debits)
   â”œâ”€ total_credit (sum of all credits)
   â””â”€ is_balanced (total_debit == total_credit)
```

---

## Voucher Lifecycle & Journal Entry Generation

### **State 1: DRAFT**
```
Voucher Status: DRAFT
â”œâ”€ Can be edited
â”œâ”€ No journal entries yet
â”œâ”€ No GL impact
â””â”€ Ready for posting
```

### **State 2: POSTED**
```
Voucher Status: POSTED (triggered by user clicking "Post")
â”œâ”€ Cannot be edited
â”œâ”€ Posting Engine runs:
â”‚  â”œâ”€ Validates balanced (DR = CR)
â”‚  â”œâ”€ Validates period is OPEN
â”‚  â”œâ”€ Validates all amounts are positive
â”‚  â””â”€ Creates JOURNAL ENTRY #1
â”‚     â”œâ”€ posted_by = current user
â”‚     â”œâ”€ posted_at = now
â”‚     â”œâ”€ period = auto-assigned or specified
â”‚     â”œâ”€ LedgerTransactions (from voucher lines)
â”‚     â”‚  â””â”€ DR Ledger â†’ CR Ledger mapping
â”‚     â”œâ”€ AccountTransactions (from voucher lines)
â”‚     â”‚  â””â”€ Account DR/CR as specified
â”‚     â””â”€ Snapshot: is_reversal_of = NULL
â”‚
â”œâ”€ GL Balances UPDATED
â”‚  â”œâ”€ Ledger balances change
â”‚  â””â”€ Account balances change
â”‚
â””â”€ marked: is_posted = TRUE (or derived from voucher.status)
```

### **State 3: REVERSED** (Optional)
```
Voucher Status: REVERSED (triggered by user clicking "Reverse")
â”œâ”€ Original voucher CANNOT be edited
â”œâ”€ New voucher created (alternative: flag same voucher)
â”œâ”€ Posting Engine runs:
â”‚  â”œâ”€ Creates JOURNAL ENTRY #2 (Reversal entry)
â”‚  â”œâ”€ Reversal entry:
â”‚  â”‚  â”œâ”€ posted_by = current user who reversed
â”‚  â”‚  â”œâ”€ posted_at = now
â”‚  â”‚  â”œâ”€ period = same as original (can be different period? policy choice)
â”‚  â”‚  â”œâ”€ LedgerTransactions (OPPOSITE of original)
â”‚  â”‚  â”‚  â””â”€ DR Ledger â†’ CR Ledger SWAPPED
â”‚  â”‚  â”œâ”€ AccountTransactions (OPPOSITE of original)
â”‚  â”‚  â”‚  â””â”€ All DR/CR reversed
â”‚  â”‚  â””â”€ Snapshot: is_reversal_of = [Original JournalEntry ID]
â”‚  â”‚
â”‚  â””â”€ Links: JournalEntry#2.is_reversal_of = JournalEntry#1.id
â”‚
â”œâ”€ GL Balances REVERTED
â”‚  â””â”€ Back to state before original posting
â”‚
â””â”€ marked: is_posted = FALSE (voucher back to draft-like state)
```

---

## Example: Sales Invoice Flow

### **Business Layer: Sales Invoice Created**
```
SalesInvoice
â”œâ”€ invoice_number: INV-2024-001
â”œâ”€ customer: XYZ Corp
â”œâ”€ amount: 100,000
â”œâ”€ line items: [Product A qty 5 @ 10k, Product B qty 2 @ 25k]
â”œâ”€ date: 2024-02-20
â”œâ”€ status: APPROVED
â””â”€ payment_terms: Net 30 days
```

### **Accounting Layer: Voucher Created (Manually or Auto)**
```
Voucher
â”œâ”€ voucher_number: V-2024-001 (auto-generated)
â”œâ”€ voucher_type: INVOICE
â”œâ”€ voucher_date: 2024-02-20
â”œâ”€ description: "Sales to XYZ Corp - INV-2024-001"
â”œâ”€ reference: SalesInvoice ID
â”œâ”€ status: DRAFT
â”‚
â”œâ”€ Line Items:
â”‚  â”œâ”€ LedgerTransaction
â”‚  â”‚  â”œâ”€ ledger_dr: Accounts Receivable (1.01)
â”‚  â”‚  â”œâ”€ ledger_cr: Sales Revenue (4.01)
â”‚  â”‚  â””â”€ amount: 100,000
â”‚  â”‚
â”‚  â””â”€ AccountTransaction
â”‚     â”œâ”€ account: XYZ Corp (Customer Account)
â”‚     â”œâ”€ dr/cr: DEBIT
â”‚     â””â”€ amount: 100,000
â”‚
â””â”€ Totals:
   â”œâ”€ total_debit: 100,000
   â”œâ”€ total_credit: 100,000
   â””â”€ is_balanced: TRUE
```

### **User Posts Voucher**
```
POST /dea/vouchers/1/post/

Posting Engine:
â”œâ”€ Validates: is_balanced âœ“
â”œâ”€ Validates: period is OPEN âœ“
â”œâ”€ Creates JournalEntry #1:
â”‚  â”œâ”€ voucher: this voucher
â”‚  â”œâ”€ posted_by: current_user
â”‚  â”œâ”€ posted_at: 2024-02-20 14:30:00
â”‚  â”œâ”€ period: Feb 2024
â”‚  â”œâ”€ LedgerTransactions: [as above]
â”‚  â”œâ”€ AccountTransactions: [as above]
â”‚  â””â”€ is_reversal_of: NULL
â”‚
â”œâ”€ Updates Balances:
â”‚  â”œâ”€ AR Ledger: +100,000
â”‚  â”œâ”€ Revenue Ledger: +100,000
â”‚  â””â”€ XYZ Corp Account: +100,000 (DR side)
â”‚
â””â”€ Voucher.status: DRAFT â†’ POSTED
```

### **GL Now Shows:**
```
Accounts Receivable Ledger
â”œâ”€ Opening: 0
â”œâ”€ V-2024-001 DR: 100,000
â””â”€ Closing: 100,000

Sales Revenue Ledger
â”œâ”€ Opening: 0
â”œâ”€ V-2024-001 CR: 100,000
â””â”€ Closing: 100,000

Customer XYZ Account
â”œâ”€ Opening: 0
â”œâ”€ Invoice INV-2024-001: 100,000 (due)
â””â”€ Closing: 100,000
```

### **User Later Reverses Voucher (e.g., return or cancellation)**
```
POST /dea/vouchers/1/reverse/  (or creates new Reversal Voucher)

Posting Engine:
â”œâ”€ Creates NEW JournalEntry #2 (Reversal):
â”‚  â”œâ”€ voucher: original voucher (or new Reversal Voucher)
â”‚  â”œâ”€ posted_by: current_user
â”‚  â”œâ”€ posted_at: 2024-02-21 09:00:00
â”‚  â”œâ”€ period: Feb 2024 (or Mar 2024, policy choice)
â”‚  â”œâ”€ LedgerTransactions: OPPOSITE
â”‚  â”‚  â”œâ”€ ledger_dr: Sales Revenue (was CR)
â”‚  â”‚  â”œâ”€ ledger_cr: Accounts Receivable (was DR)
â”‚  â”‚  â””â”€ amount: 100,000
â”‚  â”‚
â”‚  â”œâ”€ AccountTransactions: OPPOSITE
â”‚  â”‚  â”œâ”€ account: XYZ Corp
â”‚  â”‚  â”œâ”€ dr/cr: CREDIT (was DEBIT)
â”‚  â”‚  â””â”€ amount: 100,000
â”‚  â”‚
â”‚  â””â”€ is_reversal_of: JournalEntry #1 ID
â”‚
â”œâ”€ Updates Balances (reverts):
â”‚  â”œâ”€ AR Ledger: 100,000 - 100,000 = 0
â”‚  â”œâ”€ Revenue Ledger: 100,000 - 100,000 = 0
â”‚  â””â”€ XYZ Corp Account: 100,000 - 100,000 = 0
â”‚
â””â”€ Voucher.status: POSTED â†’ REVERSED
```

### **GL Now Shows:**
```
Accounts Receivable Ledger
â”œâ”€ Opening: 0
â”œâ”€ V-2024-001 DR: 100,000
â”œâ”€ V-2024-001-REV CR: 100,000
â””â”€ Closing: 0

Sales Revenue Ledger
â”œâ”€ Opening: 0
â”œâ”€ V-2024-001 CR: 100,000
â”œâ”€ V-2024-001-REV DR: 100,000
â””â”€ Closing: 0

Customer XYZ Account
â”œâ”€ Opening: 0
â”œâ”€ Invoice INV-2024-001: 100,000 (due)
â”œâ”€ Reversal: -100,000
â””â”€ Closing: 0
```

---

## Valid Scenarios - Does Your Model Fit?

### âœ… **Scenario 1: One Business Doc = One Voucher**
```
Sales Invoice â†’ One Voucher with multiple line items
Payment Received â†’ One Voucher
Loan Given â†’ One Voucher
```

### âœ… **Scenario 2: Multiple Business Docs = One Voucher** (if needed)
```
Batch Payment â†’ One Voucher with multiple payee lines
Allocation Entry â†’ One Voucher with multiple customer allocations
```

### âœ… **Scenario 3: Business Doc Can Create Multiple Vouchers** (if needed)
```
Complex Sales with tax, discount, freight â†’ Multiple vouchers?
Or all in one Voucher with multiple line items?
```

### â“ **Question for You:**
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
#1 â†’ DR 100 / CR 100
#2 â†’ CR 100 / DR 100 (complete opposite)

Result: Net effect = 0
```

### **Rule #3: Audit Trail Preserved**
```
JournalEntry #1
â”œâ”€ id: 1
â”œâ”€ amount: 100
â””â”€ is_reversal_of: NULL (original)

JournalEntry #2
â”œâ”€ id: 2
â”œâ”€ amount: 100
â””â”€ is_reversal_of: 1 (links to original)
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
â”œâ”€ Pro: Immutable snapshot
â”œâ”€ Con: Not queryable

Option B: Separate VoucherLineItem table
â”œâ”€ Pro: Queryable, flexible
â”œâ”€ Con: More tables

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

## Summary: Your Architecture is SOUND âœ…

| Aspect | Your Model | Status |
|--------|-----------|--------|
| Business docs separate from accounting | âœ… Correct | GOOD |
| Each voucher type represents business doc | âœ… Correct | GOOD |
| Voucher = accounting view of business doc | âœ… Correct | GOOD |
| One voucher can have multiple line items | âœ… Correct | GOOD |
| Voucher lifecycle: DRAFT â†’ POSTED â†’ REVERSED | âœ… Correct | GOOD |
| Posted voucher creates JE #1 | âœ… Correct | GOOD |
| Reversed voucher creates JE #2 (opposite) | âœ… Correct | GOOD |
| JE #2 links to JE #1 via is_reversal_of | âœ… Correct | GOOD |
| Line items validate balanced (DR = CR) | âœ… Correct | GOOD |

---

## Ready for CRUD Implementation? âœ…

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
- âœ… Can only edit DRAFT vouchers
- âœ… Posting requires balanced entries
- âœ… Reversing creates new JE (doesn't modify original)
- âœ… Auto-generate voucher numbers per type/period
- âœ… Track who posted/reversed and when

---

## Questions Before I Code?

1. Should reversal create a NEW voucher or flag the same one?
2. Can you reverse a reversed voucher? (un-reverse?)
3. Which period should reversal JE go to? (same or different?)
4. Should vouchers auto-detect period from date, or require manual selection?
5. Any approval workflow before posting?

Let me know, and I'll build the Voucher CRUD views! ðŸš€

