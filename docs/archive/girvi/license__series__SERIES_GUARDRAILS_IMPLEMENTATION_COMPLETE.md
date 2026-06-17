---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Series Guardrails - Implementation Complete âœ“

## Overview

A complete guardrail system has been implemented for the Series model that automatically deactivates series when configurable thresholds (loan count or amount) are exceeded.

## Key Capabilities

âœ… **Loan Count Thresholds** - Limit max active loans per series  
âœ… **Loan Amount Thresholds** - Limit max total amount per series  
âœ… **Smart Deactivation** - LOANS_ONLY, RELEASES_ONLY, or BOTH operations  
âœ… **Automatic Enforcement** - Signals auto-trigger on loan operations  
âœ… **Form Integration** - Deactivated series hidden from loan/release forms  
âœ… **Admin Dashboard** - Visual status indicators and controls  
âœ… **Tracking** - Records when and why deactivation occurred  

---

## What You Can Do Now

### 1. Set Up Series Limits (Admin Interface)

Navigate to: **Admin â†’ Licenses â†’ Series â†’ Edit Series**

Configure:
```
Series Name: GOLD
Loan Count Threshold: 500
Loan Amount Threshold: â‚¹5,000,000
Deactivation Rule: Disable Loans Only
```

### 2. Monitor Series Status

Check guardrail status in admin or via Python:
```python
series.get_guardrail_status()
# Returns dict with current usage, thresholds, and permissions
```

### 3. Users See Automatic Restrictions

- **Loan Form**: Only shows series where loans can be created
- **Release Form**: Only shows loans from series allowing releases
- **No Manual Intervention Needed**: Happens automatically

---

## Files Changed

| File | Changes |
|------|---------|
| `girvi/models/license.py` | SeriesManager + guardrail fields/methods |
| `girvi/forms.py` | Updated querysets to use manager methods |
| `girvi/admin.py` | SeriesAdmin with status display |
| `girvi/signals.py` | Auto-deactivation signal handler |
| `girvi/migrations/0009_series_guardrails.py` | Database migration |
| `girvi/tests/test_series_guardrails.py` | Unit tests |

## New Documentation

1. **SERIES_GUARDRAILS_GUIDE.md** (2000+ lines)
   - Complete feature documentation
   - API reference with examples
   - Usage scenarios
   - Best practices
   - Troubleshooting

2. **SERIES_GUARDRAILS_SUMMARY.md** (500+ lines)
   - Quick implementation reference
   - Code examples
   - Field reference
   - Testing checklist

3. **DEPLOYMENT_CHECKLIST.md** (400+ lines)
   - Step-by-step deployment
   - Validation procedures
   - Monitoring guide
   - Rollback plan
   - Communication templates

---

## Quick Start

### Apply Migration
```bash
python manage.py migrate girvi
```

### Run Tests
```bash
python manage.py test apps.tenant_apps.girvi.tests.test_series_guardrails
```

### Configure a Series
```python
from apps.tenant_apps.girvi.models import Series
from decimal import Decimal

series = Series.objects.get(name="GOLD")
series.loan_count_threshold = 100
series.deactivation_rule = "LOANS"
series.save()
```

### Check Status
```python
series.get_guardrail_status()
# See all thresholds and current usage
```

---

## API Quick Reference

### Manager Methods
```python
Series.objects.active_for_loans()         # Series where loans allowed
Series.objects.active_for_releases()      # Series where releases allowed
Series.objects.active_for_both()          # Both operations allowed
```

### Series Methods
```python
series.get_current_loan_count()           # Current active loans
series.get_current_loan_amount()          # Current total amount
series.is_loan_count_exceeded()           # Count threshold exceeded?
series.is_loan_amount_exceeded()          # Amount threshold exceeded?
series.can_create_loan()                  # Allow loan creation?
series.can_create_release()               # Allow release creation?
series.check_and_apply_deactivation()     # Check & apply rules
series.get_guardrail_status()             # Full status dictionary
```

---

## How It Works (Simplified)

