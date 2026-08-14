---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Quick Start: SaaS Monetization Implementation

## What's Been Created âœ…

### 1. **Enhanced Database Models** (`apps/subscriptions/models.py`)
- **Plan** - 3 tiers: Starter (â‚¹999), Professional (â‚¹3,999), Enterprise (Custom)
- **Subscription** - Complete lifecycle management with trial, active, past_due, cancelled states
- **Invoice** - Monthly billing with GST calculation (18% for India)
- **Payment** - Razorpay integration tracking
- **UsageMetrics** - Track daily usage for feature limits
- **PriceOverride** - Custom pricing for enterprise deals

### 2. **Razorpay Service** (`apps/subscriptions/razorpay_service.py`)
Complete payment gateway integration:
- Order creation
- Signature verification
- Webhook handling
- Payment status tracking
- Auto-renewal support

### 3. **Views** (`apps/subscriptions/views.py`)
- Plan listing page
- Checkout flow
- Payment processing
- Billing dashboard
- Invoice management
- Razorpay webhook handler

### 4. **Management Command** 
Run to create default plans:
```bash
python manage.py create_default_plans
```

### 5. **Documentation**
- `SAAS_MONETIZATION_GUIDE.md` - Complete strategy
- `SUBSCRIPTION_SETTINGS_EXAMPLE.py` - All Django settings needed

---

## Next Steps (Implementation Order)

### Step 1: Install Razorpay Package
```bash
pip install razorpay
```

### Step 2: Update Django Settings
Copy settings from `SUBSCRIPTION_SETTINGS_EXAMPLE.py` to your `django_project/settings/base.py`:

```python
# Add these to your settings
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET')
RAZORPAY_WEBHOOK_SECRET = os.environ.get('RAZORPAY_WEBHOOK_SECRET')

SUBSCRIPTION_DEFAULT_TRIAL_DAYS = 14
BILLING_TAX_RATE = Decimal('18.00')  # GST for India
BILLING_CURRENCY = 'INR'

# Email settings
BILLING_EMAIL_SENDER = 'billing@yourdomain.com'
```

### Step 3: Create Environment Variables
Add to your `.env` file:

```bash
# Razorpay (Get from https://razorpay.com/app/keys)
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxxxxxx    # Test key for development
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxx      # Test secret
RAZORPAY_WEBHOOK_SECRET=xxxxxxxxxxxxxxxx  # Webhook secret
```

### Step 4: Run Migrations
```bash
python manage.py makemigrations subscriptions
python manage.py migrate subscriptions
```

### Step 5: Create Default Plans
```bash
python manage.py create_default_plans
```

Output:
```
âœ“ Created Starter plan (â‚¹999/month)
âœ“ Created Professional plan (â‚¹3,999/month)
âœ“ Created Enterprise plan (Custom pricing)
```

### Step 6: Create URL Routes
Add to `apps/subscriptions/urls.py`:

```python
from django.urls import path
from .views import (
    SubscriptionPlanListView,
    CheckoutView,
    PaymentView,
    SubscriptionDashboardView,
    InvoiceDetailView,
    InvoicePDFView,
    razorpay_webhook,
)

app_name = 'subscriptions'

urlpatterns = [
    path('plans/', SubscriptionPlanListView.as_view(), name='plan-list'),
    path('checkout/<int:plan_id>/', CheckoutView.as_view(), name='checkout'),
    path('payment/', PaymentView.as_view(), name='payment'),
    path('dashboard/', SubscriptionDashboardView.as_view(), name='dashboard'),
    path('invoice/<int:pk>/', InvoiceDetailView.as_view(), name='invoice-detail'),
    path('invoice/<int:pk>/pdf/', InvoicePDFView.as_view(), name='invoice-pdf'),
    path('webhook/razorpay/', razorpay_webhook, name='razorpay-webhook'),
]
```

Include in main `django_project/urls.py`:
```python
path('subscriptions/', include('apps.subscriptions.urls')),
```

### Step 7: Configure Razorpay Webhooks

1. Go to https://razorpay.com/app/webhooks
2. Add webhook for your domain:
   - **URL**: `https://yourdomain.com/subscriptions/webhook/razorpay/`
   - **Events**: 
     - payment.authorized
     - payment.captured
     - payment.failed
     - payment.refunded
3. Copy webhook secret to `.env` file

### Step 8: Create Templates

Create these template files:

**`templates/subscriptions/plan_list.html`**
```django
{% extends "base.html" %}
{% block title %}Choose Your Plan{% endblock %}

{% block content %}
<div class="plans-container">
  {% for plan in plans %}
    <div class="plan-card">
      <h2>{{ plan.name }}</h2>
      <div class="price">â‚¹{{ plan.price }}<span>/month</span></div>
      <p>{{ plan.description }}</p>
      <ul>
        <li>{{ plan.max_users }} Users</li>
        <li>{{ plan.max_products }} Products</li>
        <li>{{ plan.max_invoices_per_month }} Invoices/month</li>
        {% if plan.has_advanced_reporting %}
          <li>âœ“ Advanced Reports</li>
        {% endif %}
      </ul>
      {% if current_plan.id == plan.id %}
        <button class="btn btn-secondary">Current Plan</button>
      {% else %}
        <a href="{% url 'subscriptions:checkout' plan.id %}" class="btn btn-primary">
          Choose Plan
        </a>
      {% endif %}
    </div>
  {% endfor %}
</div>
{% endblock %}
```

