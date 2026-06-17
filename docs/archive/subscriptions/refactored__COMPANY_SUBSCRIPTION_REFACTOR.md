---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Company-Based Subscription Refactoring

## Overview

The subscription system has been refactored from **user-based** to **company-based** billing. This aligns with your SaaS model where:

- **Companies (workspaces)** are the paying entities
- **Users** are members of companies with roles and permissions
- **Company owner/admins** manage billing and subscriptions
- **Staff/members** consume seats without paying individually

---

## What Changed

### Before (User-Based)
```python
Subscription.user = OneToOneField(User)  # Individual pays
```

### After (Company-Based) âœ…
```python
Subscription.company = OneToOneField(Company)  # Company pays
```

---

## Model Changes Summary

### 1. **Subscription Model**

**Removed**:
- `user` field (OneToOneField to User)
- `current_user_count` (now calculated from Membership count)
- `current_transaction_count`, `current_invoice_count` (moved to UsageMetrics)

**Added**:
- `company` field â†’ OneToOneField to Company (the paying entity)
- `razorpay_order_id` (for order tracking)

**New Methods**:
```python
def get_current_user_count()
    # Returns actual member count from Membership table
    
def get_overage_users()
    # Users exceeding plan limit
    
def get_overage_charge()
    # Extra charges for overage users
    
def can_add_member()
    # Check if company can invite more members
    
def is_billing_manager(user)
    # Check if user can manage company billing (owner or billing admin)
```

---

### 2. **Invoice Model**

**Changed**:
- Added `razorpay_order_id` field (was missing)
- Updated `__str__` to show company name: `"{invoice_number} - {company.name} - â‚¹{amount}"`
- Updated `mark_as_paid()` to use `timezone.now()`

**Related to**: Subscription (company-level invoices)

---

### 3. **Payment Model**

**Changed**:
- Fixed typo in `PaymentStatusChoices.CAPTURED` description
- Added `verbose_name` and `verbose_name_plural` for admin
- Updated `__str__` format for clarity

---

### 4. **UsageMetrics Model**

**Changed**:
- Now references company through subscription: `subscription.company.name`
- Updated `__str__` to show company name
- Added helper methods:
  - `is_near_user_limit()` - warns if >80% of user limit
  - `is_near_transaction_limit()` - warns if >80% of transaction limit
  - `is_near_invoice_limit()` - warns if >80% of invoice limit

---

### 5. **PriceOverride Model**

**Changed**:
- Referenced company through subscription
- Updated `__str__` to show company name: `"Custom pricing for {company.name}"`
- Added `is_active()` method to check date validity

---

## How Billing Works Now

### User Signs Up
1. User creates account â†’ User created in `public.user`
2. User creates "Acme Corp" company â†’ `public.company` created
3. Company auto-enters **14-day trial** â†’ `public.subscription` created with `company_id`
4. Tenant schema `acme_corp` created for company data

### User Invites Staff
1. Company owner invites staff email â†’ `CompanyInvitation` created
2. Staff accepts â†’ `Membership` created with role (owner/admin/member)
3. Staff uses company's subscription (no new subscription)
4. Staff can only access company's tenant schema

### Payment & Billing
1. **Day 14**: Trial ends, invoice generated for company
2. **Day 7 (due date)**: Company owner sees payment prompt
3. **Payment authorized**: All company members get access restored
4. **Monthly auto-renewal**: Company charged monthly (with E-Mandate)
5. **Payment fails**: Company goes into `past_due` status â†’ all members see restricted features

---

## Feature Access Control Pattern

### Old Way (Wrong)
```python
# Check if logged-in user has access
user_subscription = request.user.subscription
if not user_subscription.can_access_feature('advanced_reporting'):
    raise PermissionDenied()
```

### New Way (Correct) âœ…
```python
# Check if company (workspace) has access
company = request.workspace  # Set during middleware
if not company.subscription.can_access_feature('advanced_reporting'):
    raise PermissionDenied()
```

### Implementation in Views/Middleware
```python
class CompanySubscriptionPermissionMixin(LoginRequiredMixin):
    """Check if company subscription has access to features"""
    
    def dispatch(self, request, *args, **kwargs):
        company = get_current_company(request)
        feature = self.required_feature  # e.g., 'advanced_reporting'
        
        if not company.subscription.can_access_feature(feature):
            raise PermissionDenied(
                f"Upgrade to {self.required_plan} plan to access this feature"
            )
        
        return super().dispatch(request, *args, **kwargs)


# Usage in a view
class AdvancedReportView(CompanySubscriptionPermissionMixin, ListView):
    required_feature = 'advanced_reporting'
    required_plan = 'Professional'
    # ... rest of view
```

---

## Member Seat Limits

### Check if Company Can Add Members
```python
from apps.orgs.models import Membership

subscription = company.subscription
current_members = subscription.get_current_user_count()
max_allowed = subscription.plan.max_users
overage = subscription.get_overage_users()

if not subscription.can_add_member():
    # Show upgrade prompt
    # Company must upgrade or pay overage for â‚¹99/month per extra user
```

---

## Billing Permissions

Only company owner or billing admin can:
- View invoices
- Manage payment methods
- Upgrade/downgrade plan
- View subscription status
- Manage billing contacts

```python
# In views
if not subscription.is_billing_manager(request.user):
    raise PermissionDenied("Only company admins can manage billing")
```

---

## Data Migration (If You Had Existing Data)

If you had user-based subscriptions before:

