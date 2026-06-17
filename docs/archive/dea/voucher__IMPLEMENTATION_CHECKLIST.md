---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# âœ… Voucher CRUD Implementation Checklist

## Overview
Complete checklist for implementing and testing the Voucher CRUD system.

---

## Phase 1: Setup & Configuration (15 minutes)

### Pre-Implementation
- [ ] Review `VOUCHER_ARCHITECTURE.md` - understand the design
- [ ] Review `FILES_CREATED.md` - see what was added
- [ ] Backup your database (safety first!)
- [ ] Stop your development server (if running)

### Configuration
- [ ] All files are in place (no manual copying needed)
- [ ] `apps/tenant_apps/dea/views/voucher.py` exists âœ“
- [ ] `forms.py` has new form classes âœ“
- [ ] `tables.py` has new table classes âœ“
- [ ] `filters.py` has VoucherFilter âœ“
- [ ] `urls.py` has new URL patterns âœ“

### Dependencies
- [ ] Django 3.2+ installed (check: `python manage.py --version`)
- [ ] django-tables2 installed (check: `python manage.py shell`)
- [ ] django-filter installed
- [ ] crispy-forms installed

---

## Phase 2: Create Missing Templates (30 minutes)

### Create Include Templates
Run from your project root:
```bash
mkdir -p templates/includes
```

Create 3 files (templates from VOUCHER_IMPLEMENTATION.md):

- [ ] `templates/includes/field_input.html` - Text input wrapper
- [ ] `templates/includes/field_select.html` - Select dropdown wrapper
- [ ] `templates/includes/field_textarea.html` - Textarea wrapper

### Verify Templates Exist
```bash
ls -la templates/includes/
# Should show 3 files
```

---

## Phase 3: Test Basic Functionality (30 minutes)

### Start Django
```bash
python manage.py runserver
```

### Test List View
- [ ] Navigate to `http://localhost:8000/dea/vouchers/`
- [ ] Page should load without errors
- [ ] Displays summary cards (Total, Draft, Posted, Reversed)
- [ ] Shows filter panel on left
- [ ] Shows empty table with "No vouchers found" message

### Test Create View
- [ ] Click "New Voucher" button
- [ ] Form loads with all fields
- [ ] Click "Create Voucher"
- [ ] Voucher created successfully (redirects to detail)

### Test Detail View
- [ ] Voucher details display correctly
- [ ] Status shows as "Draft"
- [ ] All buttons visible: Edit, Delete, Post
- [ ] No Journal Entries section (not posted yet)

### Test Edit View
- [ ] Click "Edit" button
- [ ] Edit the description
- [ ] Click "Update Voucher"
- [ ] Changes saved (check detail view)

### Test Filter
- [ ] On List view, click Filter
- [ ] Filter should be sticky (form stays filled)

### Test List Pagination
- [ ] Create multiple vouchers (at least 30)
- [ ] List should paginate (25 per page)
- [ ] Pagination controls visible

---

## Phase 4: Implement Line Items (2-3 hours)

### Decision: How to Store Line Items?
Choose one:
- [ ] Option A: Create `VoucherLineItem` model
- [ ] Option B: Extract from LedgerTransaction when needed
- [ ] Option C: Store as JSON field

**Recommended:** Option B (simplest initially)

### Implement `_get_line_items()`
In `views/voucher.py`, update method:
```python
def _get_line_items(self, voucher):
    # If posted, get from LedgerTransactions
    if voucher.status == 'POSTED':
        items = []
        for je in voucher.journal_entries.all():
            for ltxn in je.ltxns.all():
                items.append({
                    'ledger_dr': ltxn.ledgerno_dr.name,
                    'ledger_cr': ltxn.ledgerno.name,
                    'amount': ltxn.amount,
                    'side': 'DEBIT/CREDIT'
                })
        return items
    # Otherwise return empty (draft state)
    return []
```

- [ ] Implement actual logic
- [ ] Test detail view shows line items

### Implement `_calculate_totals()`
In `views/voucher.py`, update method:
```python
def _calculate_totals(voucher):
    total_debit = Decimal('0')
    total_credit = Decimal('0')
    
    # Get from LedgerTransactions
    for je in voucher.journal_entries.all():
        for ltxn in je.ltxns.all():
            total_debit += ltxn.ledgerno_dr.amount
            total_credit += ltxn.ledgerno.amount
    
    return total_debit, total_credit
```

