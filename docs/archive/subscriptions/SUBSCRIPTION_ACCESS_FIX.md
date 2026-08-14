---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Fix: Subscription Access Pattern - User vs Workspace

## Issue
`AttributeError: 'CustomUser' object has no attribute 'subscription'`

### Root Cause
The code was trying to access subscriptions directly from the user object:
```python
subscription = self.request.user.subscription  # âŒ WRONG
```

However, the Subscription model is related to **Company (Workspace)**, not to the user:
```python
class Subscription(models.Model):
    company = models.OneToOneField(
        Company,  # â† Subscription belongs to workspace
        on_delete=models.CASCADE,
        related_name='subscription',
    )
```

## Solution
Changed all subscription access to go through the workspace:
```python
workspace = self.request.user.profile.workspace
subscription = workspace.subscription  # âœ… CORRECT
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
  â”œâ”€ profile (UserProfile)
  â”‚   â””â”€ workspace (Company) â† Selected workspace
  â”‚       â””â”€ subscription (Subscription) â† Current subscription
  â”‚           â””â”€ plan (Plan)
  â”‚
  â””â”€ memberships (Membership) â† Multiple workspaces user belongs to
      â””â”€ company (Company)
```

## How It Works Now

1. **User logs in** â†’ Profile has default/selected workspace
2. **Access subscription dashboard** â†’ Gets workspace from user profile
3. **Query workspace subscription** â†’ `workspace.subscription`
4. **Filter invoices** â†’ By `subscription__company=workspace`

## Best Practice Going Forward

Always remember:
- **Workspace-level features**: Access through `request.user.profile.workspace`
- **Subscription management**: Always via workspace, never directly on user
- **Multi-tenant awareness**: Each user can belong to multiple workspaces (memberships)
- **Current context**: Use `request.user.profile.workspace` as the active workspace

## Testing
After fix, the subscription dashboard should:
- âœ… Load without AttributeError
- âœ… Display current subscription details
- âœ… Show recent invoices
- âœ… Calculate usage metrics
- âœ… Display renewal dates

