# Complete User Flow Guide - Rokkad Multi-Tenant SaaS

## Overview

This document provides a comprehensive, step-by-step walkthrough of all user journeys in the Rokkad application, from initial signup to daily workspace operations. The flow leverages the unified UI/UX system with permission-based navigation and role-aware components.

---

## User Flow Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    APPLICATION ENTRY POINTS                      │
└─────────────────────────────────────────────────────────────────┘
                                ↓
                    ┌───────────────────────┐
                    │   Landing Page (/)    │
                    └───────────────────────┘
                                ↓
            ┌──────────────────┴──────────────────┐
            ↓                                     ↓
    ┌───────────────┐                   ┌─────────────────┐
    │  Sign Up      │                   │   Sign In       │
    │  /signup      │                   │   /login        │
    └───────────────┘                   └─────────────────┘
            ↓                                     ↓
            └──────────────────┬──────────────────┘
                               ↓
                    ┌──────────────────────┐
                    │  Smart Landing       │
                    │  (workspace_home)    │
                    └──────────────────────┘
                               ↓
        ┌──────────────────────┼──────────────────────┐
        ↓                      ↓                      ↓
┌──────────────┐      ┌────────────────┐    ┌────────────────┐
│ Onboarding   │      │ Workspace      │    │ Dashboard      │
│ (New User)   │      │ Selection      │    │ (Existing)     │
└──────────────┘      └────────────────┘    └────────────────┘
```

---

## Flow 1: New User Registration & Onboarding

### Step 1: Initial Registration
**URL:** `/accounts/signup/`  
**Template:** `templates/account/signup.html`

**User Actions:**
1. User visits landing page
2. Clicks "Sign Up" button
3. Enters email, username, password
4. Receives verification email
5. Clicks verification link

**Backend Process:**
- Django-allauth handles authentication
- User account created in public schema
- UserProfile created via signals
- AuditLog entry: `USER_SIGNUP`

**Next:** Redirect to onboarding start

---

### Step 2: Onboarding - Profile Setup
**URL:** `/onboarding/profile/`  
**Template:** `templates/onboarding/profile.html`  
**Decorator:** `@login_required`

**UI Features:**
- Progress bar shows 25% completion (Step 1/4)
- Form fields: Full name, phone, profile picture
- Auto-save to session storage
- Skip button available

**User Actions:**
1. Fill in personal details
2. Upload profile picture (optional)
3. Click "Continue" or "Skip"

**Backend Process:**
```python
# apps/onboarding/views.py
def onboarding_profile(request):
    progress = OnboardingProgress.objects.get_or_create(user=request.user)
    progress.current_step = 1
    progress.profile_completed = True
    progress.save()
    # Audit log
    AuditLog.log('ONBOARDING_PROFILE_COMPLETE', user=request.user)
```

**Next:** Redirect to company creation

---

### Step 3: Onboarding - Workspace Creation
**URL:** `/onboarding/company/`  
**Template:** `templates/onboarding/company.html`  
**Decorator:** `@login_required`

**UI Features:**
- Progress bar shows 50% completion (Step 2/4)
- Form fields: Company name, industry, website, timezone
- Info alert: "You'll be assigned as Owner"
- Visual preview of workspace card

**User Actions:**
1. Enter workspace details
2. Select industry from dropdown
3. Set timezone (auto-detected)
4. Click "Create Workspace"

**Backend Process:**
```python
def onboarding_company(request):
    if request.method == 'POST':
        # Create company in public schema
        company = Company.objects.create(
            name=form.cleaned_data['name'],
            creator=request.user,
            owner=request.user,
            schema_name=generate_schema_name(name),
        )
        
        # Create tenant schema
        company.create_schema()
        
        # Create Owner membership
        role = Role.objects.get(name='Owner')
        Membership.objects.create(
            user=request.user,
            company=company,
            role=role
        )
        
        # Set as active workspace
        request.user.profile.workspace = company
        request.user.profile.save()
        
        # Audit log
        AuditLog.log('COMPANY_CREATE', user=request.user, company=company)
        
        # Update onboarding progress
        progress.current_step = 2
        progress.company_completed = True
        progress.save()
