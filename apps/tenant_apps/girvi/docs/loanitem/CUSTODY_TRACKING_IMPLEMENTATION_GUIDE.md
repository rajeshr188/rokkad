# Custody Tracking Implementation Guide

## Overview

This implementation adds **physical custody tracking** to solve the repledge chaos problem. It ensures you always know where items physically are (vault, with lender, or with customer) and prevents invalid operations like releasing items that are with lenders.

## Key Features Implemented

✅ **Clear Custody Status**: Every item has IN_VAULT, WITH_LENDER, or WITH_CUSTOMER  
✅ **Automatic Return Workflow**: When customer wants to release, system returns items from lenders first  
✅ **Multi-Item Bundling**: Bundle items from different customers as collateral for one TakenLoan  
✅ **Full History**: Complete audit trail of all repledge/return events  
✅ **Validation**: Cannot release items that are with lenders (without return first)  
✅ **LTV Tracking**: Loan-to-value ratios for risk management  

## Implementation Steps

### Step 1: Update LoanItem Model

Add new fields to existing `LoanItem` model in `apps/tenant_apps/girvi/models/loan.py`:

```python
from apps.tenant_apps.girvi.models.custody_tracking import (
    ItemCustodyStatus,
    LoanItemWithCustody
)

class LoanItem(LoanItemWithCustody):  # Add mixin
    """Existing LoanItem model with custody tracking"""
    
    # ... existing fields ...
    
    # New fields added via migration:
    # - custody_status
    # - repledged_to
    # - repledged_amount
    # - repledged_at
    
    # Methods inherited from LoanItemWithCustody:
    # - repledge_to()
    # - return_from_lender()
    # - release_to_customer()
    # - Properties: is_in_vault, is_available_for_release, etc.
```

### Step 2: Enhance GivenLoan Model

Add release workflow methods:

```python
from apps.tenant_apps.girvi.models.custody_tracking import GivenLoanReleaseMixin

class GivenLoan(BaseLoan, GivenLoanReleaseMixin):  # Add mixin
    """GivenLoan with custody-aware release"""
    
    # Existing fields...
    borrower = models.ForeignKey(Customer, ...)
    
    # Methods inherited from GivenLoanReleaseMixin:
    # - can_release() -> (bool, message)
    # - get_items_by_custody() -> dict
    # - release_with_return_workflow()
```

### Step 3: Enhance TakenLoan Model

Add collateral management:

```python
from apps.tenant_apps.girvi.models.custody_tracking import TakenLoanCollateralMixin

class TakenLoan(BaseLoan, TakenLoanCollateralMixin):  # Add mixin
    """TakenLoan with collateral management"""
    
    # Existing fields...
    lender = models.ForeignKey(Customer, ...)
    
    # Methods inherited from TakenLoanCollateralMixin:
    # - add_collateral(loan_items, user, notes)
    # - return_all_collateral(user, notes)
    # - Properties: collateral_items, collateral_value, loan_to_value_ratio
```

### Step 4: Create RepledgeHistory Model

Import and register in `models/__init__.py`:

```python
from apps.tenant_apps.girvi.models.custody_tracking import RepledgeHistory

# Register in admin
from django.contrib import admin

@admin.register(RepledgeHistory)
class RepledgeHistoryAdmin(admin.ModelAdmin):
    list_display = ['loan_item', 'taken_loan', 'repledged_amount', 'is_active', 'duration_days']
    list_filter = ['returned_at', 'repledged_at']
    search_fields = ['loan_item__itemdesc', 'taken_loan__loan_id']
```

### Step 5: Run Migration

```bash
# Generate migration
python manage.py makemigrations girvi --name add_custody_tracking

# Review migration file - should match add_custody_tracking.py

# Run migration
python manage.py migrate girvi

# Verify data migration
python manage.py shell
>>> from apps.tenant_apps.girvi.models import LoanItem, RepledgeHistory
>>> LoanItem.objects.filter(custody_status='with_lender').count()
>>> RepledgeHistory.objects.filter(returned_at__isnull=True).count()
```

