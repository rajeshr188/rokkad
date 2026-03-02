# Quick Reference - Using New Permission System

## Import Decorators
```python
from apps.orgs.decorators_v2 import (
    permission_required,
    any_permission_required,
    object_permission_required
)
```

## Basic Permission Check

### Old Way (DON'T USE)
```python
from apps.orgs.decorators import roles_required

@roles_required(['Owner', 'Admin'])
def edit_company(request, company_id):
    # ❌ Hard-coded roles, not flexible
    ...
```

### New Way (USE THIS)
```python
from apps.orgs.decorators_v2 import permission_required

@permission_required('workspace_edit')
def edit_company(request, company_id):
    # ✅ Granular permission check
    # ✅ Automatic audit logging on denial
    # ✅ Works with role permission matrix
    ...
```

## Check Multiple Permissions (OR logic)

```python
@any_permission_required(['data_edit', 'data_edit_own'])
def edit_data(request, data_id):
    """User needs EITHER data_edit OR data_edit_own"""
    ...
```

## Object-Level Permissions (Guardian)

```python
from apps.orgs.models import Company

@object_permission_required('change_company', Company, pk_url_kwarg='company_id')
def update_company(request, company_id):
    """Checks if user has 'change_company' permission on specific Company instance"""
    ...
```

## Common Permission Mappings

### Workspace Operations
| Old Role Check | New Permission | Description |
|---------------|----------------|-------------|
| `Owner` | `workspace_settings` | Manage workspace settings |
| `Owner, Admin` | `workspace_edit` | Edit workspace details |
| `Owner` | `workspace_delete` | Delete workspace |
| `Owner` | `workspace_transfer` | Transfer ownership |

### Team Management
| Action | Permission | Who Has It |
|--------|-----------|------------|
| View team list | `team_list` | Owner, Admin, Member |
| Invite members | `team_invite` | Owner, Admin |
| Remove members | `team_remove` | Owner, Admin |
| Change roles | `team_change_role` | Owner, Admin |

### Data Operations
| Action | Permission | Who Has It |
|--------|-----------|------------|
| View all data | `data_view` | Owner, Admin, Member |
| View own data | `data_view_own` | Everyone |
| Create data | `data_create` | Owner, Admin, Member |
| Edit all data | `data_edit` | Owner, Admin |
| Edit own data | `data_edit_own` | Owner, Admin, Member |
| Delete data | `data_delete` | Owner, Admin |
| Export data | `data_export` | Owner, Admin, Member |

### Billing
| Action | Permission | Who Has It |
|--------|-----------|------------|
| View billing | `billing_view` | Owner, Admin |
| View history | `billing_history` | Owner, Admin |
| Manage subscription | `billing_manage` | Owner |
| Cancel subscription | `billing_cancel` | Owner only |

## Manual Permission Checks (in view code)

```python
from apps.orgs.permissions import user_has_permission, get_user_permissions

def my_view(request):
    user = request.user
    workspace = user.profile.workspace
    
    # Check single permission
    if user_has_permission(user, workspace, 'data_export'):
        # Show export button
        show_export = True
    
    # Get all user's permissions
    perms = get_user_permissions(user, workspace)
    # Returns: ['data_view', 'data_create', 'data_edit_own', ...]
    
    # Check in template
    context = {'user_permissions': perms}
```

## Template Usage

```django
{% load guardian_tags %}

{# Check permission #}
{% if 'data_export' in user_permissions %}
    <a href="{% url 'export_data' %}">Export Data</a>
{% endif %}

{# Guardian object permission #}
{% get_obj_perms user for company as "company_perms" %}
{% if "change_company" in company_perms %}
    <a href="{% url 'edit_company' company.id %}">Edit</a>
{% endif %}
```

## Custom Permission Definitions

All permissions are defined in [`apps/orgs/permissions.py`](../permissions.py):

```python
from apps.orgs.permissions import ALL_PERMISSIONS, RolePermissions

# See all available permissions
for code, name in ALL_PERMISSIONS:
    print(f"{code}: {name}")

# See permissions for a role
owner_perms = RolePermissions.OWNER
admin_perms = RolePermissions.ADMIN
```

