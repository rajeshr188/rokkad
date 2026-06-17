---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Custody Tracking Quick Reference

## ðŸŽ¯ Common Operations

### Check Item Status

```python
item = LoanItem.objects.get(id=123)

# Status checks
item.custody_status  # 'in_vault', 'with_lender', or 'with_customer'
item.is_repledged  # Boolean
item.repledged_to  # TakenLoan object or None

# Availability
item.is_available_for_repledge  # Can we repledge this?
item.is_available_for_release  # Can customer get it back?
item.can_be_returned_from_lender  # Is it with lender?
```

### Repledge Single Item

```python
from decimal import Decimal

item = LoanItem.objects.get(id=123)
taken_loan = TakenLoan.objects.get(id=456)

# Repledge
item.repledge_to(
    taken_loan=taken_loan,
    amount=Decimal('10000.00'),
    user=request.user,
    notes="Using as collateral for emergency loan"
)

# Result:
# - custody_status: IN_VAULT â†’ WITH_LENDER
# - repledged_to: taken_loan
# - RepledgeHistory created
```

### Repledge Multiple Items (Bundle)

```python
items = LoanItem.objects.filter(id__in=[123, 456, 789])
taken_loan = TakenLoan.objects.get(id=999)

# Use enhanced method
taken_loan.add_collateral(
    loan_items=list(items),
    user=request.user,
    notes="Bundled collateral from 3 customers"
)

# Loan amount distributed proportionally by value
```

### Return Item from Lender

```python
item = LoanItem.objects.get(id=123)

# Return single item
item.return_from_lender(
    user=request.user,
    notes="TakenLoan closed, returning collateral"
)

# Result:
# - custody_status: WITH_LENDER â†’ IN_VAULT
# - repledged_to: cleared
# - RepledgeHistory: returned_at = now
```

### Release Loan (Auto-Return)

```python
loan = GivenLoan.objects.get(id=123)

# Check if can release
can_release, message = loan.can_release()
if not can_release:
    print(f"Cannot release: {message}")
else:
    # Release with auto-return
    release = loan.release_with_return_workflow(
        release_date=date.today(),
        released_by=loan.borrower.name,
        created_by=request.user
    )
    # All items returned from lenders, then released to customer
```

### Close TakenLoan (Return All Collateral)

```python
taken_loan = TakenLoan.objects.get(id=456)

# Return all collateral
taken_loan.return_all_collateral(
    user=request.user,
    notes="Loan repaid, returning all collateral"
)

# Can now close the loan
can_close, message = taken_loan.can_close()
```

## ðŸ“Š QuerySets

### Filter by Custody Status

```python
# Items in vault (available)
vault_items = LoanItem.objects.in_vault()

# Items with lenders (repledged)
repledged_items = LoanItem.objects.with_lenders()

# Items released to customers
released_items = LoanItem.objects.with_customers()

# Items available for repledge right now
available = LoanItem.objects.available_for_repledge()
```

### Collateral Queries

```python
# Get collateral for TakenLoan
collateral = taken_loan.collateral_items.all()

# Or using QuerySet
collateral = LoanItem.objects.repledged_to_loan(taken_loan)

# Collateral value
total_value = taken_loan.collateral_value

# LTV ratio
ltv = taken_loan.loan_to_value_ratio  # Percentage
```

### History Queries

```python
# Item's complete repledge history
history = item.repledge_history.all()

# Active repledges only
active = item.repledge_history.filter(returned_at__isnull=True)

# Returned repledges
returned = item.repledge_history.filter(returned_at__isnull=False)

# All active repledges across all items
all_active = RepledgeHistory.objects.filter(returned_at__isnull=True)
```

### Customer Queries

```python
# All items from a customer
customer_items = LoanItem.objects.by_customer(customer)

# Items from customer currently with lenders
repledged = customer_items.with_lenders()

# Which lenders have this customer's items?
lenders = set(
    item.repledged_to.lender 
    for item in repledged 
    if item.repledged_to
)
```

## ðŸš¨ Validation Errors

### Cannot Repledge

```python
try:
    item.repledge_to(taken_loan, amount, user)
except ValidationError as e:
    # Reasons:
    # - Already repledged
    # - Not in vault (with lender or customer)
    # - Loan already released
    print(str(e))
```

### Cannot Release

```python
try:
    item.release_to_customer(user)
except ValidationError as e:
    # Reasons:
    # - With lender (need to return first)
    # - Already with customer
    print(str(e))
    
    # Solution: Use auto-return
    loan.release_with_return_workflow(...)
```

### Cannot Close TakenLoan

```python
can_close, message = taken_loan.can_close()
if not can_close:
    # Reason: Collateral not returned
    # Solution:
    taken_loan.return_all_collateral(user)
```

## ðŸ” Reporting

### Custody Summary for Loan

```python
loan = GivenLoan.objects.get(id=123)
items_by_custody = loan.get_items_by_custody()

vault_count = len(items_by_custody['in_vault'])
with_lender_count = len(items_by_custody['with_lender'])
with_customer_count = len(items_by_custody['with_customer'])
```

### Collateral Summary for TakenLoan

```python
taken_loan = TakenLoan.objects.get(id=456)

# By customer
summary = taken_loan.collateral_summary
# {
#   <Customer A>: {'count': 2, 'value': Decimal('50000')},
#   <Customer C>: {'count': 1, 'value': Decimal('30000')}
# }

# Totals
total_value = taken_loan.collateral_value
loan_amount = taken_loan.get_loan_amount
ltv = taken_loan.loan_to_value_ratio
```

### All Items with Specific Lender

