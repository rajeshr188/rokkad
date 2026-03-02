# Multi-Tenant SaaS User Flow & Authorization Enhancement Plan

## Executive Summary

Your current application has a foundational multi-tenant architecture using django-tenants, but lacks proper authorization enforcement, clear user flows, and optimized UI/UX. This document provides a comprehensive analysis and actionable enhancement plan across three areas:

1. **Authorization & Security** - Strengthening permission controls
2. **User Flow & Onboarding** - Clarifying and improving user journeys
3. **UI/UX & Navigation** - Creating a cohesive, role-aware interface

---

## 1. AUTHORIZATION & SECURITY ANALYSIS

### Current State

#### Strengths ✅
- **Tenant Isolation**: Django-tenants provides database-level schema separation
- **Role-Based Structure**: Membership model with Role association exists
- **Workspace Context**: WorkspaceMiddleware automatically routes to correct tenant schema
- **Role Decorator**: `@roles_required` decorator enforces basic role checks

#### Critical Gaps ❌

1. **No Granular Permission System**
   - Only role names checked (Owner, Admin, Member)
   - No feature-level permission mapping
   - No permission caching or hierarchy
   - Missing permission checks in views

2. **Authorization Bypass Risks**
   - WorkspaceMiddleware sets tenant based on UserProfile.workspace without re-validating membership
   - Direct API/URL access to resources without object-level permission checks
   - No audit trail of who accessed what and when
   - Subscription status not validated before workspace access

3. **Credential & Data Flow Issues**
   - Company creation unrestricted (any authenticated user can create companies)
   - Invitation system lacks expiration enforcement
   - No rate limiting on sensitive operations
   - Admin operations not logged

4. **Missing Authorization at Critical Points**
   - Tenant app views (girvi, dea, sales, purchase, contact) not protected with role checks
   - Company settings/configuration accessible without proper authorization
   - Team member actions (add/remove) not restricted

### Recommended Solutions

#### Phase 1: Permission Framework (Week 1-2)

**1.1 Implement Django Guardian for Row-Level Security**
```python
# Install django-guardian for object-level permissions
pip install django-guardian

# Models will support fine-grained permissions:
# - workspace_view, workspace_edit, workspace_delete
# - reports_view, reports_export
# - team_view, team_edit
# - billing_view, billing_edit
```

**1.2 Define Standardized Role Permission Matrix**
```
┌─────────────────┬────────┬───────┬────────┐
│ Permission      │ Owner  │ Admin │ Member │
├─────────────────┼────────┼───────┼────────┤
│ workspace_view  │   ✓    │   ✓   │   ✓    │
│ workspace_edit  │   ✓    │   ✓   │        │
│ workspace_del   │   ✓    │       │        │
│ team_view       │   ✓    │   ✓   │   ✓    │
│ team_invite     │   ✓    │   ✓   │        │
│ team_remove     │   ✓    │       │        │
│ billing_view    │   ✓    │   ✓   │        │
│ billing_edit    │   ✓    │       │        │
│ data_view       │   ✓    │   ✓   │   ✓    │
│ data_edit       │   ✓    │   ✓   │   ✓    │
│ data_export     │   ✓    │   ✓   │        │
└─────────────────┴────────┴───────┴────────┘

# Plus feature-specific perms:
- girvi_loan_create, girvi_loan_approve, girvi_loan_release
- sales_invoice_create, sales_invoice_edit
- dea_journal_entry_create, dea_reconciliation_edit
- etc.
```

**1.3 Enhance Decorators with Permission Checking**
```python
# Create new decorator set:
@permission_required('workspace_view')  # View any resource in workspace
@object_permission_required('data_edit')  # Edit specific object
@subscription_required('feature_x')  # Feature-based access
```

**1.4 Add Audit Logging**
```python
# Log all sensitive operations:
- User login/logout with IP, browser, location
- Company/workspace creation/modification
- Team member additions/removals
- Data exports
- Permission changes
- Billing operations
```

#### Phase 2: Enhanced Authorization Checks (Week 2-3)

