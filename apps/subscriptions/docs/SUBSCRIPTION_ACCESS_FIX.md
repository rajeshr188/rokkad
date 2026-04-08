# Fix: Subscription Access Pattern - User vs Workspace

## Issue
`AttributeError: 'CustomUser' object has no attribute 'subscription'`

### Root Cause
The code was trying to access subscriptions directly from the user object:
```python
subscription = self.request.user.subscription  # ❌ WRONG
```

However, the Subscription model is related to **Company (Workspace)**, not to the user:
```python
class Subscription(models.Model):
    company = models.OneToOneField(
        Company,  # ← Subscription belongs to workspace
        on_delete=models.CASCADE,
        related_name='subscription',
    )
```

## Solution
Changed all subscription access to go through the workspace:
```python
workspace = self.request.user.profile.workspace
subscription = workspace.subscription  # ✅ CORRECT
```

## Files Modified

### 1. `apps/subscriptions/views.py`

#### SubscriptionPlanListView
**Before:**
```python
context['current_subscription'] = self.request.user.subscription
```

**After:**
```python
workspace = self.request.user.profile.workspace
if workspace:
    context['current_subscription'] = workspace.subscription
else:
    context['current_subscription'] = None
```

#### SubscriptionDashboardView
**Before:**
```python
subscription = self.request.user.subscription
```

**After:**
```python
workspace = self.request.user.profile.workspace
if not workspace:
    context['subscription'] = None
    return context
subscription = workspace.subscription
```

#### InvoiceDetailView
**Before:**
```python
Invoice.objects.filter(subscription__user=self.request.user)
```

**After:**
```python
workspace = self.request.user.profile.workspace
Invoice.objects.filter(subscription__company=workspace)
```

#### InvoicePDFView
**Before:**
```python
Invoice.objects.filter(subscription__user=self.request.user)
```

**After:**
```python
workspace = self.request.user.profile.workspace
Invoice.objects.filter(subscription__company=workspace)
```

#### Added Import
Added `Http404` to imports for error handling when workspace is not selected.

## Data Model Diagram

```
User (CustomUser)
  ├─ profile (UserProfile)
  │   └─ workspace (Company) ← Selected workspace
  │       └─ subscription (Subscription) ← Current subscription
  │           └─ plan (Plan)
  │
  └─ memberships (Membership) ← Multiple workspaces user belongs to
      └─ company (Company)
```

## How It Works Now

1. **User logs in** → Profile has default/selected workspace
2. **Access subscription dashboard** → Gets workspace from user profile
3. **Query workspace subscription** → `workspace.subscription`
4. **Filter invoices** → By `subscription__company=workspace`

## Best Practice Going Forward

Always remember:
- **Workspace-level features**: Access through `request.user.profile.workspace`
- **Subscription management**: Always via workspace, never directly on user
- **Multi-tenant awareness**: Each user can belong to multiple workspaces (memberships)
- **Current context**: Use `request.user.profile.workspace` as the active workspace

## Testing
After fix, the subscription dashboard should:
- ✅ Load without AttributeError
- ✅ Display current subscription details
- ✅ Show recent invoices
- ✅ Calculate usage metrics
- ✅ Display renewal dates
