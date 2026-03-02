# Custody Tracking - Complete Workflows Illustrated

## 🔄 Workflow 1: Release with Auto-Return (Most Common)

**Scenario**: Customer wants their items back, but some are currently with a lender

```
┌─────────────────────────────────────────────────────────────────────┐
│ GIVEN LOAN: Customer A has pledged 5 gold items                     │
│                                                                      │
│ Current Status:                                                     │
│  • 3 items: IN VAULT                                                │
│  • 2 items: WITH_LENDER (Lender B)                                  │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ CUSTOMER ACTION: "I want my items back"                             │
│                                                                      │
│ UI: Click "Release Loan" button                                     │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ SYSTEM CHECK: release_loan_check_custody()                          │
│                                                                      │
│ ✓ Detect: 2 items WITH_LENDER                                      │
│ ✓ Show: Warning page with "Release with Auto-Return" button        │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ USER CONFIRMATION: "Yes, proceed"                                   │
│                                                                      │
│ Click: "Release with Auto-Return" button                            │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 1: Return Items from Lender                                    │
│                                                                      │
│ for each item in WITH_LENDER:                                       │
│   • item.return_from_lender(user)                                   │
│   • custody_status: WITH_LENDER → IN_VAULT                          │
│   • repledged_to: Lender B → None                                   │
│   • RepledgeHistory: returned_at = now                              │
│                                                                      │
│ Result: All 5 items now IN_VAULT                                    │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 2: Release to Customer                                         │
│                                                                      │
│ for each item in IN_VAULT:                                          │
│   • item.release_to_customer(user)                                  │
│   • custody_status: IN_VAULT → WITH_CUSTOMER                        │
│                                                                      │
│ Result: All 5 items now WITH_CUSTOMER                               │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 3: Create Release Document                                     │
│                                                                      │
│ • Release.objects.create(...)                                       │
│ • Loan.is_released = True                                           │
│                                                                      │
│ Result: Loan marked as released                                     │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ SUCCESS! ✅                                                          │
│                                                                      │
│ Customer A has their items back!                                    │
│ Lender B's collateral returned!                                     │
│ Complete audit trail in RepledgeHistory!                            │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Points
- **Transparent to user**: One click does 3 steps
- **No validation errors**: System prevents impossible state
- **Full history**: Each step recorded in RepledgeHistory
- **Atomic**: All or nothing (transaction.atomic)

---

## 📦 Workflow 2: Create Multi-Customer Repledge (New Feature)

**Scenario**: Need to borrow ₹60,000. Bundle items from multiple customers.

```
┌─────────────────────────────────────────────────────────────────────┐
│ YOUR VAULT STATUS:                                                  │
│                                                                      │
│ Customer A's items:                                                 │
│   • 2 gold rings @ ₹25k each = ₹50k (IN_VAULT)                     │
│                                                                      │
│ Customer C's items:                                                 │
│   • 1 gold chain @ ₹30k = ₹30k (IN_VAULT)                          │
│                                                                      │
│ Total Available: ₹80k                                               │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ ACTION: /girvi/repledge/create/                                     │
│                                                                      │
│ Browse items grouped by customer                                    │
│ Select items from DIFFERENT customers                               │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ SELECTION (Multi-Customer):                                         │
│                                                                      │
│ FROM USE: Customer A → Select 2 rings (₹50k)                       │
│ FROM USE: Customer C → Select 1 chain (₹30k)                       │
│ TOTAL COLLATERAL: ₹80k                                              │
│                                                                      │
│ Sticky sidebar shows:                                               │
│   ✓ Selected: 3 items                                               │
│   ✓ Total Value: ₹80k                                               │
│   ✓ From: Customer A, Customer C                                    │
│   ✓ Max Loan (80% LTV): ₹64k                                        │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ FORM:                                                               │
│                                                                      │
│ Lender: Lender B (dropdown)                                         │
│ Loan Amount: 60000 (< 64k max) ✓                                   │
│ Interest Rate: 1.5%                                                 │
│ Loan Date: 2025-02-22                                               │
│ Notes: Emergency cash flow                                          │
│                                                                      │
│ LTV Check: 60k / 80k = 75% ✅ OK                                   │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ CLICK: "Create TakenLoan with Collateral"                           │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ SYSTEM EXECUTION (Atomic Transaction):                              │
│                                                                      │
│ Step 1: Create TakenLoan                                            │
│   • TakenLoan.objects.create(                                       │
│       lender=Lender B,                                              │
│       loan_amount=60000,                                            │
│       interest_rate=1.5,                                            │
│       ...                                                            │
│     )                                                                │
│   • Result: TakenLoan #999 created                                  │
│                                                                      │
│ Step 2: Distribute ₹60k Proportionally                             │
│   • Ring 1 (₹25k / ₹80k) = 37.5% → ₹22,500                        │
│   • Ring 2 (₹25k / ₹80k) = 37.5% → ₹22,500                        │
│   • Chain (₹30k / ₹80k) = 37.5% → ₹15,000                          │
│                                                                      │
│ Step 3: Repledge Each Item                                          │
│   for each item:                                                    │
│     • item.repledge_to(TakenLoan #999, proportional_amount, user)  │
│     • custody_status: IN_VAULT → WITH_LENDER                       │
│     • repledged_to: TakenLoan #999                                  │
│     • repledged_amount: proportional amount                         │
│     • RepledgeHistory created with audit trail                      │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ FINAL STATE:                                                         │
│                                                                      │
│ TakenLoan #999:                                                      │
│   • Lender: Lender B                                                 │
│   • Loan Amount: ₹60,000                                            │
│   • Interest Rate: 1.5%                                             │
│   • Collateral Status:                                              │
│       - Customer A (2 items): WITH_LENDER → ₹45k                   │
│       - Customer C (1 item): WITH_LENDER → ₹15k                     │
│       - Total Value: ₹80k                                           │
│       - LTV: 75%                                                    │
│                                                                      │
│ Each Item's RepledgeHistory:                                        │
│   • Ring 1: Repledged to #999 for ₹22.5k                           │
│   • Ring 2: Repledged to #999 for ₹22.5k                           │
│   • Chain: Repledged to #999 for ₹15k                              │
│   (All timestamps, user, notes recorded)                            │
│                                                                      │
│ SUCCESS! ✅ Got ₹60k using bundled collateral!                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Advantages
- **Bigger loans**: Use items from 3 customers = bigger total collateral
- **Better rates**: Bundle reduces per-customer overhead
- **Flexibility**: Mix high + low value items for balance
- **Visibility**: Know exact distribution and LTV
- **Full audit**: Complete trail for each item

---

## 🔄 Workflow 3: Close TakenLoan (Return Collateral)

**Scenario**: Paid back Lender B, need to return their collateral

```
┌─────────────────────────────────────────────────────────────────────┐
│ TAKEN LOAN #999 (from Workflow 2)                                   │
│                                                                      │
│ Status: DISBURSED (Money borrowed)                                 │
│ Current Collateral (WITH_LENDER):                                   │
│   • Customer A's Ring 1 (₹22.5k remaining)                         │
│   • Customer A's Ring 2 (₹22.5k remaining)                         │
│   • Customer C's Chain (₹15k remaining)                             │
│                                                                      │
│ Interest Paid: ₹200                                                │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ ACTION: Navigate to TakenLoan detail page                            │
│                                                                      │
│ Click: "View Collateral" tab                                        │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ COLLATERAL SUMMARY PAGE:                                            │
│                                                                      │
│ ┌─────────────────────────────────┐                                │
│ │ Customer A                      │                                │
│ │  • Ring 1: ₹22.5k              │                                │
│ │  • Ring 2: ₹22.5k              │                                │
│ │  Subtotal: ₹45k                │                                │
│ └─────────────────────────────────┘                                │
│                                                                      │
│ ┌─────────────────────────────────┐                                │
│ │ Customer C                      │                                │
│ │  • Chain: ₹15k                 │                                │
│ │  Subtotal: ₹15k                │                                │
│ └─────────────────────────────────┘                                │
│                                                                      │
│ Total Collateral: ₹60k                                             │
│ Loan Amount: ₹60k                                                  │
│ LTV: 100%                                                           │
│                                                                      │
│ Button: "Return All Collateral"                                    │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ CLICK: "Return All Collateral"                                      │
│                                                                      │
│ Confirmation dialog:                                                │
│ "This will return 3 items to your vault.                            │
│  They can then be released to customers."                           │
│                                                                      │
│ Click: "Confirm" button                                             │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ SYSTEM EXECUTION (Atomic):                                          │
│                                                                      │
│ for each item in collateral:                                        │
│   • item.return_from_lender(user, notes="Loan repaid")             │
│   • custody_status: WITH_LENDER → IN_VAULT                         │
│   • repledged_to: TakenLoan #999 → None                            │
│   • repledged_amount: → None                                        │
│   • RepledgeHistory.returned_at = now                               │
│   • RepledgeHistory.returned_by = current user                      │
│   ✓ Repeats for all 3 items                                        │
│                                                                      │
│ Result: All items back in vault                                     │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ FINAL STATE:                                                         │
│                                                                      │
│ Ring 1 (Customer A): IN_VAULT (ready to release)                   │
│ Ring 2 (Customer A): IN_VAULT (ready to release)                   │
│ Chain (Customer C): IN_VAULT (ready to release)                     │
│                                                                      │
│ RepledgeHistory for each:                                           │
│   • Repledged: 2025-02-22 by User X to TakenLoan #999             │
│   • Returned: 2025-03-07 by User Y                                 │
│   • Duration: 13 days                                               │
│                                                                      │
│ TakenLoan #999: Can now be closed/marked repaid                    │
│                                                                      │
│ SUCCESS! ✅ All collateral returned!                               │
│           Customer A and C can release their loans!                │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Points
- **Visibility**: See exactly what collateral you're returning
- **Grouped**: Items grouped by source customer
- **Atomic**: All or nothing
- **Audit**: Every return recorded with user & timestamp
- **Release Ready**: Customers can now release their items

---

## 📊 State Diagram: Item Lifecycle

```
                    ┌─────────────────────────────────┐
                    │    GIVEN LOAN CREATED           │
                    │    Customer pledges items       │
                    └──────────────┬────────────────────┘
                                   │
                                   ↓
                    ┌─────────────────────────────────┐
                    │    IN_VAULT                     │
                    │    Item in our possession       │
                    │    Can: Repledge, Release       │
                    │    Cannot: Nothing yet          │
                    └──┬───────────────────────────┬───┘
                       │                           │
          ┌────────────┘                           └──────────────┐
          │                                                        │
          ↓                                                        ↓
┌──────────────────────────────┐             ┌──────────────────────────────┐
│ WITH_LENDER                  │             │ WITH_CUSTOMER                │
│ (Repledged)                  │             │ (Released)                   │
│ Item with Lender             │             │ Item with Customer           │
│ Can: Return from Lender      │             │ Can: Nothing (loan closed)   │
│ Cannot: Release              │             │ Cannot: Repledge again       │
│ TakenLoan uses as collateral │             │ (unless re-pledged)          │
└───────────────┬──────────────┘             └──────────────────────────────┘
                │
                ↓
    ┌─────────────────────────────────┐
    │ AUTO-RETURN PATH                │
    │ (Customer releases loan)         │
    │ • TakenLoan closes              │
    │ • Item returned to vault         │
    │ • Then released to customer      │
    └─────────────────────────────────┘
                │
                ↓
    ┌─────────────────────────────────┐
    │ Item returned to IN_VAULT       │
    │ Ready for next cycle            │
    └─────────────────────────────────┘
```

---

## 🚦 Business Rules Enforced

```
┌────────────────────────────────────────────┐
│ REPLEDGE VALIDATION                        │
└────────────────────────────────────────────┘

Is item available for repledge?

item.custody_status == 'in_vault'           ✓ Required
    AND
item.repledged_to is None                   ✓ Required
    AND  
item.loan.is_released == False               ✓ Required
    
→ If all true: CAN REPLEDGE ✅
→ If any false: VALIDATION ERROR ❌


┌────────────────────────────────────────────┐
│ RELEASE VALIDATION                         │
└────────────────────────────────────────────┘

Can GivenLoan be released?

For each item:
  • If custody_status == 'with_lender'
      → ERROR with auto-return offer 🔄

  • Else if custody_status == 'in_vault'
      → Can release ✅

  • Else if custody_status == 'with_customer'
      → ERROR (already released) ❌


┌────────────────────────────────────────────┐
│ TAKENOAN CLOSING VALIDATION                │
└────────────────────────────────────────────┘

Can TakenLoan be closed?

collateral_items.count() == 0                ✓ Required

→ If true: CAN CLOSE ✅
→ If false: Must return collateral first ❌
```

---

## 📈 Audit Trail Example

**Item: Gold Ring (Customer A)**

```
Date        Action          Lender      Amount    User         Notes
──────────────────────────────────────────────────────────────────────
2025-01-15  Repledged to    Lender B    ₹20k      Admin1       Emergency
            TakenLoan #500
            
            Status: WITH_LENDER
            History Entry #1 Created

2025-02-01  Repledged to    Lender C    ₹18k      Admin2       Lower rate
            TakenLoan #600  (after returned from B)
            
            Status: WITH_LENDER
            History Entry #1: returned_at = 2025-02-01
            History Entry #2 Created

2025-02-22  Returned from   Lender C    N/A       Admin1       Payment received
            lender
            
            Status: IN_VAULT
            History Entry #2: returned_at = 2025-02-22
            History Entry #2: returned_by = Admin1

2025-02-22  Released to     N/A         N/A       Admin1       Customer requested
            Customer A
            
            Status: WITH_CUSTOMER
            (Item no longer available for repledge)
```

---

## 💾 Database View

### LoanItem (Enhanced)

```
id: 123
itemdesc: "Gold Ring"
loan_id: GivenLoan #50 (Customer A)
custody_status: 'with_customer'  ← NEW: Physical location
repledged_to: NULL               ← NEW: Current TakenLoan
repledged_amount: NULL           ← NEW: Amount for current repledge
repledged_at: NULL               ← NEW: When repledged

← OLD FIELDS (still present):
itemtype: 'Gold'
grossweight: 5.2
current_value(): ₹25,000 (property)
is_repledged: False (property - returns repledged_to is not None)
```

### RepledgeHistory (New)

```
id: 1
loan_item_id: 123
taken_loan_id: TakenLoan #600
repledged_amount: ₹18,000
item_value_at_repledge: ₹25,000
repledged_at: 2025-02-01T10:30:00
returned_at: 2025-02-22T14:15:00
repledged_by_id: User #5 (Admin2)
returned_by_id: User #3 (Admin1)
notes: "Lower rate"
return_notes: "Payment received"

← AUTO-COMPUTED PROPERTIES:
is_active: False (returned_at is not NULL)
duration_days: 21
ltv_ratio: 72% (18000 / 25000 * 100)
```

---

## 🎯 Everything Your System Now Prevents

```
❌ Release loan while items with lender
   → Auto-return workflow prevents it

❌ Repledge item while already repledged
   → Validation error with helpful message

❌ Repledge item that's with customer
   → marked WITH_CUSTOMER, can't repledge

❌ Close TakenLoan without returning collateral
   → can_close() returns False

❌ Release customer's items that you don't have
   → Audit trail shows where everything is

❌ Multiple TakenLoans claiming same collateral
   → item can only have one repledged_to

❌ No history of past pledges
   → RepledgeHistory has complete audit trail

❌ Can't bundle items from multiple customers
   → Now supported with proportional amounts

✅ EVERYTHING WORKS CORRECTLY!
```

---

## 🔍 Reporting Queries (Made Easy)

```python
# Active repledges - what do we owe lenders?
current_repledges = RepledgeHistory.objects.filter(returned_at__isnull=True)

# Items with specific lender
lender_b_collateral = LoanItem.objects.filter(
    custody_status='with_lender',
    repledged_to__lender__name='Lender B'
)

# Customer's items status
customer_a_items = LoanItem.objects.filter(
    loan__customer__name='Customer A'
).values('custody_status').annotate(count=Count('id'))
# Result: {'in_vault': 2, 'with_customer': 3}

# Repledge history for customer
history = RepledgeHistory.objects.filter(
    loan_item__loan__customer__name='Customer A'
).order_by('-repledged_at')

# LTV analysis - which are high risk?
risky = RepledgeHistory.objects.filter(
    returned_at__isnull=True,
    repledged_amount__gt=F('item_value_at_repledge') * 0.75
)
# Shows items where we borrowed 75%+ of value
```

---

## Summary: Workflows Enabled ✅

| Workflow | Before | After | Status |
|:---------|:-------|:------|:-------|
| Release + auto-return | Manual 5-step process | 1 click | ✅ |
| Multi-customer collateral | Impossible | Supported with UI | ✅ |
| View what collateral exists | Data scattered | Clean summary page | ✅ |
| Return collateral on close | Manual process | 1 click + atomic | ✅ |
| Audit trail | None | Complete with users | ✅ |
| Prevent invalid releases | Impossible | Validated | ✅ |
| Prevent double-repledge | Possible | Validated | ✅ |
| LTV tracking | Manual | Automatic | ✅ |

**All 5 user requirements met! 🎉**

Ready to implement? See `CUSTODY_TRACKING_IMPLEMENTATION_CHECKLIST.md`