**2.1 Workspace Access Validation**
```python
# In WorkspaceMiddleware - add validation:
def process_request(self, request):
    if request.user.is_authenticated and request.user.profile.workspace:
        workspace = request.user.profile.workspace
        
        # Check: User is member of workspace
        membership = Membership.objects.get(
            user=request.user, 
            company=workspace
        )
        
        # Check: Company subscription is active
        subscription = workspace.subscription_set.filter(is_active=True).first()
        if not subscription:
            redirect_to = "upgrade_subscription"
        
        # Check: User not banned/suspended
        if membership.is_suspended:
            redirect_to = "suspended"
            
    # ... continue with existing logic
```

**2.2 Data-Level Permission Checks**
```python
# For all querysets in tenant apps:
class ContactQuerySet(models.QuerySet):
    def user_accessible(self, user):
        """Filter contacts to only those the user can access"""
        membership = Membership.objects.get(
            user=user, 
            company=user.profile.workspace
        )
        
        # Owner/Admin can see all; Members see only their created ones
        if membership.role.name in ['Owner', 'Admin']:
            return self
        else:
            return self.filter(created_by=user)
```

**2.3 API Endpoint Protection**
```python
# For any API views (if used):
from rest_framework.permissions import BasePermission

class WorkspaceObjectPermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        workspace = request.user.profile.workspace
        
        # Object must belong to user's workspace
        if hasattr(obj, 'workspace'):
            return obj.workspace == workspace
        
        # Check membership role
        membership = Membership.objects.get(
            user=request.user, 
            company=workspace
        )
        return membership.role.name in ['Owner', 'Admin']
```

#### Phase 3: Decorator-Based Granular Access Control (Week 3-4)

**3.1 Feature-Level Access Decorators**

After middleware provides baseline subscription protection, decorators enforce feature-tier restrictions:

```python
# Create decorator module: apps/subscriptions/decorators.py

from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect
from django.http import Http404

def feature_required(feature_name):
    """
    Decorator to enforce feature-level access based on subscription plan.
    
    Middleware checks: Subscription exists and is active
    Decorator checks: User's plan includes this feature
    
    Examples:
    - 'advanced_reporting' → Pro/Enterprise plans only
    - 'api_access' → Premium plans only
    - 'multi_warehouse' → Enterprise only
    - 'team_management' → All paid plans
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Middleware already validated subscription exists
            subscription = request.user.profile.workspace.subscription
            plan = subscription.plan
            
            # Define feature tier mapping
            FEATURE_TIERS = {
                'advanced_reporting': ['pro', 'enterprise'],
                'api_access': ['premium', 'enterprise'],
                'multi_warehouse': ['enterprise'],
                'multi_team': ['pro', 'enterprise'],
                'custom_fields': ['pro', 'enterprise'],
                'approval_workflows': ['pro', 'enterprise'],
                'audit_logs': ['enterprise'],
                'sso_access': ['enterprise'],
            }
            
            required_tiers = FEATURE_TIERS.get(feature_name, [])
            if plan.tier not in required_tiers:
                messages.error(
                    request,
                    f'Feature "{feature_name}" is not available in your {plan.name} plan. '
                    f'Please upgrade to access this feature.'
                )
                return redirect('subscriptions:plan-list')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
```

**3.2 Role-Based Permission Decorators**

Enforces Owner/Admin/Member granularity per Django design:

```python
def permission_required(required_permission):
    """
    Decorator to enforce role-based permissions.
    
    Works with Membership.role to verify access.
    
    Usage:
    @permission_required('workspace_edit')
    @permission_required('team_invite')
    @permission_required('billing_edit')
    
    Permission matrix (from PERMISSION_MATRIX_GUIDE.md):
    - workspace_view    → Owner, Admin, Member
    - workspace_edit    → Owner, Admin
    - workspace_delete  → Owner only
    - team_invite       → Owner, Admin
    - team_remove       → Owner only
    - billing_view      → Owner, Admin
    - billing_edit      → Owner only
    - data_export       → Owner, Admin
    """
    PERMISSION_ROLES = {
        'workspace_view': ['owner', 'admin', 'member'],
        'workspace_edit': ['owner', 'admin'],
        'workspace_delete': ['owner'],
        'team_invite': ['owner', 'admin'],
        'team_remove': ['owner'],
        'billing_view': ['owner', 'admin'],
        'billing_edit': ['owner'],
        'data_export': ['owner', 'admin'],
        'data_publish': ['owner', 'admin'],
    }
    
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            workspace = request.user.profile.workspace
            
            try:
                membership = request.user.memberships.get(company=workspace)
                role = membership.role.name.lower()
            except:
                messages.error(request, 'Not a member of this workspace')
                return redirect('user_workspaces')
            
            allowed_roles = PERMISSION_ROLES.get(required_permission, [])
            if role not in allowed_roles:
                messages.error(
                    request,
                    f'Permission denied: {required_permission} requires {allowed_roles[0]} role.'
                )
                raise Http404("Permission denied")
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
```