```

**Next:** Redirect to team invitations (optional)

---

### Step 4: Onboarding - Team Invitations (Optional)
**URL:** `/onboarding/team/`  
**Template:** `templates/onboarding/team.html`  
**Decorator:** `@login_required`

**UI Features:**
- Progress bar shows 75% completion (Step 3/4)
- Dynamic form for multiple email addresses
- Role selector (Admin or Member)
- "Skip for now" prominently displayed
- Preview of invitation email

**User Actions:**
1. Enter team member emails
2. Select role for each member
3. Click "Send Invitations" or "Skip"

**Backend Process:**
```python
def onboarding_team(request):
    if request.method == 'POST':
        for email, role_id in invitations:
            invitation = CompanyInvitation.objects.create(
                company=request.user.profile.workspace,
                email=email,
                role_id=role_id,
                inviter=request.user,
                key=generate_invitation_key()
            )
            
            # Send email
            send_invitation_email(invitation)
            
            # Audit log
            AuditLog.log('INVITATION_SENT', user=request.user, 
                        extra_data={'email': email})
        
        progress.current_step = 3
        progress.team_completed = True
        progress.save()
```

**Next:** Redirect to feature tour (optional)

---

### Step 5: Onboarding - Feature Tour (Optional)
**URL:** `/onboarding/tour/`  
**Template:** `templates/onboarding/tour.html`  
**Decorator:** `@login_required`

**UI Features:**
- Progress bar shows 100% completion (Step 4/4)
- Interactive feature checklist
- Module selection (Girvi, Sales, DEA, etc.)
- Video tutorials or tooltips
- "Start Using Rokkad" CTA

**User Actions:**
1. Review available features
2. Select modules of interest
3. Click "Complete Onboarding"

**Backend Process:**
```python
def onboarding_complete(request):
    progress = OnboardingProgress.objects.get(user=request.user)
    progress.is_complete = True
    progress.completed_at = timezone.now()
    progress.save()
    
    # Save feature preferences
    OnboardingChoice.objects.create(
        progress=progress,
        selected_features=request.POST.getlist('features')
    )
    
    # Audit log
    AuditLog.log('ONBOARDING_COMPLETE', user=request.user)
```

**Next:** Redirect to workspace dashboard

---

## Flow 2: Existing User Login

### Step 1: Authentication
**URL:** `/accounts/login/`  
**Template:** `templates/account/login.html`

**User Actions:**
1. Enter username/email and password
2. Click "Sign In"
3. (Optional) Select "Remember me"

**Backend Process:**
```python
# Django-allauth handles authentication
# WorkspaceMiddleware activates workspace context
# AuditLog entry: USER_LOGIN with IP and user agent
```

**Next:** Redirect to smart landing (workspace_home)

---

### Step 2: Smart Landing & Routing
**URL:** `/workspace/home/`  
**View:** `pages.views.workspace_home`  
**Middleware:** `SubscriptionValidationMiddleware`, `SecureWorkspaceMiddleware`

**Decision Logic:**
```python
def workspace_home(request):
    user = request.user
    
    # Check 1: Onboarding complete?
    if not user.profile.onboarding_completed:
        return redirect('onboarding_start')
    
    # Check 2: Has memberships?
    memberships = user.memberships.all()
    if not memberships.exists():
        messages.info(request, 'Create your first workspace to get started')
        return redirect('orgs_company_create')
    
    # Check 3: Workspace selected?
    if not user.profile.workspace:
        return redirect('user_workspaces')  # Show workspace selector
    
    # Check 4: Subscription active? (middleware handles this)
    # If subscription expired, middleware redirects to billing
    
    # Success: Go to workspace dashboard
    return redirect('company_dashboard')
```

**Possible Outcomes:**
1. → `/onboarding/start/` (incomplete onboarding)
2. → `/workspace/create/` (no memberships)
3. → `/dashboard/` (workspace selector)
4. → `/billing/renew/` (expired subscription)
5. → `/workspace/dashboard/` (success)

---

## Flow 3: Workspace Selection

### Scenario: User Has Multiple Workspaces
**URL:** `/dashboard/`  
**View:** `pages.views.user_workspaces`  
**Template:** `templates/pages/user_workspaces.html`

**UI Features:**
- **Card-based workspace grid:**
  - Company logo/icon
  - Workspace name
  - Member count badge
  - User's role badge (Owner/Admin/Member)
  - "View Details" button
  - "Switch" button if not active
  - "Active" badge on current workspace

- **Sidebar:**
  - Pending invitations count
  - Quick stats (workspaces, invitations)
  - Profile link

**User Actions:**
1. View all workspaces
2. Click "Switch" on desired workspace
3. Or click "View Details" to inspect before switching

**Backend Process:**
```python
def workspace_select(request, workspace_id):
    # Validate membership
    try:
        membership = Membership.objects.get(
            user=request.user,
            company_id=workspace_id
        )
    except Membership.DoesNotExist:
        raise Http404("Not a member of this workspace")
    
    # Switch workspace
    request.user.profile.workspace = membership.company
    request.user.profile.save()
    
    # Audit log
    AuditLog.log('WORKSPACE_SWITCH', 
                user=request.user, 
                company=membership.company)
    
    messages.success(request, f'Switched to {membership.company.name}')
    return redirect('company_dashboard')
