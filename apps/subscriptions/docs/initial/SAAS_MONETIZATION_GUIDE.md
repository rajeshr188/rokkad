# SaaS Monetization Strategy - India Market

## Overview
This document outlines the monetization strategy for the Rokkad SaaS application targeting 10,000+ SMBs in India.

---

## Pricing Model

### Tiered Subscription Plans

| Feature | **Starter** | **Professional** | **Enterprise** |
|---------|-----------|-----------------|----------------|
| **Monthly Price** | ₹999 | ₹3,999 | Custom |
| **Yearly Price** | ₹9,990 | ₹39,990 | Custom |
| **Annual Discount** | 20% off | 20% off | Negotiable |
| **Users** | 5 | 50 | Unlimited |
| **Products** | 100 | 2,000 | Unlimited |
| **Invoices/Month** | 500 | 10,000 | Unlimited |
| **Transactions/Month** | 500 | 10,000 | Unlimited |
| **Warehouses** | 1 | 5 | Unlimited |
| **Advanced Reports** | ❌ | ✅ | ✅ |
| **Multi-Warehouse** | ❌ | ✅ | ✅ |
| **Approvals Workflow** | ❌ | ✅ | ✅ |
| **API Access** | ❌ | ❌ | ✅ |
| **Custom Fields** | ❌ | ✅ | ✅ |
| **Trial Period** | 14 days | 14 days | 30 days |
| **Support** | Email | Priority Email | Dedicated |

---

## Revenue Streams

### 1. **Base Subscription Revenue**
```
Starter Tier:
- Monthly: ₹999 × 8,000 customers = ₹79,92,000/month
- Annual recurring: ₹9,990 × 2,000 customers = ₹1,99,80,000/year

Professional Tier:
- Monthly: ₹3,999 × 1,500 customers = ₹59,98,500/month
- Annual recurring: ₹39,990 × 500 customers = ₹1,99,95,000/year

Enterprise Tier:
- Custom pricing: ₹500 × 100 customers (avg) = ₹50,000/month avg
```

### 2. **Add-On Charges**
- **Extra Users**: ₹99/user/month (for overflow beyond plan limit)
- **Advanced Integrations**: ₹2,000-5,000/month
- **Dedicated Support**: ₹5,000-10,000/month
- **Custom Development**: ₹50,000+ (one-time)

### 3. **Transaction-Based Revenue (Optional)**
For companies preferring usage-based pricing:
- Per Invoice: ₹2-5
- Per Transaction: ₹0.50-1
- Per SKU managed: ₹0.10-0.50

---

## Payment Processing

### Razorpay Integration
Razorpay is the primary payment gateway (best for India):

**Setup Steps:**

1. **Register with Razorpay**
   - Visit: https://razorpay.com/pricing
   - Create merchant account
   - Get API keys (KEY_ID and KEY_SECRET)

2. **Update Django Settings**
   ```python
   # settings.py
   RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID')
   RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET')
   
   # Webhook settings
   RAZORPAY_WEBHOOK_SECRET = os.environ.get('RAZORPAY_WEBHOOK_SECRET')
   ```

3. **Environment Variables (.env)**
   ```
   RAZORPAY_KEY_ID=rzp_live_xxxxxxxxxxxxx
   RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxx
   RAZORPAY_WEBHOOK_SECRET=xxxxxxxxxxxxxxxx
   ```

### Payment Methods Supported
- ✅ Credit/Debit Cards (all major banks)
- ✅ Net Banking (ICICI, HDFC, SBI, Axis, etc.)
- ✅ UPI (Google Pay, PhonePe, etc.)
- ✅ Digital Wallets (Paytm, etc.)
- ✅ Recurring Payments (E-Mandate for auto-renewal)

---

## Billing Cycle

### Monthly Billing
1. **Day 1**: Invoice generated
2. **Day 7**: Payment due
3. **Day 14**: Dunning email if unpaid
4. **Day 30**: Automatic payment attempt via Razorpay E-Mandate
5. **Day 35**: Service suspension if unpaid

### Yearly Billing
- 20% discount applied automatically
- Single annual payment
- Same dunning process

---

## GST Calculation (India-Specific)

GST rates applied:
- **Base Rate**: 18% on subscription fees
- **Reverse Charge**: N/A (not applicable for SaaS)
- **Invoice Breakdown**:
  ```
  Subtotal: ₹3,999
  GST (18%): ₹719.82
  Total: ₹4,718.82
  ```