**3.3 Object-Level Permission Decorators**

Row-level data access control - users only see/edit their own data:

```python
def object_permission_required(action='view'):
    """
    Decorator for object-level (row-level) permissions.
    
    Validates user can access specific data object.
    Applied to DetailView, UpdateView, DeleteView.
    
    Middleware: Subscription validation (workspace level)
    Decorator: Object ownership/access (row level)
    
    Usage:
    @object_permission_required('view')
    @object_permission_required('edit')
    @object_permission_required('delete')
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # For class-based views, override get_object()
            # For function views, validate object access in view
            
            # Example: Only allow viewing if:
            # 1. Object belongs to user's workspace
            # 2. User has workspace access (membership)
            # 3. Role allows action (Owner/Admin for edit, all for view)
            # 4. Object not marked as private/restricted
            
            workspace = request.user.profile.workspace
            obj_workspace = getattr(kwargs.get('object'), 'workspace', None)
            
            if obj_workspace and obj_workspace != workspace:
                raise Http404("Object not found or access denied")
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
```

**3.4 Usage Examples**

```python
# In tenant app views
from apps.subscriptions.decorators import feature_required, permission_required

class AdvancedReportingView(LoginRequiredMixin, TemplateView):
    """Advanced reporting dashboard"""
    @feature_required('advanced_reporting')
    def get(self, request, *args, **kwargs):
        # Only Pro/Enterprise plans see this
        return super().get(request, *args, **kwargs)

class TeamManagementView(LoginRequiredMixin, TemplateView):
    """Team member management"""
    @permission_required('team_invite')
    def get(self, request, *args, **kwargs):
        # Only Owner/Admin can manage team
        return super().get(request, *args, **kwargs)

class DataExportView(LoginRequiredMixin, View):
    """Bulk data export"""
    @feature_required('api_access')
    @permission_required('data_export')
    def post(self, request, *args, **kwargs):
        # Must be Enterprise plan AND Owner/Admin role
        return JsonResponse({'status': 'exporting'})
```

**Summary: Defense in Depth**

| Layer | Responsibility | Example |
|-------|-----------------|---------|
| **Middleware** | Workspace subscription exists & active | Redirect to billing if no subscription |
| **Feature Decorator** | Plan includes feature | Block advanced_reporting for Basic plan |
| **Permission Decorator** | User role permits action | Block billing_edit for Member role |
| **Object Decorator** | User can access specific row | Block viewing other user's private data |

---

## 2. USER FLOW & ONBOARDING ANALYSIS

### Current State Problem Map

```
Unauthenticated User
        ↓
[Home Page] → [Sign In / Sign Up]
        ↓
[Dashboard] ← PROBLEM: No clear next step, multiple paths
    ├→ Create Company (unclear if needed)
    ├→ View Existing Companies (may not have any)
    ├→ Manage Subscriptions (not prominent)
    ├→ View Invitations (if any)
    └→ Select Workspace (required but UI unclear)
        ↓
[Tenant-Specific Dashboard]
        ↓
[Access Workspace Data]

Issues:
1. New users don't know what to do after signup
2. No onboarding wizard
3. Company creation flow is unclear
4. Subscription requirements not explained upfront
5. Workspace selection is a manual step, not guided
6. No feature discovery/tour
```

### Recommended Solutions

#### Phase 1: Onboarding & User Flow Redesign (Week 1-2)

**1.1 New User Onboarding Journey**