```

**Next:** Redirect to workspace dashboard

---

## Flow 4: Workspace Dashboard (Daily Use)

### Entry Point
**URL:** `/workspace/dashboard/`  
**View:** `company_dashboard`  
**Template:** `templates/pages/company_dashboard.html` (or tenant.html)  
**Middleware Protection:**
- `@login_required`
- `@workspace_required`
- `SubscriptionValidationMiddleware`

**UI Features:**

#### Top Navigation Bar
```
┌────────────────────────────────────────────────────────────────┐
│ [Logo] Rokkad  📦 [Workspace: ABC Corp ▼]    [👤 User Menu ▼] │
└────────────────────────────────────────────────────────────────┘
```

- **Workspace Switcher Dropdown:**
  - Current workspace with badge
  - List of all user workspaces
  - "Switch Workspace" links
  - "+ Create New Workspace"

- **User Menu Dropdown:**
  - Profile
  - Settings
  - Billing
  - Logout

#### Sidebar Navigation
(Rendered by `{% render_main_navigation %}`)

**Core Section:**
- 🏠 Dashboard
- 🏢 Workspace
  - Overview
  - Team (if `team_view` permission)
  - Settings (if `workspace_edit` permission)

**Data Section:**
- 💰 Loans (Girvi) (if `data_view`)
- 📈 Sales (if `data_view`)
- 🛒 Purchase (if `data_view`)
- 🧮 Accounting (DEA) (if `data_view`)
- 👥 Contacts (if `data_view`)

**Admin Section:**
- ⚙️ Settings (if `workspace_settings`)
- 💳 Billing (if `billing_view`)
- 📊 Reports (if `reports_view`)

**Permission-Based Rendering:**
```django
<!-- Navigation automatically filters based on user_permissions -->
{% render_main_navigation user workspace=request.tenant permissions=user_permissions %}
```

#### Main Dashboard Content

**Widgets (Permission-Aware):**

1. **Quick Stats Row:**
   - Total team members
   - Active subscriptions
   - Recent activity count
   - Your role badge

2. **Recent Activity Feed:**
   - Last 10 actions (filtered by permissions)
   - User avatars with role badges
   - Timestamps with relative dates
   - Action icons (created, edited, deleted)

3. **Quick Actions Card:**
   ```
   {% has_permission user_permissions 'data_create' as can_create %}
   {% if can_create %}
   - "+ New Loan" (Girvi)
   - "+ New Invoice" (Sales)
   - "+ New Entry" (DEA)
   {% endif %}
   ```

4. **Team Overview Card:**
   ```
   {% has_permission user_permissions 'team_view' as can_view_team %}
   {% if can_view_team %}
   - Team member list with role badges
   - "Invite Team Member" button (if team_invite permission)
   {% endif %}
   ```

5. **Subscription Status Card:**
   ```
   {% include "components/subscription_status.html" %}
   - Plan name badge
   - Days until renewal
   - Upgrade button (if not Enterprise)
   ```

---

## Flow 5: Workspace Management

### 5A: View All Workspaces
**URL:** `/workspaces/`  
**View:** `orgs_company_list`  
**Template:** `templates/company/company_list.html` (redesigned)

**UI Features:**
- **Page Header:**
  - Title: "Workspaces"
  - Description: "Manage your company workspaces"
  - "+ Create New Workspace" button (if `workspace_create` permission)

- **Workspace Cards Grid:**
  - 3-column responsive grid
  - Each card shows:
    - Company icon/logo
    - Workspace name
    - Created date
    - Member count badge
    - Your role badge
    - "View Details" button
    - Delete button (if `workspace_delete` permission)

- **Empty State:**
  ```django
  {% if not companies %}
    {% include "components/empty_state.html" with 
        title="No Workspaces Yet" 
        message="Create your first workspace to get started" 
        icon="🏢" 
        can_create=can_create %}
  {% endif %}
  ```

- **Create Modal:**
  - Bootstrap modal triggered by button
  - Company creation form
  - Info alert: "You'll be Owner"

**User Actions:**
1. View all workspaces
2. Click "+ Create New Workspace" → Modal opens
3. Fill form → Submit → Workspace created
4. Click card → View details

---

### 5B: Workspace Detail & Team Management
**URL:** `/workspace/<id>/`  
**View:** `orgs_company_detail`  
**Template:** `templates/company/company_detail.html` (redesigned)

**UI Features:**

#### Workspace Header Card
```
┌────────────────────────────────────────────────────────────┐
│  [Icon] ABC Corporation                    [Edit Workspace]│
│  📅 Created Mar 15, 2026  👤 Owner: John Doe              │
│                                                            │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐      │
│  │ Team Members │ │ Invitations  │ │ Your Role    │      │
│  │     12       │ │      3       │ │   [Owner]    │      │
│  └──────────────┘ └──────────────┘ └──────────────┘      │
└────────────────────────────────────────────────────────────┘
```

#### Tab Navigation
- **Tab 1: Team Members**
- **Tab 2: Invitations** (with pending count badge)

---

#### Tab 1: Team Members

**UI Elements:**
- **Action Bar:**
  ```django
  {% has_permission user_permissions 'team_invite' as can_invite %}
  {% if can_invite %}
  <button hx-get="{% url 'invite_to_company' company.id %}">
    + Invite Team Member
  </button>
  {% endif %}
  ```

- **Members Table:**
  | Member | Role | Date Joined | Actions |
  |--------|------|-------------|---------|
  | [Avatar] John Doe<br>john@example.com | [Owner Badge] [Edit Icon] | Mar 15, 2026 | - |
  | [Avatar] Jane Smith<br>jane@example.com | [Admin Badge] [Edit Icon] | Mar 16, 2026 | [Remove Button] |

- **Role Badges:** Color-coded (Owner: red, Admin: blue, Member: grey)

- **Edit Role (HTMX):**
  - Clicking edit icon replaces badge with dropdown
  - Select new role → Auto-saves via HTMX
  - Permission check: `team_change_role`

- **Remove Member:**
  - Button visible only if `team_remove` permission
  - Cannot remove yourself
  - Confirmation dialog: "Remove [User] from workspace?"

**Permission Logic:**
```django
{% has_permission user_permissions 'team_remove' as can_remove %}
{% if can_remove and member.user != user %}
  <a href="{% url 'orgs_membership_revoke' company.id member.id %}"
     onclick="return confirm('Remove {{ member.user }}?')">
    Remove
  </a>
{% elif member.user == user %}
  <span class="text-muted">You</span>
{% endif %}
```

---

#### Tab 2: Invitations

**UI Elements:**
- **Invitations Table:**
  | Email | Role | Invited By | Date | Status | Actions |
  |-------|------|------------|------|--------|---------|
  | new@example.com | [Member Badge] | John Doe | Mar 18, 2026 | [Pending Badge] | [Cancel Button] |
  | old@example.com | [Admin Badge] | John Doe | Mar 10, 2026 | [Accepted Badge] | - |

- **Status Badges:**
  - **Pending:** Yellow warning badge
  - **Accepted:** Green success badge
  - **Declined:** Red danger badge

- **Cancel Invitation:**
  - Button visible only if `team_invite` permission
  - Only for pending invitations
  - HTMX: Removes row on success
  - Confirmation: "Cancel invitation to [email]?"

**Empty State:**
```django
{% if not company.invitations.all %}
  {% include "components/empty_state.html" with 
      title="No Pending Invitations" 
      message="Invite team members to see pending invitations here" 
      icon="📧" %}
{% endif %}
```

---

### 5C: Create/Edit Workspace
**URL:** `/workspace/create/` or `/workspace/<id>/edit/`  
**View:** `orgs_company_create` or `orgs_company_update`  
**Template:** `templates/company/company_form.html` (redesigned)

**UI Features:**

#### Page Elements
- **Breadcrumbs:**
  - Workspaces → Create (or Company Name → Edit)

- **Form Card:**
  - Header with icon and title
  - Info alert (create): "You'll be Owner"
  - Form fields (crispy forms):
    - Company name *
    - Industry
    - Website
    - Logo upload
    - Timezone
  - Error alerts (if validation fails)
  
- **Action Buttons:**
  - [Cancel] → Back to workspace list
  - [Create Workspace] or [Save Changes] → Submit

- **What Happens Next Box (Create only):**
  ```
  ✓ You'll be assigned as Owner
  ✓ Invite team members with roles
  ✓ Set up business preferences
  ✓ Start managing data
  ```

**Backend Flow (Create):**
```python
def orgs_company_create(request):
    if request.method == 'POST':
        form = CompanyForm(request.POST, request.FILES)
        if form.is_valid():
            # Create company
            company = form.save(commit=False)
            company.creator = request.user
            company.owner = request.user
            company.schema_name = generate_schema_name(company.name)
            company.save()
            
            # Create tenant schema (django-tenants)
            company.create_schema()
            
            # Create Owner membership
            role = Role.objects.get(name='Owner')
            Membership.objects.create(
                user=request.user,
                company=company,
                role=role
            )
            
            # Set as active workspace
            request.user.profile.workspace = company
            request.user.profile.save()
            
            # Audit log
            AuditLog.log('COMPANY_CREATE', 
                        user=request.user, 
                        company=company)
            
            messages.success(request, f'Workspace "{company.name}" created!')
            return redirect('orgs_company_detail', company.id)
