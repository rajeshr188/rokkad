# Permission Matrix & Role-Based Access Control

## Current State vs Proposed State

### ❌ Current Issues

```
CURRENT FLOW (Problematic):
┌─────────────────────────────────────────┐
│ @roles_required(['Owner', 'Admin'])      │
│                                          │
│ - Only checks role name                 │
│ - No granular permission checks         │
│ - All 'Admin' roles have same power     │
│ - No feature-level access control       │
│ - No data-level (row) checks            │
│ - No subscription validation            │
└─────────────────────────────────────────┘

Result:
- Any Admin can do ANY admin action
- No audit trail
- Can't restrict feature access per plan
- Can't implement custom permissions
```

### ✅ Proposed State

```
PROPOSED FLOW (Robust):
┌─────────────────────────────────────────┐
│ @login_required                          │
│ @workspace_required                      │
│ @subscription_valid                      │
│ @permission_required('workspace_view')   │
│ @object_permission_required('edit')      │
│                                          │
│ if not has_feature_access():             │
│     return feature_locked_page()         │
└─────────────────────────────────────────┘

Result:
- Layered permission checks
- Granular feature access
- Row-level data access control  
- Full audit trail
- Subscription-aware
```

---

## Permission Matrix

### Core Workspace Permissions

```
┌──────────────────────────┬────────┬───────┬────────┬──────────┐
│ Permission               │ Owner  │ Admin │ Member │ Viewer   │
├──────────────────────────┼────────┼───────┼────────┼──────────┤
│ workspace_view           │   ✅   │  ✅   │  ✅    │   ✅     │
│ workspace_edit           │   ✅   │  ✅   │  ❌    │   ❌     │
│ workspace_delete         │   ✅   │  ❌   │  ❌    │   ❌     │
│ workspace_transfer       │   ✅   │  ❌   │  ❌    │   ❌     │
│                          │        │       │        │          │
│ team_view               │   ✅   │  ✅   │  ❌    │   ❌     │
│ team_invite             │   ✅   │  ✅   │  ❌    │   ❌     │
│ team_edit_role          │   ✅   │  ❌   │  ❌    │   ❌     │
│ team_remove             │   ✅   │  ✅*  │  ❌    │   ❌     │
│ team_suspend            │   ✅   │  ❌   │  ❌    │   ❌     │
│                          │        │       │        │          │
│ billing_view            │   ✅   │  ✅   │  ❌    │   ❌     │
│ billing_edit            │   ✅   │  ❌   │  ❌    │   ❌     │
│ billing_cancel          │   ✅   │  ❌   │  ❌    │   ❌     │
│                          │        │       │        │          │
│ audit_log_view          │   ✅   │  ✅   │  ❌    │   ❌     │
│ export_audit_log        │   ✅   │  ❌   │  ❌    │   ❌     │
└──────────────────────────┴────────┴───────┴────────┴──────────┘

* Admin can only remove Members (not other Admins)
```

### Data-Level Permissions (Per Module)

#### Loan Management (Girvi)

```
┌──────────────────────────┬────────┬───────┬────────┬──────────┐
│ Permission               │ Owner  │ Admin │ Member │ Viewer   │
├──────────────────────────┼────────┼───────┼────────┼──────────┤
│ girvi_loan_view          │   ✅   │  ✅   │  ✅    │   ❌     │
│ girvi_loan_create        │   ✅   │  ✅   │  ✅    │   ❌     │
│ girvi_loan_edit_own      │   ✅   │  ✅   │  ✅    │   ❌     │
│ girvi_loan_edit_any      │   ✅   │  ✅   │  ❌    │   ❌     │
│ girvi_loan_delete        │   ✅   │  ✅   │  ❌    │   ❌     │
│                          │        │       │        │          │
│ girvi_release_view       │   ✅   │  ✅   │  ✅    │   ✅     │
│ girvi_release_create     │   ✅   │  ✅   │  ❌    │   ❌     │
│ girvi_release_approve    │   ✅   │  ✅   │  ❌    │   ❌     │
│                          │        │       │        │          │
│ girvi_report_view        │   ✅   │  ✅   │  ✅    │   ✅     │
│ girvi_report_export      │   ✅   │  ✅   │  ❌    │   ❌     │
└──────────────────────────┴────────┴───────┴────────┴──────────┘
```

#### Sales Management

