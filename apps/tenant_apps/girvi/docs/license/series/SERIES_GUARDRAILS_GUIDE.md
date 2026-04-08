# Series Guardrails Implementation Guide

## Overview

The Series Guardrails feature adds automatic threshold-based deactivation rules to the Series model. Once a series reaches certain thresholds (loan count or amount), it can be automatically disabled for loan creation, release creation, or both. This ensures operational control over series usage.

## Key Features

### 1. **Threshold Configuration**
   - **Loan Count Threshold**: Maximum number of active loans allowed in the series
   - **Loan Amount Threshold**: Maximum total amount of active loans allowed (in ₹)
   - Leave thresholds blank for unlimited

### 2. **Deactivation Rules**
   - **NONE**: No automatic deactivation (default)
   - **LOANS_ONLY**: Disable only new loan creation
   - **RELEASES_ONLY**: Disable only release creation
   - **BOTH**: Disable both loan and release creation

### 3. **Automatic Tracking**
   - `deactivated_for_loans`: Boolean flag indicating if loans are disabled
   - `deactivated_for_releases`: Boolean flag indicating if releases are disabled
   - `deactivation_date`: When the series was auto-deactivated
   - `threshold_exceeded_reason`: Detailed reason for deactivation

## Setup Instructions

### 1. Apply Migration
```bash
python manage.py migrate girvi
```

This will add the following fields to the Series model:
- `loan_count_threshold`
- `loan_amount_threshold`
- `deactivation_rule`
- `deactivated_for_loans`
- `deactivated_for_releases`
- `deactivation_date`
- `threshold_exceeded_reason`

### 2. Configure Series Guardrails in Admin

Navigate to: **Admin → Licenses → Series → Edit Series**

Set thresholds and deactivation rules:
```
Basic Information: License, Name, Prefix, Loan Type
Configuration: Max Limit, Active Status
Guardrails & Thresholds (collapsible):
├── Loan Count Threshold: e.g., 100
├── Loan Amount Threshold: e.g., 5000000 (₹5 million)
├── Deactivation Rule: LOANS_ONLY / RELEASES_ONLY / BOTH
└── (Automated fields shown below)
    ├── Deactivated for Loans
    ├── Deactivated for Releases
    ├── Deactivation Date
    └── Threshold Exceeded Reason
```

## Usage Examples

### Example 1: Series with Loan Count Limit

**Scenario**: Gold loan series with max 500 active loans

```python
# In Django shell
from apps.tenant_apps.girvi.models import Series

series = Series.objects.get(name="GOLD")
series.loan_count_threshold = 500
series.deactivation_rule = "LOANS"
series.save()
```

**Behavior**:
- After the 500th unreleased loan is created, the series will be marked `deactivated_for_loans = True`
- Loan form will no longer show this series in the dropdown
- Further loan creation attempts will fail with validation error

### Example 2: Series with Amount Limit

**Scenario**: Silver loan series with max ₹10 million exposure

```python
series = Series.objects.get(name="SILVER")
series.loan_amount_threshold = Decimal("10000000")
series.deactivation_rule = "BOTH"  # Disable loans & releases
series.save()
```

**Behavior**:
- When total active loan amount reaches ₹10 million:
  - Both `deactivated_for_loans` and `deactivated_for_releases` become True
  - Series disappears from both loan creation and release forms
  - Existing unreleased loans cannot be released

### Example 3: Manual Deactivation

```python
# Manually disable releases only (without waiting for threshold)
series = Series.objects.get(name="PLATINUM")
series.deactivated_for_releases = True
series.deactivation_date = timezone.now()
series.threshold_exceeded_reason = "Manual - Regulatory compliance review"
series.save()
```

## API Reference

### Manager Methods

```python
# Get all active series that allow new loans
Series.objects.active_for_loans()

# Get all active series that allow new releases
Series.objects.active_for_releases()

# Get all active series that allow both
Series.objects.active_for_both()
```

### Series Model Methods

```python
series = Series.objects.get(pk=1)

# Threshold checking
series.get_current_loan_count()           # Returns: int
series.get_current_loan_amount()          # Returns: Decimal
series.is_loan_count_exceeded()           # Returns: bool
series.is_loan_amount_exceeded()          # Returns: bool
series.is_any_threshold_exceeded()        # Returns: bool

# Permission checking
series.can_create_loan()                  # Returns: bool
series.can_create_release()               # Returns: bool

# Deactivation management
series.check_and_apply_deactivation()     # Returns: (bool, str)
series.get_guardrail_status()             # Returns: dict with full status
```

### check_and_apply_deactivation() Details

**Purpose**: Check thresholds and apply deactivation rules
**Automatic**: Called automatically when loans are created/deleted
**Returns**: Tuple of (was_deactivated: bool, reason: str)

**Example**:
```python
series = Series.objects.get(name="TEST")
series.loan_count_threshold = 10
series.deactivation_rule = "LOANS"
series.save()

was_deactivated, reason = series.check_and_apply_deactivation()
# Returns: (True, "Loan count (100) reached threshold (10)")

if was_deactivated:
    print(f"Series deactivated: {reason}")
```