```

**Permission Check (Edit):**
```python
@roles_required(['Owner', 'Admin'])
def orgs_company_update(request, company_id):
    # Only Owner/Admin can edit
```

---

## Flow 6: Team Invitation Process

### 6A: Send Invitation
**URL:** `/workspace/<id>/invite/`  
**View:** `invite_to_company`  
**Template:** `templates/company/invitation_form.html` (redesigned)  
**Method:** HTMX-loaded modal/inline form

**UI Features:**
- **Form Card:**
  - Header: "Send Team Invitation"
  - Email field with validation
  - Role dropdown (Admin or Member)
  - Info alert: "Invitations expire after 7 days"

- **Role Descriptions Box:**
  ```
  [Owner Badge] Full control including billing
  [Admin Badge] Manage team, settings, data
  [Member Badge] View and edit assigned data
  ```

- **Action Buttons:**
  - [Cancel] → Back to team tab
  - [Send Invitation] → Submit (HTMX)

**Backend Process:**
```python
def invite_to_company(request, company_id):
    if request.method == 'POST':
        form = InvitationForm(request.POST)
        if form.is_valid():
            invitation = CompanyInvitation.objects.create(
                company=company,
                email=form.cleaned_data['email'],
                role=form.cleaned_data['role'],
                inviter=request.user,
                key=generate_invitation_key(),
                sent=timezone.now()
            )
            
            # Send email
            send_mail(
                subject=f'Invitation to join {company.name}',
                message=f'Click link: /invitation/accept/{invitation.key}',
                from_email='noreply@rokkad.com',
                recipient_list=[invitation.email]
            )
            
            # Audit log
            AuditLog.log('INVITATION_SENT',
                        user=request.user,
                        company=company,
                        extra_data={'email': invitation.email})
            
            messages.success(request, f'Invitation sent to {invitation.email}')
            
            # HTMX: Return updated team tab
            return render(request, 'company/company_detail.html#members-pane')
