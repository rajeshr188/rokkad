# Updating Views for Company-Based Subscriptions

## Overview

All views that access subscription data need to be updated to work with **company-level** subscriptions instead of **user-level** subscriptions.

---

## Key Changes

### Getting Subscription Reference

**Before** (User-based):
```python
subscription = request.user.subscription
```

**After** (Company-based):
```python
# Get current company from request (set by middleware)
company = get_current_company(request)
subscription = company.subscription
```

---

## Required Middleware/Context

Your views need to know the current company. Add this middleware:

```python
# apps/subscriptions/middleware.py

from apps.orgs.models import Company

class CompanyContextMiddleware:
    """Add current company to request object"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Get company from URL parameter or session
        company_id = request.GET.get('company_id') or request.session.get('current_company_id')
        
        if company_id:
            request.company = Company.objects.get(id=company_id)
            request.workspace = request.company  # Alias
        else:
            # Default to first company user is member of
            request.company = request.user.memberships.first().company if hasattr(request.user, 'memberships') else None
        
        response = self.get_response(request)
        return response
```

Add to `MIDDLEWARE`:
```python
MIDDLEWARE = [
    # ...
    'apps.subscriptions.middleware.CompanyContextMiddleware',
    # ...
]
```

---

## View Examples

### 1. Billing Dashboard View

**Before**:
```python
class SubscriptionDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'subscriptions/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            subscription = self.request.user.subscription
            context['subscription'] = subscription
            context['plan'] = subscription.plan
            
            context['recent_invoices'] = Invoice.objects.filter(
                subscription=subscription
            ).order_by('-invoice_date')[:5]
            
            # This field no longer exists!
            context['user_overage'] = max(
                0, 
                subscription.current_user_count - subscription.plan.max_users
            )
            
        except Subscription.DoesNotExist:
            context['subscription'] = None
        
        return context
```

**After**:
```python
class SubscriptionDashboardView(LoginRequiredMixin, TemplateView):
    """Display company subscription and billing info"""
    template_name = 'subscriptions/dashboard.html'
    
    def dispatch(self, request, *args, **kwargs):
        """Verify user can access billing for this company"""
        if not request.company:
            raise Http404("No workspace selected")
        
        subscription = request.company.subscription
        if not subscription.is_billing_manager(request.user):
            raise PermissionDenied("Only company admins can view billing")
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        company = self.request.company
        subscription = company.subscription
        
        context.update({
            'company': company,
            'subscription': subscription,
            'plan': subscription.plan,
            
            # Recent invoices
            'recent_invoices': Invoice.objects.filter(
                subscription=subscription
            ).order_by('-invoice_date')[:5],
            
            # Current usage (from UsageMetrics)
            'current_users': subscription.get_current_user_count(),
            'max_users': subscription.plan.max_users,
            
            # Overage information
            'user_overage': subscription.get_overage_users(),
            'overage_charge': subscription.get_overage_charge(),
            'total_monthly': subscription.get_total_charges(),
            
            # Renewal info
            'days_until_renewal': subscription.days_until_renewal(),
            'is_trial': subscription.is_trial_active(),
            'trial_end_date': subscription.trial_end_date,
            
            # Seat status
            'can_add_members': subscription.can_add_member(),
            'members_near_limit': subscription.get_current_user_count() > (subscription.plan.max_users * 0.8),
        })
        
        return context
```

---

### 2. Checkout View

**Before**:
```python
class CheckoutView(LoginRequiredMixin, TemplateView):
    template_name = 'subscriptions/checkout.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        plan_id = self.kwargs.get('plan_id')
        plan = get_object_or_404(Plan, id=plan_id, is_active=True)
        
        amount = plan.price
        gst_amount = amount * Decimal('18') / Decimal('100')
        total = amount + gst_amount
        
        context.update({
            'plan': plan,
            'base_amount': amount,
            'gst_amount': gst_amount,
            'total_amount': total,
        })
        
        return context
```

**After**:
```python
class CheckoutView(LoginRequiredMixin, TemplateView):
    """Display checkout for plan upgrade/downgrade"""
    template_name = 'subscriptions/checkout.html'
    
    def dispatch(self, request, *args, **kwargs):
        """Only billing managers can checkout"""
        if not request.company:
            return redirect('orgs:company-list')
        
        subscription = request.company.subscription
        if not subscription.is_billing_manager(request.user):
            raise PermissionDenied("Only company admins can upgrade plans")
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        plan_id = self.kwargs.get('plan_id')
        plan = get_object_or_404(Plan, id=plan_id, is_active=True)
        
        # Check for price overrides
        company = self.request.company
        override = company.subscription.price_override if hasattr(company.subscription, 'price_override') else None
        
        if override and override.is_active():
            amount = override.custom_monthly_price
        else:
            amount = plan.price
        
        gst_rate = Decimal(getattr(settings, 'BILLING_TAX_RATE', '18'))
        gst_amount = amount * gst_rate / Decimal('100')
        total = amount + gst_amount
        
        context.update({
            'company': company,
            'plan': plan,
            'billing_cycle': self.request.GET.get('cycle', 'monthly'),
            'base_amount': amount,
            'gst_rate': gst_rate,
            'gst_amount': gst_amount,
            'total_amount': total,
            'razorpay_key_id': settings.RAZORPAY_KEY_ID,
            'current_plan': company.subscription.plan,
        })
        
        return context
```