### Step 6: Update URLs

Add custody URLs to `apps/tenant_apps/girvi/urls.py`:

```python
from apps.tenant_apps.girvi.views import custody_views

urlpatterns = [
    # ... existing patterns ...
    
    # Custody tracking
    path('items/<int:item_id>/custody/', custody_views.item_custody_status, name='item_custody_status'),
    path('loans/<int:loan_id>/custody/', custody_views.loan_custody_summary, name='loan_custody_summary'),
    
    # Release workflow
    path('loans/<int:loan_id>/release/check/', custody_views.release_loan_check_custody, name='release_loan_check_custody'),
    path('loans/<int:loan_id>/release/with-return/', custody_views.release_loan_with_return, name='release_loan_with_return'),
    
    # Repledge creation
    path('repledge/create/', custody_views.create_repledge_select_items, name='create_repledge_select_items'),
    path('repledge/create/with-items/', custody_views.create_repledge_with_items, name='create_repledge_with_items'),
    
    # Collateral management
    path('taken-loans/<int:loan_id>/collateral/', custody_views.taken_loan_collateral_detail, name='taken_loan_collateral_detail'),
    path('taken-loans/<int:loan_id>/return-collateral/', custody_views.return_taken_loan_collateral, name='return_taken_loan_collateral'),
]
```

### Step 7: Update Loan Detail Template

Add custody status badge to loan detail view:

```django
<!-- templates/girvi/loan_detail.html -->

{% if loan.loan_type == 'Given' %}
    <div class="card mb-3">
        <div class="card-header">
            <h5>Item Custody Status</h5>
            <a href="{% url 'girvi:loan_custody_summary' loan.id %}" class="btn btn-sm btn-info float-right">
                <i class="fas fa-warehouse"></i> View Custody Details
            </a>
        </div>
        <div class="card-body">
            <div class="row">
                <div class="col-md-4">
                    <div class="text-center p-3 bg-success text-white rounded">
                        <h3>{{ loan.loanitems.in_vault.count }}</h3>
                        <small>In Vault</small>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="text-center p-3 bg-warning text-white rounded">
                        <h3>{{ loan.loanitems.with_lenders.count }}</h3>
                        <small>With Lenders</small>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="text-center p-3 bg-info text-white rounded">
                        <h3>{{ loan.loanitems.with_customers.count }}</h3>
                        <small>With Customer</small>
                    </div>
                </div>
            </div>
        </div>
    </div>
{% endif %}
```

### Step 8: Update Release Button

Replace direct release with custody check:

```django
<!-- Old: Direct release -->
<a href="{% url 'girvi:loan_release_create' loan.id %}" class="btn btn-primary">Release Loan</a>

<!-- New: Custody check first -->
<a href="{% url 'girvi:release_loan_check_custody' loan.id %}" class="btn btn-primary">
    <i class="fas fa-check-circle"></i> Release Loan
</a>
```

## Usage Workflows

### Workflow 1: Customer Wants to Release (Items with Lender)

**Scenario**: Customer wants their items back, but some are with lender.

```python
1. User clicks "Release Loan"
   → Redirects to custody check page

2. System shows:
   - 3 items in vault ✓
   - 2 items with Lender A ⚠️
   - "Release with Auto-Return" button

3. User clicks "Release with Auto-Return"
   → System executes:
   
   with transaction.atomic():
       # Return items from lender
       for item in items_with_lender:
           item.return_from_lender(user=user)
           # custody_status: WITH_LENDER → IN_VAULT
           # repledged_to: cleared
           # RepledgeHistory: returned_at = now
       
       # Release to customer
       for item in all_items:
           item.release_to_customer(user=user)
           # custody_status: IN_VAULT → WITH_CUSTOMER
       
       # Create release document
       release = loan.create_release(...)

4. Success! All items returned and released to customer.
```