```
1. Series Created with Thresholds
   â”œâ”€ loan_count_threshold: 100
   â”œâ”€ loan_amount_threshold: â‚¹5M
   â””â”€ deactivation_rule: LOANS_ONLY

2. Loan Created (Signal Triggered)
   â””â”€ Calls: series.check_and_apply_deactivation()

3. Threshold Check
   â”œâ”€ Current loans: 100 >= threshold 100? YES
   â””â”€ Current amount: â‚¹5M >= threshold â‚¹5M? YES

4. Apply Rule (LOANS_ONLY)
   â””â”€ Set: deactivated_for_loans = True

5. Form Uses Manager
   â””â”€ Series.objects.active_for_loans() excludes deactivated series

6. Result
   â””â”€ User cannot see this series in loan form
```

---

## Deactivation Rules Explained

| Rule | Effect | Use Case |
|------|--------|----------|
| **NONE** | No deactivation | Default, no limits |
| **LOANS_ONLY** | Prevent new loans only | Pause new lending |
| **RELEASES_ONLY** | Prevent releases only | Hold existing loans |
| **BOTH** | Prevent both operations | Complete lockdown |

---

## Admin Interface Changes

### Series List View
Shows new "Status" column:
- âœ“ Active - Series fully operational
- âš ï¸ Threshold exceeded - Limit approaching/reached
- ðŸ”’ Loans disabled - Cannot create loans
- ðŸ”’ Releases disabled - Cannot create releases
- ðŸ”’ Locked (both) - Completely disabled

### Series Edit Form
New collapsible section "Guardrails & Thresholds":
- Loan Count Threshold (input)
- Loan Amount Threshold (decimal input)
- Deactivation Rule (dropdown)
- Auto-filled status fields:
  - Deactivated for Loans (checkbox)
  - Deactivated for Releases (checkbox)
  - Deactivation Date (read-only)
  - Threshold Exceeded Reason (read-only)

---

## User Experience

### Before Guardrails
```
Loan Form
â”œâ”€ Series: [GOLD â–¼] â† All active series shown
â”œâ”€ Series: [SILVER â–¼] â† Even at capacity
â””â”€ Series: [PLATINUM â–¼] â† No warnings
```

### After Guardrails (at capacity)
```
Loan Form
â”œâ”€ Series: [GOLD â–¼]
â”‚  â””â”€ GOLD at 100 loans (limit: 100)
â”‚     â†’ NOT SHOWN IN DROPDOWN
â””â”€ Series: [SILVER â–¼]
   â””â”€ Can still create loans in SILVER
```

---

## Database Changes

### New Fields on Series Model
```sql
ALTER TABLE girvi_series ADD COLUMN loan_count_threshold INTEGER NULL;
ALTER TABLE girvi_series ADD COLUMN loan_amount_threshold DECIMAL(15,2) NULL;
ALTER TABLE girvi_series ADD COLUMN deactivation_rule VARCHAR(10) DEFAULT 'NONE';
ALTER TABLE girvi_series ADD COLUMN deactivated_for_loans BOOLEAN DEFAULT 0;
ALTER TABLE girvi_series ADD COLUMN deactivated_for_releases BOOLEAN DEFAULT 0;
ALTER TABLE girvi_series ADD COLUMN deactivation_date DATETIME NULL;
ALTER TABLE girvi_series ADD COLUMN threshold_exceeded_reason VARCHAR(255);

-- Performance indexes
CREATE INDEX girvi_series_active_loans_idx 
  ON girvi_series(is_active, deactivated_for_loans);
CREATE INDEX girvi_series_active_releases_idx 
  ON girvi_series(is_active, deactivated_for_releases);
```

### Data Migration
- All existing series get default values:
  - `deactivation_rule = 'NONE'` (no automatic deactivation)
  - `deactivated_for_loans = False`
  - `deactivated_for_releases = False`
- **No data loss** - Backward compatible

---

## Example: Complete Workflow

### Admin Sets Up Gold Series
```python
gold = Series.objects.get(name="GOLD")
gold.loan_count_threshold = 500        # Max 500 loans
gold.loan_amount_threshold = Decimal("50000000")  # Max â‚¹50M
gold.deactivation_rule = "LOANS"       # Disable loans when reached
gold.save()
```