---

### 3. Payment Processing View

**Before**:
```python
class PaymentView(LoginRequiredMixin, CreateView):
    model = Subscription
    fields = []
    
    @require_POST
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            
            plan_id = data.get('plan_id')
            razorpay_payment_id = data.get('razorpay_payment_id')
            razorpay_order_id = data.get('razorpay_order_id')
            razorpay_signature = data.get('razorpay_signature')
            
            # Verify payment
            if not RazorpayService.verify_payment_signature(
                razorpay_order_id, 
                razorpay_payment_id, 
                razorpay_signature
            ):
                return JsonResponse({'success': False, 'error': 'Payment verification failed'}, status=400)
            
            plan = get_object_or_404(Plan, id=plan_id)
            
            # Update user's subscription
            subscription, created = Subscription.objects.update_or_create(
                user=request.user,
                defaults={'plan': plan, 'status': Subscription.StatusChoices.ACTIVE}
            )
            
            return JsonResponse({'success': True, 'subscription_id': subscription.id})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
```

**After**:
```python
class PaymentView(LoginRequiredMixin, CreateView):
    """Process payment and activate subscription"""
    model = Payment
    fields = []
    
    def dispatch(self, request, *args, **kwargs):
        if not request.company:
            return JsonResponse({'success': False, 'error': 'No workspace selected'}, status=400)
        
        subscription = request.company.subscription
        if not subscription.is_billing_manager(request.user):
            return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
        
        return super().dispatch(request, *args, **kwargs)
    
    @require_POST
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            
            plan_id = data.get('plan_id')
            razorpay_payment_id = data.get('razorpay_payment_id')
            razorpay_order_id = data.get('razorpay_order_id')
            razorpay_signature = data.get('razorpay_signature')
            
            # Verify payment signature
            if not RazorpayService.verify_payment_signature(
                razorpay_order_id, 
                razorpay_payment_id, 
                razorpay_signature
            ):
                return JsonResponse({
                    'success': False,
                    'error': 'Payment verification failed'
                }, status=400)
            
            plan = get_object_or_404(Plan, id=plan_id)
            company = request.company
            
            # Update company's subscription
            subscription = company.subscription
            subscription.plan = plan
            subscription.status = Subscription.StatusChoices.ACTIVE
            subscription.save()
            
            # Find and mark invoice as paid
            try:
                invoice = Invoice.objects.get(razorpay_order_id=razorpay_order_id)
                invoice.mark_as_paid(razorpay_payment_id)
            except Invoice.DoesNotExist:
                pass
            
            # Send confirmation email to all company admins
            send_payment_confirmation(subscription, razorpay_payment_id)
            
            return JsonResponse({
                'success': True,
                'message': 'Payment successful',
                'subscription_id': subscription.id,
                'redirect_url': reverse('subscriptions:dashboard', kwargs={'company_id': company.id})
            })
            
        except Exception as e:
            logger.error(f"Payment processing error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Payment processing failed'
            }, status=500)
```

---

### 4. Invoice Detail View

**Before**:
```python
class InvoiceDetailView(LoginRequiredMixin, DetailView):
    model = Invoice
    template_name = 'subscriptions/invoice_detail.html'
    context_object_name = 'invoice'
    
    def get_object(self):
        invoice = get_object_or_404(
            Invoice,
            id=self.kwargs['pk'],
            subscription__user=self.request.user  # ❌ This won't work anymore
        )
        return invoice
```

**After**:
```python
class InvoiceDetailView(LoginRequiredMixin, DetailView):
    """Display invoice details"""
    model = Invoice
    template_name = 'subscriptions/invoice_detail.html'
    context_object_name = 'invoice'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.company:
            raise Http404("Workspace not found")
        
        invoice = self.get_object()
        if invoice.subscription.company != request.company:
            raise PermissionDenied("You don't have access to this invoice")
        
        if not invoice.subscription.is_billing_manager(request.user):
            raise PermissionDenied("Only billing managers can view invoices")
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_object(self):
        """Get invoice for current company"""
        invoice = get_object_or_404(
            Invoice,
            id=self.kwargs['pk'],
            subscription__company=self.request.company  # ✅ Company-based
        )
        return invoice
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        invoice = self.get_object()
        context.update({
            'company': invoice.subscription.company,
            'subscription': invoice.subscription,
            'gst_percentage': invoice.gst_rate,
            'can_download_pdf': True,
        })
        return context
```

---

### 5. Permission Mixin for Features

