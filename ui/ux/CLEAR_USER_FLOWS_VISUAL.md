# Clear User Flows - Visual Guide

**Companion to:** ARCHITECTURE_ASSESSMENT_AND_RECOMMENDATION.md  
**Purpose:** Provide clear visual representation of all user flows

---

## Flow 1: New User Registration → First Workspace

### Current State (Confusing)
```
User → Signup
    ↓
Email Verification
    ↓
Login
    ↓
pages.Dashboard() ← Redirects to workspace_home
    ↓
orgs.workspace_home() ← Shows workspace list (but user has none)
    ↓
User confused: "Where do I create workspace?"
    ↓
Finds "Create Company" button
    ↓
orgs.company_create()
    ↓
Company created
    ↓
Back to workspace_home
    ↓
Clicks workspace
    ↓
orgs.workspace_select() ← Sets active workspace
    ↓
pages.company_dashboard() ← Finally at dashboard
```

**Total Redirects:** 6-7 redirects, 3 apps involved

---

### After Refactor (Clear)
```
User → Signup
    ↓
Email Verification
    ↓
Login
    ↓
@onboarding_required decorator ← Checks OnboardingProgress.is_complete
    ↓
apps.onboarding.onboarding_start() ← Entry point
    ↓
┌─────────────────────────────────────────────────────┐
│ STEP 1: Profile Setup                               │
│ URL: /onboarding/profile/                           │
│ View: onboarding_profile()                          │
│ Template: onboarding/step_profile.html              │
│                                                     │
│ [Name] [Phone] [Profile Picture]                   │
│                                                     │
│ Progress: ████░░░░ 25%                              │
│                         [Skip] [Continue →]         │
└─────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────┐
│ STEP 2: Create Your Workspace                      │
│ URL: /onboarding/company/                           │
│ View: onboarding_company()                          │
│ Template: onboarding/step_company.html              │
│                                                     │
│ [Workspace Name] [Industry] [Timezone]             │
│                                                     │
│ Info: You'll be assigned as Owner with full access │
│ Progress: ████████░░ 50%                            │
│                         [Back] [Create Workspace →] │
└─────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────┐
│ STEP 3: Invite Team Members (Optional)             │
│ URL: /onboarding/team/                              │
│ View: onboarding_team()                             │
│ Template: onboarding/step_team.html                 │
│                                                     │
│ [Email 1] [Role ▼]  [+ Add Another]                │
│                                                     │
│ Progress: ████████████ 75%                          │
│                [Skip for now] [Send Invites →]     │
└─────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────┐
│ STEP 4: Choose Your Plan                           │
│ URL: /onboarding/tour/ or /subscriptions/plans/     │
│ View: onboarding_tour() → redirects to plan_list    │
│ Template: subscriptions/plan_list.html              │
│                                                     │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐                │
│ │ Basic   │ │ Pro     │ │Enterprise│                │
│ │ $29/mo  │ │ $99/mo  │ │ Custom  │                │
│ │ [Select]│ │ [Select]│ │ [Contact]│                │
│ └─────────┘ └─────────┘ └─────────┘                │
│                                                     │
│ Progress: ████████████████ 100%                     │
│                    [Start Free Trial] [Select Plan →]│
└─────────────────────────────────────────────────────┘
    ↓
Onboarding Complete!
OnboardingProgress.is_complete = True
    ↓
pages.Dashboard() ← Smart router
    ↓
Has workspace? Yes!
    ↓
apps.orgs.workspace_dashboard(workspace_id)
    ↓
┌─────────────────────────────────────────────────────┐
│ ┌─── Rokkad ──────────────────────────────────────┐ │
│ │ [Logo] 📦 My Workspace ▼  🔔│👤 User ▼        │ │
│ └─────────────────────────────────────────────────┘ │
│                                                     │
│ ┌─Sidebar────┐  ┌─Main Content────────────────────┐│
│ │ Dashboard   │  │ Welcome to My Workspace!       ││
│ │ Team        │  │                                ││
│ │ Loans       │  │ ┌──────┐ ┌──────┐ ┌──────┐   ││
│ │ Settings    │  │ │ Team │ │Active│ │ Data │   ││
│ │ Billing     │  │ │  5   │ │ Plan │ │1,234 │   ││
│ └─────────────┘  │ └──────┘ └──────┘ └──────┘   ││
│                  │                                ││
│                  │ Recent Activity:               ││
│                  │ • John added new loan          ││
│                  │ • Sarah updated contact        ││
│                  └────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

**Total Redirects:** 1 redirect, all in onboarding app

---

## Flow 2: Existing User Login → Dashboard

### Current State (Confusing)
```
User → Login
    ↓
