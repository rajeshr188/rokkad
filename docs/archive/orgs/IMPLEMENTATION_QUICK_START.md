---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Quick Start: Implementation Priority Guide

## Phase 0: Quick Wins (This Week - 3 Days)

These changes provide immediate security improvements with minimal code:

### 1. Add Subscription Validation to WorkspaceMiddleware (1 hour)

**File:** [django_project/middleware.py](django_project/middleware.py)

```python
from apps.subscriptions.models import Subscription
from django.contrib import messages
from django.shortcuts import redirect

class WorkspaceMiddleware(TenantMainMiddleware):
    def process_request(self, request):
        try:
            hostname = self.hostname_from_request(request)
        except DisallowedHost:
            return HttpResponseNotFound()

        if request.user.is_authenticated and request.user.profile.workspace:
            workspace = request.user.profile.workspace
            
            # NEW: Validate subscription status
            subscription = Subscription.objects.filter(
                company=workspace,
                is_active=True
            ).first()
            
            if not subscription:
                messages.error(request, 'Your subscription has expired. Please renew.')
                return redirect('billing:renew')
            
            # Check days until expiry
            if subscription.days_until_expiry < 7:
                messages.warning(
                    request, 
                    f'Subscription expires in {subscription.days_until_expiry} days'
                )
            
            # NEW: Check membership validity
            try:
                membership = Membership.objects.get(
                    user=request.user,
                    company=workspace
                )
                if membership.is_suspended:
                    messages.error(request, 'Your account is suspended.')
                    return redirect('account:suspended')
            except Membership.DoesNotExist:
                messages.error(request, 'You are not a member of this workspace.')
                return redirect('dashboard')
            
            connection.set_tenant(workspace)
            request.tenant = workspace
            self.setup_url_routing(request)
            return None

        connection.set_schema_to_public()
        return super().process_request(request)
```

### 2. Add is_suspended Field to Membership (30 mins)

**File:** Database migration

```bash
python manage.py makemigrations
```

Create file: `apps/orgs/migrations/0XXX_add_suspended_fields.py`

```python
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('orgs', '0XXX_previous_migration'),
    ]

    operations = [
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
    ]
```

### 3. Enhance Role Decorator (1 hour)

**File:** [apps/orgs/decorators.py](apps/orgs/decorators.py)

Replace the entire `roles_required` function with:

```python
def roles_required(allowed_roles):
    def decorator(view_func):
        @functools.wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            user = request.user
            workspace = request.user.profile.workspace

            # Check if user has workspace set
            if not workspace:
                messages.error(request, 'Please select a workspace')
                return redirect('workspace_select')

            # Get membership
            try:
                membership = Membership.objects.get(
                    user=user, 
                    company=workspace
                )
            except Membership.DoesNotExist:
                raise Http404('You are not a member of this workspace')

            # Check suspension status
            if hasattr(membership, 'is_suspended') and membership.is_suspended:
                raise Http404('Your account is suspended')

            # Check role
            if membership.role.name not in allowed_roles:
                raise Http404(
                    f'This action requires one of: {", ".join(allowed_roles)}'
                )

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator
```

### 4. Create Smart Dashboard Redirect (45 mins)

**File:** [pages/views.py](pages/views.py)

```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

@login_required
def landing(request):
    """Smart redirect based on user state"""
    user = request.user
    profile = user.profile
    
    # User has a workspace set, redirect to tenant dashboard
    if profile.workspace:
        return redirect('tenant:dashboard')
    
    # User has memberships but no workspace selected
    memberships = Membership.objects.filter(user=user)
    
    if memberships.count() == 1:
        # Auto-join if user has only one workspace
        profile.workspace = memberships.first().company
        profile.save()
        return redirect('tenant:dashboard')
    
    if memberships.count() > 1:
        # Let user select which workspace to enter
        return redirect('workspace_select')
    
    # No memberships at all - show company creation or invitations
    context = {
        'has_pending_invitations': CompanyInvitation.objects.filter(
            email=user.email
        ).exists()
    }
    return render(request, 'pages/post_signup_intro.html', context)
```

### 5. Add Invited Badge to Invitations (30 mins)

**File:** [templates/components/notifications.html](templates/components/notifications.html)