```python
# apps/subscriptions/mixins.py

class SubscriptionFeatureRequiredMixin(LoginRequiredMixin):
    """
    Mixin to restrict feature access by subscription tier.
    Usage: class MyView(SubscriptionFeatureRequiredMixin, View):
               feature_required = 'advanced_reporting'
               feature_name = 'Advanced Reporting'
    """
    feature_required = None
    feature_name = None
    required_plan = 'Professional'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.company:
            raise Http404("Workspace not found")
        
        subscription = request.company.subscription
        
        if not subscription.can_access_feature(self.feature_required):
            messages.error(
                request,
                f"{self.feature_name} requires {self.required_plan} plan or higher. "
                f"<a href='{reverse('subscriptions:checkout')}'>Upgrade now</a>"
            )
            raise PermissionDenied(
                f"{self.feature_name} is not available on your current plan"
            )
        
        return super().dispatch(request, *args, **kwargs)


# Usage in views:
class AdvancedReportView(SubscriptionFeatureRequiredMixin, ListView):
    feature_required = 'advanced_reporting'
    feature_name = 'Advanced Reports'
    required_plan = 'Professional'
    
    template_name = 'reports/advanced_reports.html'
    model = Transaction
```

---

### 6. Invite Member View

```python
class InviteMemberView(LoginRequiredMixin, CreateView):
    """Invite user to company"""
    model = CompanyInvitation
    fields = ['email', 'role']
    
    def dispatch(self, request, *args, **kwargs):
        company = request.company
        subscription = company.subscription
        
        # Check if company can add more members
        if not subscription.can_add_member():
            messages.warning(
                request,
                f"You've reached the member limit ({subscription.plan.max_users}) on {subscription.plan.name} plan. "
                f"<a href='{reverse('subscriptions:upgrade')}'>Upgrade to add more members</a>"
            )
            raise PermissionDenied("Member limit reached. Upgrade your plan.")
        
        # Check if user can invite (owner/admin)
        if not subscription.is_billing_manager(request.user):
            raise PermissionDenied("Only company admins can invite members")
        
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        form.instance.company = self.request.company
        form.instance.inviter = self.request.user
        return super().form_valid(form)
```

---

## Template Updates

### Dashboard Template

**Before**:
```django
<h1>{{ request.user }}'s Subscription</h1>
<p>Plan: {{ subscription.plan.name }}</p>
<p>Users: {{ subscription.current_user_count }} / {{ subscription.plan.max_users }}</p>
```

**After**:
```django
<h1>{{ company.name }} Subscription</h1>
<p>Plan: {{ subscription.plan.name }}</p>
<p>Users: {{ current_users }} / {{ max_users }}</p>
<p>Overage Cost: ₹{{ overage_charge }}/month</p>

{% if member_near_limit %}
  <div class="alert alert-warning">
    You're using {{ current_users }}/{{ max_users }} seats.
    <a href="{% url 'subscriptions:checkout' subscription.plan.id %}">Upgrade now</a>
  </div>
{% endif %}

{% if not can_add_members %}
  <div class="alert alert-danger">
    You've reached the member limit for your plan.
    You can add more members by paying ₹99/month per extra user,
    or <a href="{% url 'subscriptions:upgrade' %}">upgrade your plan</a>.
  </div>
{% endif %}
```

---

## Summary of Changes

| Aspect | Before | After |
|--------|--------|-------|
| Subscription owner | `request.user` | `request.company` |
| Get subscription | `request.user.subscription` | `request.company.subscription` |
| Get user count | `subscription.current_user_count` | `subscription.get_current_user_count()` |
| Overage users | Manual calc | `subscription.get_overage_users()` |
| Billing manager | Owner | Owner + billing admin role |
| Invoice recipient | User email | Company admin emails |
| Feature access | User tier | Company tier |
| Add member check | None | `subscription.can_add_member()` |

---

## Testing Views

```python
# tests.py

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from apps.orgs.models import Company, Membership, Role
from apps.subscriptions.models import Plan, Subscription

User = get_user_model()

class BillingViewTests(TestCase):
    def setUp(self):
        # Create user
        self.user = User.objects.create_user(
            username='owner', 
            email='owner@example.com',
            password='testpass123'
        )
        
        # Create company
        self.company = Company.objects.create(
            name='Acme Corp',
            owner=self.user,
            creator=self.user
        )
        
        # Create membership
        role = Role.objects.create(name='Owner')
        Membership.objects.create(
            user=self.user,
            company=self.company,
            role=role
        )
        
        # Create subscription
        plan = Plan.objects.create(
            name='Professional',
            tier='professional',
            price=Decimal('3999.00'),
            max_users=50
        )
        self.subscription = Subscription.objects.create(
            company=self.company,
            plan=plan
        )
        
        self.client = Client()
    
    def test_dashboard_access(self):
        self.client.login(username='owner', password='testpass123')
        response = self.client.get(
            reverse('subscriptions:dashboard'),
            {'company_id': self.company.id}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Acme Corp')
        self.assertContains(response, 'Professional')
    
    def test_overage_calculation(self):
        self.subscription.current_user_count = 55  # 5 over limit
        # ... test overage charges
```

---

## Deployment Notes

1. **Backup database** before migration
2. **Test views locally** with company context
3. **Monitor error logs** after deployment
4. **Update docs** for team
5. **Notify users** of any UI changes