django-allauth → account_login_redirect()
    ↓
pages.Dashboard()
    ↓
return redirect('workspace_home')
    ↓
orgs.workspace_home()
    ↓
if user.profile.workspace exists:
    return redirect('company_dashboard')
    ↓
pages.company_dashboard()
    ↓
Finally at dashboard!
```

**Total Redirects:** 4 redirects

---

### After Refactor (Clear)
```
User → Login
    ↓
django-allauth → account_login_redirect()
    ↓
pages.Dashboard() ← Smart router
    ↓
Decision tree:
├─ Has workspace? → workspace_dashboard(workspace_id) [1 redirect]
├─ Has memberships? → workspace_list() [1 redirect]
└─ No memberships? → workspace_create() [1 redirect]
    ↓
Done! (Maximum 1 redirect)
```

---

## Flow 3: Workspace Selection (Multiple Workspaces)

### URL: `/workspace/` (was `/orgs/company/list/`)
### View: `workspace_list()` (was `workspace_home()`)
### Template: `workspace/list.html`

```
┌─────────────────────────────────────────────────────────┐
│ Your Workspaces                         [+ New Workspace]│
├─────────────────────────────────────────────────────────┤
│                                                         │
│ ┌──────────────────────────────────────────┐            │
│ │ 🏢 ABC Corporation                       │            │
│ │ Role: Owner │ Team: 12 │ Last used: 2h  │            │
│ │ [Select →] [View Details]               │            │
│ └──────────────────────────────────────────┘            │
│                                                         │
│ ┌──────────────────────────────────────────┐            │
│ │ 🏢 XYZ Ltd                               │            │
│ │ Role: Admin │ Team: 5 │ Last used: 3d   │            │
│ │ [Select →] [View Details]               │            │
│ └──────────────────────────────────────────┘            │
│                                                         │
│ ┌─ Pending Invitations (2) ────────────────┐            │
│ │ • Acme Inc invited you as Member         │            │
│ │   [Accept] [Decline]                     │            │
│ │ • Tech Corp invited you as Admin         │            │
│ │   [Accept] [Decline]                     │            │
│ └──────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────┘
```

**User Actions:**
1. Click "Select" → `workspace_select(workspace_id)` → Sets active workspace → `workspace_dashboard(workspace_id)`
2. Click "View Details" → `workspace_detail(workspace_id)` → Shows team, settings, etc.
3. Click "+ New Workspace" → `workspace_create()`
4. Click "Accept" invitation → `team_accept_invitation(key)` → Creates membership → Sets active workspace → `workspace_dashboard(workspace_id)`

---

## Flow 4: Team Management

### URL: `/workspace/<id>/team/`
### View: `team_detail()` (new - consolidates membership views)
### Template: `workspace/team/team.html`

```
┌─────────────────────────────────────────────────────────┐
│ Team Management - ABC Corporation                      │
│                                          [+ Invite Member]│
├─────────────────────────────────────────────────────────┤
│                                                         │
│ ┌─ Team Members ──────────────────────────────────────┐ │
│ │                                                      │ │
│ │ ┌──────────────────────────────────────────────────┐│ │
│ │ │ 👤 John Doe (You)                                ││ │
│ │ │ john@example.com                                 ││ │
│ │ │ [Owner ▼] 🔒                                     ││ │
│ │ │ Joined: Jan 15, 2026                             ││ │
│ │ └──────────────────────────────────────────────────┘│ │
│ │                                                      │ │
│ │ ┌──────────────────────────────────────────────────┐│ │
│ │ │ 👤 Jane Smith                         [✏️ ] [🗑️]  ││ │
│ │ │ jane@example.com                                 ││ │
│ │ │ [Admin ▼]  ← Click to change role                ││ │
│ │ │ Joined: Feb 10, 2026                             ││ │
│ │ └──────────────────────────────────────────────────┘│ │
│ │                                                      │ │
│ │ ┌──────────────────────────────────────────────────┐│ │
│ │ │ 👤 Bob Wilson                         [✏️ ] [🗑️]  ││ │
│ │ │ bob@example.com                                  ││ │
│ │ │ [Member ▼]                                       ││ │
│ │ │ Joined: Feb 20, 2026                             ││ │
│ │ └──────────────────────────────────────────────────┘│ │
│ └──────────────────────────────────────────────────────┘ │
│                                                         │
│ ┌─ Pending Invitations ─────────────────────────────┐ │
│ │                                                    │ │
│ │ ┌────────────────────────────────────────────────┐│ │
│ │ │ 📧 alice@example.com                    [Cancel]││ │
│ │ │ Role: Admin | Invited by: You                  ││ │
│ │ │ Sent: Feb 25, 2026 | Expires in 5 days         ││ │
│ │ └────────────────────────────────────────────────┘│ │
│ └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Permission-Based Actions:**
- **View team** (`team_view`): Owner, Admin, Member - See who's in the workspace
- **Invite members** (`team_invite`): Owner, Admin - Show "+ Invite Member" button
- **Change roles** (`team_change_role`): Owner only - Show role dropdown (HTMX)
- **Remove members** (`team_remove`): Owner only - Show remove button