```
New User Signup
    ↓
[Step 1: Email Verification] (2 min)
    ↓
[Step 2: Profile Setup] (5 min)
    - Name, Company Type, Role, Profile Picture
    ↓
[Step 3: Company Setup] (5-10 min)
    - Company Name, Industry, Website
    - Tax Info
    - Currency/Timezone
    ↓
[Step 4: Plan Selection] (3 min)
    - Show plans with features
    - Free trial option highlighted
    ↓
[Step 5: Billing Setup] (2 min)
    - Payment method (if not free)
    - Billing email
    ↓
[Onboarding Complete]
    ↓
[Application Tour / Feature Discovery]
    ↓
[Empty Dashboard with Quick Actions]
```

**Implementation Structure:**
```python
# Create dedicated onboarding app
apps/
    onboarding/
        views.py        # Step views + progress tracking
        forms.py        # Clean step forms
        models.py       # OnboardingProgress tracker
        templates/
            step_1_email_verify.html
            step_2_profile.html
            step_3_company.html
            step_4_plan.html
            step_5_billing.html
            progress_bar.html

# Model to track progress
class OnboardingProgress:
    user = ForeignKey(User)
    step = IntegerField()  # 1-5
    completed_at = DateTimeField()
    company_created = BooleanField()
    subscription_active = BooleanField()
    
# Decorator to redirect to onboarding if needed
@onboarding_complete_required
def dashboard(request):
    ...
```

**1.2 Authenticated User Dashboard Redesign**

For users who completed onboarding - clear action items:

```
┌─ Dashboard (Home) ──────────────────────┐
│                                         │
│ Welcome back, [User Name]!             │
│                                         │
│ ┌─ Your Workspaces ─────────────────┐  │
│ │ [Company 1] - Last accessed 2h ago│  │
│ │ [Company 2] - Last accessed 5d ago│  │
│ │ [+] Create New Workspace          │  │
│ └─────────────────────────────────────┘  │
│                                         │
│ ┌─ Invitations (if any) ────────────┐  │
│ │ [Invite from Company] - Expires.. │  │
│ │ [Accept] [Decline]               │  │
│ └─────────────────────────────────────┘  │
│                                         │
│ ┌─ Account Actions ──────────────────┐  │
│ │ [Profile Settings] [Subscription]  │  │
│ │ [Billing History]  [Support]       │  │
│ └─────────────────────────────────────┘  │
│                                         │
└─────────────────────────────────────────┘
```

**1.3 Workspace Entry Points**

```python
# OPTION 1: Direct tenant URL
# user.company.com/workspace/ → Auto-load that workspace

# OPTION 2: Workspace Selector
# app.com/select-workspace/ → List user's workspaces
# OR app.com/workspace/[id]/enter/ → Enter specific workspace

# Recommendation: Use OPTION 1 for better UX
# Each workspace should have its own domain/subdomain

# In WorkspaceMiddleware:
def process_request(self, request):
    hostname = self.hostname_from_request(request)
    
    # Get workspace from hostname
    domain = Domain.objects.get(domain=hostname)
    workspace = domain.tenant
    
    # Verify user is member
    membership = Membership.objects.get(
        user=request.user,
        company=workspace
    )
    
    # Auto-load workspace context - no manual selection needed
    connection.set_tenant(workspace)
    request.tenant = workspace
```

**1.4 Company Creation Flow**

```python
# Create a wizard-based company setup

class CompanyCreationWizard:
    Step 1: Basic Info (name, website, timezone)
    Step 2: Plan Selection (free vs paid)
    Step 3: Team Setup (add initial members?)
    Step 4: Billing (if paid plan)
    Step 5: Confirmation (create + initialize)
    
# Auto-create:
- All required schemas/tables
- Default settings/preferences
- Sample data (optional)
- Initial user as Owner
```

**1.5 Workspace Switching UI**

```html
<!-- In tenant base template -->
<div class="workspace-switcher">
    <span>📦 Current Workspace: {{ request.tenant.name }}</span>
    
    <div class="dropdown">
        <h6>Switch Workspace</h6>
        {% for membership in user.memberships.all %}
            <a href="/workspace/{{ membership.company.id }}/enter/">
                {{ membership.company.name }}
                <small>({{ membership.role.name }})</small>
            </a>
        {% endfor %}
        <hr>
        <a href="/workspace/create/">+ Create New Workspace</a>
        <a href="/dashboard/">← Back to Dashboard</a>
    </div>
</div>
```

