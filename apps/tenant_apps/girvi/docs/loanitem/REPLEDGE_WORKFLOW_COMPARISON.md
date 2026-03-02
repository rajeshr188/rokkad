# Repledge Workflow - Current vs Proposed

## 🔄 Current Problem Visualization

```
CURRENT (Confusing):

Customer A                    Your Business                    Lender B
    |                              |                                |
    |--[Gold 100g]->               |                                |
    |   (GivenLoan #1)             |                                |
    |                              |                                |
    |                         [Gold in vault?]                      |
    |                              |                                |
    |                              |-------[Same Gold 100g]-------->|
    |                              |    (TakenLoan #1)              |
    |                              |    RepledgedLoanItem           |
    |                              |                                |
    |<--"I want my gold!"          |                                |
    |                              |                                |
    |                         ❌ Can't give!                        |
    |                         (Gold is with Lender B)               |
    |                              |                                |

PROBLEM: No tracking of physical custody!
         Database shows gold in both places!
```

---

## ✅ Proposed Solution - Custody Tracking

```
PROPOSED:

Customer A                    Your Business                    Lender B
    |                              |                                |
    |--[Gold 100g]->               |                                |
    |   (GivenLoan #1)             |                                |
    |                              |                                |
    |                    LoanItem:                                  |
    |                    custody_status = IN_VAULT                  |
    |                              |                                |
    |                              |-------[Gold 100g]-------->     |
    |                              |  (TakenLoan #1)                |
    |                              |                                |
    |                    LoanItem:                                  |
    |                    custody_status = WITH_LENDER               |
    |                    repledged_to = TakenLoan #1                |
    |                              |                                |
    |<--"I want my gold!"          |                                |
    |                              |                                |
    |    ❌ "Sorry, item is        |                                |
    |       WITH_LENDER"           |                                |
    |                              |                                |
    |                              |<------[Gold returned]----------|
    |                              |  (TakenLoan released)          |
    |                              |                                |
    |                    LoanItem:                                  |
    |                    custody_status = IN_VAULT                  |
    |                    repledged_to = NULL                        |
    |                              |                                |
    |<------[Gold returned]--------|                                |
    |   (GivenLoan released)       |                                |

SOLUTION: Clear custody status prevents conflicts!
```

---

## 📊 State Diagram

```
LoanItem Custody States:

    ┌──────────────┐
    │   CREATED    │
    │  (New Item)  │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │  IN_VAULT    │◄────────┐
    │ (Available)  │         │
    └──┬────────┬──┘         │
       │        │            │
       │        │            │ return_from_repledge()
       │        │            │
       │        │     ┌──────┴───────────┐
       │        └────►│   WITH_LENDER    │
       │ repledge()   │   (Repledged)    │
       │              └──────────────────┘
       │
       │ release_to_customer()
       │
       ▼
    ┌──────────────────┐
    │ WITH_CUSTOMER    │
    │   (Released)     │
    └──────────────────┘
```

---

## 🎯 Key Questions to Answer

Before choosing an approach, answer these:

### 1. **Can items be partially repledged?**
   - ❓ Can you repledge 50g from a 100g item?
   - Current model: NO
   - Proposed: With custody tracking, YES (need weight splits)

### 2. **Can multiple items be used for one TakenLoan?**
   - ❓ Can you bundle items from different GivenLoans?
   - Current model: YES (multiple RepledgedLoanItems)
   - Proposed: YES (multiple items with repledged_to same TakenLoan)

### 3. **What happens if customer wants release while item is repledged?**
   - ❓ Should release be blocked?
   - Current model: NO VALIDATION ❌
   - Proposed: BLOCKED with clear error ✅

### 4. **Who decides repledge amount?**
   - ❓ Is it based on item value or arbitrary?
   - Current model: Arbitrary (repledged_loanamount)
   - Proposed: Can be based on LTV ratio

### 5. **Do you need history of past repledges?**
   - ❓ Track all past repledges of an item?
   - Current model: NO
   - Proposed: YES (RepledgeHistory model)

---

## 💼 Business Scenarios

### Scenario 1: Simple Repledge
```
1. Customer pledges gold → GivenLoan
2. You need cash → Repledge to lender → TakenLoan
3. You get cash back → Return from repledge
4. Customer redeems → Release to customer

Custody flow:
  IN_VAULT → WITH_LENDER → IN_VAULT → WITH_CUSTOMER
```

### Scenario 2: Blocked Release
```
1. Customer pledges gold → GivenLoan
2. You repledge to lender → TakenLoan
3. Customer wants to redeem

Current: ❌ System allows release (gold not there!)
Proposed: ✅ System blocks with "Item WITH_LENDER"
```

### Scenario 3: Multi-Item Collateral
```
You want to take ₹100,000 from Lender B:

Option A: Use one expensive item
- 1x Gold 150g (worth ₹120,000) → TakenLoan

Option B: Bundle multiple items  
- Gold 50g (₹40,000)
- Gold 40g (₹32,000)
- Silver 100g (₹30,000)
Total: ₹102,000 → TakenLoan

Both supported in proposed model!
```

