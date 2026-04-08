# Series Guardrails - Visual Guide

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        LOAN CREATION FLOW                        │
└─────────────────────────────────────────────────────────────────┘

User Creates Loan
    │
    ├─→ 1. FORM FILTERING (Automatic)
    │   ├─ LoanForm loads
    │   ├─ Uses: Series.objects.active_for_loans()
    │   └─ Result: Only eligible series shown to user
    │
    ├─→ 2. FORM VALIDATION (If user selects deactivated series)
    │   ├─ Form checks: series.can_create_loan()
    │   └─ Prevents invalid selection
    │
    ├─→ 3. LOAN SAVED
    │   └─ Django saves GivenLoan instance
    │
    ├─→ 4. SIGNAL TRIGGERED (post_save)
    │   └─ check_series_guardrails() signal handler fires
    │       └─ Extracts: instance.series reference
    │
    ├─→ 5. THRESHOLD CHECKING
    │   └─ series.check_and_apply_deactivation()
    │       ├─ Get current: get_current_loan_count()
    │       ├─ Get current: get_current_loan_amount()
    │       ├─ Check: is_loan_count_exceeded()
    │       ├─ Check: is_loan_amount_exceeded()
    │       └─ Result: True/False
    │
    ├─→ 6. APPLY DEACTIVATION (If threshold exceeded)
    │   └─ Based on deactivation_rule:
    │       │
    │       ├─ LOANS_ONLY
    │       │   └─ Set: deactivated_for_loans = True
    │       │
    │       ├─ RELEASES_ONLY
    │       │   └─ Set: deactivated_for_releases = True
    │       │
    │       ├─ BOTH
    │       │   ├─ Set: deactivated_for_loans = True
    │       │   └─ Set: deactivated_for_releases = True
    │       │
    │       └─ NONE (default)
    │           └─ No action
    │
    └─→ 7. NEXT LOAN ATTEMPT
        └─ Series NOT shown in form dropdown
           (Because: active_for_loans() filters them out)
```

---

## Data Flow Diagram

```
SERIES MODEL
├─ Thresholds (configured)
│  ├─ loan_count_threshold
│  ├─ loan_amount_threshold
│  └─ deactivation_rule
│
├─ Status (auto-updated)
│  ├─ deactivated_for_loans
│  ├─ deactivated_for_releases
│  ├─ deactivation_date
│  └─ threshold_exceeded_reason
│
└─ Methods
   ├─ Calculation
   │  ├─ get_current_loan_count()
   │  ├─ get_current_loan_amount()
   │  ├─ is_loan_count_exceeded()
   │  └─ is_loan_amount_exceeded()
   │
   ├─ Permission
   │  ├─ can_create_loan()
   │  └─ can_create_release()
   │
   └─ Management
      ├─ check_and_apply_deactivation()
      └─ get_guardrail_status()