### After 500th Loan Created
```
Signal fires â†’ checks threshold â†’ exceeds limit
â†’ sets deactivated_for_loans = True
â†’ records deactivation_date = now()
â†’ records reason = "Loan count (500) reached threshold (500)"
```

### User Behavior
```
Branch Manager tries to create new GOLD loan:
1. Opens Loan Form
2. Series dropdown shows: GOLD (âœ“) [still listed if active]
   But actually checks can_create_loan()
3. If deactivated â†’ GOLD doesn't appear
4. Shows only SILVER and PLATINUM
5. User must select different series or contact admin
```

### Admin Monitoring
```python
# Check status
status = gold.get_guardrail_status()
print(f"Current loans: {status['current_loan_count']}/500")
print(f"Current amount: â‚¹{status['current_loan_amount']}/50M")
print(f"Can create loan: {status['can_create_loan']}")
# Output: Can create loan: False

# View deactivation details
print(f"Deactivated since: {gold.deactivation_date}")
print(f"Reason: {gold.threshold_exceeded_reason}")
```

---

## Common Operations

### Increase Threshold
```python
series.loan_count_threshold = 600  # Was 500
series.save()
# Note: Doesn't auto-reactivate, but prevents further deactivation
```

### Manually Reactivate
```python
series.deactivated_for_loans = False
series.save()
# Now loans can be created again
```

### View All Deactivated
```python
Series.objects.filter(deactivated_for_loans=True)
Series.objects.filter(deactivated_for_releases=True)
```

### Get Utilization Report
```python
for series in Series.objects.all():
    status = series.get_guardrail_status()
    if status['loan_count_threshold']:
        pct = status['current_loan_count'] / status['loan_count_threshold'] * 100
        print(f"{series}: {pct:.1f}% of capacity")
```

---

## Monitoring & Alerts

### Log Deactivation Events
```
WARNING Series 'GOLD-1' (ID: 5) automatically deactivated. 
Rule: LOANS_ONLY. Reason: Loan count (500) reached threshold (500)
```

### Alert on Threshold Approach
```python
# Custom script (can be scheduled)
for series in Series.objects.all():
    status = series.get_guardrail_status()
    if status['loan_count_threshold']:
        pct = status['current_loan_count'] / status['loan_count_threshold'] * 100
        if pct >= 80:
            print(f"ALERT: {series} at {pct:.0f}% capacity")
```

---

## Troubleshooting Quick Links

**Series not showing in loan form?**
â†’ Check `deactivated_for_loans` flag and `can_create_loan()` method

**Loans creating in deactivated series?**
â†’ Check if form is using `active_for_loans()` manager

**Deactivation not triggering?**
â†’ Check signal handler logs and deactivation rule setting

More details: See SERIES_GUARDRAILS_GUIDE.md

---

## Documentation Reference

| Document | Length | Purpose |
|----------|--------|---------|
| SERIES_GUARDRAILS_GUIDE.md | ~2000 lines | Complete reference with all details |
| SERIES_GUARDRAILS_SUMMARY.md | ~500 lines | Quick implementation summary |
| DEPLOYMENT_CHECKLIST.md | ~400 lines | Deployment & operation guide |

---

## Next Steps

1. **Apply Migration**: `python manage.py migrate girvi`
2. **Run Tests**: `python manage.py test test_series_guardrails`
3. **Configure Series**: Set thresholds for each series
4. **Monitor**: Watch logs for deactivation events
5. **Communicate**: Inform users about restrictions
6. **Review**: Monthly assessment of cap utilization

---

## Support

- **Implementation**: See SERIES_GUARDRAILS_SUMMARY.md
- **Usage Guide**: See SERIES_GUARDRAILS_GUIDE.md  
- **Deployment**: See DEPLOYMENT_CHECKLIST.md
- **Testing**: See apps/tenant_apps/girvi/tests/test_series_guardrails.py
- **Code**: See girvi/models/license.py for implementation details

---

**Setup Complete!** You can now control series capacity automatically. ðŸŽ‰