---

## ⚖️ Comparison Matrix

| Feature | Current Model | Option 1 (Full Custody) | Option 2 (Pool) | Option 3 (Simple) | **Recommended (Hybrid)** |
|---------|--------------|------------------------|-----------------|-------------------|--------------------------|
| **Custody Tracking** | ❌ None | ✅ Full chain | ⚠️ Pool only | ⚠️ Basic | ✅ Status + History |
| **Prevent Invalid Release** | ❌ No | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| **History** | ❌ No | ✅ Full | ⚠️ Allocation only | ✅ Separate table | ✅ Separate table |
| **Complexity** | Simple | High | Medium | Low | **Medium** |
| **Partial Repledge** | ❌ No | ✅ With splits | ⚠️ Via pool | ❌ No | ⚠️ Can add later |
| **Multi-item TakenLoan** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| **Chain Tracking** | ❌ No | ✅ Full chain | ⚠️ Limited | ❌ No | ✅ Via history |
| **Risk Management** | ❌ No | ✅ Yes | ✅ Yes | ⚠️ Basic | ✅ LTV ratios |
| **Migration Effort** | - | High | Medium | Low | **Medium** |

**Verdict:** Recommended (Hybrid) balances features vs complexity

---

## 🛠️ Implementation Priority

### Phase 1: Critical Fix (Now)
1. Add `custody_status` field to LoanItem
2. Add validation to prevent release when WITH_LENDER
3. Migrate existing RepledgedLoanItems

### Phase 2: Enhanced Tracking (Next)
1. Add RepledgeHistory model
2. Update TakenLoan to query collateral_items
3. Add custody change methods (repledge_to, return_from)

### Phase 3: Advanced Features (Later)
1. Partial repledge support (weight splits)
2. LTV ratio calculations
3. Risk dashboards

---

## 📝 Example Code Usage

### Creating a TakenLoan with Collateral

```python
# Option A: Manual repledge
loan_item = LoanItem.objects.get(id=123)
if loan_item.is_available_for_repledge:
    taken_loan = TakenLoan.objects.create(
        lender=lender_customer,
        series=series,
        loan_date=timezone.now()
    )
    
    loan_item.repledge_to(
        taken_loan=taken_loan,
        amount=50000,
        user=request.user
    )
else:
    # Item not available - show custody status
    print(f"Cannot repledge - status: {loan_item.custody_status}")


# Option B: Batch repledge
taken_loan = TakenLoan.objects.create(...)

items = LoanItem.objects.filter(
    id__in=[123, 456, 789]
)

taken_loan.add_collateral(
    loan_items=items,
    user=request.user
)
```

### Checking Release Eligibility

```python
given_loan = GivenLoan.objects.get(id=456)

# Current (no validation):
given_loan.create_release(...)  # ❌ Might fail if items are repledged

# Proposed (with validation):
can_release, message = given_loan.can_release()
if can_release:
    given_loan.create_release(...)
else:
    # Show user: "Cannot release: Item #123 is WITH_LENDER"
    raise ValidationError(message)
```

### Viewing Custody Status

```python
# Dashboard: Items currently repledged
repledged_items = LoanItem.objects.filter(
    custody_status=ItemCustodyStatus.WITH_LENDER
).select_related('repledged_to', 'loan')

for item in repledged_items:
    print(f"{item} → {item.repledged_to.lender.name}")
    print(f"  Amount: ₹{item.repledged_amount}")
    print(f"  Since: {item.repledged_at}")


# History: All past repledges of an item
item = LoanItem.objects.get(id=123)
for history in item.repledge_history.all():
    status = "Active" if history.is_active else "Returned"
    print(f"{history.repledged_at}: → {history.taken_loan.lender.name} ({status})")
```

---

## 🤔 Decision Guide

**Choose Recommended (Hybrid) if:**
- ✅ You need custody tracking
- ✅ You want to prevent invalid releases
- ✅ You need audit history
- ✅ Balance between features and complexity is important

**Choose Full Custody (Option 1) if:**
- You need complete chain tracking
- Partial repledges are critical
- Multiple custody transfers expected

**Choose Simple (Option 3) if:**
- You have simple repledge needs
- Minimal complexity preferred
- Quick migration required

---

## ❓ Questions for You

1. **How often do items get repledged?**
   - Rarely → Simple approach
   - Frequently → Full tracking

2. **Do customers try to release while items are repledged?**
   - Yes → Need validation ✅
   - No → Less critical

3. **Do you need to know full item history?**
   - Yes → RepledgeHistory model
   - No → Just current state

4. **Can one item be repledged multiple times (chain)?**
   - Yes → Complex tracking needed
   - No → Simpler model works

5. **Do you bundle items from different customers?**
   - Yes → Need pool concept
   - No → Direct item linking works

---

**Let me know your answers and I'll help implement the best solution!**