**GST Compliance**:
- All invoices include GST
- GST certificate available for registered businesses
- Tax invoice format compliant with Indian tax laws

---

## Implementation Checklist

### Phase 1: Foundation (Month 1-2)
- ✅ Database models created (Plan, Subscription, Invoice, Payment)
- ✅ Razorpay service integration
- ⬜ Payment checkout page
- ⬜ Invoice generation and email delivery
- ⬜ Invoice download (PDF) feature
- ⬜ Trial period management

### Phase 2: Operations (Month 3-4)
- ⬜ Billing dashboard (view invoices, usage, renewal date)
- ⬜ Plan upgrade/downgrade flow
- ⬜ Auto-renewal and dunning management
- ⬜ Feature access control based on plan tier
- ⬜ Usage metrics tracking

### Phase 3: Scale (Month 5-6)
- ⬜ Annual billing option
- ⬜ Coupon/discount codes
- ⬜ Referral program (e.g., 20% commission per referral)
- ⬜ White-label pricing for resellers
- ⬜ Custom pricing overrides for enterprise deals

### Phase 4: Growth (Month 7+)
- ⬜ Analytics dashboard (MRR, ARR, churn rate)
- ⬜ Automated dunning and retry logic
- ⬜ API rate limiting based on tier
- ⬜ Multi-currency support
- ⬜ Marketplace for add-ons

---

## Key Metrics to Track

### Business Metrics
```python
MRR (Monthly Recurring Revenue) = Sum of all active monthly subscriptions
ARR (Annual Recurring Revenue) = MRR × 12
Churn Rate = (Cancelled customers / Total customers) × 100
CAC (Customer Acquisition Cost) = Marketing spend / New customers
LTV (Lifetime Value) = (ARPU × Gross margin) / Monthly churn rate
```

### Usage Metrics
- Active users per subscription
- Transactions per month
- Invoice count
- Warehouse count
- Feature adoption rate by tier

### Billing Metrics
- Failed payment rate
- Days to revenue (payment collection time)
- Refund rate
- Payment method distribution

---

## Migration Path from Free to Paid

### Current State: Free Trial
- All users get 14-day free trial
- Unlimited features during trial
- Email reminder 3 days before trial ends

### After Trial Ends
1. **Email Campaign** (Day 14)
   - Offer for the plan matching their usage
   - Limited-time discount (₹500 off first month)

2. **In-App Prompts** (Day 15+)
   - Non-intrusive banner
   - "Upgrade to continue" when feature limit reached

3. **Checkout Flow**
   - Select plan
   - Billing cycle (monthly/yearly)
   - Apply coupon if any
   - Razorpay payment gateway
   - Instant account activation

---

## Feature Access Control

### Implementation Example
```python
# In views or serializers
if not request.user.subscription.can_access_feature('advanced_reporting'):
    raise PermissionDenied("Upgrade to Professional plan for this feature")

# In models
if subscription.plan.has_multi_warehouse:
    # Enable multi-warehouse UI
```

### Features by Tier
- **Starter**: Basic inventory, invoicing, reports
- **Professional**: Advanced reports, multi-warehouse, approval workflow
- **Enterprise**: Custom integrations, API access, white-label options

---

## Industry Benchmarks (SaaS in India)

- **CAC**: ₹5,000-15,000 per customer
- **LTV**: ₹3,00,000-10,00,000+
- **Churn Rate**: 5-10% monthly for SMB SaaS
- **Expansion Revenue**: 30-50% of MRR
- **Gross Margin**: 70-85% for SaaS

---

## Next Steps

1. **Create migration** for new models
   ```bash
   python manage.py makemigrations subscriptions
   python manage.py migrate
   ```

2. **Initialize default plans**
   ```bash
   python manage.py create_default_plans
   ```

3. **Implement payment views** (checkout, webhook handler)
4. **Add feature access controls** throughout the app
5. **Create billing dashboard** for customers
6. **Set up Razorpay webhooks** for payment status updates
7. **Create invoice PDF generation** service
8. **Build analytics dashboard** for company metrics

---

## Resources

- **Razorpay Docs**: https://razorpay.com/docs/
- **Razorpay Integration Guide**: https://razorpay.com/docs/payments/
- **Indian SaaS Market Analysis**: https://yourstory.com/
- **Payment Security**: PCI DSS compliance via Razorpay

---

**Last Updated**: Feb 27, 2025  
**Status**: Ready for implementation