```

---

## Form Integration Points

```
LOAN FORM
├─ series = forms.ModelChoiceField(
│  └─ queryset=Series.objects.active_for_loans()
│     │
│     └─ MANAGER FILTERS
│        ├─ is_active = True
│        └─ deactivated_for_loans = False
│
└─ Result: User only sees eligible series

                        ↓
                        
RELEASE FORM
├─ loan = forms.ModelChoiceField(
│  └─ queryset=GivenLoan.objects.filter(
│     release__isnull=True,
│     series__in=Series.objects.active_for_releases()
│  )
│
└─ Result: User only sees loans from eligible series
```

---

## Manager Method Behavior

```
SERIESMANAGER METHODS

active_for_loans()
├─ Filters: is_active=True
└─ Filters: deactivated_for_loans=False
   └─ Results in: Series where loans CAN be created

active_for_releases()
├─ Filters: is_active=True
└─ Filters: deactivated_for_releases=False
   └─ Results in: Series where releases CAN be created

active_for_both()
├─ Filters: is_active=True
├─ Filters: deactivated_for_loans=False
└─ Filters: deactivated_for_releases=False
   └─ Results in: Series where BOTH operations allowed
```

---

## Deactivation Rule Decision Tree

```
THRESHOLD EXCEEDED?
├─ NO → No deactivation (keep as is)
│
└─ YES → Check deactivation_rule
   │
   ├─ NONE (default)
   │  └─ X Do nothing (no deactivation)
   │
   ├─ LOANS_ONLY
   │  ├─ Set: deactivated_for_loans = True ✓
   │  └─ Keep: deactivated_for_releases = False
   │
   ├─ RELEASES_ONLY
   │  ├─ Keep: deactivated_for_loans = False
   │  └─ Set: deactivated_for_releases = True ✓
   │
   └─ BOTH
      ├─ Set: deactivated_for_loans = True ✓
      └─ Set: deactivated_for_releases = True ✓
```

---

## Permission Matrix

```
┌─────────────────────┬──────────────┬──────────────────┐
│ Scenario            │ Can Create   │ Can Create       │
│                     │ Loan?        │ Release?         │
├─────────────────────┼──────────────┼──────────────────┤
│ Normal (no limits)  │ ✓ Yes        │ ✓ Yes            │
├─────────────────────┼──────────────┼──────────────────┤
│ Inactive series     │ ✗ No         │ ✗ No             │
├─────────────────────┼──────────────┼──────────────────┤
│ Deactivated Loans   │ ✗ No         │ ✓ Yes (if rule   │
│                     │              │   allows)        │
├─────────────────────┼──────────────┼──────────────────┤
│ Deactivated Releases│ ✓ Yes (if    │ ✗ No             │
│                     │   rule allows)│                 │
├─────────────────────┼──────────────┼──────────────────┤
│ Deactivated Both    │ ✗ No         │ ✗ No             │
└─────────────────────┴──────────────┴──────────────────┘
```

---

## Signal Flow Diagram

```
SIGNAL CHAIN
├─ Loan Created/Updated/Deleted
│  └─ post_save or post_delete signal emitted
│
├─ Signal Receiver Triggered
│  └─ check_series_guardrails(sender, instance, **kwargs)
│
├─ Extract Series
│  └─ series = instance.series
│
├─ Check Thresholds
│  └─ series.check_and_apply_deactivation()
│     ├─ Calculate: get_current_loan_count()
│     ├─ Calculate: get_current_loan_amount()
│     ├─ Compare: Against loan_count_threshold
│     ├─ Compare: Against loan_amount_threshold
│     └─ Decision: Apply deactivation?
│
├─ If YES - Update Series
│  ├─ Set: deactivated_for_loans or deactivated_for_releases
│  ├─ Set: deactivation_date = now()
│  ├─ Set: threshold_exceeded_reason = message
│  └─ Save: series.save()
│
└─ Log Event
   └─ logger.warning("Series deactivated...")
      (Visible in logs for monitoring)
```

---

## Threshold Checking Algorithm

```
def check_and_apply_deactivation():
    
    Step 1: Validate Configuration
    ├─ if deactivation_rule == "NONE": 
    │  └─ return False  # Do nothing
    │
    └─ if no thresholds set:
       └─ return False  # Do nothing
    
    Step 2: Calculate Current Usage
    ├─ loan_count = get_current_loan_count()
    ├─ loan_amount = get_current_loan_amount()
    │
    └─ Build threshold list:
       ├─ if loan_count >= loan_count_threshold
       │  └─ add to "exceeded" list
       │
       └─ if loan_amount >= loan_amount_threshold
          └─ add to "exceeded" list
    
    Step 3: Check if Any Exceeded
    ├─ if nothing exceeded:
    │  └─ return False  # No deactivation needed
    │
    └─ if something exceeded:
       └─ continue to step 4
    
    Step 4: Apply Deactivation Based on Rule
    ├─ if rule includes LOANS:
    │  ├─ if not already deactivated:
    │  │  ├─ set deactivated_for_loans = True
    │  │  └─ was_updated = True
    │  │
    │  └─ record deactivation_date & reason
    │
    ├─ if rule includes RELEASES:
    │  ├─ if not already deactivated:
    │  │  ├─ set deactivated_for_releases = True
    │  │  └─ was_updated = True
    │  │
    │  └─ record deactivation_date & reason
    │
    └─ continue to step 5
    
    Step 5: Persist Changes
    ├─ if was_updated:
    │  └─ series.save()
    │
    └─ return (was_updated, reason_message)
```

---

## Admin Interface Layout

```
SERIES ADMIN - EDIT VIEW

┌─────────────────────────────────────────────────────┐
│ Series: GOLD-1                                      │
├─────────────────────────────────────────────────────┤
│ ▼ Basic Information                                 │
│  ├─ License: [License 01]                           │
│  ├─ Name: [GOLD]                                    │
│  ├─ Prefix: [G]                                     │
│  └─ Loan Type: [Given ▼]                            │
├─────────────────────────────────────────────────────┤
│ ▼ Configuration                                     │
│  ├─ Max Limit: [5]                                  │
│  └─ Is Active: [✓]                                  │
├─────────────────────────────────────────────────────┤
│ ▶ Guardrails & Thresholds (Collapsible)            │
│  ├─ Loan Count Threshold: [500]                     │
│  ├─ Loan Amount Threshold: [5000000]                │
│  ├─ Deactivation Rule: [LOANS_ONLY ▼]               │
│  │                                                 │
│  ├─ Deactivated for Loans: [✓] (Auto-managed)      │
│  ├─ Deactivated for Releases: [ ] (Auto-managed)   │
│  ├─ Deactivation Date: 2026-03-16 10:30 (Read-only)│
│  └─ Reason: Loan count (500) reached... (Read-only)│
└─────────────────────────────────────────────────────┘
```

---

## Series List View

```
SERIES ADMIN - LIST VIEW

Series              Created         Status                  Edit
────────────────────────────────────────────────────────────────
GOLD-1              3/10/26         🔒 Locked (loans)       [Edit]
SILVER-1            3/08/26         ⚠️ Threshold exceeded   [Edit]
PLATINUM-1          2/15/26         ✓ Active                [Edit]
BRONZE-1            1/20/26         🔒 Locked (both)        [Edit]
COPPER-1            3/01/26         ✓ Active                [Edit]
────────────────────────────────────────────────────────────────

Legend:
✓ Active         - Series fully operational
⚠️ Threshold    - At least one threshold breached
🔒 Locked        - One or both operations disabled
```

---

## Monitoring Dashboard (Conceptual)

```
┌─────────────────────────────────────────────────────────┐
│                 SERIES CAPACITY MONITOR                 │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ GOLD Series                                             │
│ Loans: ████████████████████░░░ 500/500 active          │
│        ⚠️ AT CAPACITY (100%)                            │
│ Amount: ███████████████░░░░░░ ₹5.0M/10M                 │
│         50% utilized                                   │
│ Status: 🔒 Deactivated for loans since 3/16 10:30     │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ SILVER Series                                           │
│ Loans: ███████████░░░░░░░░░░░ 250/500 active           │
│        50% utilized                                    │
│ Amount: ████████░░░░░░░░░░░░░ ₹3.2M/10M                 │
│         32% utilized                                   │
│ Status: ✓ Active and operational                       │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ PLATINUM Series                                         │
│ Loans: ██░░░░░░░░░░░░░░░░░░░░░ 25/500 active           │
│        5% utilized                                     │
│ Amount: ░░░░░░░░░░░░░░░░░░░░░░░ ₹0.5M/10M              │
│         5% utilized                                    │
│ Status: ✓ Active and operational                       │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Query Chain for Loan Form

```
User Opens Loan Form
    │
    └─→ LoanForm initialization
        │
        └─→ series field queryset evaluation
            │
            └─→ Series.objects.active_for_loans()
                │
                ├─ Applied Filter 1: is_active=True
                │  └─ Removes: deactivated series
                │
                ├─ Applied Filter 2: deactivated_for_loans=False
                │  └─ Removes: loans-disabled series
                │
                └─ Returns: Eligible series list
                    │
                    └─→ Rendered in dropdown to user
```

---

## Example Threshold Scenarios

```
Scenario 1: GOLD Series - LOANS_ONLY Rule
┌──────────────────────────────────────────┐
│ Config:                                  │
│ • Loan Count Threshold: 100              │
│ • Deactivation Rule: LOANS_ONLY          │
├──────────────────────────────────────────┤
│ Current State:                           │
│ • Active Loans: 95                       │
│ • Status: ✓ Active                       │
├──────────────────────────────────────────┤
│ At 100+ Loans:                           │
│ • deactivated_for_loans = True           │
│ • deactivated_for_releases = False       │
│ • Loan Form: Series NOT shown            │
│ • Release Form: Series shown ✓           │
└──────────────────────────────────────────┘

Scenario 2: SILVER Series - BOTH Rule
┌──────────────────────────────────────────┐
│ Config:                                  │
│ • Amount Threshold: ₹5M                  │
│ • Deactivation Rule: BOTH                │
├──────────────────────────────────────────┤
│ Current State:                           │
│ • Active Amount: ₹4.5M                   │
│ • Status: ⚠️ Threshold exceeded          │
├──────────────────────────────────────────┤
│ At ₹5M+ Amount:                          │
│ • deactivated_for_loans = True           │
│ • deactivated_for_releases = True        │
│ • Loan Form: Series NOT shown            │
│ • Release Form: Series NOT shown         │
│ • Result: Series fully locked            │
└──────────────────────────────────────────┘
```

---

## Performance Impact

```
QUERY OPTIMIZATION

Before Guardrails:
└─ Series.objects.filter(is_active=True)
   └─ Full table scan if no index

After Guardrails:
├─ Series.objects.active_for_loans()
│  └─ Uses index: (is_active, deactivated_for_loans)
│     └─ ~10-100x faster on large tables
│
└─ Added indexes:
   ├─ girvi_series_active_loans_idx
   │  └─ (is_active, deactivated_for_loans)
   │
   └─ girvi_series_active_releases_idx
      └─ (is_active, deactivated_for_releases)
```

---

## Implementation Status Checklist

```
✅ Models
  ├─ SeriesManager created
  ├─ Guardrail fields added
  └─ Threshold checking methods added

✅ Forms
  ├─ LoanForm updated
  ├─ ReleaseForm updated
  └─ SeriesForm updated

✅ Admin
  ├─ SeriesAdmin enhanced
  └─ Status display added

✅ Signals
  └─ check_series_guardrails() added

✅ Database
  └─ Migration 0009_series_guardrails.py created

✅ Tests
  └─ test_series_guardrails.py created

✅ Documentation
  ├─ SERIES_GUARDRAILS_GUIDE.md
  ├─ SERIES_GUARDRAILS_SUMMARY.md
  ├─ DEPLOYMENT_CHECKLIST.md
  └─ SERIES_GUARDRAILS_IMPLEMENTATION_COMPLETE.md
```

---

This visual guide maps out the complete system architecture and data flow!
