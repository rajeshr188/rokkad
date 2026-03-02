# Context Processor Analysis & Usage Gap

**Date:** March 2, 2026  
**Status:** Context processors ARE implemented but NOT being used in templates

---

## ✅ GOOD NEWS: Infrastructure Exists

### 1. Context Processors Defined

File: [django_project/context_processors.py](django_project/context_processors.py)

Your context processors provide **5 well-designed processors**:

```python
✅ user_permissions(request)
   - Returns: user_permissions (set of permission codenames)
   - Returns: user_role (Owner/Admin/Member)
   - Returns: user_workspace (Company object)

✅ navigation_config(request)
   - Returns: navigation_config (navigation structure)

✅ workspace_context(request)
   - Returns: in_tenant (boolean)
   - Returns: workspace_name (string)
   - Returns: workspace_theme (color)

✅ subscription_context(request)
   - Returns: has_active_subscription (boolean)
   - Returns: subscription_plan (name)
   - Returns: days_until_renewal (int)
   - Returns: subscription_expired (boolean)

✅ theme_processor (from apps.orgs)
   - Returns: theme, logo, workspace colors
```

### 2. Context Processors Registered

File: [django_project/settings/base.py](django_project/settings/base.py#L140-L150)

```python
TEMPLATES = [
    {
        "OPTIONS": {
            "context_processors": [
                # ... Django defaults ...
                "django_project.context_processors.user_permissions",      # ✅ REGISTERED
                "django_project.context_processors.navigation_config",     # ✅ REGISTERED
                "django_project.context_processors.workspace_context",     # ✅ REGISTERED
                "django_project.context_processors.subscription_context",  # ✅ REGISTERED
            ]
        }
    }
]
```

**Status:** ✅ **All properly registered in settings**

---

## ❌ THE PROBLEM: Unused in Templates

### Current Sidebar Implementation

File: [templates/components/navigation/sidebar.html](templates/components/navigation/sidebar.html)

```django
<!-- PROBLEM: Using non-existent custom filter -->
{% if request.user|has_permission:"company.manage_members" %}
    <!-- Show Team section -->
{% endif %}

{% if request.user|has_permission:"company.change_company" %}
    <!-- Show Settings section -->
{% endif %}
```

**Issues:**

1. **`|has_permission:` custom filter doesn't exist**
   - Should be using `user_permissions` from context processor instead
   - This filter is trying to use Django's object permission system
   - But it's being used without a target object

2. **Not using available context variables**
   - `user_permissions` (set of permission strings) - **AVAILABLE, NOT USED**
   - `user_role` (Owner/Admin/Member) - **AVAILABLE, NOT USED**
   - `user_workspace` - **AVAILABLE, NOT USED**
   - `subscription_plan` - **AVAILABLE, NOT USED**
   - `has_active_subscription` - **AVAILABLE, NOT USED**

---

## 🎯 THE FIX: Use Context Processor Variables

### Correct Approach

Instead of:
```django
{% if request.user|has_permission:"company.manage_members" %}
```

Use:
```django
{% if 'team_invite' in user_permissions %}
```

Or:
```django
{% if user_role in "Owner,Admin" %}
```

Or:
```django
{% if has_active_subscription %}
```

---

## BEFORE & AFTER COMPARISON

### ❌ BEFORE (Current - Broken)

```django
{% load orgs_tags %}

<!-- Team Management (Admin/Manager only) -->
{% if request.user|has_permission:"company.manage_members" %}
    <div class="nav-section">
        <h6 class="nav-section-title">Team</h6>
        <a class="nav-link" href="{% url 'team_invitations' %}">
            <i class="bi bi-people"></i> Members
        </a>
    </div>
{% endif %}

<!-- Workspace Settings (Admin only) -->
{% if request.user|has_permission:"company.change_company" %}
    <div class="nav-section">
        <h6 class="nav-section-title">Settings</h6>
        <a class="nav-link" href="{% url 'workspace_detail' %}">
            <i class="bi bi-gear"></i> Workspace Settings
        </a>
    </div>
{% endif %}
```

**Problem:** The `|has_permission:` filter doesn't exist, so:
- Team section always hidden (permission check fails)
- Settings section always hidden (permission check fails)
- **Users cannot see team management or settings options!**

---

### ✅ AFTER (Fixed - Using Context Processors)

```django
{% load orgs_tags %}

<!-- Team Management (Team invite permission) -->
{% if 'team_invite' in user_permissions %}
    <div class="nav-section">
        <h6 class="nav-section-title">Team</h6>
        <a class="nav-link" href="{% url 'team_invitations' %}">
            <i class="bi bi-people"></i> Members
        </a>
        <a class="nav-link" href="{% url 'team_invite' workspace_id=user_workspace.id %}">
            <i class="bi bi-person-plus"></i> Invite Member
        </a>
    </div>
{% endif %}

<!-- Workspace Settings (workspace_edit permission) -->
{% if 'workspace_edit' in user_permissions %}
    <div class="nav-section">
        <h6 class="nav-section-title">Settings</h6>
        <a class="nav-link" href="{% url 'workspace_detail' workspace_id=user_workspace.id %}">
            <i class="bi bi-gear"></i> Workspace Settings
        </a>
        <a class="nav-link" href="{% url 'workspace_preferences' workspace_id=user_workspace.id %}">
            <i class="bi bi-sliders"></i> Preferences
        </a>
    </div>
{% endif %}

<!-- Billing (Owner/Admin only) -->
{% if user_role in 'Owner,Admin' %}
    <div class="nav-section">
        <h6 class="nav-section-title">Billing</h6>
        <a class="nav-link" href="{% url 'subscriptions:dashboard' %}">
            <i class="bi bi-credit-card"></i> Subscription
            {% if not has_active_subscription %}
            <span class="badge bg-warning text-dark float-end">Action Needed</span>
            {% endif %}
        </a>
    </div>
{% endif %}

<!-- Tenant Apps (if workspace selected) -->
{% if user_workspace and user_workspace.schema_name != 'public' %}
    <div class="nav-section">
        <h6 class="nav-section-title">Features</h6>
        <a class="nav-link" href="{% url 'contact_customer_list' %}">
            <i class="bi bi-people-fill"></i> Contacts
        </a>
        <a class="nav-link" href="{% url 'girvi:girvi_loan_list' %}">
            <i class="bi bi-cash-coin"></i> Girvi (Loans)
        </a>
        <a class="nav-link" href="{% url 'sales:sales_invoice_list' %}">
            <i class="bi bi-receipt"></i> Sales
        </a>
        <a class="nav-link" href="{% url 'dea:journal_entry_list' %}">
            <i class="bi bi-graph-up"></i> Accounting
        </a>
    </div>
{% endif %}
```

**Benefits:**
- ✅ Uses actual context processor variables
- ✅ Permission checks work correctly
- ✅ Subscription status visible to users
- ✅ Tenant app links now appear in navigation
- ✅ Role-based visibility (Owner/Admin vs Member)

---

## What Each Context Variable Provides

### `user_permissions` (Set)

```python
# In template: user_permissions
# Returns: {'workspace_view', 'workspace_edit', 'team_invite', 'data_view', ...}

# Usage:
{% if 'workspace_view' in user_permissions %}
{% if 'team_invite' in user_permissions %}
{% if 'workspace_delete' in user_permissions %}
{% if 'billing_edit' in user_permissions %}
```

### `user_role` (String)

```python
# In template: user_role
# Returns: 'Owner' or 'Admin' or 'Member' or None

# Usage:
{% if user_role == 'Owner' %}
{% if user_role in 'Owner,Admin' %}
{% if user_role != 'Member' %}
```

### `user_workspace` (Company Object)

```python
# In template: user_workspace
# Returns: Company instance or None

# Usage:
{% if user_workspace %}
    Workspace: {{ user_workspace.name }}
    {% url 'workspace_detail' workspace_id=user_workspace.id %}
    {% url 'team_invite' workspace_id=user_workspace.id %}
{% endif %}

# Accessing workspace properties:
{{ user_workspace.name }}
{{ user_workspace.schema_name }}
{{ user_workspace.created_at }}
{{ user_workspace.owner.get_full_name }}
```

### `has_active_subscription` (Boolean)

```python
# In template: has_active_subscription
# Returns: True or False

# Usage:
{% if has_active_subscription %}
    <span class="badge bg-success">Active</span>
{% else %}
    <span class="badge bg-warning">Renew Required</span>
{% endif %}
```

### `subscription_plan` (String)

```python
# In template: subscription_plan
# Returns: Plan name like 'Basic', 'Pro', 'Enterprise' or None

# Usage:
{% if subscription_plan == 'Pro' %}
    Advanced reporting available
{% endif %}

{% if subscription_plan %}
    Current plan: {{ subscription_plan }}
{% endif %}
```

### `in_tenant` (Boolean)

```python
# In template: in_tenant
# Returns: True if in workspace, False if in public schema

# Usage:
{% if in_tenant %}
    <!-- Show workspace-specific UI -->
    {% include 'components/navigation/sidebar.html' %}
{% else %}
    <!-- Show public UI -->
{% endif %}
```

---

## Permission Code Names Reference

Based on your context processor's `_get_permissions_for_role()` function:

### Base Permissions (All Roles)
```
workspace_view
data_view
team_view
```

### Admin+ Permissions
```
workspace_edit
team_invite
billing_view
data_edit
data_export
data_publish
girvi_loan_view
sales_invoice_view
purchase_invoice_view
dea_journal_view
contact_view
```

### Owner-Only Permissions
```
workspace_delete
team_remove
billing_edit
billing_delete
workspace_settings
admin_access
```

---

## Fix Checklist

- [ ] **Update sidebar.html** to use context processor variables
- [ ] **Remove custom `|has_permission:` filters** 
- [ ] **Add tenant app navigation** to sidebar using `user_workspace`
- [ ] **Add subscription status widget** using `has_active_subscription`
- [ ] **Add billing quick access** using `user_role` and `has_active_subscription`
- [ ] **Test all permission checks** work correctly
- [ ] **Test in templates:** verify context variables are available
- [ ] **Add custom template filter** (optional enhancement) for checking permissions in templates

---

## Optional: Create Helper Template Filter

For extra convenience, you could add a custom template filter (though not necessary):

File: `apps/orgs/templatetags/orgs_tags.py`

```python
@register.filter
def has_perm(user_permissions, perm_name):
    """Check if permission exists in user_permissions set"""
    return perm_name in user_permissions

# Usage in template:
{% if user_permissions|has_perm:"team_invite" %}
```

---

## Summary

| Item | Status | Details |
|------|--------|---------|
| Context Processors Defined | ✅ | Complete, well-structured |
| Context Processors Registered | ✅ | In settings/base.py |
| Providing to Templates | ✅ | All 5 processors active |
| Being Used in Sidebar | ❌ | Sidebar using broken filters instead |
| Being Used in Dashboard | ❌ | Dashboard not checking permissions |
| Tenant App Navigation | ❌ | Not integrated |
| Subscription UI Integration | ❌ | Not shown to users |

**Root Cause:** Sidebar.html and other templates haven't been updated to use the context processor variables. They're trying to use custom filters that don't exist.

**Solution:** Simple template updates to use available context variables - no code changes needed!

---

## Next Steps

1. Review your context processor output by adding debug in template:
   ```django
   <!-- DEBUG: Remove after testing -->
   <div style="display: none;">
       Permissions: {{ user_permissions }}
       Role: {{ user_role }}
       Workspace: {{ user_workspace.name }}
       Active Subscription: {{ has_active_subscription }}
   </div>
   ```

2. Update [templates/components/navigation/sidebar.html](templates/components/navigation/sidebar.html) using the AFTER examples above

3. Update [templates/company/workspace_dashboard.html](templates/company/workspace_dashboard.html) to show subscription status

4. Test each permission check in browser

5. Remove debug comments after verification

---

**Document Date:** March 2, 2026  
**Assessment:** Your context processor infrastructure is EXCELLENT. Just need templates to use it!