#### Phase 2: Smart Redirects & Entry Points (Week 2-3)

**2.1 Intelligent Landing Based on User State**

```python
# views.py - Enhanced home/dashboard routing
def landing(request):
    """Smart redirect based on user state"""
    if not request.user.is_authenticated:
        return redirect('home')  # Public homepage
    
    user = request.user
    profile = user.profile
    
    # Check onboarding status
    if not profile.onboarding_completed:
        return redirect('onboarding')
    
    # Check memberships
    memberships = Membership.objects.filter(user=user)
    
    if not memberships.exists():
        return redirect('workspace_create')  # No workspace
    
    if not profile.workspace:
        return redirect('workspace_select')  # Can join, but hasn't selected
    
    # Auto-enter workspace
    return redirect('tenant:dashboard')
```

**2.2 Subscription-Aware Access Control**

```python
from apps.subscriptions.models import Subscription

class SubscriptionRequiredMixin:
    """Ensure workspace subscription is active"""
    
    def dispatch(self, request, *args, **kwargs):
        workspace = request.user.profile.workspace
        
        subscription = Subscription.objects.filter(
            company=workspace,
            is_active=True
        ).first()
        
        if not subscription:
            messages.warning(
                request, 
                'Subscription expired. Please renew to continue.'
            )
            return redirect('billing:renew_subscription')
        
        if subscription.days_until_cancel < 7:
            messages.info(
                request,
                f'Subscription renews in {subscription.days_until_cancel} days'
            )
        
        return super().dispatch(request, *args, **kwargs)
```

**2.3 Invitation Expiration Enforcement**

```python
# In CompanyInvitation model
def is_expired(self):
    expiry_days = app_settings.INVITATION_EXPIRY  # e.g., 7 days
    return self.sent + timedelta(days=expiry_days) < timezone.now()

# Middleware or decorator to auto-expire
@invitation_valid_required
def accept_invitation(request, key):
    invitation = CompanyInvitation.objects.get(key=key)
    
    if invitation.is_expired():
        invitation.delete()
        raise Http404("Invitation has expired")
    
    # Accept invitation...
```

---

## 3. UI/UX & NAVIGATION ANALYSIS

### Current State Problems

**Technical Issues:**
- Dual template system (_base.html + tenant.html) creates maintenance burden
- No component-based UI framework
- Permission checks not integrated into templates
- No context variables passed for conditional rendering

**User Experience Issues:**
- Navigation items shown regardless of user permissions
- No visual indication of current location/workspace
- Inconsistent styling between public and tenant sections
- No role-based feature visibility
- Empty states not handled gracefully

### Recommended Solutions

#### Phase 1: Unified Navigation & Layout System (Week 1-2)

**1.1 Create Unified Base Template**

```html
<!-- templates/layouts/base.html -->
<html>
<head>...</head>
<body>
    <!-- Top Navigation Bar -->
    <nav class="navbar">
        <div class="navbar-brand">
            <a href="/">Rokkad</a>
        </div>
        
        <!-- Workspace Indicator (if in tenant) -->
        {% if request.tenant %}
            <div class="workspace-badge">
                📦 {{ request.tenant.name }}
                <a href="/workspace/switch/">Change</a>
            </div>
        {% endif %}
        
        <!-- Main Navigation -->
        <ul class="navbar-menu">
            {% with perms=request.user.get_permissions %}
                {% if 'workspace_view' in perms %}
                    <li><a href="{% url 'workspace:dashboard' %}">Dashboard</a></li>
                {% endif %}
                
                {% if 'data_view' in perms %}
                    <li class="dropdown">
                        <a href="#">Data</a>
                        <ul class="dropdown-menu">
                            {% if 'girvi_loan_view' in perms %}
                                <li><a href="{% url 'girvi:loan_list' %}">Loans</a></li>
                            {% endif %}
                            {% if 'sales_invoice_view' in perms %}
                                <li><a href="{% url 'sales:invoice_list' %}">Sales</a></li>
                            {% endif %}
                            {% if 'purchase_invoice_view' in perms %}
                                <li><a href="{% url 'purchase:invoice_list' %}">Purchase</a></li>
                            {% endif %}
                        </ul>
                    </li>
                {% endif %}
                
                {% if 'team_view' in perms %}
                    <li><a href="{% url 'workspace:team' %}">Team</a></li>
                {% endif %}
                
                {% if 'billing_view' in perms %}
                    <li><a href="{% url 'billing:overview' %}">Billing</a></li>
                {% endif %}
            {% endwith %}
        </ul>
        
        <!-- User Menu -->
        <div class="user-menu">
            <span>{{ user.get_full_name }}</span>
            <a href="{% url 'profile' %}">Profile</a>
            <a href="{% url 'account_logout' %}">Logout</a>
        </div>
    </nav>
    
    <!-- Main Content -->
    <main class="container">
        {% include "components/messages.html" %}
        {% block content %}{% endblock %}
    </main>
    
    <!-- Footer -->
    <footer>...</footer>
</body>
</html>
```

