---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# JournalEntry `is_posted` Refactoring Summary

## What Changed

Refactored the `JournalEntry` model to remove the `is_posted` BooleanField and derive the posting status from the related `Voucher.status` instead.

## Why This Is Better

âœ… **Single Source of Truth**: Posting state is now derived from `Voucher.status` only
âœ… **Simplified Database**: Removed redundant field from database schema
âœ… **Reduced Migration**: Fewer database changes and migrations needed
âœ… **Less Room for Sync Errors**: Can't have entry and voucher with mismatched statuses
âœ… **Cleaner Architecture**: Status logic lives in one place (Voucher model)

## Changes Made

### 1. JournalEntry Model (`apps/tenant_apps/dea/models/journal.py`)

**Removed:**
- `is_posted` BooleanField
- Database indexes on `is_posted`

**Added:**
- `@property is_posted` that derives from `voucher.status`

```python
@property
def is_posted(self):
    """
    Derive posting status from voucher status.
    Posted if voucher is POSTED (not DRAFT, not REVERSED).
    """
    from .voucher import VoucherStatus
    return self.voucher.status == VoucherStatus.POSTED
```

**Updated Methods:**
- `__str__()`: Uses property automatically
- `clean()`: References voucher.status directly
- `delete()`: References voucher.status directly

### 2. Posting Engines

**Files Modified:**
- `apps/tenant_apps/dea/posting/engine.py`
- `apps/tenant_apps/dea/posting/engine_new.py`

**Changes:**
- Removed `is_posted=True` parameter from `JournalEntry.objects.create()`
- Property will return True automatically when voucher.status is POSTED

### 3. Dashboard View (`apps/tenant_apps/dea/views/dashboard.py`)

**Changed:**
- Filter: `is_posted=True` â†’ `voucher__status=VoucherStatus.POSTED`
- Uses reverse relation to access voucher status

### 4. Templates

**No Changes Needed!**
- `entry.is_posted` in templates continues to work
- Django templates can access properties just like fields
- Template code remains identical

## Benefits

| Aspect | Before | After |
|--------|--------|-------|
| Database Fields | 2 (is_posted + voucher FK) | 1 (voucher FK only) |
| Indexes | 2 | 0 |
| Sources of Truth | 2 (field + voucher status) | 1 (voucher status) |
| Sync Issues Possible | Yes | No |
| Query Overhead | Slightly faster | Minimal (normal FK join) |

## Query Impact

### Before
```python
JournalEntry.objects.filter(is_posted=True)  # Direct field
```

### After
```python
JournalEntry.objects.filter(voucher__status=VoucherStatus.POSTED)  # FK join
```

**Performance**: Negligible for realistic data sizes. Modern databases optimize FK joins efficiently.

## Migration Required

You'll need to create a migration to drop the `is_posted` field:

```bash
python manage.py makemigrations dea
python manage.py migrate dea
```

The migration will:
1. Drop the `is_posted` BooleanField
2. Drop the associated indexes
3. Keep journal_entries data intact (no data loss)

## Testing Checklist

âœ… Check property returns correct values:
```python
je = JournalEntry.objects.first()
print(je.is_posted)  # Should work as before
```

âœ… Verify in templates:
```django
{% if entry.is_posted %}
    Posted
{% endif %}
```

âœ… Dashboard alerts work:
- Check for unbalanced entries filter

âœ… Posting engine creates entries:
- Create and post a voucher
- Verify is_posted returns True

## Architecture Improvement

This follows the **DRY Principle** (Don't Repeat Yourself):
- Eliminates data duplication
- Single source of truth for posting state
- More maintainable long-term

The property pattern is ideal here because:
1. Posting state is purely derived (not independent)
2. The relationship is stable (FK won't change)
3. Performance impact is minimal

## Summary

âœ… Cleaner code architecture
âœ… Single source of truth
âœ… No redundant database field
âœ… Templates unchanged
âœ… Views updated
âœ… Engines simplified
âœ… Ready for migration

The refactoring maintains 100% backward compatibility at the code level (templates, views, properties all work the same way) while improving the underlying architecture.

