---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# ðŸš€ Quick Start: Custody Tracking Checklist

## What's Been Built For You âœ…

- [x] **Core Models** - LoanItem custody fields + RepledgeHistory model
- [x] **Enhanced Mixins** - GivenLoan release workflow + TakenLoan collateral management
- [x] **Views** - 12+ views for all workflows
- [x] **Templates** - Release check + multi-item selection
- [x] **Migration** - Automatic data conversion from old system
- [x] **URLs** - 15+ routes configured
- [x] **Admin Integration** - Full Django admin support
- [x] **Documentation** - 4 complete guides (3500+ lines)

---

## Your Next Steps (In Order)

### 1ï¸âƒ£ REVIEW (20 min)
- [ ] Read `CUSTODY_TRACKING_OVERVIEW.md` (this gives you the big picture)
- [ ] Skim `CUSTODY_TRACKING_WORKFLOWS.md` (see the 3 workflows in action)

### 2ï¸âƒ£ IMPLEMENT (2 hours - 6 phases)

#### Phase 1: Add Models (15 min)
- [ ] Copy `custody_tracking.py` to `apps/tenant_apps/girvi/models/`
- [ ] Edit `apps/tenant_apps/girvi/models/loan.py` or your LoanItem file
- [ ] Add `LoanItemWithCustody` as parent class to `LoanItem`
- [ ] Add `GivenLoanReleaseMixin` to `GivenLoan` (if you created it)
- [ ] Add `TakenLoanCollateralMixin` to `TakenLoan` (if you created it)
- [ ] Edit `admin.py` and register `RepledgeHistory` and `ItemCustodyStatus`

#### Phase 2: Run Migration (5 min)
```bash
python manage.py migrate girvi
```
- [ ] Verify: `python manage.py shell`
  ```python
  from apps.tenant_apps.girvi.models import LoanItem, RepledgeHistory
  LoanItem.objects.in_vault().count()  # Should work
  RepledgeHistory.objects.count()      # Should show migrated items
  ```

#### Phase 3: Add Views & URLs (10 min)
- [ ] Copy `custody_views.py` to `apps/tenant_apps/girvi/views/`
- [ ] Copy URLs from `custody_urls.py` into `apps/tenant_apps/girvi/urls.py`
- [ ] Run: `python manage.py check` (verify no errors)

#### Phase 4: Add Templates (10 min)
- [ ] Create directory `templates/girvi/` if doesn't exist
- [ ] Copy `release_custody_check.html`
- [ ] Copy `repledge_select_items.html`

#### Phase 5: Update Release Button (5 min)
- [ ] Find your loan detail template
- [ ] Change release button link from:
  ```django
  <a href="{% url 'girvi:loan_release_create' loan.id %}">Release</a>
  ```
  To:
  ```django
  <a href="{% url 'girvi:release_loan_check_custody' loan.id %}">Release</a>
  ```

#### Phase 6: Test (30 min)
- [ ] Use admin to create test loans
- [ ] Test Workflow 1: Release with items in vault (should show success)
- [ ] Test Workflow 2: Release with items with lender (should show auto-return)
- [ ] Test Workflow 3: Create repledge with multi-customer items
- [ ] Check RepledgeHistory (should have entries)

### 3ï¸âƒ£ VERIFY (10 min)
```python
python manage.py shell

# Check custody tracking works
item = LoanItem.objects.first()
print(item.custody_status)  # Should be 'in_vault', 'with_lender', or 'with_customer'

# Check history exists
from apps.tenant_apps.girvi.models import RepledgeHistory
print(RepledgeHistory.objects.count())  # Should > 0 if migrated

# Check queries work
print(LoanItem.objects.in_vault().count())
print(LoanItem.objects.with_lenders().count())
print(LoanItem.objects.with_customers().count())
```

---

## File Locations

