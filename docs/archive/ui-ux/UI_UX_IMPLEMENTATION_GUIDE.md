---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# UI/UX & Navigation Implementation Guide

## Overview

This implementation provides a permission-aware, role-based UI system with reusable components for your Django application. It includes context processors, template components, and template tags for handling navigation, permissions, and subscription status.

## Components & Usage

### 1. Context Processors

Context processors automatically inject variables into all templates.

#### `user_permissions`
Provides permission information for the current user.

**Available in templates:**
- `user_permissions`: Set of permission codenames
- `user_role`: User's role in current workspace (Owner, Admin, Member)
- `user_workspace`: Current workspace object

**Example:**
```django
{% if 'data_edit' in user_permissions %}
  <button>Edit</button>
{% endif %}
```

#### `navigation_config`
Provides navigation structure configuration.

**Available in templates:**
- `navigation_config`: Dictionary with navigation structure

#### `workspace_context`
Provides workspace-specific variables.

**Available in templates:**
- `in_tenant`: Boolean - whether user is in a tenant workspace
- `workspace_name`: Current workspace name
- `workspace_theme`: Theme color from workspace settings

#### `subscription_context`
Provides subscription/billing information.

**Available in templates:**
- `has_active_subscription`: Boolean
- `subscription_plan`: Current plan name
- `days_until_renewal`: Days until next billing cycle
- `subscription_expired`: Whether subscription is past due

---

## 2. Template Components

Located in `templates/components/`, these are reusable, permission-aware components.

### action_buttons.html
Shows/hides action buttons based on user permissions.

**Usage:**
```django
{% include "components/action_buttons.html" with object=contact %}
```

**Displays:**
- View button (always)
- Edit button (requires `data_edit` permission)
- Export button (requires `data_export` permission)
- Delete button (requires `data_delete` permission)

---

### empty_state.html
Shows when no items exist in a list.

**Usage:**
```django
{% with items=contact_list %}
  {% include "components/empty_state.html" with 
      message="No contacts yet" 
      icon="ðŸ“­"
      create_url="/contacts/create/"
      can_create=True %}
{% endwith %}
```

---

### role_badge.html
Displays user's role with colored badge and icon.

**Usage:**
```django
{% include "components/role_badge.html" with role=user_role %}
```

**Roles:**
- **Owner** (red badge, crown icon): Full access
- **Admin** (blue badge, shield icon): Administrative access
- **Member** (grey badge, person icon): Limited access

---

### breadcrumbs.html
Shows navigation path through the app.

**Usage:**
```django
{% with breadcrumblist=breadcrumbs %}
  {% include "components/breadcrumbs.html" %}
{% endwith %}
```

**Format:**
```python
breadcrumbs = [
    {'label': 'Contacts', 'url': '/contacts/'},
    {'label': 'John Doe', 'url': None},  # Current page (no link)
]
```

---

### feature_locked.html
Shows alert when feature is not available in user's plan.

**Usage:**
```django
{% include "components/feature_locked.html" with 
    feature_name="Advanced Reporting" 
    required_plan="Pro" %}
```

---

### permission_check.html
Conditionally shows content based on permissions/role.

**Usage:**
```django
{% include "components/permission_check.html" with 
    permission='workspace_edit' 
    show_denied=True %}
  <a href="/workspace/settings/">Edit Workspace</a>
{% endinclude %}
```

---

### subscription_status.html
Shows subscription alerts (expiring, overdue, etc.).

**Usage:**
```django
{% include "components/subscription_status.html" with 
    has_active_subscription=has_active_subscription
    subscription_plan=subscription_plan
    days_until_renewal=days_until_renewal
    subscription_expired=subscription_expired
    workspace_name=workspace_name %}
```

---

### navigation.html
Main navigation menu with permission filtering.

**Usage:**
```django
{% load permissions %}
{% render_main_navigation user workspace=request.tenant permissions=user_permissions %}
```

