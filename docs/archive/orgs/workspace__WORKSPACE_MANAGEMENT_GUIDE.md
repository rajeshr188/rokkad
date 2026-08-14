---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Workspace Management & Switching Guide

## Overview
Users can now easily switch between workspaces, clear their workspace selection, and manage their workspace access through a dedicated workspace management interface.

## Available Features

### 1. **Switch Workspace** 
**Function**: `switch_workspace(request, workspace_id)`
**URL**: `/accounts/switch/workspace/<workspace_id>/`
**Access**: Authenticated users only

#### What it does:
- Switches user's active workspace
- Validates user membership in target workspace
- Sets the workspace in `user.profile.workspace`
- Logs audit trail
- Displays success message
- Redirects to workspace dashboard

#### Usage:
```html
<!-- From navigation or template -->
<a href="{% url 'switch_workspace' workspace.id %}">Switch to {{ workspace.name }}</a>
```

#### Response:
```
Timeline:
1. User clicks "Switch workspace"
2. Validates: User is authenticated
3. Validates: Workspace exists and not deleted
4. Validates: User has membership
5. Sets: user.profile.workspace = workspace âœ“
6. Logs: Audit trail with action
7. Shows: Success message
8. Redirects: workspace_dashboard (with stats & data)
```

---

### 2. **Clear Workspace**
**Function**: `clear_workspace(request)`
**URL**: `/accounts/clear/workspace/`
**Access**: Authenticated users only

#### What it does:
- Resets workspace to public schema
- Returns user to root public workspace
- Allows user to select different workspace
- Logs the action
- Shows confirmation message

#### Usage:
```html
<!-- From workspace dropdown or settings -->
<a href="{% url 'clear_workspace' %}">Clear Workspace</a>
```

#### Timeline:
```
1. User clicks "Clear Workspace"
2. Gets public schema
3. Stores current workspace (for logging)
4. Sets: user.profile.workspace = public âœ“
5. Logs: WORKSPACE_CLEAR audit
6. Shows: "Workspace cleared. You can now select a different one."
7. Redirects: workspace_selector (workspace list)
```

#### After clearing:
- User is in public schema
- Must select workspace again via workspace_selector
- Can click on any workspace to enter it
- Will trigger smart routing on dashboard

---

### 3. **Reset Workspace**
**Function**: `reset_workspace(request)`
**URL**: `/accounts/reset/workspace/`
**Access**: Authenticated users only

#### What it does:
- Similar to clear_workspace but with explicit "reset" semantics
- Sets workspace back to public
- Logs as WORKSPACE_RESET (different audit type)
- Redirects to workspace selector
- Better for intentional workspace reset

#### Usage:
```html
<!-- Workspace management page -->
<a href="{% url 'reset_workspace' %}">Reset Workspace</a>
```

---

### 4. **Workspace Management Dashboard**
**Function**: `workspace_management(request)`  
**URL**: `/accounts/workspace/management/`
**Template**: `account/workspace_management.html`
**Access**: Authenticated users only

#### Features:
- **Current Workspace Display**
  - Shows active workspace name
  - Displays workspace schema
  - Shows creation date
  - Provides quick actions (Go to Dashboard, Clear Workspace)

- **All Workspaces List**
  - Table of all user's workspaces
  - Shows role per workspace (Owner, Admin, Member)
  - Displays member count
  - Creation date
  - Switch buttons

- **Quick Actions**
  - Create new workspace
  - Reset workspace selection
  - Links to workspace selector

#### Timeline:
```
1. User visits /accounts/workspace/management/
2. View fetches:
   - Current active workspace
   - All user's memberships
   - Role information
3. Renders comprehensive workspace management interface
4. User can:
   - Switch to different workspace
   - Clear current selection
   - Create new workspace
   - View all available workspaces
```

---

## User Workflow Examples