- [ ] Implement actual logic
- [ ] Test post_voucher() can validate balance

---

## Phase 5: Implement Journal Entry Creation (1-2 hours)

### Implement `_create_journal_entry()`
In `views/voucher.py`, update method:

```python
def _create_journal_entry(voucher, period, posted_by, is_reversal=False):
    from django.utils import timezone
    
    je = JournalEntry.objects.create(
        voucher=voucher,
        period=period,
        posted_by=posted_by,
        posted_at=timezone.now(),
        desc=f"Entry from {voucher.voucher_type.name}"
    )
    
    # Create transactions from line items
    for line in voucher.get_line_items():
        if is_reversal:
            # Swap debit/credit
            dr = line['ledger_cr']
            cr = line['ledger_dr']
        else:
            dr = line['ledger_dr']
            cr = line['ledger_cr']
        
        # Create LedgerTransaction
        LedgerTransaction.objects.create_txn(
            journal_entry=je,
            ledgerno=cr,
            ledgerno_dr=dr,
            amount=line['amount']
        )
    
    return je
```

- [ ] Implement actual logic
- [ ] Test post_voucher() creates JE
- [ ] Verify JE appears in detail view

---

## Phase 6: Test Posting & Reversing (45 minutes)

### Test Posting
- [ ] Create a test voucher with line items
- [ ] Click "Post to Journal"
- [ ] System should:
  - [ ] Validate balanced
  - [ ] Create JournalEntry
  - [ ] Lock voucher (change to POSTED)
  - [ ] Show success message
  - [ ] Disable Edit/Delete buttons
  - [ ] Show JE in detail view

### Test Failed Posting
- [ ] Create voucher with UNBALANCED items
- [ ] Click "Post"
- [ ] Should fail with "Not balanced" message
- [ ] Voucher stays DRAFT

### Test Reversing
- [ ] On posted voucher, click "Reverse"
- [ ] System should:
  - [ ] Create reversal JE
  - [ ] Mark voucher as REVERSED
  - [ ] Create opposite transactions
  - [ ] Balances should cancel out
  - [ ] Show success message

---

## Phase 7: Testing & Validation (1-2 hours)

### Manual Testing
- [ ] âœ… List view works
- [ ] âœ… Search/filter works  
- [ ] âœ… Pagination works
- [ ] âœ… Create works
- [ ] âœ… Edit works
- [ ] âœ… Delete works
- [ ] âœ… Detail view works
- [ ] âœ… Post works
- [ ] âœ… Reverse works
- [ ] âœ… Status badges display correctly
- [ ] âœ… Action buttons contextual
- [ ] âœ… No JavaScript errors
- [ ] âœ… Mobile responsive

### Database Testing
- [ ] âœ… Voucher created in DB
- [ ] âœ… JournalEntry created on post
- [ ] âœ… LedgerTransactions created
- [ ] âœ… Status changes correctly
- [ ] âœ… Reversals link correctly (is_reversal_of)

### Edge Cases
- [ ] Cannot edit posted voucher
- [ ] Cannot delete posted voucher
- [ ] Cannot post already posted
- [ ] Cannot reverse draft
- [ ] Multiple reversals handled

---

## Phase 8: Add Signal Handlers (Optional but Recommended)

### Create signals.py
```python
# apps/tenant_apps/dea/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import JournalEntry, LedgerTransaction, AccountTransaction

@receiver(post_save, sender=JournalEntry)
def update_balances_on_je_create(sender, instance, created, **kwargs):
    """Auto-update GL and account balances when JE is posted"""
    if not created:
        return
    
    # Update ledger balances
    for ltxn in instance.ltxns.all():
        ltxn.ledgerno.update_balance()
        ltxn.ledgerno_dr.update_balance()
    
    # Update account balances
    for atxn in instance.atxns.all():
        atxn.account.update_balance()
```

- [ ] Create signals.py
- [ ] Register in apps.py

---

## Phase 9: Add Permissions (Optional)

### Create Django Permissions
```python
# In Voucher model Meta
class Meta:
    permissions = [
        ('can_post_voucher', 'Can post vouchers'),
        ('can_reverse_voucher', 'Can reverse vouchers'),
    ]
```

- [ ] Add to model
- [ ] Run migrations: `python manage.py makemigrations && migrate`
- [ ] Add checks in views:
  - [ ] `@permission_required('dea.can_post_voucher')`
  - [ ] `@permission_required('dea.can_reverse_voucher')`

