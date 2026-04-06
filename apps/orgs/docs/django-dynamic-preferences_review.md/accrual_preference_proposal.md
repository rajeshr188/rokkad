# Proposed Dynamic Preferences For Girvi Interest Accrual

_Last updated: 2026-04-06_

> **Implementation status:** the first set of these preferences has now been added in code. `Loan__Accrual_Timing` is wired into the scheduled accrual command/task path, `Loan__Auto_Post_Accruals` and `Loan__Allow_Backfill_Posting` influence command posting behavior, and the catch-up toggles are now honored in receipt / release / renewal flows.

---

## Goal

These preference definitions are the recommended next step for making the new Girvi interest accrual behavior more configurable at the **company/workspace level** while keeping the underlying service idempotent.

They are intended for `django-dynamic-preferences` and fit the existing project pattern:
- global default,
- optional company override,
- typed access through `CompanyPreferences`.

---

## Recommended Section

Use the existing `Loan` section for these first settings.

If the list grows further later, it can be split into a dedicated section such as:
- `Loan_Accrual`

For now, keeping them under `Loan` is the simplest and most consistent choice.

---

## Exact Preference Definitions To Add

### 1. `Loan__Accrual_Timing`
**Type:** `ChoicePreference`  
**Purpose:** Controls when the scheduled accrual batch should normally run.

**Recommended values:**
- `EOM` = End of month
- `BOM` = Beginning of next month

**Recommended default:** `EOM`

**Why it matters:**
This captures the business decision already agreed in the accrual design. The service remains callable any day, but the automated schedule window becomes configurable per company.

**Suggested definition:**

```python
class BaseLoanAccrualTiming(ChoicePreference):
    section = loan_section
    name = "Accrual_Timing"
    default = "EOM"
    choices = [
        ("EOM", "End of Month"),
        ("BOM", "Beginning of Next Month"),
    ]
    required = True
```

---

### 2. `Loan__Auto_Post_Accruals`
**Type:** `BooleanPreference`  
**Purpose:** Controls whether scheduled/manual accrual runs should automatically post DEA journal entries, or only create accrual rows.

**Recommended default:** `True`

**Why it matters:**
Some companies may want preview/draft accrual rows first before finance posts journals. This is a clean operational toggle.

**Suggested definition:**

```python
class BaseLoanAutoPostAccruals(BooleanPreference):
    section = loan_section
    name = "Auto_Post_Accruals"
    default = True
    required = False
```

---

### 3. `Loan__Catchup_On_Receipt`
**Type:** `BooleanPreference`  
**Purpose:** Enables/disables catch-up accrual before a payment receipt is posted.

**Recommended default:** `True`

**Why it matters:**
This behavior is currently desirable and already implemented. Making it explicit as a policy flag gives controlled flexibility.

**Suggested definition:**

```python
class BaseLoanCatchupOnReceipt(BooleanPreference):
    section = loan_section
    name = "Catchup_On_Receipt"
    default = True
    required = False
```

---

### 4. `Loan__Catchup_On_Release`
**Type:** `BooleanPreference`  
**Purpose:** Enables/disables catch-up accrual before loan release/closure.

**Recommended default:** `True`

**Suggested definition:**

```python
class BaseLoanCatchupOnRelease(BooleanPreference):
    section = loan_section
    name = "Catchup_On_Release"
    default = True
    required = False
```

---

### 5. `Loan__Catchup_On_Renewal`
**Type:** `BooleanPreference`  
**Purpose:** Enables/disables catch-up accrual before renewal rollover.

**Recommended default:** `True`

**Suggested definition:**

```python
class BaseLoanCatchupOnRenewal(BooleanPreference):
    section = loan_section
    name = "Catchup_On_Renewal"
    default = True
    required = False
```

---

### 6. `Loan__Allow_Backfill_Posting`
**Type:** `BooleanPreference`  
**Purpose:** Controls whether one-time backfill runs are allowed to post to DEA directly, or should remain row-only by default.

**Recommended default:** `False`

**Why it matters:**
Backfill is more sensitive than normal scheduled accrual. Many finance teams may want review before automatic posting of old periods.

**Suggested definition:**

```python
class BaseLoanAllowBackfillPosting(BooleanPreference):
    section = loan_section
    name = "Allow_Backfill_Posting"
    default = False
    required = False
```

---

## Nice-to-have Later

These are valid future preferences, but not necessary for the first rollout.

### 7. `Loan__Accrual_Notice_Days`
**Type:** `IntegerPreference`  
**Use:** how many days before due/close to send reminders or surface alerts.

### 8. `Loan__Suspend_Accrual_On_NPA`
**Type:** `BooleanPreference`  
**Use:** future NPA handling policy.

### 9. `Loan__Accrual_Requires_Review`
**Type:** `BooleanPreference`  
**Use:** future finance approval workflow before DEA posting.

---

## Recommended `CompanyPreferences` Accessors

To keep the existing typed helper pattern clean, add properties like:

```python
@property
def loan_accrual_timing(self):
    return self._get("Loan__Accrual_Timing")

@property
def loan_auto_post_accruals(self):
    return self._get("Loan__Auto_Post_Accruals")

@property
def loan_catchup_on_receipt(self):
    return self._get("Loan__Catchup_On_Receipt")

@property
def loan_catchup_on_release(self):
    return self._get("Loan__Catchup_On_Release")

@property
def loan_catchup_on_renewal(self):
    return self._get("Loan__Catchup_On_Renewal")

@property
def loan_allow_backfill_posting(self):
    return self._get("Loan__Allow_Backfill_Posting")
```

---

## How They Should Be Used In Code

### Scheduler / command layer
- `loan_accrual_timing`
- `loan_auto_post_accruals`
- `loan_allow_backfill_posting`

### Service / settlement layer
- `loan_catchup_on_receipt`
- `loan_catchup_on_release`
- `loan_catchup_on_renewal`

This keeps preferences attached to **policy decisions**, not to low-level math.

### Current implementation status
These are now wired as follows:
- scheduled task path (`accrue_loan_interest_batch`) passes `respect_timing=True`
- the accrual command respects `Loan__Accrual_Timing` for scheduled runs
- batch posting respects `Loan__Auto_Post_Accruals`
- backfill posting respects `Loan__Allow_Backfill_Posting`
- receipt / release / renewal catch-up hooks respect their corresponding `Catchup_On_*` toggles

---

## Recommendation On Fit

These settings are a **strong fit** for `django-dynamic-preferences` because they are:
- company-wide,
- changed occasionally,
- operational or policy driven,
- and safe to resolve at runtime.

The actual accrual rows, journal links, and accounting history should still remain in the regular domain models — not in preferences.

---

## Suggested First Implementation Order

1. `Loan__Accrual_Timing`
2. `Loan__Auto_Post_Accruals`
3. `Loan__Catchup_On_Receipt`
4. `Loan__Catchup_On_Release`
5. `Loan__Catchup_On_Renewal`
6. `Loan__Allow_Backfill_Posting`

This gives the most value with the least complexity.
