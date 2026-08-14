---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Series Guardrails - Deployment Checklist

## Pre-Deployment

### Code Changes Review
- [x] Series model updated with new fields
- [x] Series manager added with filtering methods
- [x] SeriesForm updated with guardrail fields
- [x] LoanForm uses `active_for_loans()` manager
- [x] ReleaseForm uses `active_for_releases()` manager
- [x] SeriesAdmin updated with status display
- [x] Signal handlers added for auto-deactivation
- [x] Migration created for database changes
- [x] Unit tests created

### Files Modified
1. **apps/tenant_apps/girvi/models/license.py** - Series model + SeriesManager
2. **apps/tenant_apps/girvi/forms.py** - SeriesForm, LoanForm, ReleaseForm
3. **apps/tenant_apps/girvi/admin.py** - SeriesAdmin improvements
4. **apps/tenant_apps/girvi/signals.py** - Guardrail checking signals
5. **apps/tenant_apps/girvi/migrations/0009_series_guardrails.py** - Database migration

### New Documentation
1. **SERIES_GUARDRAILS_GUIDE.md** - Complete usage guide
2. **SERIES_GUARDRAILS_SUMMARY.md** - Implementation summary
3. **DEPLOYMENT_CHECKLIST.md** - This file

### New Tests
1. **apps/tenant_apps/girvi/tests/test_series_guardrails.py** - Unit tests

---

## Deployment Steps

### Stage 1: Development/Staging

```bash
# 1. Apply migration
python manage.py migrate girvi

# 2. Run tests
python manage.py test apps.tenant_apps.girvi.tests.test_series_guardrails

# 3. Check no errors
python manage.py check
```

### Stage 2: Configuration Review

- [ ] Review existing Series in the system
- [ ] Plan guardrail thresholds for each series
- [ ] Document thresholds in spreadsheet/wiki
- [ ] Identify series that need immediate deactivation
- [ ] Plan communication with stakeholders

### Stage 3: Production Deployment

```bash
# 1. Backup database
python manage.py dumpdata > backup_pre_guardrails.json

# 2. Apply migration
python manage.py migrate girvi

# 3. Verify migration applied
python manage.py showmigrations girvi
# Should show: [X] 0009_series_guardrails

# 4. Verify forms work
# Test loan creation âœ“
# Test release creation âœ“
# Check Series dropdown in both forms âœ“
```

### Stage 4: Configuration in Production

```python
# Via Django admin or shell script
from apps.tenant_apps.girvi.models import Series
from decimal import Decimal

# Example 1: Gold series with count limit
gold_series = Series.objects.get(name="GOLD")
gold_series.loan_count_threshold = 500
gold_series.deactivation_rule = "LOANS"
gold_series.save()

# Example 2: Silver series with amount limit
silver_series = Series.objects.get(name="SILVER")
silver_series.loan_amount_threshold = Decimal("10000000")  # â‚¹10M
silver_series.deactivation_rule = "BOTH"
silver_series.save()
```

### Stage 5: Validation

```bash
# Verify queries work
python manage.py shell

>>> from apps.tenant_apps.girvi.models import Series
>>> 
>>> # Test manager
>>> Series.objects.active_for_loans().count()
>>> Series.objects.active_for_releases().count()
>>>
>>> # Test status
>>> s = Series.objects.first()
>>> s.get_guardrail_status()
>>>
>>> # Test deactivation check
>>> s.check_and_apply_deactivation()
```

---

## Post-Deployment Validation

### Functional Tests

- [ ] Loan form shows only `active_for_loans()` series
- [ ] Release form shows only loans from `active_for_releases()` series
- [ ] Series admin shows guardrail status indicators
- [ ] Can configure thresholds in admin
- [ ] Thresholds values saved correctly
- [ ] Deactivation rule applies correctly
- [ ] Signals trigger on loan save/delete
- [ ] Logs show deactivation events

### Data Integrity

```python
# Verify no data corruption
>>> Series.objects.all().count()
>>> Series.objects.filter(deactivated_for_loans=True).count()
>>> Series.objects.filter(deactivated_for_releases=True).count()
>>> Series.objects.filter(is_active=True).count()
```

### Performance

```bash
# Check for N+1 queries on loan form
# Should use select_related and use optimized manager

# Check admin list view performance
# Should use indexes on deactivation fields
```

---

## Monitoring & Alerting

### Initial Monitoring (First Week)

```bash
# Monitor logs for deactivation events
tail -f logs/django.log | grep "automatically deactivated"

# Check for any signal errors
tail -f logs/django.log | grep "check_series_guardrails"

# Monitor form filtering
tail -f logs/django.log | grep "active_for_loans\|active_for_releases"
```

### Weekly Review

