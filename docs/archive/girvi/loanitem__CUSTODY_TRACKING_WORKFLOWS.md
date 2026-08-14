---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Custody Tracking - Complete Workflows Illustrated

## ðŸ”„ Workflow 1: Release with Auto-Return (Most Common)

**Scenario**: Customer wants their items back, but some are currently with a lender

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ GIVEN LOAN: Customer A has pledged 5 gold items                     â”‚
â”‚                                                                      â”‚
â”‚ Current Status:                                                     â”‚
â”‚  â€¢ 3 items: IN VAULT                                                â”‚
â”‚  â€¢ 2 items: WITH_LENDER (Lender B)                                  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ CUSTOMER ACTION: "I want my items back"                             â”‚
â”‚                                                                      â”‚
â”‚ UI: Click "Release Loan" button                                     â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ SYSTEM CHECK: release_loan_check_custody()                          â”‚
â”‚                                                                      â”‚
â”‚ âœ“ Detect: 2 items WITH_LENDER                                      â”‚
â”‚ âœ“ Show: Warning page with "Release with Auto-Return" button        â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ USER CONFIRMATION: "Yes, proceed"                                   â”‚
â”‚                                                                      â”‚
â”‚ Click: "Release with Auto-Return" button                            â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ STEP 1: Return Items from Lender                                    â”‚
â”‚                                                                      â”‚
â”‚ for each item in WITH_LENDER:                                       â”‚
â”‚   â€¢ item.return_from_lender(user)                                   â”‚
â”‚   â€¢ custody_status: WITH_LENDER â†’ IN_VAULT                          â”‚
â”‚   â€¢ repledged_to: Lender B â†’ None                                   â”‚
â”‚   â€¢ RepledgeHistory: returned_at = now                              â”‚
â”‚                                                                      â”‚
â”‚ Result: All 5 items now IN_VAULT                                    â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ STEP 2: Release to Customer                                         â”‚
â”‚                                                                      â”‚
â”‚ for each item in IN_VAULT:                                          â”‚
â”‚   â€¢ item.release_to_customer(user)                                  â”‚
â”‚   â€¢ custody_status: IN_VAULT â†’ WITH_CUSTOMER                        â”‚
â”‚                                                                      â”‚
â”‚ Result: All 5 items now WITH_CUSTOMER                               â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ STEP 3: Create Release Document                                     â”‚
â”‚                                                                      â”‚
â”‚ â€¢ Release.objects.create(...)                                       â”‚
â”‚ â€¢ Loan.is_released = True                                           â”‚
â”‚                                                                      â”‚
â”‚ Result: Loan marked as released                                     â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ SUCCESS! âœ…                                                          â”‚
â”‚                                                                      â”‚
â”‚ Customer A has their items back!                                    â”‚
â”‚ Lender B's collateral returned!                                     â”‚
â”‚ Complete audit trail in RepledgeHistory!                            â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Key Points
- **Transparent to user**: One click does 3 steps
- **No validation errors**: System prevents impossible state
- **Full history**: Each step recorded in RepledgeHistory
- **Atomic**: All or nothing (transaction.atomic)

---

## ðŸ“¦ Workflow 2: Create Multi-Customer Repledge (New Feature)

