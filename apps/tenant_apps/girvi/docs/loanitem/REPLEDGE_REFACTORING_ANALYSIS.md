# Repledge Model Analysis & Refactoring Suggestions

## 🔍 Current Implementation Analysis

### Current Model Structure

```python
class LoanItem(models.Model):
    loan = ForeignKey(Loan)  # Belongs to a GivenLoan
    is_repledged = BooleanField(default=False)
    # ... item details (weight, purity, etc.)

class RepledgedLoanItem(models.Model):
    original_loanitem = ForeignKey(LoanItem)  # Points to GivenLoan item
    loan = ForeignKey(Loan)  # Points to TakenLoan
    repledged_loanamount = DecimalField()
    # ... interest details
```

### What This Tries to Model

**Scenario:**
1. Customer A pledges gold with us → `GivenLoan` + `LoanItem`
2. We take that gold and pledge it with Lender B to get money → `TakenLoan` + `RepledgedLoanItem`

---

## 🚨 Critical Problems

### Problem 1: **Physical Custody Confusion**

```
Customer A's gold → We hold it (GivenLoan)
                 ↓
                 We give it to Lender B (TakenLoan/Repledge)
```

**Issue**: 
- `GivenLoan.loanitems` shows we still have the gold
- But `RepledgedLoanItem` shows we gave it to someone else!
- **Where is the gold physically?**

### Problem 2: **Release Impossibility**

```
Customer A wants gold back → But we don't have it!
                           → It's with Lender B!
```

**Issue**: 
- Customer A can theoretically "release" their loan
- But we can't give them the gold because Lender B has it
- **No validation prevents this conflict**

### Problem 3: **Semantic Confusion**

"Repledge" has multiple meanings:

**Meaning 1 (Current)**: Use customer's pledged items as collateral for our loan
- Customer A → [Gold] → Us
- Us → [Customer A's Gold] → Lender B

**Meaning 2 (Alternative)**: Customer repledges items they got from us
- Customer A → [Gold] → Us → Release
- Customer A gets gold back
- Customer A → [Same Gold] → Us again (repledge)

**Which is intended?**

### Problem 4: **Chain Tracking**

What if:
1. Customer A → Gold → Us (GivenLoan #1)
2. Us → Gold → Lender B (TakenLoan #1)
3. Lender B → Gold → Lender C (TakenLoan #2)

**Issue**: No way to track the full chain

### Problem 5: **Partial Repledge Complexity**

What if:
- Customer pledges 100g gold
- We only repledge 50g to Lender B
- **Current model doesn't support partial repledge**

---

## 💡 Refactoring Suggestions

### Option 1: **Collateral Custody Tracking** (Recommended)

Model the physical location and custody chain of items:

```python
class CollateralCustody(models.Model):
    """Tracks who physically holds the collateral"""
    
    class CustodyStatus(models.TextChoices):
        WITH_US = "with_us", "In Our Custody"
        WITH_LENDER = "with_lender", "Pledged to Lender"
        RELEASED = "released", "Released to Customer"
        AUCTIONED = "auctioned", "Auctioned/Sold"
    
    loan_item = models.ForeignKey(LoanItem, on_delete=models.CASCADE)
    
    # Custody tracking
    status = models.CharField(max_length=20, choices=CustodyStatus.choices)
    held_by = models.CharField(max_length=255, help_text="Who holds it now")
    location = models.CharField(max_length=255, blank=True)
    
    # If repledged
    repledged_to_loan = models.ForeignKey(
        'TakenLoan',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="TakenLoan where this item is used as collateral"
    )
    repledged_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Audit
    changed_at = models.DateTimeField(auto_now=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL)
    
    class Meta:
        ordering = ['-changed_at']
        get_latest_by = 'changed_at'
    
    def __str__(self):
        return f"{self.loan_item} - {self.status} - {self.held_by}"


class LoanItem(models.Model):
    # ... existing fields ...
    
    @property
    def current_custody(self):
        """Get current custody status"""
        return self.collateralcustody_set.latest()
    
    @property
    def is_available_for_repledge(self):
        """Can this item be repledged?"""
        custody = self.current_custody
        return (
            custody.status == CollateralCustody.CustodyStatus.WITH_US
            and not self.loan.is_released
        )
    
    def repledge_to(self, taken_loan, amount, changed_by):
        """Repledge this item to a TakenLoan"""
        if not self.is_available_for_repledge:
            raise ValidationError("Item not available for repledge")
        
        # Create custody record
        CollateralCustody.objects.create(
            loan_item=self,
            status=CollateralCustody.CustodyStatus.WITH_LENDER,
            held_by=taken_loan.lender.name,
            repledged_to_loan=taken_loan,
            repledged_amount=amount,
            changed_by=changed_by
        )


class GivenLoan(BaseLoan):
    # ... existing fields ...
    
    def can_release(self):
        """Check if loan can be released (all items in our custody)"""
        for item in self.loanitems.all():
            custody = item.current_custody
            if custody.status != CollateralCustody.CustodyStatus.WITH_US:
                return False, f"Item {item} not in our custody (status: {custody.status})"
        return True, "All items available for release"


class TakenLoan(BaseLoan):
    # ... existing fields ...
    
    @property
    def collateral_items(self):
        """Get all items used as collateral for this TakenLoan"""
        custody_records = CollateralCustody.objects.filter(
            repledged_to_loan=self,
            status=CollateralCustody.CustodyStatus.WITH_LENDER
        )
        return [custody.loan_item for custody in custody_records]
    
    @property
    def collateral_value(self):
        """Total current value of collateral"""
        return sum(item.current_value() for item in self.collateral_items)
```

**Benefits:**
- ✅ Clear custody tracking
- ✅ Prevents invalid releases
- ✅ Full audit trail
- ✅ Supports custody chains
- ✅ Can handle partial repledges

---

### Option 2: **Explicit Collateral Pool**

Create a separate pool for managing collateral:

```python
class CollateralPool(models.Model):
    """Pool of items available for repledging"""
    
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)
    
    def total_value(self):
        return sum(item.current_value() for item in self.items.all())
    
    def available_items(self):
        """Items not currently repledged"""
        return self.items.filter(
            collateralallocation__isnull=True
        )


class CollateralAllocation(models.Model):
    """Allocation of specific items to a TakenLoan"""
    
    loan_item = models.ForeignKey(
        LoanItem,
        on_delete=models.CASCADE,
        related_name='allocations'
    )
    pool = models.ForeignKey(
        CollateralPool,
        on_delete=models.CASCADE,
        related_name='items'
    )
    taken_loan = models.ForeignKey(
        'TakenLoan',
        on_delete=models.CASCADE,
        related_name='collateral_allocations'
    )
    
    allocated_amount = models.DecimalField(max_digits=10, decimal_places=2)
    allocated_at = models.DateTimeField(auto_now_add=True)
    released_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['loan_item', 'taken_loan'],
                condition=models.Q(released_at__isnull=True),
                name='unique_active_allocation'
            )
        ]
    
    @property
    def is_active(self):
        return self.released_at is None
```

---

### Option 3: **Simpler - Just Track State**

If you don't need full custody tracking, just track repledge state:

```python
class LoanItem(models.Model):
    # ... existing fields ...
    
    class RepledgeStatus(models.TextChoices):
        AVAILABLE = "available", "Available"
        REPLEDGED = "repledged", "Repledged to Lender"
        RETURNED = "returned", "Returned from Repledge"
    
    repledge_status = models.CharField(
        max_length=20,
        choices=RepledgeStatus.choices,
        default=RepledgeStatus.AVAILABLE
    )
    
    # Track current repledge if active
    current_repledge_loan = models.ForeignKey(
        'TakenLoan',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='collateral_items',
        help_text="TakenLoan using this item as collateral"
    )
    
    repledge_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    @property
    def is_available_for_release(self):
        """Can this item be released to customer?"""
        return self.repledge_status == self.RepledgeStatus.AVAILABLE


class RepledgeHistory(models.Model):
    """Historical record of repledges"""
    
    loan_item = models.ForeignKey(
        LoanItem,
        on_delete=models.CASCADE,
        related_name='repledge_history'
    )
    taken_loan = models.ForeignKey('TakenLoan', on_delete=models.CASCADE)
    
    repledged_amount = models.DecimalField(max_digits=10, decimal_places=2)
    repledged_at = models.DateTimeField(auto_now_add=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    
    repledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    
    class Meta:
        ordering = ['-repledged_at']
```

**Benefits:**
- ✅ Simpler than Option 1
- ✅ Tracks history
- ✅ Prevents invalid releases
- ❌ No detailed custody chain
- ❌ No partial amount tracking

---

## 🎯 Recommended Approach

### **Hybrid: Option 1 + Simplified Tracking**

```python
class ItemCustodyStatus(models.TextChoices):
    """Where is the item physically?"""
    IN_VAULT = "in_vault", "In Our Vault"
    WITH_LENDER = "with_lender", "Pledged to Lender"
    WITH_CUSTOMER = "with_customer", "Released to Customer"


class LoanItem(models.Model):
    # ... existing fields ...
    
    # Current custody
    custody_status = models.CharField(
        max_length=20,
        choices=ItemCustodyStatus.choices,
        default=ItemCustodyStatus.IN_VAULT,
        db_index=True
    )
    
    # If repledged
    repledged_to = models.ForeignKey(
        'TakenLoan',
        null=True,
        blank=True,
        on_delete=models.PROTECT,  # Can't delete TakenLoan if items still pledged
        related_name='collateral_items',
        help_text="Active repledge - item is with this lender"
    )
    
    repledged_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Amount borrowed using this item as collateral"
    )
    
    repledged_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When item was repledged"
    )
    
    # Remove old is_repledged boolean
    # is_repledged = models.BooleanField(default=False)  # REMOVE THIS
    
    class Meta:
        indexes = [
            models.Index(fields=['custody_status', 'repledged_to']),
        ]
    
    @property
    def is_repledged(self):
        """Backward compatibility"""
        return self.repledged_to is not None
    
    @property
    def is_available_for_release(self):
        """Can customer get this item back?"""
        return self.custody_status == ItemCustodyStatus.IN_VAULT
    
    @property
    def is_available_for_repledge(self):
        """Can we repledge this item?"""
        return (
            not self.loan.is_released
            and self.custody_status == ItemCustodyStatus.IN_VAULT
            and self.repledged_to is None
        )
    
    def repledge_to(self, taken_loan, amount, user):
        """Repledge this item to a TakenLoan"""
        if not self.is_available_for_repledge:
            raise ValidationError(
                f"Item cannot be repledged (status: {self.custody_status})"
            )
        
        self.custody_status = ItemCustodyStatus.WITH_LENDER
        self.repledged_to = taken_loan
        self.repledged_amount = amount
        self.repledged_at = timezone.now()
        self.save()
        
        # Create history record
        RepledgeHistory.objects.create(
            loan_item=self,
            taken_loan=taken_loan,
            repledged_amount=amount,
            repledged_by=user
        )
    
    def return_from_repledge(self, user):
        """Return item from repledge to our vault"""
        if self.repledged_to is None:
            raise ValidationError("Item is not currently repledged")
        
        taken_loan = self.repledged_to
        
        # Mark repledge as returned
        history = RepledgeHistory.objects.filter(
            loan_item=self,
            taken_loan=taken_loan,
            returned_at__isnull=True
        ).first()
        
        if history:
            history.returned_at = timezone.now()
            history.save()
        
        # Reset custody
        self.custody_status = ItemCustodyStatus.IN_VAULT
        self.repledged_to = None
        self.repledged_amount = None
        self.repledged_at = None
        self.save()
    
    def clean(self):
        """Validation"""
        super().clean()
        
        # Validate custody status matches repledge state
        if self.repledged_to and self.custody_status != ItemCustodyStatus.WITH_LENDER:
            raise ValidationError(
                "Item repledged to loan but custody status is not WITH_LENDER"
            )
        
        if not self.repledged_to and self.custody_status == ItemCustodyStatus.WITH_LENDER:
            raise ValidationError(
                "Custody status is WITH_LENDER but no repledge loan specified"
            )


class RepledgeHistory(models.Model):
    """Historical record of all repledges"""
    
    loan_item = models.ForeignKey(
        LoanItem,
        on_delete=models.CASCADE,
        related_name='repledge_history'
    )
    taken_loan = models.ForeignKey(
        'TakenLoan',
        on_delete=models.CASCADE,
        related_name='repledge_history_items'
    )
    
    # Amounts
    repledged_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Amount borrowed using this item"
    )
    item_value_at_repledge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Market value of item when repledged"
    )
    
    # Dates
    repledged_at = models.DateTimeField(auto_now_add=True)
    returned_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When item was returned to our vault"
    )
    
    # Audit
    repledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='repledges_created'
    )
    
    returned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='repledges_returned',
        blank=True
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-repledged_at']
        verbose_name = "Repledge History"
        verbose_name_plural = "Repledge Histories"
    
    @property
    def is_active(self):
        return self.returned_at is None
    
    @property
    def duration_days(self):
        if self.returned_at:
            return (self.returned_at - self.repledged_at).days
        return (timezone.now() - self.repledged_at).days
    
    def __str__(self):
        status = "Active" if self.is_active else "Returned"
        return f"{self.loan_item} → {self.taken_loan.lender.name} ({status})"


# Update TakenLoan to use collateral
class TakenLoan(BaseLoan):
    lender = models.ForeignKey(Customer, related_name="loans_given")
    # ... other fields ...
    
    @property
    def collateral_items(self):
        """Items currently pledged as collateral for this loan"""
        return LoanItem.objects.filter(repledged_to=self)
    
    @property
    def collateral_value(self):
        """Current market value of all collateral"""
        return sum(item.current_value() for item in self.collateral_items)
    
    @property
    def loan_to_value_ratio(self):
        """LTV ratio - important for risk assessment"""
        collateral = self.collateral_value
        if collateral == 0:
            return 0
        return (self.get_loan_amount / collateral) * 100
    
    def can_release(self):
        """Check if TakenLoan can be released"""
        if self.collateral_items.exists():
            return False, "Cannot release - items still pledged as collateral"
        return True, "No collateral items blocking release"
    
    def add_collateral(self, loan_items: list, user):
        """Add items as collateral"""
        for item in loan_items:
            if not item.is_available_for_repledge:
                raise ValidationError(f"Item {item} not available for repledge")
            
            # Calculate amount proportionally
            item_value = item.current_value()
            total_value = sum(i.current_value() for i in loan_items)
            item_amount = (item_value / total_value) * self.get_loan_amount
            
            item.repledge_to(self, item_amount, user)


# Now RepledgedLoanItem can be deprecated/removed
# Or kept as a backwards-compatible view
```

---

## 📋 Migration Steps

### 1. Add New Fields
```python
# migration
class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name='loanitem',
            name='custody_status',
            field=models.CharField(default='in_vault', max_length=20),
        ),
        migrations.AddField(
            model_name='loanitem',
            name='repledged_to',
            field=models.ForeignKey(null=True, blank=True, to='girvi.TakenLoan'),
        ),
        # ... other fields
    ]
```

### 2. Migrate Existing Data
```python
def migrate_repledges(apps, schema_editor):
    LoanItem = apps.get_model('girvi', 'LoanItem')
    RepledgedLoanItem = apps.get_model('girvi', 'RepledgedLoanItem')
    
    for repledge in RepledgedLoanItem.objects.all():
        item = repledge.original_loanitem
        
        # Update custody
        item.custody_status = 'with_lender'
        item.repledged_to = repledge.loan
        item.repledged_amount = repledge.repledged_loanamount
        item.repledged_at = repledge.repledged_date
        item.save()
        
        # Create history
        RepledgeHistory.objects.create(
            loan_item=item,
            taken_loan=repledge.loan,
            repledged_amount=repledge.repledged_loanamount,
            repledged_at=repledge.repledged_date
        )
```

### 3. Update Views/Forms

### 4. Deprecate Old Model
Mark `RepledgedLoanItem` as deprecated but keep for backward compatibility.

---

## 🎯 Benefits of Recommended Approach

1. **✅ Clear Custody** - Always know where each item is
2. **✅ Prevent Invalid Releases** - Can't release items not in vault
3. **✅ Full History** - Track all repledge events
4. **✅ Risk Management** - Calculate LTV ratios
5. **✅ Audit Trail** - Who repledged what and when
6. **✅ Validation** - Enforce business rules at model level
7. **✅ Backward Compatible** - Keep old RepledgedLoanItem if needed

---

## 🚀 Next Steps

1. **Decide** which option fits your business model best
2. **Review** the custody workflow with stakeholders
3. **Test** with sample data
4. **Implement** chosen approach
5. **Migrate** existing data
6. **Update** UI to show custody status clearly

Let me know which approach makes sense for your use case!