**Implementation:**
```django
<!-- workspace/team/team.html -->
{% load orgs_tags %}

{% has_permission 'team_invite' as can_invite %}
{% has_permission 'team_remove' as can_remove %}
{% has_permission 'team_change_role' as can_change_role %}

<!-- Invite button -->
{% if can_invite %}
    <a href="{% url 'team_invite' workspace.id %}" class="btn btn-primary">
        + Invite Member
    </a>
{% endif %}

<!-- Member actions -->
{% for member in members %}
    <div class="member-card">
        <h5>{{ member.user.get_full_name }}</h5>
        
        <!-- Role badge with edit (HTMX) -->
        {% if can_change_role and member.user != request.user %}
            <div hx-get="{% url 'team_change_role' workspace.id member.id %}"
                 hx-target="this">
                {% role_badge member.role.name %}
            </div>
        {% else %}
            {% role_badge member.role.name %}
        {% endif %}
        
        <!-- Remove button -->
        {% if can_remove and member.user != request.user %}
            <a href="{% url 'team_remove_member' workspace.id member.id %}"
               class="btn btn-sm btn-danger"
               onclick="return confirm('Remove {{ member.user.email }}?')">
                Remove
            </a>
        {% endif %}
    </div>
{% endfor %}
```

---

## Flow 5: Subscription Management

### URL: `/subscriptions/dashboard/`
### View: `SubscriptionDashboardView` (already implemented)
### Template: `subscriptions/dashboard.html`

```
┌─────────────────────────────────────────────────────────┐
│ Billing & Subscription                                 │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ ┌─ Current Plan ──────────────────────────────────────┐ │
│ │                                                      │ │
│ │ Pro Plan                            [Upgrade Plan]  │ │
│ │ $99.00 / month                                       │ │
│ │                                                      │ │
│ │ Status: Active ✓                                     │ │
│ │ Next billing: March 15, 2026                         │ │
│ │                                                      │ │
│ │ Features Included:                                   │ │
│ │ ✓ Advanced Reporting                                 │ │
│ │ ✓ API Access                                         │ │
│ │ ✓ Up to 20 team members                              │ │
│ │ ✓ Priority Support                                   │ │
│ └──────────────────────────────────────────────────────┘ │
│                                                         │
│ ┌─ Payment Method ─────────────────────────────────────┐ │
│ │ Visa •••• 4242                     [Update Method]  │ │
│ │ Expires: 12/2027                                     │ │
│ └──────────────────────────────────────────────────────┘ │
│                                                         │
│ ┌─ Billing History ────────────────────────────────────┐ │
│ │                                                      │ │
│ │ Feb 15, 2026  │ $99.00  │ Paid ✓   │ [📄 Invoice]  │ │
│ │ Jan 15, 2026  │ $99.00  │ Paid ✓   │ [📄 Invoice]  │ │
│ │ Dec 15, 2025  │ $99.00  │ Paid ✓   │ [📄 Invoice]  │ │
│ └──────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Permission-Based Access:**
- **View billing** (`billing_view`): Owner, Admin
- **Edit billing** (`billing_edit`): Owner only

**Middleware Protection:**
```python
# SubscriptionValidationMiddleware (already exists)
# Checks on every request to tenant URLs:

1. Is subscription attached to workspace? 
   NO → Redirect to /subscriptions/plans/
   
2. Is subscription active?
   NO → Redirect to /subscriptions/dashboard/ with warning
   
3. Is subscription expiring soon (< 7 days)?
   YES → Show warning banner
```

---

## Flow 6: Invitation Acceptance (External User)

### Entry: User receives email with invitation link
### URL: `/invitations/<key>/accept/`
### View: `team_accept_invitation()` (was `CustomAcceptInvite`)

```
Email:
┌─────────────────────────────────────────────────────────┐
│ You've been invited to join ABC Corporation at Rokkad  │
│                                                         │
│ John Doe has invited you to join their workspace       │
│ as an Admin.                                            │
│                                                         │
│ [Accept Invitation]  [Decline]                          │
│                                                         │
│ This invitation expires on March 7, 2026                │
└─────────────────────────────────────────────────────────┘

User clicks "Accept Invitation"
    ↓
Is user logged in?
├─ NO → Redirect to login with ?next=/invitations/abc123/accept/
│   ↓
│   User logs in or signs up
│   ↓
│   Redirect back to /invitations/abc123/accept/
│
└─ YES → Continue to acceptance page
    ↓
┌─────────────────────────────────────────────────────────┐
│ Accept Invitation                                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ You've been invited to:                                 │
│                                                         │
│ ┌──────────────────────────────────────────────────────┐│
│ │ 🏢 ABC Corporation                                    ││
│ │                                                       ││
│ │ Role: Admin                                           ││
│ │ Invited by: John Doe (john@example.com)               ││
│ │ Invitation sent: Feb 25, 2026                         ││
│ │                                                       ││
│ │ As an Admin, you will be able to:                    ││
│ │ ✓ View and manage workspace data                      ││
│ │ ✓ Invite other team members                           ││
│ │ ✓ View billing information                            ││
│ │ ✗ Delete workspace (Owner only)                       ││
│ └──────────────────────────────────────────────────────┘│
│                                                         │
│              [Accept & Join] [Decline]                  │
└─────────────────────────────────────────────────────────┘

User clicks "Accept & Join"
    ↓
Backend:
1. Verify invitation is valid (not expired, not accepted)
2. Check if user already a member (skip if yes)
3. Create Membership record
4. Mark invitation as accepted
5. Set workspace as active in user profile
6. Send notification email to inviter
7. Log audit entry
    ↓
Redirect to workspace_dashboard(workspace_id)
    ↓
┌─────────────────────────────────────────────────────────┐
│ ✅ Welcome to ABC Corporation!                          │
│                                                         │
│ You've successfully joined as Admin.                    │
└─────────────────────────────────────────────────────────┘
```

---

## Flow 7: Permission-Based Navigation

### Sidebar Rendering (Dynamic)

```python
# Every page render calls:
{% render_sidebar %}
    ↓
Template tag checks user's role permissions
    ↓
Filters navigation items by permission requirements
    ↓
Renders only authorized items
```

**Example for different roles:**

### Owner View
```
┌─ Navigation ────────┐
│ 🏠 Dashboard        │ ← workspace_view
│ 👥 Team             │ ← team_view
│ 💰 Loans            │ ← data_view
│ 📈 Sales            │ ← data_view
│ 🧮 Accounting       │ ← data_view
│ ⚙️  Settings        │ ← workspace_edit
│ 💳 Billing          │ ← billing_view
│ 📊 Reports          │ ← reports_view
└─────────────────────┘
```

### Admin View
```
┌─ Navigation ────────┐
│ 🏠 Dashboard        │ ← workspace_view
│ 👥 Team             │ ← team_view
│ 💰 Loans            │ ← data_view
│ 📈 Sales            │ ← data_view
│ 🧮 Accounting       │ ← data_view
│ ⚙️  Settings        │ ← workspace_edit
│ 💳 Billing          │ ← billing_view (read-only)
│ 📊 Reports          │ ← reports_view
└─────────────────────┘
```

### Member View
```
┌─ Navigation ────────┐
│ 🏠 Dashboard        │ ← workspace_view
│ 💰 Loans            │ ← data_view
│ 📈 Sales            │ ← data_view
│ 🧮 Accounting       │ ← data_view
└─────────────────────┘
```

**Implementation:**
```django
<!-- components/navigation/sidebar.html -->
{% load orgs_tags %}