```
┌──────────────────────────┬────────┬───────┬────────┬──────────┐
│ Permission               │ Owner  │ Admin │ Member │ Viewer   │
├──────────────────────────┼────────┼───────┼────────┼──────────┤
│ sales_invoice_view       │   ✅   │  ✅   │  ✅    │   ❌     │
│ sales_invoice_create     │   ✅   │  ✅   │  ✅    │   ❌     │
│ sales_invoice_edit_own   │   ✅   │  ✅   │  ✅    │   ❌     │
│ sales_invoice_edit_any   │   ✅   │  ✅   │  ❌    │   ❌     │
│ sales_invoice_delete     │   ✅   │  ✅   │  ❌    │   ❌     │
│                          │        │       │        │          │
│ sales_receipt_view       │   ✅   │  ✅   │  ✅    │   ❌     │
│ sales_receipt_create     │   ✅   │  ✅   │  ✅    │   ❌     │
│ sales_receipt_print      │   ✅   │  ✅   │  ✅    │   ❌     │
│                          │        │       │        │          │
│ sales_customer_view      │   ✅   │  ✅   │  ✅    │   ✅     │
│ sales_customer_edit      │   ✅   │  ✅   │  ❌    │   ❌     │
└──────────────────────────┴────────┴───────┴────────┴──────────┘
```

#### Purchase Management

```
┌──────────────────────────┬────────┬───────┬────────┬──────────┐
│ Permission               │ Owner  │ Admin │ Member │ Viewer   │
├──────────────────────────┼────────┼───────┼────────┼──────────┤
│ purchase_invoice_view    │   ✅   │  ✅   │  ✅    │   ❌     │
│ purchase_invoice_create  │   ✅   │  ✅   │  ✅    │   ❌     │
│ purchase_invoice_edit    │   ✅   │  ✅   │  ❌    │   ❌     │
│ purchase_invoice_delete  │   ✅   │  ✅   │  ❌    │   ❌     │
│                          │        │       │        │          │
│ purchase_payment_view    │   ✅   │  ✅   │  ✅    │   ❌     │
│ purchase_payment_create  │   ✅   │  ✅   │  ❌    │   ❌     │
│ purchase_supplier_edit   │   ✅   │  ✅   │  ❌    │   ❌     │
└──────────────────────────┴────────┴───────┴────────┴──────────┘
```

#### Accounting (DEA - Double Entry Accounting)

```
┌──────────────────────────┬────────┬───────┬────────┬──────────┐
│ Permission               │ Owner  │ Admin │ Member │ Viewer   │
├──────────────────────────┼────────┼───────┼────────┼──────────┤
│ dea_journal_view         │   ✅   │  ✅   │  ❌    │   ❌     │
│ dea_journal_create       │   ✅   │  ✅   │  ❌    │   ❌     │
│ dea_journal_approve      │   ✅   │  ✅   │  ❌    │   ❌     │
│                          │        │       │        │          │
│ dea_ledger_view          │   ✅   │  ✅   │  ✅    │   ✅     │
│ dea_reconcile            │   ✅   │  ✅   │  ❌    │   ❌     │
│ dea_report_view          │   ✅   │  ✅   │  ✅    │   ✅     │
│ dea_report_export        │   ✅   │  ✅   │  ❌    │   ❌     │
│                          │        │       │        │          │
│ dea_opening_balance_edit │   ✅   │  ❌   │  ❌    │   ❌     │
│ dea_close_period         │   ✅   │  ✅   │  ❌    │   ❌     │
└──────────────────────────┴────────┴───────┴────────┴──────────┘
```

---

## Feature-Level Access Control

### Per-Plan Feature Availability

```
PLAN: Free
├── Workspace: 1
├── Team Members: 3
├── Features:
│   ├── Loan Management: ✅ (read-only)
│   ├── Invoice/Receipt: ✅ (read-only)
│   ├── Accounting: ❌ (locked)
│   ├── Reports: ❌ (limited)
│   └── API Access: ❌
└── Storage: 1 GB

PLAN: Pro ($49/mo)
├── Workspace: 5
├── Team Members: 10
├── Features:
│   ├── Loan Management: ✅ (full)
│   ├── Invoice/Receipt: ✅ (full)
│   ├── Accounting: ✅ (read-only)
│   ├── Reports: ✅ (standard)
│   └── API Access: ✅ (basic)
└── Storage: 10 GB

PLAN: Business ($149/mo)
├── Workspace: Unlimited
├── Team Members: Unlimited
├── Features:
│   ├── All Pro features: ✅
│   ├── Accounting: ✅ (full)
│   ├── Advanced Reports: ✅
│   ├── API Access: ✅ (pro)
│   ├── Webhooks: ✅
│   └── Support: Priority email
└── Storage: 100 GB

PLAN: Enterprise (Custom)
├── Everything in Business: ✅
└── Plus:
    ├── Account Manager: ✅
    ├── Custom Integration: ✅
    ├── On-premise Option: ✅
    └── SLA: ✅
```