### get_guardrail_status() Details

**Purpose**: Get comprehensive status of thresholds (for dashboards/reports)
**Returns**: Dictionary with all relevant fields

**Example**:
```python
status = series.get_guardrail_status()
print(status)
# Output:
# {
#     'series_id': 1,
#     'series_name': 'GOLD-1',
#     'is_active': True,
#     'deactivation_rule': 'LOANS',
#     'deactivated_for_loans': True,
#     'deactivated_for_releases': False,
#     'deactivation_date': datetime(2026, 3, 16, 10, 30),
#     'reason': 'Loan count (500) reached threshold (500)',
#     'loan_count_threshold': 500,
#     'loan_amount_threshold': None,
#     'current_loan_count': 500,
#     'current_loan_amount': 4500000.00,
#     'is_loan_count_exceeded': True,
#     'is_loan_amount_exceeded': False,
#     'can_create_loan': False,
#     'can_create_release': True,
# }
```

## Form Integration

### LoanForm Changes

```python
# OLD
series = forms.ModelChoiceField(
    queryset=Series.objects.filter(is_active=True),
    ...
)

# NEW - Automatically filters deactivated series
series = forms.ModelChoiceField(
    queryset=Series.objects.active_for_loans(),
    ...
)
```

### ReleaseForm Changes

```python
# OLD
loan = forms.ModelChoiceField(
    queryset=GivenLoan.objects.filter(release__isnull=True),
    ...
)

# NEW - Only shows loans from series that allow releases
loan = forms.ModelChoiceField(
    queryset=GivenLoan.objects.filter(
        release__isnull=True,
        series__in=Series.objects.active_for_releases()
    ),
    ...
)
```

## Signal Handlers

### Automatic Deactivation on Loan Save/Delete

```python
# In signals.py
@receiver(post_save, sender=GivenLoan)
@receiver(post_delete, sender=GivenLoan)
def check_series_guardrails(sender, instance, **kwargs):
    series = instance.series
    was_deactivated, reason = series.check_and_apply_deactivation()
    if was_deactivated:
        logger.warning(
            f"Series '{series}' deactivated. Rule: {series.deactivation_rule}"
        )
```

**Triggered When**:
- Loan is created
- Loan is updated
- Loan is deleted
- Any related data changes (LoanItem, etc.)

## Monitoring & Reporting

### Get All Deactivated Series

```python
# Series deactivated for loans
deactivated_for_loans = Series.objects.filter(deactivated_for_loans=True)

# Series deactivated for releases
deactivated_for_releases = Series.objects.filter(deactivated_for_releases=True)

# Series near threshold
near_threshold = []
for series in Series.objects.all():
    if series.loan_count_threshold:
        pct = (series.get_current_loan_count() / series.loan_count_threshold) * 100
        if pct > 80:  # 80% of limit
            near_threshold.append({
                'series': series,
                'usage_percent': pct
            })
```

### Admin Dashboard Status

The Series admin now shows a `guardrail_status` display:
- ✓ Active - Series is fully operational
- ⚠️ Threshold exceeded - At least one threshold breached
- 🔒 Loans disabled - Cannot create new loans
- 🔒 Releases disabled - Cannot create new releases
- 🔒 Locked (loans & releases) - Completely deactivated

## Best Practices

### 1. **Setting Appropriate Thresholds**
   - Start with conservative limits
   - Monitor usage patterns before setting final thresholds
   - Review and adjust quarterly

### 2. **Testing**
   - Test in sandbox/test tenant first
   - Verify form filtering works correctly
   - Check signal handlers in logs

### 3. **Communication**
   - Notify branch managers before enabling guardrails
   - Provide alternative series for users when one is deactivated
   - Track deactivation reasons for future review

### 4. **Monitoring**
   - Regularly review deactivated series
   - Check for series approaching thresholds (80%+ usage)
   - Audit deactivation reasons and dates

## Troubleshooting

### Issue: Series doesn't disappear from loan form even though threshold exceeded

**Solution**: 
1. Check if `deactivation_rule` is set (cannot be "NONE")
2. Verify `deactivated_for_loans` is True
3. Clear any form caching
4. Check signal logs for errors

### Issue: Signal handler not triggering deactivation

**Solution**:
1. Verify migration was applied: `python manage.py showmigrations girvi`
2. Check signals are registered in `__init__.py`
3. Verify threshold values are set
4. Check logs for exceptions in `check_series_guardrails`

### Issue: Can still create releases in deactivated series

**Solution**:
1. Verify `deactivated_for_releases` is True (not just `deactivated_for_loans`)
2. Check deactivation rule is "RELEASES" or "BOTH"
3. Verify ReleaseForm is using `active_for_releases()` manager

## Future Enhancements

- [ ] Admin actions to bulk enable/disable series
- [ ] Email alerts when thresholds are approached
- [ ] Graphical dashboard showing series capacity
- [ ] Historical tracking of deactivation/reactivation events
- [ ] Configurable threshold alert percentages (e.g., alert at 80%)
- [ ] Time-based deactivation (e.g., disable on certain dates)
- [ ] Scheduled reactivation if loan amounts decrease