**`templates/subscriptions/checkout.html`**
```django
{% extends "base.html" %}
{% load static %}

{% block title %}Checkout - {{ plan.name }}{% endblock %}

{% block content %}
<div class="checkout-container">
  <h1>{{ plan.name }} Plan</h1>
  
  <div class="price-breakdown">
    <div>Base Amount: â‚¹{{ base_amount }}</div>
    <div>GST ({{ gst_rate }}%): â‚¹{{ gst_amount }}</div>
    <h3>Total: â‚¹{{ total_amount }}</h3>
  </div>

  <form id="paymentForm">
    <button type="button" onclick="payWithRazorpay()" class="btn btn-primary">
      Pay with Razorpay
    </button>
  </form>
</div>

<script src="https://checkout.razorpay.com/v1/checkout.js"></script>
<script>
function payWithRazorpay() {
  const options = {
    key: "{{ razorpay_key_id }}",
    amount: {{ total_amount }} * 100,  // Amount in paise
    currency: "INR",
    description: "{{ plan.name }} Subscription",
    prefill: {
      name: "{{ user.get_full_name }}",
      email: "{{ user.email }}",
    },
    handler: function(response) {
      // Save payment details and confirm subscription
      submitPayment(response);
    }
  };
  const rzp1 = new Razorpay(options);
  rzp1.open();
}
</script>
{% endblock %}
```

### Step 9: Add Feature Access Control

In your views/serializers, check subscription tier:

```python
from django.core.exceptions import PermissionDenied

def generate_advanced_report(request):
    if not request.user.subscription.can_access_feature('advanced_reporting'):
        raise PermissionDenied("Upgrade to Professional plan to access reports")
    # Generate report...
```

### Step 10: Setup Email Templates

Create `templates/subscriptions/emails/` folder with:
- `subscription_confirmation.html`
- `invoice.html`
- `renewal_reminder.html`
- `payment_failed.html`

---

## Testing Payouts

### Razorpay Test Cards

Use these card numbers for testing (test mode):
- **Success Card**: 4111111111111111 (any future date, any CVV)
- **Failed Card**: 4000000000000002
- **3D Secure**: 4012888888881881

CVV and Expiry: Any valid values

---

## Current Pricing (â‚¹ INR)

| Plan | Monthly | Annual | Users | Invoices | Features |
|------|---------|--------|-------|----------|----------|
| Starter | â‚¹999 | â‚¹9,990 | 5 | 500 | Basic |
| Professional | â‚¹3,999 | â‚¹39,990 | 50 | 10,000 | Advanced |
| Enterprise | Custom | Custom | âˆž | âˆž | All |

---

## Monitoring Checklist

### Before Going Live
- [ ] All Razorpay settings configured in production
- [ ] Email templates created and tested
- [ ] Webhook endpoint tested
- [ ] SSL/HTTPS enabled
- [ ] Payment success, failure flows tested
- [ ] Invoice generation tested
- [ ] Feature access control working
- [ ] Trial period logic verified
- [ ] GST calculation correct (18%)

### Daily Monitoring
- [ ] Check failed payments
- [ ] Monitor trial-to-paid conversion
- [ ] Track churn rate
- [ ] Verify webhook processing

### Weekly Reporting
- [ ] MRR (Monthly Recurring Revenue)
- [ ] Active subscriptions by tier
- [ ] Payment success rate
- [ ] Top upgrade reasons (feedback)

---

## Revenue Projections (Example)

Based on 10,000 SMB targets:

**Conservative (20% conversion):**
- Starter: 1,600 users Ã— â‚¹999 = â‚¹15.98L/month = â‚¹1.91Cr/year
- Professional: 400 users Ã— â‚¹3,999 = â‚¹15.99L/month = â‚¹1.92Cr/year
- **Total MRR**: â‚¹31.97L (~â‚¹2M/month)
- **Annual**: â‚¹3.83Cr

**Optimistic (35% conversion):**
- Starter: 2,800 users Ã— â‚¹999 = â‚¹27.97L/month
- Professional: 700 users Ã— â‚¹3,999 = â‚¹27.99L/month
- **Total MRR**: â‚¹55.96L (~â‚¹3.5M/month)
- **Annual**: â‚¹6.71Cr

---

## Common Issues & Solutions

### Issue: Webhook not triggering
**Solution**: 
1. Check webhook URL is publicly accessible
2. Verify webhook secret matches
3. Check firewall/rate limiting

### Issue: Payment fails after creating order
**Solution**:
1. Verify Razorpay keys are correct
2. Check amount calculation (in paise)
3. Look at Razorpay dashboard for error details

### Issue: GST calculation incorrect
**Solution**: 
1. Verify `BILLING_TAX_RATE` is set to `Decimal('18.00')`
2. Check Invoice.save() method calculates correctly
3. Test with manual creation

---

## File Reference

| File | Purpose |
|------|---------|
| `apps/subscriptions/models.py` | All subscription models |
| `apps/subscriptions/razorpay_service.py` | Payment gateway integration |
| `apps/subscriptions/views.py` | Payment & billing views |
| `apps/subscriptions/management/commands/create_default_plans.py` | Initialize plans |
| `SAAS_MONETIZATION_GUIDE.md` | Strategy documentation |
| `SUBSCRIPTION_SETTINGS_EXAMPLE.py` | Django settings reference |

---

## Questions or Issues?

- **Razorpay Support**: https://razorpay.com/support
- **Django Documentation**: https://docs.djangoproject.com
- **Your Rokkad Team**: support@rokkad.com

---

**Status**: Ready to implement! ðŸš€

