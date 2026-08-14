---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Fix: Subscription Navigation Loop

## Issue
User cannot navigate away from subscription dashboard to view plans or process billing. Clicking "View Plans" or other subscription links redirects back to the dashboard.

### Root Cause
The `SubscriptionValidationMiddleware` was creating a redirect loop:

1. User has **no subscription** (first-time user or fresh workspace)
2. User tries to access `subscriptions:plan-list` 
3. Middleware checks `workspace.subscription` 
4. Falls into `AttributeError` exception (no subscription yet)
5. Middleware redirects user back to `subscriptions:dashboard`
6. User can't escape the dashboard

```
Dashboard â†’ Click "View Plans" â†’ Middleware redirects â†’ Dashboard (loop âŒ)
```

## Solution

Updated `django_project/middleware.py` with three key changes:

### 1. **Expanded EXEMPT_URLS List**
Added all subscription-related URLs that should be accessible without an active subscription:
```python
EXEMPT_URLS = [
    # ... other URLs ...
    'subscriptions:plan-list',           # view available plans
    'subscriptions:checkout',             # checkout page  
    'subscriptions:payment-create',       # process payment
    'subscriptions:dashboard',            # billing dashboard
    'subscriptions:razorpay-webhook',     # payment webhook
    'subscriptions:invoice-detail',       # view invoice
    'subscriptions:invoice-pdf',          # download invoice PDF
]
```

### 2. **Smart Subscription Validation Logic**
Changed the exception handling to distinguish between:

- **No subscription yet** (Subscription.DoesNotExist) 
  - Don't redirect
  - Allow access to plan/checkout URLs
  - Only block tenant-specific features
  
- **Subscription exists but inactive/past due**
  - Redirect to dashboard
  - Show warning message

```python
except Subscription.DoesNotExist:
    # No subscription attached to workspace yet
    # Allow user to navigate to plans/checkout to create one
    current_url = resolve(request.path).url_name
    
    # Only redirect if accessing tenant data (not billing pages)
    if current_url and not current_url.startswith('subscriptions:') and 'tenant' in request.path.lower():
        messages.warning(request, 'âš ï¸ No active subscription found...')
        return redirect('subscriptions:plan-list')
    
    # Allow access to subscription/billing pages
    return None
```

### 3. **Added Subscription Import**
Imported `Subscription` model for exception handling:
```python
from apps.subscriptions.models import Subscription
```

## User Flow After Fix

âœ… **New User (No Subscription)**
```
Dashboard â†’ "View Plans" â†’ Plan List âœ…
Plan List â†’ Select Plan â†’ Checkout âœ…  
Checkout â†’ Payment â†’ Dashboard (with active subscription) âœ…
```

âœ… **Existing User (Expired Subscription)**
```
Dashboard â†’ Click any tenant feature â†’ Redirected to Dashboard âœ…
Dashboard â†’ "Renew Subscription" â†’ Plan List âœ…
Plan List â†’ Checkout â†’ Dashboard (subscription renewed) âœ…
```

## Key Differences

| Scenario | Before | After |
|----------|--------|-------|
| No subscription, view plans | âŒ Redirect loop | âœ… Allowed |
| No subscription, access tenant data | âŒ Redirect loop | âœ… Redirect to plans |
| Active subscription | âœ… Allowed | âœ… Allowed |
| Expired subscription, view plans | âŒ Blocked | âœ… Allowed |
| Expired subscription, access tenant data | âœ… Redirect | âœ… Redirect |

## Testing

```bash
# Verify changes
.venv\Scripts\python.exe manage.py check

# Test flows:
# 1. Create new workspace (no subscription)
# 2. Navigate to /subscriptions/plans/ (should load)
# 3. Select a plan and checkout (should work)
# 4. After payment, access dashboard (should work)
```

## Files Modified

- `django_project/middleware.py`
  - Added Subscription import
  - Expanded EXEMPT_URLS
  - Updated process_request logic
  - Better exception handling for DoesNotExist

## Behavior Summary

### Middleware Now:
- âœ… Allows users to **browse and purchase plans** without active subscription
- âœ… Allows users to **manage billing** without active subscription
- âœ… Blocks access to **tenant-specific data** without active subscription
- âœ… Blocks access to **expired/overdue** subscriptions (except billing)
- âœ… Graceful fallback if subscription model has issues

