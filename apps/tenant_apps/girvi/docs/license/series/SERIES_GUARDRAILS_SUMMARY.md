# Series Guardrails - Implementation Summary

## What Was Implemented

### 1. **Series Model Enhancements** (`license.py`)

#### New Fields:
```python
loan_count_threshold              # Max active loans allowed
loan_amount_threshold             # Max loan amount allowed (₹)
deactivation_rule                 # NONE | LOANS_ONLY | RELEASES_ONLY | BOTH
deactivated_for_loans             # Auto-flag: disables loan creation
deactivated_for_releases          # Auto-flag: disables release creation
deactivation_date                 # When threshold was exceeded
threshold_exceeded_reason         # Reason for deactivation
```

#### New Methods:
```python
get_current_loan_count()          # Current active loans
get_current_loan_amount()         # Current total amount
is_loan_count_exceeded()          # Check if loan count threshold reached
is_loan_amount_exceeded()         # Check if amount threshold reached
is_any_threshold_exceeded()       # Either threshold exceeded?
can_create_loan()                 # Can new loans be created?
can_create_release()              # Can new releases be created?
check_and_apply_deactivation()    # Apply rules & return status
get_guardrail_status()            # Get full status dict
```

#### New Manager:
```python
Series.objects.active_for_loans()      # Series where loans can be created
Series.objects.active_for_releases()   # Series where releases can be created
Series.objects.active_for_both()       # Series for both operations
```

---

### 2. **Form Updates** (`forms.py`)

#### LoanForm:
```python
# Before
series = forms.ModelChoiceField(
    queryset=Series.objects.filter(is_active=True),
)

# After
series = forms.ModelChoiceField(
    queryset=Series.objects.active_for_loans(),
)
```

#### ReleaseForm:
```python
# Before
loan = forms.ModelChoiceField(
    queryset=GivenLoan.objects.filter(release__isnull=True),
)

# After
loan = forms.ModelChoiceField(
    queryset=GivenLoan.objects.filter(
        release__isnull=True,
        series__in=Series.objects.active_for_releases()
    ),
)
```

#### SeriesForm:
Added fields for configuration:
- `loan_count_threshold`
- `loan_amount_threshold`
- `deactivation_rule`

---

### 3. **Admin Interface** (`admin.py`)

#### Updated SeriesAdmin:
- New `guardrail_status` display column
- Organized fieldsets with collapsible guardrails section
- Visual indicators:
  - ✓ Active
  - ⚠️ Threshold exceeded
  - 🔒 Loans disabled
  - 🔒 Releases disabled
  - 🔒 Locked (both)

---

### 4. **Automatic Signal Handlers** (`signals.py`)

```python
@receiver(post_save, sender=GivenLoan)
@receiver(post_delete, sender=GivenLoan)
def check_series_guardrails(sender, instance, **kwargs):
    # Automatically checks and applies deactivation after loan operations
```

Triggers when:
- Loan created/updated/deleted
- Related loan items modified

---

### 5. **Database Migration** (`migrations/0009_series_guardrails.py`)

Adds:
- 7 new fields to Series model
- 2 database indexes for performance:
  - `(is_active, deactivated_for_loans)`
  - `(is_active, deactivated_for_releases)`

---

## Quick Start

### Step 1: Apply Migration
```bash
python manage.py migrate girvi
```

### Step 2: Configure a Series
```python
from apps.tenant_apps.girvi.models import Series

series = Series.objects.get(name="GOLD")
series.loan_count_threshold = 100      # Max 100 active loans
series.loan_amount_threshold = 5000000  # Max ₹5 million
series.deactivation_rule = "LOANS"     # Disable loans only
series.save()
```

### Step 3: Monitor
```python
# Check status
status = series.get_guardrail_status()
print(f"Can create loan: {status['can_create_loan']}")
print(f"Current loans: {status['current_loan_count']}")

# View all deactivated series
deactivated = Series.objects.filter(deactivated_for_loans=True)
for s in deactivated:
    print(f"{s} - Reason: {s.threshold_exceeded_reason}")
```

---

## Key Behaviors

### Automatic Deactivation
When a loan is created/deleted and a threshold is exceeded:
1. Signal handler fires
2. `check_and_apply_deactivation()` called
3. If threshold exceeded + rule configured:
   - Sets `deactivated_for_loans = True` (if rule includes loans)
   - Sets `deactivated_for_releases = True` (if rule includes releases)
   - Records `deactivation_date` and `threshold_exceeded_reason`
   - Logs warning with details

### Form Filtering
- **Loan Form**: Only shows series where `deactivated_for_loans = False`
- **Release Form**: Only shows loans from series where `deactivated_for_releases = False`
- Users cannot select deactivated series even if `is_active = True`

### Admin Display
- Deactivated series marked with visual indicators
- Guardrail settings collapsible for cleaner interface
- `deactivated_for_*` fields show auto-deactivation status
- Easily reset by unchecking `deactivated_for_*` flags

---

## Example Scenarios

### Scenario 1: Series at Capacity
```python
series.loan_count_threshold = 100
series.deactivation_rule = "LOANS"

# After 100th loan is created:
# → deactivated_for_loans = True
# → Disappears from loan form
# → Error if trying to create another loan programmatically
```

### Scenario 2: Amount Control
```python
series.loan_amount_threshold = Decimal("10000000")  # ₹10M
series.deactivation_rule = "BOTH"  # Lock both operations

# At ₹10M exposure:
# → deactivated_for_loans = True
# → deactivated_for_releases = True
# → Neither form shows this series
```

### Scenario 3: Release Control
```python
series.deactivation_rule = "RELEASES"

# When amount/count threshold exceeded:
# → Only deactivated_for_releases = True
# → Can still create new loans
# → Cannot release existing loans
```

---

## Field Reference

| Field | Type | Purpose |
|-------|------|---------|
| `loan_count_threshold` | PositiveInt | Max active loans before auto-deactivate |
| `loan_amount_threshold` | Decimal | Max total amount before auto-deactivate |
| `deactivation_rule` | Choice | What to disable when threshold hit |
| `deactivated_for_loans` | Bool | **Auto-set**: Loans disabled (don't create) |
| `deactivated_for_releases` | Bool | **Auto-set**: Releases disabled (don't create) |
| `deactivation_date` | DateTime | **Auto-set**: When threshold was exceeded |
| `threshold_exceeded_reason` | String | **Auto-set**: Which threshold was exceeded |

---

## Testing Checklist

- [ ] Migration applied successfully
- [ ] Series fields visible in admin
- [ ] Can configure thresholds and rules
- [ ] Loan form shows only eligible series
- [ ] Release form shows only eligible loans
- [ ] Signals trigger deactivation when threshold hit
- [ ] Deactivated series hidden from forms
- [ ] Admin status display shows correct indicators
- [ ] Can manually toggle deactivation flags

---

## Next Steps

1. **Review the SERIES_GUARDRAILS_GUIDE.md** for detailed usage
2. **Test in development** with sample thresholds
3. **Configure production series** with appropriate limits
4. **Monitor logs** for deactivation events
5. **Set up alerts** for series approaching thresholds (optional enhancement)