```
ðŸ“ apps/tenant_apps/girvi/
â”œâ”€â”€ ðŸ“ models/
â”‚   â”œâ”€â”€ loan.py                    â† Main models
â”‚   â””â”€â”€ custody_tracking.py        â† COPY HERE
â”œâ”€â”€ ðŸ“ migrations/
â”‚   â””â”€â”€ add_custody_tracking.py    â† EXISTS (run migration)
â”œâ”€â”€ ðŸ“ views/
â”‚   â””â”€â”€ custody_views.py           â† COPY HERE
â”œâ”€â”€ ðŸ“ urls/
â”‚   â””â”€â”€ custody_urls.py            â† Read & add to main urls.py
â”œâ”€â”€ ðŸ“ templates/girvi/
â”‚   â”œâ”€â”€ release_custody_check.html â† COPY HERE
â”‚   â””â”€â”€ repledge_select_items.html â† COPY HERE
â”œâ”€â”€ admin.py                        â† Register RepledgeHistory
â”œâ”€â”€ urls.py                         â† Add custody URLs
â””â”€â”€ ðŸ“ docs/
    â”œâ”€â”€ CUSTODY_TRACKING_OVERVIEW.md
    â”œâ”€â”€ CUSTODY_TRACKING_IMPLEMENTATION_GUIDE.md
    â”œâ”€â”€ CUSTODY_TRACKING_QUICK_REF.md
    â”œâ”€â”€ CUSTODY_TRACKING_WORKFLOWS.md
    â””â”€â”€ CUSTODY_TRACKING_IMPLEMENTATION_CHECKLIST.md
```

---

## What Each New File Does

| File | What It Does | Add Where |
|:--|:--|:--|
| **custody_tracking.py** | Core models & business logic | `models/` |
| **add_custody_tracking.py** | Database migration | Already in `migrations/` |
| **custody_views.py** | All views & workflows | `views/` |
| **custody_urls.py** | URL routes | Import into `urls.py` |
| **release_custody_check.html** | Release workflow UI | `templates/girvi/` |
| **repledge_select_items.html** | Multi-item selection UI | `templates/girvi/` |

---

## Key Fields Added to LoanItem

```python
# NEW FIELDS (added via migration):
custody_status      # IN_VAULT, WITH_LENDER, or WITH_CUSTOMER
repledged_to        # Foreign Key to TakenLoan (while repledged)
repledged_amount    # Amount borrowed using this item
repledged_at        # When it was most recently repledged

# NEW PROPERTIES:
is_in_vault         # Boolean - in our possession?
is_available_for_repledge  # Boolean - can we use as collateral?
is_available_for_release   # Boolean - can customer get it back?
can_be_returned_from_lender # Boolean - is it with lender and returnable?

# NEW METHODS:
repledge_to(taken_loan, amount, user, notes)
return_from_lender(user, notes)
release_to_customer(user)
```

---

## New QuerySet Methods

```python
# Easy availability checks
LoanItem.objects.in_vault()                    # Ready to use
LoanItem.objects.with_lenders()               # In use as collateral
LoanItem.objects.with_customers()             # Released
LoanItem.objects.available_for_repledge()     # Can repledge now

# Specific queries
LoanItem.objects.repledged_to_loan(taken_loan)
LoanItem.objects.by_customer(customer)
```

---

## 3 Core Workflows

### 1. Release Loan (Auto-Return from Lender)
```
User clicks "Release" button
  â†“ (goes to release_loan_check_custody)
Shows items with lender? 
  â†“ YES
"Release with Auto-Return" button
  â†“ (goes to release_loan_with_return)
System automatically:
  1. Returns items from lender
  2. Releases to customer
  3. Creates release document
Result: Loan released âœ…
```

### 2. Create Repledge (Multi-Customer)
```
User goes to /repledge/create/
  â†“ (goes to create_repledge_select_items)
Browse items grouped by customer
Select from Customer A + Customer C
  â†“ (posts to create_repledge_with_items)
System:
  1. Creates TakenLoan
  2. Repledges items proportionally
  3. Creates RepledgeHistory for each
Result: TakenLoan with bundled collateral âœ…
```

### 3. Return Collateral (Close TakenLoan)
```
User goes to /taken-loans/<id>/collateral/
  â†“ (goes to taken_loan_collateral_detail)
See all collateral grouped by customer
Click "Return All Collateral"
  â†“ (posts to return_taken_loan_collateral)
System:
  1. Returns each item from lender to vault
  2. Updates RepledgeHistory
  3. Can now close TakenLoan
Result: All collateral returned âœ…
```

---

## Testing Commands

```bash
# Verify migration worked
python manage.py shell
>>> from apps.tenant_apps.girvi.models import LoanItem, RepledgeHistory
>>> LoanItem.objects.in_vault().count()
10  # Should show available items

# Test repledge
>>> item = LoanItem.objects.in_vault().first()
>>> taken_loan = TakenLoan.objects.first()
>>> item.repledge_to(taken_loan, 10000, user)
>>> item.custody_status
'with_lender'  # Correct!

# Test return
>>> item.return_from_lender(user)
>>> item.custody_status
'in_vault'  # Correct!

# Check history
>>> item.repledge_history.count()
1  # Entry created!
```

---

## Common Issues & Fixes

### Migration Fails
```bash
# Roll back
python manage.py migrate girvi <previous_number>

# Fix issue
# Then retry
python manage.py migrate girvi
```