---

## 3. Template Tags

Located in `django_project/templatetags/permissions.py`, these provide utility functions for templates.

### `render_main_navigation`
Renders filtered navigation based on permissions.

```django
{% load permissions %}
{% render_main_navigation user workspace=request.tenant permissions=user_permissions %}
```

### `has_permission`
Check if user has a specific permission.

```django
{% load permissions %}
{% has_permission user_permissions 'data_edit' as can_edit %}
{% if can_edit %}
  <button>Edit</button>
{% endif %}
```

### `has_role`
Check if user has a specific role or higher.

```django
{% load permissions %}
{% has_role user_role 'admin' as is_admin %}
```

Role hierarchy: `owner` >= `admin` >= `member`

### `role_badge`
Render role badge.

```django
{% load permissions %}
{% role_badge user_role %}
{% role_badge user_role size='small' %}
```

### `action_buttons`
Render permission-based action buttons.

```django
{% load permissions %}
{% action_buttons object user_permissions %}
```

### `breadcrumbs`
Render breadcrumb navigation.

```django
{% load permissions %}
{% breadcrumbs breadcrumb_list in_tenant=True workspace_name=workspace_name %}
```

### `empty_state`
Render empty state message.

```django
{% load permissions %}
{% empty_state items message="No items found" create_url="/create/" can_create=True %}
```

### `feature_locked`
Render feature unavailable alert.

```django
{% load permissions %}
{% feature_locked "Advanced Reporting" "Pro" %}
```

### `subscription_status_alert`
Render subscription status alert.

```django
{% load permissions %}
{% subscription_status_alert has_active_subscription subscription_plan days_until_renewal subscription_expired workspace_name %}
```

### Filters

#### `permission_required`
Filter list to only items with required permission.

```django
{% load permissions %}
{% for item in items|permission_required:'data_edit' %}
  ...
{% endfor %}
```

#### `role_label`
Get display label for a role.

```django
{% load permissions %}
{{ user_role|role_label }}
```

Output: "Workspace Owner", "Administrator", "Team Member"

---

## 4. Navigation Configuration

Define all navigation items in `django_project/navigation.py`.

### Structure

```python
NAVIGATION_STRUCTURE = {
    'main': [
        {
            'id': 'dashboard',
            'label': 'Dashboard',
            'url_name': 'dashboard',
            'icon': 'house-fill',
            'required_permission': 'workspace_view',
        },
        {
            'id': 'data',
            'label': 'Data',
            'icon': 'database',
            'submenu': [
                {
                    'id': 'sales',
                    'label': 'Sales',
                    'url_name': 'sales:invoice_list',
                    'required_permission': 'data_view',
                }
            ]
        }
    ]
}
```

### Adding New Navigation Items

1. Edit `django_project/navigation.py`
2. Add item to appropriate section
3. Include `required_permission` for permission-based visibility
4. Add `submenu` list for dropdown items

---

## 5. Usage Examples in Views

### Controller/View Setup

```python
# views.py
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin

class ContactListView(LoginRequiredMixin, ListView):
    model = Contact
    template_name = 'contacts/contact_list.html'
    context_object_name = 'contacts'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Breadcrumbs
        context['breadcrumbs'] = [
            {'label': 'Contacts', 'url': None}  # Current page
        ]
        
        # Empty state message
        context['empty_message'] = "No contacts found. Create one to get started."
        context['create_url'] = self.model.get_create_url()
        
        return context
```

### Template Usage