```python
# One-time management command to migrate
from django.core.management.base import BaseCommand
from apps.subscriptions.models import Subscription
from apps.orgs.models import Company

class Command(BaseCommand):
    def handle(self, *args, **options):
        # Get all old user-based subscriptions
        # For each subscription, find the user's owned company
        # Create new company-based subscription
        # Delete old user-based subscription
        pass
```

**If you're starting fresh**: No migration needed. Just start creating companies and subscriptions will auto-attach.

---

## Required Migrations

Generate and apply migrations:

```bash
# Generate migration for model changes
python manage.py makemigrations subscriptions

# View the migration to verify
cat apps/subscriptions/migrations/0002_refactor_to_company_based.py

# Apply migration
python manage.py migrate subscriptions
```

### What the Migration Will Do
1. Change `Subscription.user` ForeignKey to `Subscription.company` ForeignKey
2. Create `razorpay_order_id` field on Invoice
3. Add indexes on UsageMetrics
4. Drop `current_user_count`, `current_transaction_count`, `current_invoice_count` fields from Subscription

---

## Views to Update

### Billing Dashboard
**Old**:
```python
subscription = request.user.subscription
```

**New**:
```python
company = request.workspace  # From middleware/context
subscription = company.subscription
```

### Payment Checkout
**Old**:
```python
subscription, created = Subscription.objects.update_or_create(
    user=request.user,
    defaults={'plan': plan}
)
```

**New**:
```python
company = request.workspace
subscription, created = Subscription.objects.update_or_create(
    company=company,
    defaults={'plan': plan}
)
```

### Invoice Generation
**Old**:
```python
def generate_invoice(subscription, plan):
    invoice = Invoice.objects.create(
        subscription=subscription,
        base_amount=plan.price,
        # ...
    )
    # Send email to subscription.user.email
```

**New**:
```python
def generate_invoice(subscription, plan):
    invoice = Invoice.objects.create(
        subscription=subscription,
        base_amount=plan.price,
        # ...
    )
    # Send email to all company admins
    admins = subscription.company.memberships.filter(
        role__permissions__codename='manage_company_billing'
    ).values_list('user__email', flat=True)
    for email in admins:
        send_invoice_email(email, invoice)
```

---

## Django Admin Updates

### Register models in `admin.py`

```python
from django.contrib import admin
from .models import Plan, Subscription, Invoice, Payment, UsageMetrics, PriceOverride

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('company', 'plan', 'status', 'start_date', 'is_active')
    list_filter = ('status', 'plan', 'created_at')
    search_fields = ('company__name',)
    readonly_fields = ('created_at', 'updated_at', 'start_date')
    
    fieldsets = (
        ('Company', {
            'fields': ('company', 'plan', 'status')
        }),
        ('Billing', {
            'fields': ('start_date', 'trial_end_date', 'end_date', 'is_active', 'auto_renew')
        }),
        ('Razorpay', {
            'fields': ('razorpay_subscription_id',),
            'classes': ('collapse',)
        }),
        ('Cancellation', {
            'fields': ('cancellation_reason', 'cancelled_at'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'subscription', 'status', 'total_amount', 'invoice_date')
    list_filter = ('status', 'invoice_date', 'created_at')
    search_fields = ('invoice_number', 'subscription__company__name')
    readonly_fields = ('invoice_number', 'created_at', 'updated_at')
```

---

## Testing Checklist

- [ ] Create company â†’ subscription auto-created in trial
- [ ] Trial active for 14 days
- [ ] End of trial â†’ status changes to `past_due`
- [ ] Can't add members beyond plan limit
- [ ] Overage cost calculation correct
- [ ] Feature access control working (can_access_feature)
- [ ] Invoice generation working
- [ ] Payment processing updates subscription status
- [ ] Only billing managers can access billing views
- [ ] UsageMetrics tracked daily
- [ ] Price override working for enterprise customers

---

## Settings to Update

In `django_project/settings.py`, ensure these are set:

```python
# Subscription settings
SUBSCRIPTION_DEFAULT_TRIAL_DAYS = 14
BILLING_TAX_RATE = Decimal('18.00')  # GST for India
BILLING_CURRENCY = 'INR'
BILLING_EMAIL_SENDER = 'billing@yourdomain.com'

# Feature flags per plan (handled in Plan model now)
```

---

## API Updates (If Applicable)

### Serializers Example
```python
class SubscriptionSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    current_users = serializers.SerializerMethodField()
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'company', 'company_name', 'plan', 'plan_name',
            'status', 'start_date', 'end_date', 'trial_end_date',
            'current_users', 'is_active', 'auto_renew'
        ]
    
    def get_current_users(self, obj):
        return obj.get_current_user_count()
```

---

## Backward Compatibility Notes

âš ï¸ **Breaking Changes**:
- `Subscription.user` no longer exists
- Views expecting `request.user.subscription` will fail
- Invoices now reference `subscription.company` not `subscription.user`

âœ… **Compatible**:
- All payment methods (Razorpay) still work
- Feature flags unchanged
- GST calculation unchanged
- Plan tiers unchanged

---

## Next Steps

1. **Generate migrations**:
   ```bash
   python manage.py makemigrations subscriptions
   ```

2. **Review migration file** to ensure it matches your data

3. **Apply migration** (with backup first):
   ```bash
   python manage.py migrate subscriptions
   ```

4. **Update views** (see examples above)

5. **Update URLs** to include company context

6. **Test billing flow** end-to-end

7. **Update documentation** in your app

---

## Support

Questions about the refactoring?
- Check model docstrings
- Review new helper methods
- Look at method signatures for usage patterns

The models are fully documented inline for clarity.