---

## Phase 10: Write Unit Tests

### Create test file
```bash
# apps/tenant_apps/dea/tests/test_voucher.py

from django.test import TestCase
from ..models import Voucher, VoucherType, JournalEntry
from ..views import VoucherListView

class VoucherListViewTest(TestCase):
    def setUp(self):
        self.voucher_type = VoucherType.objects.create(name='Invoice')
    
    def test_list_view_renders(self):
        response = self.client.get('/dea/vouchers/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Vouchers')
    
    # ... more tests
```

- [ ] Create test_voucher.py
- [ ] Write test cases
- [ ] Run tests: `python manage.py test apps.tenant_apps.dea.tests.test_voucher`
- [ ] All tests pass

---

## Phase 11: Integration with Business Documents

### Add to Invoice/Loan/Payment Models
```python
# In your business doc model
def create_voucher(self):
    """Create accounting voucher from this document"""
    from django.contrib.contenttypes.models import ContentType
    from dea.models import Voucher, VoucherType
    
    voucher_type = VoucherType.objects.get(name='Invoice')
    # ... create lines, etc.
    return voucher
```

- [ ] Add create_voucher() to each business doc
- [ ] Add "Create Voucher" button to detail views
- [ ] Test integration flow

---

## Phase 12: Go Live Checklist

### Security
- [ ] Permissions enforced
- [ ] CSRF tokens in forms
- [ ] SQL injection prevented (ORM used)
- [ ] XSS prevented (templates escaped)

### Performance
- [ ] Queries optimized (select_related, prefetch_related)
- [ ] Pagination working (reduces DB load)
- [ ] Indexes on voucher_date, status (at minimum)

### Documentation
- [ ] Code commented
- [ ] README updated
- [ ] API documented
- [ ] Standard operating procedures written

### Testing
- [ ] Unit tests written and passing
- [ ] Integration tests passing
- [ ] Manual testing complete
- [ ] Edge cases handled

### Deployment
- [ ] Database migrations applied
- [ ] Static files collected
- [ ] Environment variables set
- [ ] Backups taken
- [ ] Monitoring enabled

---

## Troubleshooting

### Issue: Templates not found
**Solution:** Create include templates (Phase 2)

### Issue: Filter dropdown empty
**Solution:** Check VoucherType records exist in DB

### Issue: Post fails with "No period"
**Solution:** Create accounting periods first

### Issue: Line items not showing
**Solution:** Implement _get_line_items() (Phase 4)

### Issue: JE not created on post
**Solution:** Implement _create_journal_entry() (Phase 5)

---

## Success Criteria

âœ… All tests pass  
âœ… All views render without errors  
âœ… Can create voucher  
âœ… Can edit draft voucher  
âœ… Can post voucher (creates JE)  
âœ… Can reverse voucher (creates opposite JE)  
âœ… GL balances update  
âœ… All filters work  
âœ… Pagination works  
âœ… Status badges show correctly  
âœ… Mobile responsive  
âœ… No security issues  
âœ… Good performance  

---

## Timeline Estimate

| Phase | Task | Time |
|-------|------|------|
| 1 | Setup & config | 15 min |
| 2 | Create templates | 30 min |
| 3 | Test basic | 30 min |
| 4 | Line items | 2-3 hrs |
| 5 | Journal entries | 1-2 hrs |
| 6 | Test post/reverse | 45 min |
| 7 | Full testing | 1-2 hrs |
| 8 | Signals | 1 hr (opt) |
| 9 | Permissions | 1 hr (opt) |
| 10 | Unit tests | 2-3 hrs |
| 11 | Integration | 2-3 hrs |
| 12 | Go live | 1-2 hrs |
| **TOTAL** | | **15-22 hrs** |

*Phases 1-7 are critical. Remaining are optional but recommended.*

---

## Get Help

If stuck, refer to:
1. `VOUCHER_IMPLEMENTATION.md` - Implementation details
2. Code comments in `views/voucher.py` - Docstrings
3. `VOUCHER_QUICK_REFERENCE.md` - API reference
4. `FILES_CREATED.md` - File structure
5. Django docs - General framework help

---

## Success!

When you complete all phases:
âœ… Full working Voucher CRUD system  
âœ… Can post transactions to journal  
âœ… Can reverse transactions  
âœ… GL balances update automatically  
âœ… Production-ready code  

You did it! ðŸŽ‰