### Workflow 2: Create Repledge with Multi-Customer Collateral

**Scenario**: You want to borrow from Lender B using items from Customer A and Customer C.

```python
1. Navigate to /girvi/repledge/create/
   → Shows all available items grouped by customer

2. Select items:
   - Customer A: 2 gold rings (₹50,000 total)
   - Customer C: 1 gold chain (₹30,000 total)
   - Total collateral: ₹80,000

3. Fill form:
   - Lender: Lender B
   - Loan Amount: ₹60,000 (75% LTV ✓)
   - Interest Rate: 1.5%
   - Date: Today

4. Click "Create TakenLoan with Collateral"
   → System executes:
   
   with transaction.atomic():
       # Create TakenLoan
       taken_loan = TakenLoan.objects.create(
           lender=lender_b,
           loan_amount=60000,
           ...
       )
       
       # Repledge items proportionally
       for item in selected_items:
           item_amount = (item.value / total_value) * loan_amount
           item.repledge_to(
               taken_loan=taken_loan,
               amount=item_amount,
               user=user
           )
           # custody_status: IN_VAULT → WITH_LENDER
           # repledged_to: taken_loan
           # RepledgeHistory: created

5. Success! TakenLoan created with bundled collateral.
```

### Workflow 3: Close TakenLoan (Return Collateral)

**Scenario**: You paid back Lender B, need to return collateral.

```python
1. Navigate to TakenLoan detail page
2. Click "View Collateral" → Shows:
   - Customer A: 2 items
   - Customer C: 1 item
   - Total collateral value: ₹80,000
   - LTV ratio: 75%

3. Click "Return All Collateral"
   → System executes:
   
   with transaction.atomic():
       for item in taken_loan.collateral_items:
           item.return_from_lender(user=user)
           # custody_status: WITH_LENDER → IN_VAULT
           # repledged_to: cleared
           # RepledgeHistory: returned_at = now

4. Success! All collateral back in vault.
   Now Customer A and C can release their loans if they want.
```

## QuerySet Usage

The implementation adds custom QuerySet methods:

```python
# Filter items by custody status
vault_items = LoanItem.objects.in_vault()
repledged_items = LoanItem.objects.with_lenders()
released_items = LoanItem.objects.with_customers()

# Find items available for repledge
available = LoanItem.objects.available_for_repledge()

# Get collateral for specific TakenLoan
collateral = LoanItem.objects.repledged_to_loan(taken_loan)

# Get items by customer
customer_items = LoanItem.objects.by_customer(customer)

# Chain with other filters
gold = LoanItem.objects.in_vault().filter(itemtype__name='Gold')
```

## Validation Rules

The system enforces these rules:

### Cannot Repledge Item If:
- ❌ Already repledged (repledged_to is set)
- ❌ Not in vault (custody_status != IN_VAULT)
- ❌ Loan is released

### Cannot Release Item If:
- ❌ With lender (custody_status == WITH_LENDER)
  - **Solution**: Use `release_with_return_workflow()`
- ❌ Already with customer (custody_status == WITH_CUSTOMER)

### Cannot Close TakenLoan If:
- ❌ Collateral items not returned
  - **Solution**: Call `return_all_collateral()` first

## Reporting Queries

```python
# Active repledges
active = RepledgeHistory.objects.filter(returned_at__isnull=True)

# Items currently with specific lender
with_lender_a = LoanItem.objects.filter(
    custody_status=ItemCustodyStatus.WITH_LENDER,
    repledged_to__lender__name='Lender A'
)

# Total value with lenders
from django.db.models import Sum
total = with_lender_a.aggregate(
    total=Sum('repledged_amount')
)['total']

# Average repledge duration
from django.db.models import F, ExpressionWrapper, fields
from django.utils import timezone

avg_duration = RepledgeHistory.objects.filter(
    returned_at__isnull=False
).annotate(
    duration=ExpressionWrapper(
        F('returned_at') - F('repledged_at'),
        output_field=fields.DurationField()
    )
).aggregate(Avg('duration'))

# High LTV loans (risky)
risky = RepledgeHistory.objects.annotate(
    ltv=F('repledged_amount') / F('item_value_at_repledge') * 100
).filter(ltv__gt=80)
```