```

---

### 6B: Accept Invitation
**URL:** `/invitation/accept/<key>/`  
**View:** `accept_invitation`  
**Template:** `templates/pages/workspace_invitations.html`

**UI Flow:**

1. **User clicks email link** → Redirected to accept page

2. **Invitation Validation:**
   - Check if key exists
   - Check if not expired (7 days)
   - Check if not already accepted
   - Check if user already member

3. **Accept Page UI:**
   ```
   ┌─────────────────────────────────────────────┐
   │  You've been invited to join                │
   │                                             │
   │  [Company Icon] ABC Corporation             │
   │                                             │
   │  Invited by: John Doe                       │
   │  Role: [Admin Badge]                        │
   │  Expires: Mar 25, 2026                      │
   │                                             │
   │  [Accept Invitation] [Decline]              │
   └─────────────────────────────────────────────┘
   ```

4. **User clicks "Accept":**

**Backend Process:**
```python
def accept_invitation(request, key):
    try:
        invitation = CompanyInvitation.objects.get(key=key)
    except CompanyInvitation.DoesNotExist:
        raise Http404("Invalid invitation")
    
    # Check expiration
    if invitation.is_expired():
        messages.error(request, 'This invitation has expired')
        return redirect('dashboard')
    
    # Create membership
    Membership.objects.create(
        user=request.user,
        company=invitation.company,
        role=invitation.role
    )
    
    # Mark accepted
    invitation.accepted = True
    invitation.save()
    
    # Set as active workspace (optional)
    request.user.profile.workspace = invitation.company
    request.user.profile.save()
    
    # Audit log
    AuditLog.log('INVITATION_ACCEPTED',
                user=request.user,
                company=invitation.company)
    
    messages.success(request, f'Welcome to {invitation.company.name}!')
    return redirect('company_dashboard')