**1.2 Create Permission Context Processor**

```python
# django_project/context_processors.py
from django.contrib.auth.models import Permission

def user_permissions(request):
    """Add user permissions to template context"""
    if not request.user.is_authenticated:
        return {'user_permissions': set()}
    
    workspace = request.user.profile.workspace
    if not workspace:
        return {'user_permissions': set()}
    
    # Get user's membership
    from apps.orgs.models import Membership
    membership = Membership.objects.get(
        user=request.user,
        company=workspace
    )
    
    # Get all permissions for user's role
    perms = membership.role.permissions.values_list('codename', flat=True)
    
    return {
        'user_permissions': set(perms),
        'user_role': membership.role.name,
        'user_workspace': workspace
    }
```

**1.3 Navigation Configuration (Declarative)**

```python
# apps/navigation/config.py
NAVIGATION_STRUCTURE = {
    'authenticated': {
        'dashboard': {
            'label': 'Dashboard',
            'url_name': 'dashboard',
            'icon': 'home',
        },
        'data': {
            'label': 'Data',
            'icon': 'database',
            'submenu': {
                'loans': {'label': 'Loans', 'url_name': 'girvi:loan_list'},
                'sales': {'label': 'Sales', 'url_name': 'sales:invoice_list'},
                'purchase': {'label': 'Purchase', 'url_name': 'purchase:invoice_list'},
                'accounting': {'label': 'Accounting', 'url_name': 'dea:journal_list'},
            }
        },
    },
    'tenant_only': {
        'team': {
            'label': 'Team',
            'url_name': 'workspace:team',
            'icon': 'users',
            'required_permission': 'team_view',
        },
        'settings': {
            'label': 'Settings',
            'url_name': 'workspace:settings',
            'icon': 'cog',
            'required_permission': 'workspace_edit',
        },
        'billing': {
            'label': 'Billing',
            'url_name': 'billing:overview',
            'icon': 'credit-card',
            'required_permission': 'billing_view',
        }
    }
}

# Template filter
@register.inclusion_tag('components/navigation.html')
def render_navigation(user, workspace=None):
    """Render filtered navigation based on permissions"""
    nav_items = []
    
    for item_key, item_config in NAVIGATION_STRUCTURE.items():
        # Check permissions
        required_perm = item_config.get('required_permission')
        if required_perm and not user.has_perm(required_perm):
            continue
        
        nav_items.append({
            'label': item_config['label'],
            'url': reverse(item_config['url_name']),
            'icon': item_config.get('icon'),
            'submenu': item_config.get('submenu', {})
        })
    
    return {'items': nav_items}
```

#### Phase 2: Role-Based UI & Component System (Week 2-3)

**2.1 Permission-Based Template Components**