## Admin Integration

```python
# apps/tenant_apps/girvi/admin.py

from django.contrib import admin
from apps.tenant_apps.girvi.models import LoanItem, RepledgeHistory

class RepledgeHistoryInline(admin.TabularInline):
    model = RepledgeHistory
    extra = 0
    readonly_fields = ['repledged_at', 'returned_at', 'duration_days', 'ltv_ratio']
    can_delete = False

@admin.register(LoanItem)
class LoanItemAdmin(admin.ModelAdmin):
    list_display = ['itemdesc', 'loan', 'custody_status', 'is_repledged', 'current_value']
    list_filter = ['custody_status', 'itemtype']
    search_fields = ['itemdesc', 'loan__loan_id']
    inlines = [RepledgeHistoryInline]
    
    def get_readonly_fields(self, request, obj=None):
        if obj and obj.custody_status == 'with_lender':
            return ['custody_status', 'repledged_to', 'repledged_amount']
        return []

@admin.register(RepledgeHistory)
class RepledgeHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'loan_item',
        'taken_loan',
        'repledged_amount',
        'item_value_at_repledge',
        'ltv_ratio',
        'is_active',
        'duration_days'
    ]
    list_filter = ['returned_at', 'repledged_at']
    search_fields = [
        'loan_item__itemdesc',
        'taken_loan__loan_id',
        'loan_item__loan__customer__name',
        'taken_loan__lender__name'
    ]
    date_hierarchy = 'repledged_at'
    readonly_fields = ['repledged_at', 'ltv_ratio', 'duration_days']
```

## Testing

### Unit Tests

```python
# tests/test_custody_tracking.py

from django.test import TestCase
from apps.tenant_apps.girvi.models import LoanItem, GivenLoan, TakenLoan
from apps.tenant_apps.girvi.models.custody_tracking import ItemCustodyStatus

class CustodyTrackingTests(TestCase):
    
    def test_repledge_item(self):
        """Test repledging an item to TakenLoan"""
        item = LoanItem.objects.create(...)
        taken_loan = TakenLoan.objects.create(...)
        
        item.repledge_to(taken_loan, amount=10000, user=self.user)
        
        self.assertEqual(item.custody_status, ItemCustodyStatus.WITH_LENDER)
        self.assertEqual(item.repledged_to, taken_loan)
        self.assertEqual(item.repledge_history.count(), 1)
    
    def test_cannot_repledge_twice(self):
        """Test that item cannot be repledged while already repledged"""
        item = LoanItem.objects.create(...)
        taken_loan1 = TakenLoan.objects.create(...)
        taken_loan2 = TakenLoan.objects.create(...)
        
        item.repledge_to(taken_loan1, amount=10000, user=self.user)
        
        with self.assertRaises(ValidationError):
            item.repledge_to(taken_loan2, amount=5000, user=self.user)
    
    def test_release_with_return_workflow(self):
        """Test automatic return when releasing"""
        loan = GivenLoan.objects.create(...)
        item = LoanItem.objects.create(loan=loan, ...)
        taken_loan = TakenLoan.objects.create(...)
        
        # Repledge item
        item.repledge_to(taken_loan, amount=10000, user=self.user)
        self.assertEqual(item.custody_status, ItemCustodyStatus.WITH_LENDER)
        
        # Release with auto-return
        release = loan.release_with_return_workflow(
            release_date=date.today(),
            released_by='Customer',
            created_by=self.user
        )
        
        item.refresh_from_db()
        self.assertEqual(item.custody_status, ItemCustodyStatus.WITH_CUSTOMER)
        self.assertIsNone(item.repledged_to)
```