```python
lender = Customer.objects.get(name='Lender A')

# Items currently with this lender
items = LoanItem.objects.filter(
    custody_status='with_lender',
    repledged_to__lender=lender
)

# Total value
from django.db.models import Sum
total = items.aggregate(Sum('repledged_amount'))['repledged_amount__sum']
```

### Active Repledges Report

```python
from django.utils import timezone
from datetime import timedelta

# All active
active = RepledgeHistory.objects.filter(returned_at__isnull=True)

# Active longer than 30 days
thirty_days_ago = timezone.now() - timedelta(days=30)
long_running = active.filter(repledged_at__lt=thirty_days_ago)

# High LTV (risky)
risky = active.filter(
    repledged_amount__gt=F('item_value_at_repledge') * 0.8
)
```

## ðŸŽ¨ Template Examples

### Show Custody Status Badge

```django
{% if item.custody_status == 'in_vault' %}
    <span class="badge badge-success">In Vault</span>
{% elif item.custody_status == 'with_lender' %}
    <span class="badge badge-warning">
        With {{ item.repledged_to.lender.name }}
    </span>
{% else %}
    <span class="badge badge-info">Released</span>
{% endif %}
```

### Release Button with Check

```django
{% if not loan.is_released %}
    <a href="{% url 'girvi:release_loan_check_custody' loan.id %}" 
       class="btn btn-primary">
        <i class="fas fa-check-circle"></i> Release Loan
    </a>
{% endif %}
```

### Custody Summary Widget

```django
<div class="row">
    <div class="col-md-4">
        <div class="card bg-success text-white">
            <div class="card-body text-center">
                <h3>{{ loan.loanitems.in_vault.count }}</h3>
                <small>In Vault</small>
            </div>
        </div>
    </div>
    <div class="col-md-4">
        <div class="card bg-warning text-white">
            <div class="card-body text-center">
                <h3>{{ loan.loanitems.with_lenders.count }}</h3>
                <small>With Lenders</small>
            </div>
        </div>
    </div>
    <div class="col-md-4">
        <div class="card bg-info text-white">
            <div class="card-body text-center">
                <h3>{{ loan.loanitems.with_customers.count }}</h3>
                <small>With Customer</small>
            </div>
        </div>
    </div>
</div>
```

## ðŸ”— URL Patterns

```python
# Item custody
{% url 'girvi:item_custody_status' item.id %}

# Loan custody summary
{% url 'girvi:loan_custody_summary' loan.id %}

# Release with custody check
{% url 'girvi:release_loan_check_custody' loan.id %}

# Create repledge
{% url 'girvi:create_repledge_select_items' %}

# Collateral detail
{% url 'girvi:taken_loan_collateral_detail' taken_loan.id %}

# History report
{% url 'girvi:repledge_history_report' %}

# AJAX API
{% url 'girvi:api_check_release_custody' loan.id %}
{% url 'girvi:api_item_custody_status' item.id %}
```

## ðŸš€ JavaScript/AJAX

### Check Custody Before Action

```javascript
// Check if loan can be released
fetch(`/girvi/api/loans/${loanId}/check-custody/`)
    .then(response => response.json())
    .then(data => {
        if (data.can_release) {
            // Proceed to release
        } else {
            alert(`Cannot release: ${data.items_with_lender} items with lender(s): ${data.lenders.join(', ')}`);
        }
    });
```

### Get Item Status

```javascript
fetch(`/girvi/api/items/${itemId}/custody/`)
    .then(response => response.json())
    .then(data => {
        console.log('Status:', data.custody_display);
        console.log('Is repledged:', data.is_repledged);
        if (data.repledged_to) {
            console.log('With lender:', data.repledged_to.lender);
        }
    });
```

## ðŸ“ Admin Actions

### Bulk Return from Lender

```python
# admin.py
from django.contrib import admin

@admin.register(LoanItem)
class LoanItemAdmin(admin.ModelAdmin):
    actions = ['bulk_return_from_lender']
    
    def bulk_return_from_lender(self, request, queryset):
        count = 0
        for item in queryset.filter(custody_status='with_lender'):
            item.return_from_lender(user=request.user, notes="Admin bulk return")
            count += 1
        self.message_user(request, f"Returned {count} items from lenders")
    
    bulk_return_from_lender.short_description = "Return selected items from lenders"
```

## ðŸ› Debugging

### Check Custody Consistency

```python
# Find items with inconsistent state
inconsistent = LoanItem.objects.filter(
    custody_status='with_lender',
    repledged_to__isnull=True
)

# Or opposite
inconsistent2 = LoanItem.objects.filter(
    custody_status='in_vault',
    repledged_to__isnull=False
)
```

### Verify History Completeness

```python
# Items repledged but no history
no_history = LoanItem.objects.filter(
    custody_status='with_lender'
).exclude(
    repledge_history__returned_at__isnull=True
)
```

### Fix Stuck Items

```python
# Reset to vault (use carefully!)
item = LoanItem.objects.get(id=123)
item.custody_status = ItemCustodyStatus.IN_VAULT
item.repledged_to = None
item.repledged_amount = None
item.repledged_at = None
item.save()
```

## ðŸ“ž Support

For issues or questions:

1. Check [CUSTODY_TRACKING_IMPLEMENTATION_GUIDE.md](CUSTODY_TRACKING_IMPLEMENTATION_GUIDE.md)
2. Review [REPLEDGE_REFACTORING_ANALYSIS.md](REPLEDGE_REFACTORING_ANALYSIS.md)
3. Check RepledgeHistory records for audit trail
4. Verify custody_status field consistency

---

**Remember**: Always use `transaction.atomic()` when making multiple custody changes!