```html
{% if pending_invitations %}
    <div class="alert alert-info">
        <h5>ðŸ“¬ You have {{ pending_invitations|length }} pending invitation(s)</h5>
        {% for invitation in pending_invitations %}
            <div class="invitation-card">
                <p><strong>{{ invitation.company.name }}</strong> invited you as <span class="badge">{{ invitation.role.name }}</span></p>
                <small class="text-muted">Expires {{ invitation.sent|add_days:app_settings.INVITATION_EXPIRY|date }}</small>
                <div class="mt-2">
                    <a href="{% url 'invitations:accept' invitation.key %}" class="btn btn-sm btn-success">Accept</a>
                    <a href="{% url 'invitations:decline' invitation.key %}" class="btn btn-sm btn-danger">Decline</a>
                </div>
            </div>
        {% endfor %}
    </div>
{% endif %}
```

---

## Phase 1: Foundation (Week 1)

### High-Impact, Manageable Tasks

#### 1. Create Permission System (3 days)

**Goal:** Move from role-name checking to permission-based checks

Files to create/modify:
- `apps/orgs/models.py` - Add permissions to Role model
- `apps/orgs/permissions.py` - Define all app permissions
- `apps/orgs/context_processors.py` - Add user permissions to context

```python
# apps/orgs/permissions.py
WORKSPACE_PERMISSIONS = {
    'workspace_view': 'Can view workspace',
    'workspace_edit': 'Can edit workspace settings',
    'workspace_delete': 'Can delete workspace',
}

TEAM_PERMISSIONS = {
    'team_view': 'Can view team members',
    'team_invite': 'Can invite users to team',
    'team_edit': 'Can edit team members',
    'team_remove': 'Can remove team members',
}

BILLING_PERMISSIONS = {
    'billing_view': 'Can view billing info',
    'billing_edit': 'Can edit billing',
    'billing_export': 'Can export billing data',
}

DATA_PERMISSIONS = {
    'data_view': 'Can view data',
    'data_edit': 'Can edit data',
    'data_create': 'Can create data',
    'data_export': 'Can export data',
}

# All permissions
ALL_PERMISSIONS = {
    **WORKSPACE_PERMISSIONS,
    **TEAM_PERMISSIONS,
    **BILLING_PERMISSIONS,
    **DATA_PERMISSIONS,
}

# Role to permission mapping
ROLE_PERMISSIONS = {
    'Owner': list(ALL_PERMISSIONS.keys()),
    'Admin': [
        'workspace_view', 'workspace_edit',
        'team_view', 'team_invite', 'team_edit',
        'billing_view', 'data_view', 'data_edit', 'data_create', 'data_export'
    ],
    'Member': [
        'workspace_view',
        'team_view',
        'data_view', 'data_edit', 'data_create',
    ]
}
```

#### 2. Add Audit Logging (2 days)

Create `apps/audit/models.py`:

```python
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('login', 'User Login'),
        ('logout', 'User Logout'),
        ('company_create', 'Company Created'),
        ('company_edit', 'Company Edited'),
        ('company_delete', 'Company Deleted'),
        ('team_invite', 'User Invited'),
        ('team_remove', 'User Removed'),
        ('workspace_switch', 'Workspace Switched'),
        ('data_create', 'Data Created'),
        ('data_edit', 'Data Edited'),
        ('data_delete', 'Data Deleted'),
        ('export', 'Data Exported'),
    ]
    
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    resource_type = models.CharField(max_length=100)  # 'Company', 'Loan', etc
    resource_id = models.CharField(max_length=100)
    resource_name = models.CharField(max_length=255, blank=True)
    workspace = models.ForeignKey(
        'orgs.Company', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True
    )
    changes = models.JSONField(null=True, blank=True)  # Before/after values
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['workspace', '-timestamp']),
            models.Index(fields=['action']),
        ]
    
    def __str__(self):
        return f'{self.user} - {self.action} on {self.resource_type}'

    @staticmethod
    def log(user, action, resource_type, resource_id, request=None, 
            resource_name='', workspace=None, changes=None):
        """Helper to create audit log entries"""
        
        ip = request.META.get('REMOTE_ADDR') if request else '0.0.0.0'
        ua = request.META.get('HTTP_USER_AGENT') if request else 'Unknown'
        
        AuditLog.objects.create(
            user=user,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id),
            resource_name=resource_name,
            workspace=workspace,
            changes=changes,
            ip_address=ip,
            user_agent=ua,
        )
```

#### 3. Create Onboarding Progress Tracker (2 days)

File: `apps/onboarding/models.py`