```html
<!-- templates/components/action_buttons.html -->
{% if 'data_edit' in user_permissions %}
    <a href="{{ object.get_edit_url }}" class="btn btn-primary">
        Edit
    </a>
{% else %}
    <span class="btn btn-disabled" title="Requires Editor role">
        Edit
    </span>
{% endif %}

{% if 'data_export' in user_permissions %}
    <a href="{{ object.get_export_url }}" class="btn btn-secondary">
        Export
    </a>
{% endif %}

<!-- Permission check in lists -->
{% if 'data_delete' in user_permissions %}
    <form method="post" action="{{ object.get_delete_url }}" class="inline">
        {% csrf_token %}
        <button type="submit" class="btn btn-danger" 
                onclick="return confirm('Delete this item?')">
            Delete
        </button>
    </form>
{% endif %}
```

**2.2 Empty State Handling**

```html
<!-- templates/components/empty_state.html -->
{% if not items %}
    <div class="empty-state">
        <div class="empty-icon">📭</div>
        <h3>No Items Yet</h3>
        <p>{{ message }}</p>
        
        {% if can_create %}
            <a href="{{ create_url }}" class="btn btn-primary">
                Create {{ item_type }}
            </a>
        {% else %}
            <p class="text-muted">
                You don't have permissions to create {{ item_type }}.
                Contact your workspace admin.
            </p>
        {% endif %}
    </div>
{% else %}
    {% block items_content %}{% endblock %}
{% endif %}
```

**2.3 Role Badge & Status Indicators**

```html
<!-- User card in team lists -->
<div class="team-member">
    <img src="{{ member.profile_picture }}" alt="{{ member.name }}" class="avatar">
    <div class="member-info">
        <h4>{{ member.get_full_name }}</h4>
        <span class="role-badge role-{{ membership.role.name|lower }}">
            {{ membership.role.name }}
        </span>
        {% if membership.is_pending %}
            <span class="badge badge-warning">Pending</span>
        {% endif %}
        {% if membership.is_suspended %}
            <span class="badge badge-danger">Suspended</span>
        {% endif %}
    </div>
    <div class="member-actions">
        {% if 'team_edit' in user_permissions %}
            <a href="..." class="icon-btn" title="Edit">✏️</a>
            <a href="..." class="icon-btn" title="Remove">🗑️</a>
        {% endif %}
    </div>
</div>
```

**2.4 Breadcrumb Navigation**

```html
<!-- templates/components/breadcrumbs.html -->
<nav class="breadcrumbs">
    <a href="{% url 'dashboard' %}">Dashboard</a>
    {% if request.tenant %}
        <span>›</span>
        <a href="{% url 'workspace:dashboard' %}">{{ request.tenant.name }}</a>
        {% block breadcrumbs %}{% endblock %}
    {% endif %}
</nav>
```

#### Phase 3: Progressive Disclosure & Onboarding UI (Week 3-4)

**3.1 Feature Tour System**

```python
# apps/onboarding/tours.py
FEATURE_TOURS = {
    'dashboard': {
        'name': 'Dashboard Overview',
        'steps': [
            {
                'target': '.loan-card',
                'title': 'Loan Management',
                'description': 'Track all loans and their status here',
                'position': 'bottom',
                'image': '/static/tours/loan-demo.gif'
            },
            {
                'target': '.metrics-section',
                'title': 'Key Metrics',
                'description': 'Real-time overview of your business',
                'position': 'left',
            },
            # ... more steps
        ]
    },
    'girvi': {
        'name': 'Loan Management',
        'steps': [
            # ...
        ]
    }
}

# Template integration
<script>
    new Shepherd.Tour({
        useModalOverlay: true,
        steps: {{ tour_data|safe }}
    }).start();
</script>
```

**3.2 Feature Gating & Contextual Help**

```html
<!-- Show feature availability based on plan -->
{% if 'girvi_loan_create' not in user_permissions %}
    <div class="feature-locked">
        <h3>🔒 Loan Management</h3>
        <p>This feature is available in {{ workspace.plan.name }} plan</p>
        <a href="{% url 'billing:upgrade' %}" class="btn btn-primary">
            Upgrade to Unlock
        </a>
    </div>
{% endif %}

<!-- Contextual help -->
<div class="help-banner">
    <span class="help-icon">?</span>
    <p>New to loan management? <a href="#" data-tour="girvi">Take a tour</a></p>
    <button class="close-help" aria-label="Close">×</button>
</div>
```

---

## 4. IMPLEMENTATION TIMELINE