```django
{% load permissions %}

{% block content %}
<div class="container">
  <!-- Breadcrumbs -->
  {% breadcrumbs breadcrumbs %}
  
  <!-- Subscription alert if needed -->
  {% subscription_status_alert has_active_subscription subscription_plan days_until_renewal subscription_expired workspace_name %}
  
  <!-- Page heading -->
  <div class="d-flex justify-content-between align-items-center mb-4">
    <h1>Contacts</h1>
    
    {% if 'data_edit' in user_permissions %}
      <a href="/contacts/create/" class="btn btn-primary">
        <i class="bi bi-plus-circle"></i> New Contact
      </a>
    {% endif %}
  </div>
  
  <!-- Empty state -->
  {% if not contacts %}
    {% empty_state contacts message=empty_message create_url=create_url can_create=True %}
  {% else %}
    <!-- Contact list -->
    <div class="table-responsive">
      <table class="table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Role</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {% for contact in contacts %}
            <tr>
              <td>{{ contact.name }}</td>
              <td>{{ contact.email }}</td>
              <td>{% role_badge contact.role %}</td>
              <td>{% action_buttons contact user_permissions %}</td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  {% endif %}
</div>
{% endblock %}
```

---

## 6. Permission System Integration

### Defining Permissions

The system uses a permission matrix (see `PERMISSION_MATRIX_GUIDE.md`):

**Default Role Permissions:**

| Permission | Owner | Admin | Member |
|-----------|-------|-------|--------|
| workspace_view | âœ“ | âœ“ | âœ“ |
| workspace_edit | âœ“ | âœ“ | âœ— |
| workspace_delete | âœ“ | âœ— | âœ— |
| team_view | âœ“ | âœ“ | âœ“ |
| team_invite | âœ“ | âœ“ | âœ— |
| team_remove | âœ“ | âœ— | âœ— |
| data_view | âœ“ | âœ“ | âœ“ |
| data_edit | âœ“ | âœ“ | âœ“ |
| data_export | âœ“ | âœ“ | âœ— |
| billing_view | âœ“ | âœ“ | âœ— |
| billing_edit | âœ“ | âœ— | âœ— |

### Custom Permissions

To add custom permissions:

1. Update `_get_permissions_for_role()` in `django_project/context_processors.py`
2. Add permission checks in views/components
3. Update navigation visibility in `django_project/navigation.py`

---

## 7. Best Practices

### âœ… DO

- Use context processors to provide global variables
- Include permission checks in templates
- Use breadcrumbs for navigation clarity
- Show empty states with helpful messages
- Display role badges in team/user lists
- Include subscription status alerts
- Use consistent icons from Bootstrap Icons

### âŒ DON'T

- Rely only on backend permission checks (always validate in templates)
- Show action buttons user can't perform
- Hide critical information from admins
- Use hardcoded URLs instead of reverse()
- Skip empty state handling

---

## 8. Styling & Customization

### Icons

Components use Bootstrap Icons (https://icons.getbootstrap.com/). Examples:
- `house-fill` - Dashboard
- `database` - Data
- `people-fill` - Team
- `credit-card` - Billing
- `gear-fill` - Settings
- `shield-check` - Admin
- `crown` - Owner

### Colors

- **Owner**: `bg-danger` (red)
- **Admin**: `bg-primary` (blue)
- **Member**: `bg-secondary` (grey)

### Responsive

All components are Bootstrap 5 compatible and mobile-friendly.

---

## 9. Troubleshooting

### Permissions not showing in template

**Issue:** `user_permissions` is empty

**Solution:**
1. Check context processor is registered in settings
2. Use `{% debug %}` tag to inspect context
3. Verify membership exists for user

### Navigation items not appearing

**Issue:** Menu items are hidden

**Solution:**
1. Check permission codename in navigation config
2. Verify user has permission in `user_role`
3. Check breadcrumb structure

### Components not rendering

**Issue:** Include tags not working

**Solution:**
1. Verify component file exists in `templates/components/`
2. Check context variables are passed
3. Ensure `{% load permissions %}` at top of template

---

## Next Steps

1. **Update existing templates** to use new components
2. **Add permission checks** to all views
3. **Configure navigation** for your app structure
4. **Test permission flows** with different roles
5. **Customize styling** to match your brand