```python
# Check for series near thresholds
from apps.tenant_apps.girvi.models import Series

for series in Series.objects.all():
    if series.loan_count_threshold:
        pct = (series.get_current_loan_count() / series.loan_count_threshold) * 100
        if pct >= 80:
            print(f"WARNING: {series} at {pct:.1f}% of loan count threshold")
    
    if series.loan_amount_threshold:
        pct = (series.get_current_loan_amount() / series.loan_amount_threshold) * 100
        if pct >= 80:
            print(f"WARNING: {series} at {pct:.1f}% of amount threshold")

# Audit deactivations
deactivated = Series.objects.filter(
    deactivated_for_loans=True
) | Series.objects.filter(deactivated_for_releases=True)

for s in deactivated:
    print(f"{s}: {s.threshold_exceeded_reason}")
```

### Monthly Review

1. Review all deactivated series
2. Check if thresholds need adjustment
3. Analyze trends in loan creation
4. Plan for capacity expansion
5. Document lessons learned

---

## Rollback Plan

If issues occur:

### Immediate Rollback

```bash
# If migration causes issues
python manage.py migrate girvi 0008_remove_loanchangelog_loan_loanchangelog_content_type_and_more

# Restore from backup
python manage.py loaddata backup_pre_guardrails.json
```

### Code Rollback

Revert changes in:
1. `license.py` - Remove Series manager and guardrail methods
2. `forms.py` - Revert to old Series queryset filtering
3. `admin.py` - Remove guardrail_status display
4. `signals.py` - Remove check_series_guardrails handler

### Partial Rollback (Keep Migration)

If migration is fine but code has issues:

```python
# Disable guardrails by setting all to NONE
Series.objects.all().update(deactivation_rule="NONE")

# Or disable auto-deactivation flags
Series.objects.all().update(
    deactivated_for_loans=False,
    deactivated_for_releases=False
)
```

---

## Troubleshooting Guide

### Issue: Series not deactivating when threshold reached

**Debug Steps:**
```python
# Check series config
series.loan_count_threshold
series.deactivation_rule
series.deactivated_for_loans

# Check current counts
series.get_current_loan_count()
series.is_loan_count_exceeded()

# Manually trigger check
was_deactivated, reason = series.check_and_apply_deactivation()
```

**Common Causes:**
- Deactivation rule is "NONE"
- Thresholds not set
- Signal handler not registered
- Loan count/amount calculated incorrectly

### Issue: Forms still show deactivated series

**Debug Steps:**
```python
# Test manager
list(Series.objects.active_for_loans())

# Check deactivation flags
Series.objects.filter(deactivated_for_loans=False).count()

# Verify form is using right queryset
# Check forms.py LoanForm
```

**Solution:**
- Clear any caching (Redis, browser, etc.)
- Restart Django server
- Verify LoanForm.series queryset uses active_for_loans()

### Issue: Signal handler not firing

**Debug Steps:**
```python
# Check signals are connected
from django.db.models.signals import post_save
from apps.tenant_apps.girvi.signals import check_series_guardrails

# Verify receiver is registered
post_save.has_listeners(GivenLoan)
```

**Solution:**
- Check signals.py is imported in apps.py
- Verify import path is correct
- Check logs for receiver exceptions

---

## Communication Plan

### For Administrators

**Email Template:**
```
Subject: Series Guardrails Feature Deployment

The system now includes automatic capacity controls for loan series.

KEY FEATURES:
- Set maximum loan count per series
- Set maximum loan amount per series
- Auto-disable loans and/or releases when limits reached
- Only active series shown in forms

ACTION REQUIRED:
1. Review configurations in Admin > Licenses > Series
2. Set appropriate thresholds for each series
3. Monitor deactivation events in logs

TIMELINE:
- Week 1: Configuration and testing
- Week 2: Monitor for issues
- Ongoing: Review deactivation events weekly
```

### For Users

**In-App Notification:**
```
"Series <name> has reached its limit and is no longer accepting new loans.
Please contact your administrator to increase the limit or use another series."
```

---

## Success Metrics

### Week 1
- [ ] Migration applied successfully
- [ ] No increase in error rates
- [ ] Series filtering working correctly
- [ ] Signals executing without errors

### Week 4
- [ ] Appropriate thresholds documented for all series
- [ ] No unexpected deactivations
- [ ] Forms performing normally
- [ ] Team comfortable with feature

### Month 3
- [ ] Guardrails preventing operational overloads
- [ ] Deactivations following documented policies
- [ ] Thresholds reviewed and adjusted as needed
- [ ] ROI: Improved operational control

---

## Next Phase Enhancements

- [ ] Admin action to bulk deactivate/reactivate series
- [ ] Email alerts when series approaches threshold
- [ ] Dashboard visualization of series capacity
- [ ] Historical tracking of deactivation/reactivation
- [ ] Scheduled deactivation rules (e.g., by date)
- [ ] Automatic reactivation if loan amounts decrease

---

**Ready to Deploy!** âœ“

For questions, refer to:
- SERIES_GUARDRAILS_GUIDE.md - Complete detailed guide
- SERIES_GUARDRAILS_SUMMARY.md - Quick reference
- test_series_guardrails.py - Test examples