<nav class="sidebar">
    {% for item in nav_items %}
        {% has_permission item.permission as has_perm %}
        {% if has_perm %}
            <a href="{% url item.url workspace.id %}" 
               class="nav-link {% if current_path == item.url %}active{% endif %}">
                <i class="bi bi-{{ item.icon }}"></i>
                {{ item.title }}
            </a>
        {% endif %}
    {% endfor %}
</nav>
```

---

## Flow 8: Feature-Gated Access

### Scenario: User tries to access "Advanced Reporting"

```
User clicks "Advanced Reports" link
    ↓
URL: /reports/advanced/
View: advanced_reports_view()
Decorators:
    @login_required
    @workspace_required
    @feature_required('advanced_reporting')  ← NEW
    @permission_required('reports_view')
    ↓
feature_required decorator checks:
    1. Get workspace subscription
    2. Check plan includes 'advanced_reporting'
    ↓
Is feature included?
├─ YES → Continue to view
│   ↓
│   permission_required decorator checks:
│       Get user's role
│       Check role has 'reports_view' permission
│       ↓
│   Has permission?
│   ├─ YES → Render advanced_reports.html
│   └─ NO → Show 403 error
│
└─ NO → Show upgrade prompt
    ↓
┌─────────────────────────────────────────────────────────┐
│ 🔒 Premium Feature                                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ Advanced Reporting is available on Pro and Enterprise  │
│ plans.                                                  │
│                                                         │
│ With Advanced Reporting, you can:                       │
│ • Custom report builder                                 │
│ • 50+ pre-built templates                               │
│ • Schedule automated reports                            │
│ • Export to Excel, PDF                                  │
│                                                         │
│ Your current plan: Basic                                │
│                                                         │
│        [Upgrade to Pro] [Learn More]                    │
└─────────────────────────────────────────────────────────┘
```

---

## Summary: All User Journeys

| Journey | Entry Point | Steps | End Point |
|---------|-------------|-------|-----------|
| **New User** | Signup | 1. Verify email<br>2. Onboarding (4 steps)<br>3. Choose plan | Workspace Dashboard |
| **Returning User** | Login | 1. Smart router<br>2. Select workspace (if needed) | Workspace Dashboard |
| **Switch Workspace** | Dashboard dropdown | 1. Click dropdown<br>2. Select workspace | Workspace Dashboard |
| **Create Workspace** | Workspace list | 1. Fill form<br>2. Submit | New Workspace Dashboard |
| **Invite Team** | Team page | 1. Enter emails<br>2. Choose roles<br>3. Send | Team page (updated) |
| **Accept Invitation** | Email link | 1. Login/Signup<br>2. Review invitation<br>3. Accept | Workspace Dashboard |
| **Manage Team** | Team page | 1. View members<br>2. Change roles (HTMX)<br>3. Remove members | Team page (updated) |
| **Manage Subscription** | Billing sidebar | 1. Select plan<br>2. Checkout<br>3. Payment | Subscription Dashboard |
| **Renew Expired Subscription** | Auto-redirect | 1. Choose plan<br>2. Payment | Workspace Dashboard |

---

## Key Improvements After Refactor

### Before:
- ❌ 6-7 redirects to reach dashboard
- ❌ Logic scattered across 3 apps
- ❌ Confusing URL patterns
- ❌ No visual permission indicators
- ❌ Hard to understand flow from code

### After:
- ✅ Maximum 1 redirect
- ✅ All workspace logic in `apps/orgs/`
- ✅ Consistent `/workspace/` URLs
- ✅ Permission-based UI components
- ✅ Clear, documented flows

---

**Next:** See ARCHITECTURE_ASSESSMENT_AND_RECOMMENDATION.md for implementation plan.