```python
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class OnboardingProgress(models.Model):
    STEPS = [
        (1, 'Email Verification'),
        (2, 'Profile Setup'),
        (3, 'Company Setup'),
        (4, 'Plan Selection'),
        (5, 'Billing Setup'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='onboarding')
    current_step = models.IntegerField(choices=STEPS, default=1)
    completed_steps = models.JSONField(default=list)  # [1, 2, 3, ...]
    company_created = models.BooleanField(default=False)
    subscription_active = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    skipped_at = models.DateTimeField(null=True, blank=True)
    
    def is_complete(self):
        return 5 in self.completed_steps
    
    def mark_step_complete(self, step):
        if step not in self.completed_steps:
            self.completed_steps.append(step)
            self.current_step = step + 1
            self.save()
            
            if self.is_complete():
                self.completed_at = timezone.now()
                self.save()
```

---

## Phase 2: Core Improvements (Week 2)

### Main Tasks

#### 1. Build Onboarding Wizard (3 days)

Structure:
```
apps/onboarding/
    views.py           # Wizard view handling
    forms.py           # Step forms
    templates/
        step_1_email_verify.html
        step_2_profile.html
        step_3_company.html
        step_4_plan.html
        step_5_billing.html
        progress_bar.html
```

#### 2. Workspace Selector Component (2 days)

Create workspace selection and switching UI

#### 3. Permission Context Processor (1 day)

Ensure all templates have access to user permissions

---

## Phase 3: UI Polish (Week 3-4)

### Tasks

1. Create unified base template
2. Implement role-based UI components
3. Add feature gates to features
4. Create empty state templates
5. Add role-based navigation items

---

## Testing Strategy

### Unit Tests to Add

**Test: Authorization Middleware**
```python
# apps/orgs/tests.py
def test_workspace_middleware_validates_subscription():
    """Expired subscription should redirect"""
    user = User.objects.create_user('test@test.com')
    workspace = Company.objects.create(name='test')
    Membership.objects.create(user=user, company=workspace)
    
    # Set expired subscription
    Subscription.objects.create(
        user=user,
        company=workspace,
        is_active=False  # EXPIRED
    )
    
    request = RequestFactory().get('/')
    request.user = user
    request.user.profile.workspace = workspace
    
    middleware = WorkspaceMiddleware(lambda r: HttpResponse())
    response = middleware(request)
    
    assert response.status_code == 302  # Redirect
    # Should redirect to billing page
```

**Test: Role Decorator**
```python
def test_roles_required_checks_membership():
    """User without correct role should get 404"""
    user = User.objects.create_user('member@test.com')
    workspace = Company.objects.create(name='test')
    
    # Create role
    member_role = Role.objects.create(name='Member')
    Membership.objects.create(
        user=user, 
        company=workspace,
        role=member_role
    )
    
    # Create protected view
    @roles_required(['Owner', 'Admin'])
    def protected_view(request):
        return HttpResponse('OK')
    
    request = RequestFactory().get('/')
    request.user = user
    request.user.profile.workspace = workspace
    
    # Should raise Http404
    with pytest.raises(Http404):
        protected_view(request)
```

---

## File Checklist for Implementation

### Phase 0 (Quick Wins)
- [ ] Modify `django_project/middleware.py` - Add subscription validation
- [ ] Create migration for `Membership.is_suspended`
- [ ] Update `apps/orgs/decorators.py`
- [ ] Add `landing()` view to `pages/views.py`
- [ ] Create notification template

### Phase 1 (Foundation)
- [ ] Create `apps/orgs/permissions.py`
- [ ] Create `apps/audit/models.py` + migration
- [ ] Create `apps/onboarding/models.py` + migration
- [ ] Add context processor `apps/orgs/context_processors.py`
- [ ] Create initial tests

### Phase 2 (Onboarding & Flows)
- [ ] Create `apps/onboarding/views.py` (wizard)
- [ ] Create `apps/onboarding/forms.py`
- [ ] Create `apps/onboarding/templates/`
- [ ] Create workspace selector view & template
- [ ] Add permission checks to existing views

### Phase 3 (UI/UX)
- [ ] Create unified `templates/layouts/base.html`
- [ ] Create permission-aware template filters
- [ ] Component library `templates/components/`
- [ ] Update existing templates to use unified base
- [ ] Add feature gates to modules

---

## Estimated Timeline

- **Phase 0:** 4-5 hours (can do in afternoon)
- **Phase 1:** 3-4 days
- **Phase 2:** 4-5 days
- **Phase 3:** 5-7 days

**Total:** ~2-3 weeks for full implementation

---

## Success Criteria

âœ… All sensitive operations require explicit authorization check  
âœ… Subscription status validated on every workspace access  
âœ… Audit log captures all critical actions  
âœ… New users can complete onboarding in <15 minutes  
âœ… Workspace switching is intuitive  
âœ… UI hides features user doesn't have permission for  
âœ… >90% test coverage for auth flows  
âœ… No authorization bypass vulnerabilities  

---