### Scenario 1: User Has Multiple Workspaces and Wants to Switch
```
User's Workspaces:
â”œâ”€ Workspace A (current)
â”œâ”€ Workspace B
â””â”€ Workspace C

Action Sequence:
1. User clicks workspace dropdown (navbar)
2. Selects "Workspace B"
3. click "Switch" â†’ switch_workspace(workspace_B.id)
4. Redirected to Workspace B / Dashboard
5. user.profile.workspace = Workspace B âœ“
```

### Scenario 2: User Wants to Change Workspace After Creation
```
Timeline:
1. User creates a new workspace
2. Form submits with workspace details
3. Workspace created with:
   - Domain mapping
   - Owner membership assigned
   - user.profile.workspace = new_workspace âœ“
4. Redirected to workspace_list
5. User sees new workspace in list
6. Clicks on it to enter
7. Redirected to workspace_dashboard
```

### Scenario 3: User Wants to Return to Public and Select Different Workspace
```
Current: User in Workspace A
Action: Click "Clear Workspace"

Timeline:
1. clear_workspace() called
2. Validates authentication
3. Gets public schema
4. Sets: user.profile.workspace = public  âœ“
5. Logs: WORKSPACE_CLEAR, from:A, to:Public
6. Message: "Workspace cleared. Select a different one."
7. Redirects: workspace_selector
8. User sees list of workspaces
9. Clicks different workspace â†’ workspace_select()
10. Redirected to: workspace_dashboard âœ“
```

### Scenario 4: User Resets and Smart Routing Kicks In
```
User has workspace set but wants fresh start

Action: Click "Reset Workspace" in management page

Timeline:
1. reset_workspace() called
2. Stores current workspace
3. Sets: user.profile.workspace = public
4. Logs: WORKSPACE_RESET, from:X, to:Public
5. Message: "Reset. Please select workspace."
6. Redirects: workspace_selector
7. User selects workspace
8. Next visit to /dashboard/:
   - Smart routing detects workspace selected âœ“
   - Redirects directly to workspace_dashboard
```

---

## Navigation Integration

### Main Navigation (`templates/components/navigation/main_nav.html`)
```html
<!-- Workspace Dropdown -->
<li class="nav-item dropdown">
    <a class="nav-link dropdown-toggle" href="#" id="workspaceDropdown">
        Current Workspace Name
    </a>
    <ul class="dropdown-menu dropdown-menu-end">
        <!-- List of user's workspaces -->
        <li><a href="{% url 'workspace_select' ws.id %}">Workspace</a></li>
        <!-- All workspaces link -->
        <li><a href="{% url 'workspace_list' %}">All Workspaces</a></li>
        <!-- Clear workspace (if not public) -->
        {% if request.user.profile.workspace.schema_name != 'public' %}
        <li><a href="{% url 'clear_workspace' %}">Clear Workspace</a></li>
        {% endif %}
    </ul>
</li>

<!-- User Dropdown -->
<li class="nav-item dropdown">
    <a class="nav-link dropdown-toggle" href="#" id="userDropdown">
        User Menu
    </a>
    <ul class="dropdown-menu dropdown-menu-end">
        <li><a href="{% url 'userprofile_detail' %}">Profile</a></li>
        <li><a href="{% url 'workspace_management' %}">Workspace Management</a></li>
        <li><a href="{% url 'account_logout' %}">Sign Out</a></li>
    </ul>
</li>
```

### Tenant Navigation (`templates/tenant.html`)
- Similar workspace dropdown with same options
- "Clear Workspace" option for non-public workspaces
- "Workspace Management" link

---

## Database/ORM Interactions

### Model Methods Used
```python
# In accounts/models.py - UserProfile model
def set_workspace(self, workspace):
    """Set the active workspace for user profile"""
    self.workspace = workspace
    self.save()
```

### Queries Performed
```python
# Switch workspace validation
user.memberships.get(company=workspace)  # Verifies user can access

# In workspace_management view
user.memberships.select_related('company', 'role').filter(
    company__is_deleted=False
).order_by('-company__updated_at')  # All user's workspaces
```