```

---

### 6C: View All Invitations (User Perspective)
**URL:** `/invitations/`  
**View:** `workspace_invitations`  
**Template:** `templates/pages/workspace_invitations.html`

**UI Features:**
- **Pending Invitations List:**
  - Card for each invitation
  - Company name and logo
  - Inviter info
  - Role badge
  - Expiration date
  - [Accept] [Decline] buttons

- **Empty State:**
  - "No pending invitations"
  - "Check your email for invitation links"

---

## Flow 7: Data Operations (Example: Girvi/Loans)

### 7A: View Data List
**URL:** `/loans/`  
**View:** `tenant_apps.girvi.views.loan_list`  
**Decorators:** `@login_required`, `@workspace_required`  
**Permission Check:** `data_view`

**UI Features:**
- **Page Header:**
  - Breadcrumbs: Dashboard → Loans
  - Title: "Loans (गिरवी)"
  - "+ New Loan" button (if `data_create` permission)

- **Data Table:**
  - Columns: ID, Customer, Amount, Date, Status, Actions
  - Row actions based on permissions:
    - View (always)
    - Edit (if `data_edit`)
    - Delete (if `data_delete`)
  - Pagination

- **Empty State:**
  ```django
  {% if not loans %}
    {% include "components/empty_state.html" with 
        title="No Loans Yet" 
        message="Create your first loan to get started" 
        icon="💰" 
        create_url=url 
        can_create=can_create %}
  {% endif %}
  ```

**Permission-Based Actions:**
```django
{% include "components/action_buttons.html" with object=loan %}
<!-- Automatically shows/hides Edit, Export, Delete based on user_permissions -->
```

---

### 7B: Create/Edit Data
**URL:** `/loans/create/` or `/loans/<id>/edit/`  
**Decorators:** 
- Create: `@permission_required('data_create')`
- Edit: `@permission_required('data_edit')`

**UI Features:**
- Form with all fields
- Permission-gated features:
  - Advanced fields visible only for Owner/Admin
  - Approval workflow for Members

**Backend:**
```python
@permission_required('data_create')
def loan_create(request):
    if request.method == 'POST':
        # Create loan
        loan = form.save(commit=False)
        loan.created_by = request.user
        loan.workspace = request.user.profile.workspace
        loan.save()
        
        # Audit log
        AuditLog.log('LOAN_CREATE', 
                    user=request.user, 
                    extra_data={'loan_id': loan.id})
```

---

## Flow 8: Subscription Management

### 8A: View Subscription Status
**URL:** `/billing/dashboard/`  
**View:** `subscriptions:dashboard`  
**Permission:** `billing_view`

**UI Features:**
- **Current Plan Card:**
  - Plan name badge (Basic, Pro, Enterprise)
  - Features list with checkmarks
  - Next billing date
  - Amount
  - [Upgrade Plan] button (if not Enterprise)

- **Billing History:**
  - Invoice table
  - Download PDF buttons
  - Payment status badges

- **Payment Method:**
  - Card details (masked)
  - [Update Payment Method]

---

### 8B: Subscription Expired Flow

**Middleware:** `SubscriptionValidationMiddleware`

**Trigger:**
- User tries to access tenant URLs
- Subscription status is `past_due` or `canceled`

**Redirect:**
```python
# django_project/middleware.py
if not subscription or not subscription.is_active:
    messages.warning(request, 
        'Your subscription has expired. Please renew to continue.')
    return redirect('subscriptions:plan-list')
```

**Renewal UI:**
- **Billing Alert Banner:**
  ```
  ⚠️ Your subscription expired on Mar 15, 2026.
     Renew now to regain access to your workspace.
     [Renew Subscription]
  ```

- **Plan Selection:**
  - Choose plan (Basic, Pro, Enterprise)
  - Payment form (Razorpay integration)
  - Confirm & pay

**After Payment:**
```python
# Subscription reactivated
subscription.status = 'active'
subscription.save()

# User redirected to dashboard
messages.success(request, 'Subscription renewed! Welcome back.')
return redirect('company_dashboard')
```

---

## Flow 9: Subscription Validation (Middleware Protection)

### Automatic Checks on Every Request

**File:** `django_project/middleware.py - SubscriptionValidationMiddleware`

**Process:**
```python
def process_request(self, request):
    # Skip for exempt URLs (login, signup, billing, etc.)
    if current_url in EXEMPT_URLS:
        return None
    
    # Skip if no workspace
    if not request.user.profile.workspace:
        return None
    
    workspace = request.user.profile.workspace
    
    # Check subscription
    subscription = Subscription.objects.filter(
        company=workspace,
        is_active=True
    ).first()
    
    if not subscription:
        messages.error(request, 
            'No active subscription. Please subscribe to continue.')
        return redirect('subscriptions:plan-list')
    
    # Check expiration
    if subscription.is_expired():
        messages.warning(request, 
            'Subscription expired. Please renew.')
        return redirect('subscriptions:dashboard')
    
    # Check upcoming renewal (7 days warning)
    if subscription.days_until_renewal() <= 7:
        messages.info(request, 
            f'Subscription renews in {subscription.days_until_renewal()} days')
    
    # Allow request to continue
    return None
