---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Series Guardrails - Visual Guide

## System Architecture Diagram

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                        LOAN CREATION FLOW                        â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

User Creates Loan
    â”‚
    â”œâ”€â†’ 1. FORM FILTERING (Automatic)
    â”‚   â”œâ”€ LoanForm loads
    â”‚   â”œâ”€ Uses: Series.objects.active_for_loans()
    â”‚   â””â”€ Result: Only eligible series shown to user
    â”‚
    â”œâ”€â†’ 2. FORM VALIDATION (If user selects deactivated series)
    â”‚   â”œâ”€ Form checks: series.can_create_loan()
    â”‚   â””â”€ Prevents invalid selection
    â”‚
    â”œâ”€â†’ 3. LOAN SAVED
    â”‚   â””â”€ Django saves GivenLoan instance
    â”‚
    â”œâ”€â†’ 4. SIGNAL TRIGGERED (post_save)
    â”‚   â””â”€ check_series_guardrails() signal handler fires
    â”‚       â””â”€ Extracts: instance.series reference
    â”‚
    â”œâ”€â†’ 5. THRESHOLD CHECKING
    â”‚   â””â”€ series.check_and_apply_deactivation()
    â”‚       â”œâ”€ Get current: get_current_loan_count()
    â”‚       â”œâ”€ Get current: get_current_loan_amount()
    â”‚       â”œâ”€ Check: is_loan_count_exceeded()
    â”‚       â”œâ”€ Check: is_loan_amount_exceeded()
    â”‚       â””â”€ Result: True/False
    â”‚
    â”œâ”€â†’ 6. APPLY DEACTIVATION (If threshold exceeded)
    â”‚   â””â”€ Based on deactivation_rule:
    â”‚       â”‚
    â”‚       â”œâ”€ LOANS_ONLY
    â”‚       â”‚   â””â”€ Set: deactivated_for_loans = True
    â”‚       â”‚
    â”‚       â”œâ”€ RELEASES_ONLY
    â”‚       â”‚   â””â”€ Set: deactivated_for_releases = True
    â”‚       â”‚
    â”‚       â”œâ”€ BOTH
    â”‚       â”‚   â”œâ”€ Set: deactivated_for_loans = True
    â”‚       â”‚   â””â”€ Set: deactivated_for_releases = True
    â”‚       â”‚
    â”‚       â””â”€ NONE (default)
    â”‚           â””â”€ No action
    â”‚
    â””â”€â†’ 7. NEXT LOAN ATTEMPT
        â””â”€ Series NOT shown in form dropdown
           (Because: active_for_loans() filters them out)
```

---

## Data Flow Diagram

```
SERIES MODEL
â”œâ”€ Thresholds (configured)
â”‚  â”œâ”€ loan_count_threshold
â”‚  â”œâ”€ loan_amount_threshold
â”‚  â””â”€ deactivation_rule
â”‚
â”œâ”€ Status (auto-updated)
â”‚  â”œâ”€ deactivated_for_loans
â”‚  â”œâ”€ deactivated_for_releases
â”‚  â”œâ”€ deactivation_date
â”‚  â””â”€ threshold_exceeded_reason
â”‚
â””â”€ Methods
   â”œâ”€ Calculation
   â”‚  â”œâ”€ get_current_loan_count()
   â”‚  â”œâ”€ get_current_loan_amount()
   â”‚  â”œâ”€ is_loan_count_exceeded()
   â”‚  â””â”€ is_loan_amount_exceeded()
   â”‚
   â”œâ”€ Permission
   â”‚  â”œâ”€ can_create_loan()
   â”‚  â””â”€ can_create_release()
   â”‚
   â””â”€ Management
      â”œâ”€ check_and_apply_deactivation()
      â””â”€ get_guardrail_status()