---

## Audit Logging

All workspace switching/clearing actions are logged:

```python
AuditLog.log(
    'WORKSPACE_SWITCH',  # or WORKSPACE_CLEAR, WORKSPACE_RESET
    user=request.user,
    company=workspace,
    description=f'Switched to workspace: {workspace.name}',
    request=request,
    success=True
)
```

### Available Log Types:
- `WORKSPACE_SWITCH` - User switched to a workspace
- `WORKSPACE_CLEAR` - User cleared workspace selection
- `WORKSPACE_RESET` - User reset workspace selection
- `WORKSPACE_CREATE` - User created new workspace

---

## Security & Validation

### All Views Check:
1. âœ… User is authenticated (`@login_required`)
2. âœ… Workspace exists (`get_object_or_404()`)
3. âœ… Workspace not deleted (`is_deleted=False`)
4. âœ… User has membership (`Membership.DoesNotExist`)
5. âœ… Permission denied if not member (`messages.error()`)

### Error Handling:
```python
try:
    membership = request.user.memberships.get(company=workspace)
except Membership.DoesNotExist:
    messages.error(request, "You don't have access to this workspace")
    return redirect("workspace_selector")
```

---

## URLs & Routing

### URL Patterns (`accounts/urls.py`)
```python
path('switch/workspace/<int:workspace_id>/', views.switch_workspace, name='switch_workspace')
path('clear/workspace/', views.clear_workspace, name='clear_workspace')
path('reset/workspace/', views.reset_workspace, name='reset_workspace')
path('workspace/management/', views.workspace_management, name='workspace_management')
```

### Smart Dashboard Routing (`pages/views.py`)
```python
@login_required
def Dashboard(request):  # /dashboard/
    if user has valid workspace:
        return redirect('workspace_dashboard', workspace_id=X)
    elif user has memberships:
        return redirect('workspace_selector')
    else:
        messages.info("Let's create your first workspace!")
        return redirect('workspace_create')
```

---

## Templates

### Workspace Management Template
**File**: `templates/account/workspace_management.html`

Features:
- Current workspace info card
- All workspaces table with switch buttons
- Quick action buttons
- Clear workspace modal with confirmation
- Responsive design
- i18n support

---

## User Messages

Users see appropriate feedback messages:

1. **Switch Workspace Success**:  
   "Switched to {workspace.name}"

2. **Clear/Reset Success**:  
   "Workspace cleared. You can now select a different one."

3. **Error - No Access**:  
   "You don't have access to this workspace"

4. **Error - Not Found**:  
   "Workspace not found or access denied"

---

## Related Views & Functions

- `workspace_selector()` - Show user's workspaces to choose from
- `workspace_select()` - Alternative switching method (in apps/orgs/)
- `workspace_dashboard()` - Main workspace dashboard
- `workspace_create()` - Create new workspace
- `workspace_list()` - List all user's workspaces
- `Dashboard()` - Smart router (pages/views.py)

---

## Testing Checklist

- [ ] Switch between workspaces (single & multiple)
- [ ] Clear workspace then select different one
- [ ] Reset workspace and return to selector
- [ ] Verify audit logs for all actions
- [ ] Test error cases (no membership, deleted workspace)
- [ ] Verify messages display correctly
- [ ] Test on mobile and desktop
- [ ] Test language switching (if multi-language)
- [ ] Test with different user roles (Owner, Admin, Member)
- [ ] Verify workspace appears in navigation

---

## Summary

The workspace management system provides:

âœ… **Multiple ways to switch**: Dropdown, list, management page  
âœ… **Clear & reset options**: Return to public, select again  
âœ… **Full audit trail**: All actions logged  
âœ… **Security validation**: User membership verified  
âœ… **User feedback**: Messages for all actions  
âœ… **Mobile responsive**: Works on all devices  
âœ… **Internationalized**: Multi-language support  
âœ… **Smart routing**: Automatic dashboard direction  