```

**Exempt URLs (No Subscription Check):**
- Authentication: login, logout, signup
- Public: home, about, help
- Onboarding: all onboarding steps
- Workspace: selection, creation, invitations
- Subscription: plan-list, checkout, payment, dashboard
- Admin: Django admin

---

## Flow 10: Security & Audit

### Workspace Access Validation

**Middleware:** `apps.orgs.middleware_v2.SecureWorkspaceMiddleware`

**Process:**
```python
def process_request(self, request):
    if request.user.is_authenticated and request.user.profile.workspace:
        workspace = request.user.profile.workspace
        
        # Critical Check: Validate membership
        try:
            membership = Membership.objects.get(
                user=request.user,
                company=workspace
            )
        except Membership.DoesNotExist:
            # SECURITY: Unauthorized access attempt
            AuditLog.log('UNAUTHORIZED_ACCESS_ATTEMPT',
                        user=request.user,
                        extra_data={
                            'workspace': workspace.name,
                            'ip': get_client_ip(request),
                            'user_agent': request.META.get('HTTP_USER_AGENT')
                        })
            
            # Clear invalid workspace
            request.user.profile.workspace = None
            request.user.profile.save()
            
            messages.error(request, 
                'Access denied: You are not a member of this workspace')
            return redirect('user_workspaces')
        
        # Check: Company still exists
        if workspace.is_deleted:
            messages.error(request, 'This workspace has been deleted')
            return redirect('orgs_company_list')
        
        # Check: Subscription active (if required)
        # ... subscription validation ...
        
        # Access granted
        connection.set_tenant(workspace)
        request.tenant = workspace
```

---

## Permission Matrix Reference

### Permission-to-Action Mapping

| Action | Required Permission | Roles with Access |
|--------|---------------------|-------------------|
| View workspace | `workspace_view` | Owner, Admin, Member |
| Edit workspace | `workspace_edit` | Owner, Admin |
| Delete workspace | `workspace_delete` | Owner |
| View team | `team_view` | Owner, Admin, Member |
| Invite team | `team_invite` | Owner, Admin |
| Remove team | `team_remove` | Owner |
| Change role | `team_change_role` | Owner |
| View billing | `billing_view` | Owner, Admin |
| Edit billing | `billing_edit` | Owner |
| View data | `data_view` | Owner, Admin, Member |
| Create data | `data_create` | Owner, Admin, Member |
| Edit data | `data_edit` | Owner, Admin, Member |
| Delete data | `data_delete` | Owner, Admin |
| Export data | `data_export` | Owner, Admin |

### Template Usage

**Check Permission:**
```django
{% has_permission user_permissions 'data_edit' as can_edit %}
{% if can_edit %}
  <button>Edit</button>
{% endif %}
```

**Check Role:**
```django
{% has_role user_role 'admin' as is_admin %}
{% if is_admin %}
  <!-- Admin-only content -->
{% endif %}
```

**Render Role Badge:**
```django
{% role_badge user_role %}
{% role_badge user_role size='small' %}
```

---

## Error Handling & Edge Cases

### Scenario 1: User Loses Membership
**Trigger:** Owner removes user from workspace

**Process:**
1. Membership deleted from database
2. User's next request hits `SecureWorkspaceMiddleware`
3. Middleware detects no membership
4. Audit log: `UNAUTHORIZED_ACCESS_ATTEMPT`
5. Workspace cleared from profile
6. Redirect to workspace selector
7. Message: "You are no longer a member of [Workspace]"

**User Recovery:**
- Select different workspace
- Accept new invitation
- Create new workspace

---

### Scenario 2: Subscription Expires During Session
**Trigger:** Subscription end_date passes while user is working

**Process:**
1. User submits action (e.g., create loan)
2. Middleware checks subscription
3. Finds expired status
4. Blocks request
5. Redirect to billing dashboard
6. Banner: "Subscription expired. Please renew."

**Prevention:**
- Warning 7 days before expiration
- Email notifications at 7d, 3d, 1d before expiration
- Grace period (optional, configured per plan)

---

### Scenario 3: Multiple Browser Sessions
**Trigger:** User logged in on multiple devices/browsers

**Behavior:**
- All sessions validated independently
- Workspace changes sync via database (not session)
- Switching workspace in Browser A affects Browser B on next request

**Audit:**
- Each login tracked separately
- IP and user agent logged
- Session IDs tracked

---

### Scenario 4: Invitation Expired
**Trigger:** User clicks invitation link after 7 days

**Process:**
```python
def accept_invitation(request, key):
    invitation = CompanyInvitation.objects.get(key=key)
    
    if invitation.is_expired():
        invitation.delete()  # Clean up
        messages.error(request, 
            'This invitation has expired. Please request a new one.')
        return redirect('dashboard')