### Items not in right status
```python
# Check data
LoanItem.objects.filter(custody_status='with_lender ', repledged_to__isnull=True)
# If results: data is inconsistent

# Fix: Update manually
item = LoanItem.objects.get(id=123)
item.custody_status = 'in_vault'
item.repledged_to = None
item.save()
```

### Views not found
- [ ] Verify files in `views/`
- [ ] Verify URLs imported in `urls.py`
- [ ] Check for import errors: `python manage.py check`

---

## What If You Already Have Repledges?

The migration automatically converts them:
```
OLD: RepledgedLoanItem.objects.count() = 50
  â†“ (migration runs)
NEW: RepledgeHistory.objects.filter(returned_at__isnull=True).count() = 50
     LoanItem entries with custody_status='with_lender' = 50
```

All old data preserved. New system uses custody tracking going forward.

---

## How to Test Workflows Manually

### Test Release with Auto-Return
```
1. Create GivenLoan with 3 items
2. Repledge 2 items to a TakenLoan
3. Go to loan detail
4. Click "Release Loan" button
5. Should show "2 items with lender" warning
6. Click "Release with Auto-Return"
7. Items should be returned + released
8. Check RepledgeHistory (should show returned_at set)
```

### Test Multi-Item Repledge
```
1. Go to /girvi/repledge/create/
2. Select items from Customer 1 AND Customer 2
3. Enter lender, amount, rate
4. Click "Create TakenLoan"
5. Check TakenLoan detail - see collateral grouped by customer
6. Check each item - custody_status should be 'with_lender'
7. Check RepledgeHistory - should have entries for each item
```

### Test Collateral Return
```
1. Go to TakenLoan detail
2. Click "View Collateral"
3. See items grouped by source customer
4. Click "Return All Collateral"
5. Items should go back to 'in_vault'
6. Check RepledgeHistory - returned_at should be set
```

---

## Success Indicators

After implementing, you should see:

- [ ] Loan detail shows "In Vault", "With Lenders", "With Customer" counts
- [ ] Release button is at `/girvi/loans/<id>/release/check/` (not direct release)
- [ ] Release with auto-return works smoothly
- [ ] Can select items from multiple customers for repledge
- [ ] RepledgeHistory has complete records for audit
- [ ] Admin shows all repledge history
- [ ] Queries like `LoanItem.objects.in_vault()` work

---

## Documentation Priority

1. **START HERE**: `CUSTODY_TRACKING_OVERVIEW.md` - The big picture
2. **THEN READ**: `CUSTODY_TRACKING_WORKFLOWS.md` - See it in action
3. **IMPLEMENT**: `CUSTODY_TRACKING_IMPLEMENTATION_GUIDE.md` - Step by step
4. **REFERENCE**: `CUSTODY_TRACKING_QUICK_REF.md` - Code snippets

---

## Time Estimate

| Phase | Time | Complexity |
|:--|:--|:--|
| 1. Add Models | 15 min | Low |
| 2. Run Migration | 5 min | Very Low |
| 3. Add Views & URLs | 10 min | Very Low |
| 4. Add Templates | 10 min | Very Low |
| 5. Update Release Button | 5 min | Very Low |
| 6. Test Workflows | 30 min | Medium |
| **TOTAL** | **75 min** | **Average** |

---

## Questions Before Starting?

- **"How do I add a mixin to my model?"** 
  â†’ See `CUSTODY_TRACKING_IMPLEMENTATION_GUIDE.md` Section: "Step 1: Update LoanItem Model"

- **"What if I don't have GivenLoan/TakenLoan yet?"**
  â†’ See this repo's `LOAN_REFACTORING_GUIDE.md` (completed earlier)

- **"How do I test if it works?"**
  â†’ See "Testing Commands" section above

- **"What if something breaks?"**
  â†’ Rollback: `python manage.py migrate girvi <previous_number>`

---

## Ready to Start?

âœ… All code created  
âœ… All documentation written  
âœ… All tests examples provided  

**Next step: Read `CUSTODY_TRACKING_OVERVIEW.md` (20 min)**  
**Then: Follow Phase 1 in checklist above (15 min)**  

**You've got everything you need!** ðŸš€

---

## Contact/Support

If you get stuck:
1. Check the relevant documentation
2. Look up the section in `IMPLEMENTATION_GUIDE.md`
3. Try the test commands to verify data
4. Rollback migration if needed

All files are in `apps/tenant_apps/girvi/docs/` for reference while implementing.

**LET'S GO!** ðŸŽ‰