## Audit Logging

### Automatic (via decorator)
```python
from apps.orgs.audit import audit_log

@audit_log('COMPANY_UPDATE', description='Update company settings')
def update_company_settings(request, company_id):
    # Automatically logs to AuditLog table
    ...
```

### Manual
```python
from apps.orgs.audit import AuditLog

def my_view(request):
    company = request.user.profile.workspace
    
    # Log action
    AuditLog.log(
        action='DATA_EXPORT',
        user=request.user,
        company=company,
        description='Exported customer data',
        request=request,
        success=True,
        data={'format': 'CSV', 'rows': 1234}
    )
```

## Error Handling

### Default Behavior
- `@permission_required` raises `PermissionDenied` (403 page)
- Logs denial to audit log
- Shows error message to user

### Custom Behavior
```python
@permission_required('data_export', raise_exception=False, log_denial=True)
def export_data(request):
    # Returns HttpResponseForbidden instead of raising exception
    # Still logs to audit
    ...
```

## Migration Guide

### Step 1: Identify Old Decorators
```bash
# Find all uses of old decorators
grep -r "@roles_required" apps/orgs/views.py
grep -r "@role_required" apps/orgs/views.py
```

### Step 2: Map to New Permissions
| Old Decorator | New Decorator | Notes |
|--------------|---------------|-------|
| `@roles_required(['Owner'])` | `@permission_required('workspace_delete')` | Specific to action |
| `@roles_required(['Owner', 'Admin'])` | `@permission_required('workspace_edit')` | Both have this |
| `@roles_required(['Owner', 'Admin', 'Member'])` | `@permission_required('data_view')` | All 3 have this |

### Step 3: Update Imports
```python
# OLD
from apps.orgs.decorators import roles_required

# NEW
from apps.orgs.decorators_v2 import permission_required
```

### Step 4: Update Decorator
```python
# OLD
@roles_required(['Owner', 'Admin'])

# NEW
@permission_required('workspace_edit')  # See PERMISSION_MATRIX.md
```

### Step 5: Test
```bash
# Run view test
.venv\Scripts\python.exe manage.py test apps.orgs.tests.test_views
```

## Common Patterns

### View with Multiple Checks
```python
@login_required
@permission_required('data_view')
def list_data(request):
    """User needs data_view permission"""
    
    # Check if user can also edit
    can_edit = user_has_permission(request.user, request.user.profile.workspace, 'data_edit')
    
    return render(request, 'data_list.html', {
        'can_edit': can_edit
    })
```

### View with Conditional Logic
```python
@login_required
def edit_data(request, data_id):
    data = get_object_or_404(Data, id=data_id)
    user = request.user
    workspace = user.profile.workspace
    
    # Check if user owns the data
    is_owner = data.created_by == user
    
    # Check permissions
    can_edit_all = user_has_permission(user, workspace, 'data_edit')
    can_edit_own = user_has_permission(user, workspace, 'data_edit_own')
    
    if not (can_edit_all or (can_edit_own and is_owner)):
        raise PermissionDenied("Cannot edit this data")
    
    # ... edit logic
```

### CRUD Pattern
```python
# List - most users can view
@permission_required('data_view')
def data_list(request):
    ...

# Create - needs create permission
@permission_required('data_create')
def data_create(request):
    ...

# Edit - needs edit permission OR owns the data
@any_permission_required(['data_edit', 'data_edit_own'])
def data_edit(request, data_id):
    data = get_object_or_404(Data, id=data_id)
    if not (user_has_permission(request.user, workspace, 'data_edit') or 
            data.created_by == request.user):
        raise PermissionDenied()
    ...

# Delete - only admins
@permission_required('data_delete')
def data_delete(request, data_id):
    ...
```

## See Also

- [`PERMISSION_MATRIX.md`](PERMISSION_MATRIX.md) - Complete list of all 71 permissions
- [`apps/orgs/permissions.py`](../permissions.py) - Permission definitions
- [`apps/orgs/decorators_v2.py`](../decorators_v2.py) - Decorator implementations
- [`PHASE_0_COMPLETION_SUMMARY.md`](PHASE_0_COMPLETION_SUMMARY.md) - Implementation details