```

**User Action:**
- Contact workspace owner
- Request new invitation

---

## Summary: Complete User Journey Map

```
┌─────────────────────────────────────────────────────────────────────┐
│                          USER LIFECYCLE                              │
└─────────────────────────────────────────────────────────────────────┘

1.  SIGNUP → Email Verification → Profile Setup
2.  ONBOARDING → Profile → Workspace → Team → Tour → Complete
3.  LOGIN → Smart Landing → Workspace Selection → Dashboard
4.  DAILY USE → Navigation (permission-filtered) → Data Operations
5.  TEAM MGMT → Invite → Accept → Manage Roles → Remove
6.  WORKSPACE MGMT → Create → Switch → Edit → Delete (Owner only)
7.  SUBSCRIPTION → Active Check → Warning → Renewal → Reactivation
8.  SECURITY → Membership Validation → Audit Logging → Access Control
9.  LOGOUT → Session End → Audit Log → Redirect to Login

Every step:
✓ Permission-validated
✓ Audit-logged
✓ Subscription-protected (where applicable)
✓ Membership-validated
✓ Role-aware UI
```

---

## Implementation Checklist

### ✅ Completed Components
- [x] User registration & authentication
- [x] 4-step onboarding wizard
- [x] Smart landing/routing logic
- [x] Workspace selection interface
- [x] Permission-based navigation
- [x] Role badge components
- [x] Empty state templates
- [x] Action button components
- [x] Breadcrumb navigation
- [x] Subscription validation middleware
- [x] Secure workspace middleware
- [x] Audit logging system
- [x] Team invitation flow
- [x] Workspace management UI
- [x] Context processors (permissions, roles)
- [x] Template tags (has_permission, has_role, role_badge)

### 🎨 UI/UX Features
- [x] Unified base template
- [x] Permission-aware menus
- [x] Role-based visibility
- [x] Empty state handling
- [x] Loading states (HTMX)
- [x] Toast notifications
- [x] Modal dialogs
- [x] Card-based layouts
- [x] Responsive grid system
- [x] Bootstrap Icons integration
- [x] Hover effects & transitions

### 🔒 Security Features
- [x] Membership validation
- [x] Subscription enforcement
- [x] Permission decorators
- [x] Audit logging (30+ actions)
- [x] IP & user agent tracking
- [x] Unauthorized access detection
- [x] Session management
- [x] CSRF protection
- [x] XSS prevention (Django templates)

---

## Next Steps for Further Enhancement

### Recommended Additions
1. **Feature-tier decorators** (as per status report)
2. **Object-level permissions** with Guardian
3. **Rate limiting** on sensitive operations
4. **Two-factor authentication** (django-allauth-2fa)
5. **Email notifications** for team events
6. **Real-time notifications** (Django Channels + WebSockets)
7. **Activity feed** with filtering
8. **Advanced audit dashboard** with charts
9. **Workspace templates** for quick setup
10. **Data import/export wizard**

---

## Conclusion

This complete user flow guide documents every interaction path in the Rokkad multi-tenant SaaS application. The system is built on:

- **Permission-based access control** (71 granular permissions)
- **Role-aware UI components** (Owner, Admin, Member)
- **Subscription-protected workspaces**
- **Comprehensive audit logging**
- **Secure multi-tenant architecture**

Every user action is:
1. **Authenticated** (Django-allauth)
2. **Authorized** (Permission system)
3. **Validated** (Middleware layers)
4. **Audited** (AuditLog entries)
5. **Rendered** (Permission-filtered UI)

The flow ensures **data isolation**, **subscription compliance**, and **clear user journeys** from signup to daily operations.

---

**Document Version:** 1.0  
**Last Updated:** February 28, 2026  
**Author:** GitHub Copilot (Claude Sonnet 4.5)