### Feature Gating Implementation

```python
# apps/orgs/permissions.py
FEATURE_PERMISSIONS = {
    'girvi': {
        'read': ['Free', 'Pro', 'Business', 'Enterprise'],
        'write': ['Pro', 'Business', 'Enterprise'],
        'approve': ['Business', 'Enterprise'],
        'advanced_features': ['Business', 'Enterprise'],
    },
    'sales': {
        'read': ['Free', 'Pro', 'Business', 'Enterprise'],
        'write': ['Free', 'Pro', 'Business', 'Enterprise'],
    },
    'dea': {
        'read': ['Pro', 'Business', 'Enterprise'],
        'write': ['Business', 'Enterprise'],
        'reconcile': ['Business', 'Enterprise'],
    },
    'reports': {
        'standard': ['Pro', 'Business', 'Enterprise'],
        'advanced': ['Business', 'Enterprise'],
        'custom': ['Enterprise'],
    },
    'api': {
        'basic': ['Pro', 'Business', 'Enterprise'],
        'pro': ['Business', 'Enterprise'],
        'enterprise': ['Enterprise'],
    }
}

# Decorator usage
@feature_required('girvi', 'write')
def create_loan(request):
    # Only users on Pro+ plans with write permission
    pass

@feature_required('dea')
def view_accounting(request):
    # Only Pro+ users
    pass
```

### Checking Feature Access in Templates

```html
{% load permission_tags %}

<!-- Feature-based UI rendering -->
{% if user|has_feature:'girvi_write' %}
    <a href="{% url 'girvi:loan_create' %}" class="btn btn-primary">
        Create Loan
    </a>
{% else %}
    <div class="feature-locked">
        <p>Loan creation requires {{ required_plan }} plan</p>
        <a href="{% url 'billing:upgrade' %}">Upgrade Now</a>
    </div>
{% endif %}

<!-- Role-based UI -->
{% if user|has_permission:'team_invite' %}
    <button id="invite-team-member">Invite Team Member</button>
{% endif %}

<!-- Object-level permission check -->
{% if invoice|user_can:'edit':user %}
    <a href="{{ invoice.get_edit_url }}">Edit</a>
{% endif %}
```

---

## Implementation Code Examples

### 1. Permission Decorator

```python
# apps/orgs/decorators.py
from functools import wraps
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.contrib import messages

def permission_required(permission_codename):
    """Check if user has specific permission in their workspace"""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            user = request.user
            workspace = user.profile.workspace
            
            if not workspace:
                raise Http404('No workspace selected')
            
            # Get user's membership
            try:
                membership = Membership.objects.get(
                    user=user,
                    company=workspace
                )
            except Membership.DoesNotExist:
                raise Http404('Not a member of this workspace')
            
            # Check if role has permission
            has_perm = membership.role.permissions.filter(
                codename=permission_codename
            ).exists()
            
            if not has_perm:
                raise Http404(
                    f'This action requires "{permission_codename}" permission'
                )
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator

# Usage
@permission_required('team_invite')
def invite_user(request):
    # Only users with team_invite permission
    pass
```

### 2. Feature Gating Decorator

```python
def feature_required(feature_name, access_level='read'):
    """Check if user's plan includes this feature at this access level"""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            user = request.user
            workspace = user.profile.workspace
            
            if not workspace:
                raise Http404('No workspace selected')
            
            # Get subscription
            subscription = Subscription.objects.filter(
                company=workspace,
                is_active=True
            ).first()
            
            if not subscription:
                messages.error(request, 'Subscription required')
                return redirect('billing:renew')
            
            # Check feature availability
            plan = subscription.plan.name
            if plan not in FEATURE_PERMISSIONS[feature_name].get(access_level, []):
                return render(request, 'features/feature_locked.html', {
                    'feature': feature_name,
                    'required_plan': FEATURE_PERMISSIONS[feature_name][access_level][0],
                    'upgrade_url': reverse('billing:upgrade')
                })
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator

# Usage
@feature_required('dea', 'write')
def create_journal_entry(request):
    # Only Business+ plans with DEA write access
    pass
```

### 3. Template Permission Filter