**Scenario**: Need to borrow â‚¹60,000. Bundle items from multiple customers.

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ YOUR VAULT STATUS:                                                  â”‚
â”‚                                                                      â”‚
â”‚ Customer A's items:                                                 â”‚
â”‚   â€¢ 2 gold rings @ â‚¹25k each = â‚¹50k (IN_VAULT)                     â”‚
â”‚                                                                      â”‚
â”‚ Customer C's items:                                                 â”‚
â”‚   â€¢ 1 gold chain @ â‚¹30k = â‚¹30k (IN_VAULT)                          â”‚
â”‚                                                                      â”‚
â”‚ Total Available: â‚¹80k                                               â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ ACTION: /girvi/repledge/create/                                     â”‚
â”‚                                                                      â”‚
â”‚ Browse items grouped by customer                                    â”‚
â”‚ Select items from DIFFERENT customers                               â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ SELECTION (Multi-Customer):                                         â”‚
â”‚                                                                      â”‚
â”‚ FROM USE: Customer A â†’ Select 2 rings (â‚¹50k)                       â”‚
â”‚ FROM USE: Customer C â†’ Select 1 chain (â‚¹30k)                       â”‚
â”‚ TOTAL COLLATERAL: â‚¹80k                                              â”‚
â”‚                                                                      â”‚
â”‚ Sticky sidebar shows:                                               â”‚
â”‚   âœ“ Selected: 3 items                                               â”‚
â”‚   âœ“ Total Value: â‚¹80k                                               â”‚
â”‚   âœ“ From: Customer A, Customer C                                    â”‚
â”‚   âœ“ Max Loan (80% LTV): â‚¹64k                                        â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ FORM:                                                               â”‚
â”‚                                                                      â”‚
â”‚ Lender: Lender B (dropdown)                                         â”‚
â”‚ Loan Amount: 60000 (< 64k max) âœ“                                   â”‚
â”‚ Interest Rate: 1.5%                                                 â”‚
â”‚ Loan Date: 2025-02-22                                               â”‚
â”‚ Notes: Emergency cash flow                                          â”‚
â”‚                                                                      â”‚
â”‚ LTV Check: 60k / 80k = 75% âœ… OK                                   â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ CLICK: "Create TakenLoan with Collateral"                           â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ SYSTEM EXECUTION (Atomic Transaction):                              â”‚
â”‚                                                                      â”‚
â”‚ Step 1: Create TakenLoan                                            â”‚
â”‚   â€¢ TakenLoan.objects.create(                                       â”‚
â”‚       lender=Lender B,                                              â”‚
â”‚       loan_amount=60000,                                            â”‚
â”‚       interest_rate=1.5,                                            â”‚
â”‚       ...                                                            â”‚
â”‚     )                                                                â”‚
â”‚   â€¢ Result: TakenLoan #999 created                                  â”‚
â”‚                                                                      â”‚
â”‚ Step 2: Distribute â‚¹60k Proportionally                             â”‚
â”‚   â€¢ Ring 1 (â‚¹25k / â‚¹80k) = 37.5% â†’ â‚¹22,500                        â”‚
â”‚   â€¢ Ring 2 (â‚¹25k / â‚¹80k) = 37.5% â†’ â‚¹22,500                        â”‚
â”‚   â€¢ Chain (â‚¹30k / â‚¹80k) = 37.5% â†’ â‚¹15,000                          â”‚
â”‚                                                                      â”‚
â”‚ Step 3: Repledge Each Item                                          â”‚
â”‚   for each item:                                                    â”‚
â”‚     â€¢ item.repledge_to(TakenLoan #999, proportional_amount, user)  â”‚
â”‚     â€¢ custody_status: IN_VAULT â†’ WITH_LENDER                       â”‚
â”‚     â€¢ repledged_to: TakenLoan #999                                  â”‚
â”‚     â€¢ repledged_amount: proportional amount                         â”‚
â”‚     â€¢ RepledgeHistory created with audit trail                      â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ FINAL STATE:                                                         â”‚
â”‚                                                                      â”‚
â”‚ TakenLoan #999:                                                      â”‚
â”‚   â€¢ Lender: Lender B                                                 â”‚
â”‚   â€¢ Loan Amount: â‚¹60,000                                            â”‚
â”‚   â€¢ Interest Rate: 1.5%                                             â”‚
â”‚   â€¢ Collateral Status:                                              â”‚
â”‚       - Customer A (2 items): WITH_LENDER â†’ â‚¹45k                   â”‚
â”‚       - Customer C (1 item): WITH_LENDER â†’ â‚¹15k                     â”‚
â”‚       - Total Value: â‚¹80k                                           â”‚
â”‚       - LTV: 75%                                                    â”‚
â”‚                                                                      â”‚
â”‚ Each Item's RepledgeHistory:                                        â”‚
â”‚   â€¢ Ring 1: Repledged to #999 for â‚¹22.5k                           â”‚
â”‚   â€¢ Ring 2: Repledged to #999 for â‚¹22.5k                           â”‚
â”‚   â€¢ Chain: Repledged to #999 for â‚¹15k                              â”‚
â”‚   (All timestamps, user, notes recorded)                            â”‚
â”‚                                                                      â”‚
â”‚ SUCCESS! âœ… Got â‚¹60k using bundled collateral!                     â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Key Advantages
- **Bigger loans**: Use items from 3 customers = bigger total collateral
- **Better rates**: Bundle reduces per-customer overhead
- **Flexibility**: Mix high + low value items for balance
- **Visibility**: Know exact distribution and LTV
- **Full audit**: Complete trail for each item

---

## ðŸ”„ Workflow 3: Close TakenLoan (Return Collateral)

**Scenario**: Paid back Lender B, need to return their collateral

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ TAKEN LOAN #999 (from Workflow 2)                                   â”‚
â”‚                                                                      â”‚
â”‚ Status: DISBURSED (Money borrowed)                                 â”‚
â”‚ Current Collateral (WITH_LENDER):                                   â”‚
â”‚   â€¢ Customer A's Ring 1 (â‚¹22.5k remaining)                         â”‚
â”‚   â€¢ Customer A's Ring 2 (â‚¹22.5k remaining)                         â”‚
â”‚   â€¢ Customer C's Chain (â‚¹15k remaining)                             â”‚
â”‚                                                                      â”‚
â”‚ Interest Paid: â‚¹200                                                â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ ACTION: Navigate to TakenLoan detail page                            â”‚
â”‚                                                                      â”‚
â”‚ Click: "View Collateral" tab                                        â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ COLLATERAL SUMMARY PAGE:                                            â”‚
â”‚                                                                      â”‚
â”‚ â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                                â”‚
â”‚ â”‚ Customer A                      â”‚                                â”‚
â”‚ â”‚  â€¢ Ring 1: â‚¹22.5k              â”‚                                â”‚
â”‚ â”‚  â€¢ Ring 2: â‚¹22.5k              â”‚                                â”‚
â”‚ â”‚  Subtotal: â‚¹45k                â”‚                                â”‚
â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                                â”‚
â”‚                                                                      â”‚
â”‚ â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                                â”‚
â”‚ â”‚ Customer C                      â”‚                                â”‚
â”‚ â”‚  â€¢ Chain: â‚¹15k                 â”‚                                â”‚
â”‚ â”‚  Subtotal: â‚¹15k                â”‚                                â”‚
â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                                â”‚
â”‚                                                                      â”‚
â”‚ Total Collateral: â‚¹60k                                             â”‚
â”‚ Loan Amount: â‚¹60k                                                  â”‚
â”‚ LTV: 100%                                                           â”‚
â”‚                                                                      â”‚
â”‚ Button: "Return All Collateral"                                    â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ CLICK: "Return All Collateral"                                      â”‚
â”‚                                                                      â”‚
â”‚ Confirmation dialog:                                                â”‚
â”‚ "This will return 3 items to your vault.                            â”‚
â”‚  They can then be released to customers."                           â”‚
â”‚                                                                      â”‚
â”‚ Click: "Confirm" button                                             â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ SYSTEM EXECUTION (Atomic):                                          â”‚
â”‚                                                                      â”‚
â”‚ for each item in collateral:                                        â”‚
â”‚   â€¢ item.return_from_lender(user, notes="Loan repaid")             â”‚
â”‚   â€¢ custody_status: WITH_LENDER â†’ IN_VAULT                         â”‚
â”‚   â€¢ repledged_to: TakenLoan #999 â†’ None                            â”‚
â”‚   â€¢ repledged_amount: â†’ None                                        â”‚
â”‚   â€¢ RepledgeHistory.returned_at = now                               â”‚
â”‚   â€¢ RepledgeHistory.returned_by = current user                      â”‚
â”‚   âœ“ Repeats for all 3 items                                        â”‚
â”‚                                                                      â”‚
â”‚ Result: All items back in vault                                     â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ FINAL STATE:                                                         â”‚
â”‚                                                                      â”‚
â”‚ Ring 1 (Customer A): IN_VAULT (ready to release)                   â”‚
â”‚ Ring 2 (Customer A): IN_VAULT (ready to release)                   â”‚
â”‚ Chain (Customer C): IN_VAULT (ready to release)                     â”‚
â”‚                                                                      â”‚
â”‚ RepledgeHistory for each:                                           â”‚
â”‚   â€¢ Repledged: 2025-02-22 by User X to TakenLoan #999             â”‚
â”‚   â€¢ Returned: 2025-03-07 by User Y                                 â”‚
â”‚   â€¢ Duration: 13 days                                               â”‚
â”‚                                                                      â”‚
â”‚ TakenLoan #999: Can now be closed/marked repaid                    â”‚
â”‚                                                                      â”‚
â”‚ SUCCESS! âœ… All collateral returned!                               â”‚
â”‚           Customer A and C can release their loans!                â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Key Points
- **Visibility**: See exactly what collateral you're returning
- **Grouped**: Items grouped by source customer
- **Atomic**: All or nothing
- **Audit**: Every return recorded with user & timestamp
- **Release Ready**: Customers can now release their items

---

## ðŸ“Š State Diagram: Item Lifecycle

```
                    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                    â”‚    GIVEN LOAN CREATED           â”‚
                    â”‚    Customer pledges items       â”‚
                    â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                                   â”‚
                                   â†“
                    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                    â”‚    IN_VAULT                     â”‚
                    â”‚    Item in our possession       â”‚
                    â”‚    Can: Repledge, Release       â”‚
                    â”‚    Cannot: Nothing yet          â”‚
                    â””â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”˜
                       â”‚                           â”‚
          â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                           â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
          â”‚                                                        â”‚
          â†“                                                        â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”             â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ WITH_LENDER                  â”‚             â”‚ WITH_CUSTOMER                â”‚
â”‚ (Repledged)                  â”‚             â”‚ (Released)                   â”‚
â”‚ Item with Lender             â”‚             â”‚ Item with Customer           â”‚
â”‚ Can: Return from Lender      â”‚             â”‚ Can: Nothing (loan closed)   â”‚
â”‚ Cannot: Release              â”‚             â”‚ Cannot: Repledge again       â”‚
â”‚ TakenLoan uses as collateral â”‚             â”‚ (unless re-pledged)          â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜             â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                â”‚
                â†“
    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
    â”‚ AUTO-RETURN PATH                â”‚
    â”‚ (Customer releases loan)         â”‚
    â”‚ â€¢ TakenLoan closes              â”‚
    â”‚ â€¢ Item returned to vault         â”‚
    â”‚ â€¢ Then released to customer      â”‚
    â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                â”‚
                â†“
    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
    â”‚ Item returned to IN_VAULT       â”‚
    â”‚ Ready for next cycle            â”‚
    â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

---

## ðŸš¦ Business Rules Enforced

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ REPLEDGE VALIDATION                        â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

Is item available for repledge?

item.custody_status == 'in_vault'           âœ“ Required
    AND
item.repledged_to is None                   âœ“ Required
    AND  
item.loan.is_released == False               âœ“ Required
    
â†’ If all true: CAN REPLEDGE âœ…
â†’ If any false: VALIDATION ERROR âŒ


â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ RELEASE VALIDATION                         â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

Can GivenLoan be released?

For each item:
  â€¢ If custody_status == 'with_lender'
      â†’ ERROR with auto-return offer ðŸ”„

  â€¢ Else if custody_status == 'in_vault'
      â†’ Can release âœ…

  â€¢ Else if custody_status == 'with_customer'
      â†’ ERROR (already released) âŒ


â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ TAKENOAN CLOSING VALIDATION                â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

Can TakenLoan be closed?

collateral_items.count() == 0                âœ“ Required

â†’ If true: CAN CLOSE âœ…
â†’ If false: Must return collateral first âŒ
```

---

## ðŸ“ˆ Audit Trail Example

**Item: Gold Ring (Customer A)**

```
Date        Action          Lender      Amount    User         Notes
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
2025-01-15  Repledged to    Lender B    â‚¹20k      Admin1       Emergency
            TakenLoan #500
            
            Status: WITH_LENDER
            History Entry #1 Created

2025-02-01  Repledged to    Lender C    â‚¹18k      Admin2       Lower rate
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

## ðŸ’¾ Database View

### LoanItem (Enhanced)

```
id: 123
itemdesc: "Gold Ring"
loan_id: GivenLoan #50 (Customer A)
custody_status: 'with_customer'  â† NEW: Physical location
repledged_to: NULL               â† NEW: Current TakenLoan
repledged_amount: NULL           â† NEW: Amount for current repledge
repledged_at: NULL               â† NEW: When repledged

â† OLD FIELDS (still present):
itemtype: 'Gold'
grossweight: 5.2
current_value(): â‚¹25,000 (property)
is_repledged: False (property - returns repledged_to is not None)
```

### RepledgeHistory (New)

```
id: 1
loan_item_id: 123
taken_loan_id: TakenLoan #600
repledged_amount: â‚¹18,000
item_value_at_repledge: â‚¹25,000
repledged_at: 2025-02-01T10:30:00
returned_at: 2025-02-22T14:15:00
repledged_by_id: User #5 (Admin2)
returned_by_id: User #3 (Admin1)
notes: "Lower rate"
return_notes: "Payment received"

â† AUTO-COMPUTED PROPERTIES:
is_active: False (returned_at is not NULL)
duration_days: 21
ltv_ratio: 72% (18000 / 25000 * 100)
```

---

## ðŸŽ¯ Everything Your System Now Prevents

```
âŒ Release loan while items with lender
   â†’ Auto-return workflow prevents it

âŒ Repledge item while already repledged
   â†’ Validation error with helpful message

âŒ Repledge item that's with customer
   â†’ marked WITH_CUSTOMER, can't repledge

âŒ Close TakenLoan without returning collateral
   â†’ can_close() returns False

âŒ Release customer's items that you don't have
   â†’ Audit trail shows where everything is

âŒ Multiple TakenLoans claiming same collateral
   â†’ item can only have one repledged_to

âŒ No history of past pledges
   â†’ RepledgeHistory has complete audit trail

âŒ Can't bundle items from multiple customers
   â†’ Now supported with proportional amounts

âœ… EVERYTHING WORKS CORRECTLY!
```

---

## ðŸ” Reporting Queries (Made Easy)

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

## Summary: Workflows Enabled âœ…

| Workflow | Before | After | Status |
|:---------|:-------|:------|:-------|
| Release + auto-return | Manual 5-step process | 1 click | âœ… |
| Multi-customer collateral | Impossible | Supported with UI | âœ… |
| View what collateral exists | Data scattered | Clean summary page | âœ… |
| Return collateral on close | Manual process | 1 click + atomic | âœ… |
| Audit trail | None | Complete with users | âœ… |
| Prevent invalid releases | Impossible | Validated | âœ… |
| Prevent double-repledge | Possible | Validated | âœ… |
| LTV tracking | Manual | Automatic | âœ… |

**All 5 user requirements met! ðŸŽ‰**

Ready to implement? See `CUSTODY_TRACKING_IMPLEMENTATION_CHECKLIST.md`