```

---

## Form Integration Points

```
LOAN FORM
â”œâ”€ series = forms.ModelChoiceField(
â”‚  â””â”€ queryset=Series.objects.active_for_loans()
â”‚     â”‚
â”‚     â””â”€ MANAGER FILTERS
â”‚        â”œâ”€ is_active = True
â”‚        â””â”€ deactivated_for_loans = False
â”‚
â””â”€ Result: User only sees eligible series

                        â†“
                        
RELEASE FORM
â”œâ”€ loan = forms.ModelChoiceField(
â”‚  â””â”€ queryset=GivenLoan.objects.filter(
â”‚     release__isnull=True,
â”‚     series__in=Series.objects.active_for_releases()
â”‚  )
â”‚
â””â”€ Result: User only sees loans from eligible series
```

---

## Manager Method Behavior

```
SERIESMANAGER METHODS

active_for_loans()
â”œâ”€ Filters: is_active=True
â””â”€ Filters: deactivated_for_loans=False
   â””â”€ Results in: Series where loans CAN be created

active_for_releases()
â”œâ”€ Filters: is_active=True
â””â”€ Filters: deactivated_for_releases=False
   â””â”€ Results in: Series where releases CAN be created

active_for_both()
â”œâ”€ Filters: is_active=True
â”œâ”€ Filters: deactivated_for_loans=False
â””â”€ Filters: deactivated_for_releases=False
   â””â”€ Results in: Series where BOTH operations allowed
```

---

## Deactivation Rule Decision Tree

```
THRESHOLD EXCEEDED?
â”œâ”€ NO â†’ No deactivation (keep as is)
â”‚
â””â”€ YES â†’ Check deactivation_rule
   â”‚
   â”œâ”€ NONE (default)
   â”‚  â””â”€ X Do nothing (no deactivation)
   â”‚
   â”œâ”€ LOANS_ONLY
   â”‚  â”œâ”€ Set: deactivated_for_loans = True âœ“
   â”‚  â””â”€ Keep: deactivated_for_releases = False
   â”‚
   â”œâ”€ RELEASES_ONLY
   â”‚  â”œâ”€ Keep: deactivated_for_loans = False
   â”‚  â””â”€ Set: deactivated_for_releases = True âœ“
   â”‚
   â””â”€ BOTH
      â”œâ”€ Set: deactivated_for_loans = True âœ“
      â””â”€ Set: deactivated_for_releases = True âœ“
```

---

## Permission Matrix

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ Scenario            â”‚ Can Create   â”‚ Can Create       â”‚
â”‚                     â”‚ Loan?        â”‚ Release?         â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ Normal (no limits)  â”‚ âœ“ Yes        â”‚ âœ“ Yes            â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ Inactive series     â”‚ âœ— No         â”‚ âœ— No             â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ Deactivated Loans   â”‚ âœ— No         â”‚ âœ“ Yes (if rule   â”‚
â”‚                     â”‚              â”‚   allows)        â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ Deactivated Releasesâ”‚ âœ“ Yes (if    â”‚ âœ— No             â”‚
â”‚                     â”‚   rule allows)â”‚                 â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ Deactivated Both    â”‚ âœ— No         â”‚ âœ— No             â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

---

## Signal Flow Diagram

```
SIGNAL CHAIN
â”œâ”€ Loan Created/Updated/Deleted
â”‚  â””â”€ post_save or post_delete signal emitted
â”‚
â”œâ”€ Signal Receiver Triggered
â”‚  â””â”€ check_series_guardrails(sender, instance, **kwargs)
â”‚
â”œâ”€ Extract Series
â”‚  â””â”€ series = instance.series
â”‚
â”œâ”€ Check Thresholds
â”‚  â””â”€ series.check_and_apply_deactivation()
â”‚     â”œâ”€ Calculate: get_current_loan_count()
â”‚     â”œâ”€ Calculate: get_current_loan_amount()
â”‚     â”œâ”€ Compare: Against loan_count_threshold
â”‚     â”œâ”€ Compare: Against loan_amount_threshold
â”‚     â””â”€ Decision: Apply deactivation?
â”‚
â”œâ”€ If YES - Update Series
â”‚  â”œâ”€ Set: deactivated_for_loans or deactivated_for_releases
â”‚  â”œâ”€ Set: deactivation_date = now()
â”‚  â”œâ”€ Set: threshold_exceeded_reason = message
â”‚  â””â”€ Save: series.save()
â”‚
â””â”€ Log Event
   â””â”€ logger.warning("Series deactivated...")
      (Visible in logs for monitoring)
```

---

## Threshold Checking Algorithm

```
def check_and_apply_deactivation():
    
    Step 1: Validate Configuration
    â”œâ”€ if deactivation_rule == "NONE": 
    â”‚  â””â”€ return False  # Do nothing
    â”‚
    â””â”€ if no thresholds set:
       â””â”€ return False  # Do nothing
    
    Step 2: Calculate Current Usage
    â”œâ”€ loan_count = get_current_loan_count()
    â”œâ”€ loan_amount = get_current_loan_amount()
    â”‚
    â””â”€ Build threshold list:
       â”œâ”€ if loan_count >= loan_count_threshold
       â”‚  â””â”€ add to "exceeded" list
       â”‚
       â””â”€ if loan_amount >= loan_amount_threshold
          â””â”€ add to "exceeded" list
    
    Step 3: Check if Any Exceeded
    â”œâ”€ if nothing exceeded:
    â”‚  â””â”€ return False  # No deactivation needed
    â”‚
    â””â”€ if something exceeded:
       â””â”€ continue to step 4
    
    Step 4: Apply Deactivation Based on Rule
    â”œâ”€ if rule includes LOANS:
    â”‚  â”œâ”€ if not already deactivated:
    â”‚  â”‚  â”œâ”€ set deactivated_for_loans = True
    â”‚  â”‚  â””â”€ was_updated = True
    â”‚  â”‚
    â”‚  â””â”€ record deactivation_date & reason
    â”‚
    â”œâ”€ if rule includes RELEASES:
    â”‚  â”œâ”€ if not already deactivated:
    â”‚  â”‚  â”œâ”€ set deactivated_for_releases = True
    â”‚  â”‚  â””â”€ was_updated = True
    â”‚  â”‚
    â”‚  â””â”€ record deactivation_date & reason
    â”‚
    â””â”€ continue to step 5
    
    Step 5: Persist Changes
    â”œâ”€ if was_updated:
    â”‚  â””â”€ series.save()
    â”‚
    â””â”€ return (was_updated, reason_message)
```

---

## Admin Interface Layout

```
SERIES ADMIN - EDIT VIEW

â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ Series: GOLD-1                                      â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ â–¼ Basic Information                                 â”‚
â”‚  â”œâ”€ License: [License 01]                           â”‚
â”‚  â”œâ”€ Name: [GOLD]                                    â”‚
â”‚  â”œâ”€ Prefix: [G]                                     â”‚
â”‚  â””â”€ Loan Type: [Given â–¼]                            â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ â–¼ Configuration                                     â”‚
â”‚  â”œâ”€ Max Limit: [5]                                  â”‚
â”‚  â””â”€ Is Active: [âœ“]                                  â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ â–¶ Guardrails & Thresholds (Collapsible)            â”‚
â”‚  â”œâ”€ Loan Count Threshold: [500]                     â”‚
â”‚  â”œâ”€ Loan Amount Threshold: [5000000]                â”‚
â”‚  â”œâ”€ Deactivation Rule: [LOANS_ONLY â–¼]               â”‚
â”‚  â”‚                                                 â”‚
â”‚  â”œâ”€ Deactivated for Loans: [âœ“] (Auto-managed)      â”‚
â”‚  â”œâ”€ Deactivated for Releases: [ ] (Auto-managed)   â”‚
â”‚  â”œâ”€ Deactivation Date: 2026-03-16 10:30 (Read-only)â”‚
â”‚  â””â”€ Reason: Loan count (500) reached... (Read-only)â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

---

## Series List View

```
SERIES ADMIN - LIST VIEW

Series              Created         Status                  Edit
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
GOLD-1              3/10/26         ðŸ”’ Locked (loans)       [Edit]
SILVER-1            3/08/26         âš ï¸ Threshold exceeded   [Edit]
PLATINUM-1          2/15/26         âœ“ Active                [Edit]
BRONZE-1            1/20/26         ðŸ”’ Locked (both)        [Edit]
COPPER-1            3/01/26         âœ“ Active                [Edit]
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

Legend:
âœ“ Active         - Series fully operational
âš ï¸ Threshold    - At least one threshold breached
ðŸ”’ Locked        - One or both operations disabled
```

---

## Monitoring Dashboard (Conceptual)

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                 SERIES CAPACITY MONITOR                 â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                         â”‚
â”‚ GOLD Series                                             â”‚
â”‚ Loans: â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–‘â–‘â–‘ 500/500 active          â”‚
â”‚        âš ï¸ AT CAPACITY (100%)                            â”‚
â”‚ Amount: â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–‘â–‘â–‘â–‘â–‘â–‘ â‚¹5.0M/10M                 â”‚
â”‚         50% utilized                                   â”‚
â”‚ Status: ðŸ”’ Deactivated for loans since 3/16 10:30     â”‚
â”‚                                                         â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ SILVER Series                                           â”‚
â”‚ Loans: â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘ 250/500 active           â”‚
â”‚        50% utilized                                    â”‚
â”‚ Amount: â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘ â‚¹3.2M/10M                 â”‚
â”‚         32% utilized                                   â”‚
â”‚ Status: âœ“ Active and operational                       â”‚
â”‚                                                         â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ PLATINUM Series                                         â”‚
â”‚ Loans: â–ˆâ–ˆâ–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘ 25/500 active           â”‚
â”‚        5% utilized                                     â”‚
â”‚ Amount: â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘ â‚¹0.5M/10M              â”‚
â”‚         5% utilized                                    â”‚
â”‚ Status: âœ“ Active and operational                       â”‚
â”‚                                                         â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

---

## Query Chain for Loan Form

```
User Opens Loan Form
    â”‚
    â””â”€â†’ LoanForm initialization
        â”‚
        â””â”€â†’ series field queryset evaluation
            â”‚
            â””â”€â†’ Series.objects.active_for_loans()
                â”‚
                â”œâ”€ Applied Filter 1: is_active=True
                â”‚  â””â”€ Removes: deactivated series
                â”‚
                â”œâ”€ Applied Filter 2: deactivated_for_loans=False
                â”‚  â””â”€ Removes: loans-disabled series
                â”‚
                â””â”€ Returns: Eligible series list
                    â”‚
                    â””â”€â†’ Rendered in dropdown to user
```

---

## Example Threshold Scenarios

```
Scenario 1: GOLD Series - LOANS_ONLY Rule
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ Config:                                  â”‚
â”‚ â€¢ Loan Count Threshold: 100              â”‚
â”‚ â€¢ Deactivation Rule: LOANS_ONLY          â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ Current State:                           â”‚
â”‚ â€¢ Active Loans: 95                       â”‚
â”‚ â€¢ Status: âœ“ Active                       â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ At 100+ Loans:                           â”‚
â”‚ â€¢ deactivated_for_loans = True           â”‚
â”‚ â€¢ deactivated_for_releases = False       â”‚
â”‚ â€¢ Loan Form: Series NOT shown            â”‚
â”‚ â€¢ Release Form: Series shown âœ“           â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

Scenario 2: SILVER Series - BOTH Rule
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ Config:                                  â”‚
â”‚ â€¢ Amount Threshold: â‚¹5M                  â”‚
â”‚ â€¢ Deactivation Rule: BOTH                â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ Current State:                           â”‚
â”‚ â€¢ Active Amount: â‚¹4.5M                   â”‚
â”‚ â€¢ Status: âš ï¸ Threshold exceeded          â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ At â‚¹5M+ Amount:                          â”‚
â”‚ â€¢ deactivated_for_loans = True           â”‚
â”‚ â€¢ deactivated_for_releases = True        â”‚
â”‚ â€¢ Loan Form: Series NOT shown            â”‚
â”‚ â€¢ Release Form: Series NOT shown         â”‚
â”‚ â€¢ Result: Series fully locked            â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

---

## Performance Impact

```
QUERY OPTIMIZATION

Before Guardrails:
â””â”€ Series.objects.filter(is_active=True)
   â””â”€ Full table scan if no index

After Guardrails:
â”œâ”€ Series.objects.active_for_loans()
â”‚  â””â”€ Uses index: (is_active, deactivated_for_loans)
â”‚     â””â”€ ~10-100x faster on large tables
â”‚
â””â”€ Added indexes:
   â”œâ”€ girvi_series_active_loans_idx
   â”‚  â””â”€ (is_active, deactivated_for_loans)
   â”‚
   â””â”€ girvi_series_active_releases_idx
      â””â”€ (is_active, deactivated_for_releases)
```

---

## Implementation Status Checklist

```
âœ… Models
  â”œâ”€ SeriesManager created
  â”œâ”€ Guardrail fields added
  â””â”€ Threshold checking methods added

âœ… Forms
  â”œâ”€ LoanForm updated
  â”œâ”€ ReleaseForm updated
  â””â”€ SeriesForm updated

âœ… Admin
  â”œâ”€ SeriesAdmin enhanced
  â””â”€ Status display added

âœ… Signals
  â””â”€ check_series_guardrails() added

âœ… Database
  â””â”€ Migration 0009_series_guardrails.py created

âœ… Tests
  â””â”€ test_series_guardrails.py created

âœ… Documentation
  â”œâ”€ SERIES_GUARDRAILS_GUIDE.md
  â”œâ”€ SERIES_GUARDRAILS_SUMMARY.md
  â”œâ”€ DEPLOYMENT_CHECKLIST.md
  â””â”€ SERIES_GUARDRAILS_IMPLEMENTATION_COMPLETE.md
```

---

This visual guide maps out the complete system architecture and data flow!