### Week 1: Foundation
- [ ] Set up django-guardian for row-level permissions
- [ ] Create permission matrix and migration
- [ ] Implement audit logging
- [ ] Create new decorator set
- [ ] Start onboarding wizard design

### Week 2: Core Auth & Flows
- [ ] Implement onboarding flow
- [ ] Add subscription validation to middleware
- [ ] Create workspace selector/switcher
- [ ] Start unified template system
- [ ] Set up navigation configuration

### Week 3: UI & Features
- [ ] Complete unified templates
- [ ] Implement permission-based UI rendering
- [ ] Add role badges and indicators
- [ ] Company creation wizard
- [ ] Workspace switching UI

### Week 4: Polish & Testing
- [ ] Feature tours and progressive disclosure
- [ ] Empty state handling
- [ ] Comprehensive testing (unit + integration)
- [ ] Performance optimization
- [ ] User acceptance testing

---

## 5. DATABASE MIGRATIONS NEEDED

```python
# Migration 1: Add permissions to Membership and Role
class Migration(migrations.Migration):
    operations = [
        # Add permission model if using django.contrib.auth.Permission
        
        # Add fields to Membership
        migrations.AddField(
            model_name='membership',
            name='is_suspended',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='membership',
            name='date_suspended',
            field=models.DateTimeField(null=True, blank=True),
        ),
        
        # Add onboarding tracking
        migrations.AddField(
            model_name='userprofile',
            name='onboarding_completed',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='onboarding_completed_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
        
        # Link subscription to Company (not just User)
        migrations.AddField(
            model_name='subscription',
            name='company',
            field=models.ForeignKey('orgs.Company', on_delete=models.CASCADE),
        ),
    ]

# Migration 2: Create AuditLog model
class Migration(migrations.Migration):
    operations = [
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.AutoField(primary_key=True)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=models.CASCADE, to='accounts.CustomUser')),
                ('action', models.CharField(max_length=100)),  # 'login', 'create_company', etc
                ('resource_type', models.CharField(max_length=100)),  # 'Company', 'Membership', etc
                ('resource_id', models.CharField(max_length=100)),
                ('changes', models.JSONField(null=True, blank=True)),  # What changed
                ('ip_address', models.GenericIPAddressField()),
                ('user_agent', models.TextField()),
                ('workspace', models.ForeignKey(null=True, blank=True, on_delete=models.CASCADE, to='orgs.Company')),
            ],
        ),
    ]
```

---

## 6. CRITICAL SUCCESS METRICS

Monitor these KPIs after implementation:

**User Engagement:**
- Onboarding completion rate (target: >80%)
- Time to first action after signup (target: <5 minutes)
- Feature discovery rate (target: >70% per role)

**Security:**
- Authorization bypass attempts blocked (target: 100%)
- Audit log coverage (target: 100% of sensitive ops)
- Permission inconsistencies detected (target: 0)

**User Experience:**
- Navigation clarity score (survey, target: >4/5)
- Role-based UI appreciation (survey, target: >4/5)
- Feature discoverability (analytics, target: >70%)

---

## 7. TECHNICAL DEBT ADDRESSED

This plan resolves:
- ❌ No row-level permission system → ✅ Django-guardian + custom permissions
- ❌ Unclear authorization → ✅ Explicit permission decorators and context processors
- ❌ Poor onboarding → ✅ Guided wizard and in-app tours
- ❌ Dual templates → ✅ Unified base + conditional components
- ❌ Hidden features → ✅ Progressive disclosure + feature gating
- ❌ No audit trail → ✅ Comprehensive AuditLog model
- ❌ Subscription enforcement → ✅ Middleware-level validation

---

## 8. RECOMMENDATIONS FOR IMMEDIATE ACTION

**Priority 1 (Do Now):**
1. Add `is_suspended` and audit fields to existing models
2. Create OnboardingProgress tracking
3. Implement basic permission context processor
4. Add subscription validation to WorkspaceMiddleware

**Priority 2 (Next Sprint):**
1. Build onboarding wizard (most impactful for UX)
2. Create unified template system
3. Implement audit logging
4. Add role badge display

**Priority 3 (Polish):**
1. Feature tours
2. Empty state handling
3. Advanced permission checks
4. Performance optimization

---