## Migration from Old System

If you have existing `RepledgedLoanItem` records:

1. The migration automatically converts them to new system
2. Old `RepledgedLoanItem` model remains for backward compatibility (read-only)
3. All new operations use custody tracking

To verify migration:

```python
from apps.tenant_apps.girvi.models import LoanItem, RepledgedLoanItem, RepledgeHistory

# Check old system
old_count = RepledgedLoanItem.objects.count()

# Check new system
new_count = RepledgeHistory.objects.count()
with_lender = LoanItem.objects.filter(custody_status='with_lender').count()

print(f"Old: {old_count} RepledgedLoanItems")
print(f"New: {new_count} RepledgeHistory records")
print(f"New: {with_lender} items with lenders")
```

## Performance Considerations

### Indexes Added

Migration adds these indexes:
- `LoanItem.custody_status` (for filtering)
- `RepledgeHistory (loan_item, repledged_at)` (for history queries)
- `RepledgeHistory (taken_loan, repledged_at)` (for collateral queries)
- `RepledgeHistory.returned_at` (for active/returned filtering)

### Query Optimization

```python
# Use select_related for foreign keys
items = LoanItem.objects.select_related(
    'loan',
    'loan__customer',
    'repledged_to',
    'repledged_to__lender'
).in_vault()

# Use prefetch_related for reverse relations
loans = GivenLoan.objects.prefetch_related(
    'loanitems',
    'loanitems__repledge_history'
)

# Annotate custody counts
from django.db.models import Count, Case, When

loans = GivenLoan.objects.annotate(
    items_in_vault=Count(
        Case(When(loanitems__custody_status='in_vault', then=1))
    ),
    items_with_lender=Count(
        Case(When(loanitems__custody_status='with_lender', then=1))
    )
)
```

## What's Next?

After implementing custody tracking:

1. **Dashboard Widgets**: Add custody status summary to main dashboard
2. **Alerts**: Email notifications when items need to be returned
3. **Reports**: Generate monthly repledge activity reports
4. **Mobile App**: Scan items to check custody status
5. **Integration**: Connect with accounting for lender payments

## Troubleshooting

### Migration Failed

```bash
# Rollback
python manage.py migrate girvi <previous_migration_number>

# Check for data issues
python manage.py shell
>>> from apps.tenant_apps.girvi.models import RepledgedLoanItem
>>> RepledgedLoanItem.objects.filter(original_loanitem__isnull=True)
```

### Items Stuck in Wrong Status

```python
# Reset item to vault
item = LoanItem.objects.get(id=123)
item.custody_status = ItemCustodyStatus.IN_VAULT
item.repledged_to = None
item.repledged_amount = None
item.repledged_at = None
item.save()
```

### History Missing

```python
# Manually create history record
RepledgeHistory.objects.create(
    loan_item=item,
    taken_loan=taken_loan,
    repledged_amount=item.repledged_amount,
    item_value_at_repledge=item.current_value(),
    repledged_at=item.repledged_at or timezone.now(),
    notes="Manually created for data fix"
)
```

## Summary

This implementation provides:

✅ **Physical custody tracking** - Always know where items are  
✅ **Automatic workflows** - Return from lenders when releasing  
✅ **Multi-customer bundling** - Use items from different customers as collateral  
✅ **Full audit trail** - Complete history of all movements  
✅ **Validation** - Prevents invalid operations  
✅ **Backward compatible** - Old RepledgedLoanItem data migrated  

Your requirements are fully met:
- ✅ Items get repledged very often → Efficient tracking
- ✅ Customers can release while repledged → Auto-return workflow
- ✅ Full history preferred → RepledgeHistory model
- ✅ No multiple repledges without release → Validation enforced
- ✅ Bundle items from different customers → Multi-item collateral

**Ready to implement!**