```python
# apps/orgs/templatetags/permissions.py
from django import template

register = template.Library()

@register.filter
def has_permission(user, permission_codename):
    """Check if user has permission in their current workspace"""
    if not user.is_authenticated:
        return False
    
    workspace = user.profile.workspace
    if not workspace:
        return False
    
    try:
        membership = Membership.objects.get(
            user=user,
            company=workspace
        )
        return membership.role.permissions.filter(
            codename=permission_codename
        ).exists()
    except Membership.DoesNotExist:
        return False

@register.filter
def has_feature(user, feature_spec):
    """Check if user's plan includes feature
    
    Usage: {% if user|has_feature:'girvi_write' %}
    """
    if not user.is_authenticated:
        return False
    
    workspace = user.profile.workspace
    if not workspace:
        return False
    
    subscription = workspace.subscription_set.filter(is_active=True).first()
    if not subscription:
        return False
    
    feature_name, access_level = feature_spec.split('_', 1)
    plan = subscription.plan.name
    
    return plan in FEATURE_PERMISSIONS.get(feature_name, {}).get(access_level, [])

@register.filter
def can_edit(obj, user):
    """Check if user can edit object"""
    if not obj:
        return False
    
    # If object has workspace field, user must be in that workspace
    if hasattr(obj, 'workspace'):
        if obj.workspace != user.profile.workspace:
            return False
    
    # Check role permission
    workspace = user.profile.workspace
    try:
        membership = Membership.objects.get(
            user=user,
            company=workspace
        )
        return membership.role.name in ['Owner', 'Admin']
    except Membership.DoesNotExist:
        return False
```

---

## Audit Logging Examples

### What to Log

```python
# apps/audit/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from apps.audit.models import AuditLog

@receiver(post_save, sender=Membership)
def log_membership_changes(sender, instance, created, request=None, **kwargs):
    """Log when team members are added or modified"""
    if created:
        action = 'team_invite'
        changes = {
            'user': instance.user.email,
            'role': instance.role.name,
            'date_joined': str(instance.date_joined)
        }
    else:
        action = 'team_edit_role'
        changes = {
            'role': instance.role.name
        }
    
    AuditLog.log(
        user=request.user if request else instance.user,
        action=action,
        resource_type='Membership',
        resource_id=instance.id,
        resource_name=instance.user.email,
        workspace=instance.company,
        changes=changes,
        request=request
    )

@receiver(post_save, sender=Subscription)
def log_subscription_changes(sender, instance, created, **kwargs):
    """Log subscription changes"""
    AuditLog.log(
        user=instance.company.owner.user,  # Workspace owner
        action='subscription_edit' if not created else 'subscription_create',
        resource_type='Subscription',
        resource_id=instance.id,
        resource_name=instance.plan.name,
        workspace=instance.company,
    )
```

### Audit Log Viewer

```html
<!-- templates/audit/log_viewer.html -->
<div class="audit-log-viewer">
    <h3>Activity Log</h3>
    
    <table class="table">
        <thead>
            <tr>
                <th>Time</th>
                <th>User</th>
                <th>Action</th>
                <th>Resource</th>
                <th>Changes</th>
                <th>IP Address</th>
            </tr>
        </thead>
        <tbody>
            {% for log in logs %}
                <tr class="log-{{ log.action }}">
                    <td>{{ log.timestamp|date:"short" }}</td>
                    <td>{{ log.user.get_full_name }}</td>
                    <td>
                        <span class="badge badge-{{ log.get_action_color }}">
                            {{ log.get_action_display }}
                        </span>
                    </td>
                    <td>{{ log.resource_type }}: {{ log.resource_name }}</td>
                    <td>
                        {% if log.changes %}
                            <details>
                                <summary>View</summary>
                                {% for key, value in log.changes.items %}
                                    <div>{{ key }}: {{ value }}</div>
                                {% endfor %}
                            </details>
                        {% endif %}
                    </td>
                    <td>{{ log.ip_address }}</td>
                </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
```

---

## Migration Path

### Step 1: Create Infrastructure
- Permissions model relationships
- AuditLog model
- Decorators and filters

### Step 2: Assign Permissions
- Map existing roles to permissions
- Set up initial permission matrix
- Validate no gaps

### Step 3: Enforce Permissions
- Add decorators to sensitive views
- Test all access paths
- Handle authorization failures gracefully

### Step 4: Audit & Monitor
- Enable audit logging
- Monitor for unusual activities
- Create admin dashboard

---

