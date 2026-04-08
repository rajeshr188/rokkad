# Current State vs Proposed State: Visual Comparison

## Architecture Overview

### Current Architecture (As-Is)

```
┌─────────────────────────────────────────────────────────────────┐
│                        PUBLIC SCHEMA                             │
│  (Shared across all users - accounts, companies, subscriptions)  │
│                                                                   │
│  CustomUser ─────────────────┬──────────────────────────────┐   │
│                              │                              │   │
│                         UserProfile                    Membership│
│                          (workspace)                   (role)    │
│                              │                              │   │
│                              └─────────> Company            │   │
│                                      (public schema)        │   │
│                                                              │   │
│  Problem: UserProfile.workspace manually set,              │   │
│  no validation that user should access it                  │   │
└─────────────────────────────────────────────────────────────────┘
                                 ↓
           WorkspaceMiddleware checks this field
            (NO validation of subscription)
                                 ↓
┌─────────────────────────────────────────────────────────────────┐
│            TENANT SCHEMA (company_123)                           │
│   (Company-specific data: loans, sales, contacts, etc)          │
│                                                                   │
│  Problem: Full access to schema once tenant set                │
│  - No subscription check                                        │
│  - No membership status check                                   │
│  - No permission checks                                        │
│  - No audit logging                                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Security Gaps (Current Implementation)

```
┌─────────────────────────────────────────────────────────────────┐
│                    AUTHORIZATION BYPASS RISKS                    │
│                                                                   │
│  1. Workspace Selection Not Validated                           │
│     ───────────────────────────────────────────────────────────  │
│     User manually sets UserProfile.workspace                    │
│     No check that user is actually a member                     │
│     No check that company subscription is active               │
│                                 │                               │
│                         User could:                             │
│                    - Join workspace without invite             │
│                    - Access expired subscriptions              │
│                    - Add themselves as Admin                   │
│                                                                   │
│  2. Role-Based, Not Permission-Based                           │
│     ───────────────────────────────────────────────────────────  │
│     @roles_required(['Owner', 'Admin'])                        │
│       checks role name only, not actual permissions            │
│                                 │                               │
│                         User could:                             │
│                    - Explore functionality through URLs        │
│                    - Access API endpoints directly             │
│                    - See data fields they shouldn't            │
│                                                                   │
│  3. No Suspension/Deactivation Logic                           │
│     ───────────────────────────────────────────────────────────  │
│     Members can't be suspended                                 │
│     Revoked access still works if they know the URL           │
│                                                                   │
│  4. No Audit Trail                                             │
│     ───────────────────────────────────────────────────────────  │
│     Can't track who created loans, invoices, etc              │
│     Can't detect suspicious activity                          │
│     Can't comply with audit requirements                      │
│                                                                   │
│  5. Subscription Not Enforced                                  │
│     ───────────────────────────────────────────────────────────  │
│     Expired subscription doesn't block access                 │
│     Features not locked per plan                             │
│     Can't upsell based on usage                             │
│                                                                   │
│  6. Object-Level Permissions Missing                           │
│     ───────────────────────────────────────────────────────────  │
│     Can't restrict data per user                             │
│     Members can edit any document created by anyone          │
│     Can't implement read-only roles effectively              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Proposed Architecture (To-Be)

```
┌─────────────────────────────────────────────────────────────────┐
│                    LAYERED AUTHORIZATION                         │
│                                                                   │
│  HTTP Request                                                    │
│      ↓                                                           │
│  [1] Authentication Middleware                                  │
│      └─> User loaded and verified                              │
│      ↓                                                           │
│  [2] Workspace Middleware                                       │
│      ├─> Check workspace set?                                  │
│      ├─> Load tenant schema                                    │
│      └─> Check membership exists                               │
│      ↓                                                           │
│  [3] Subscription Validator                                     │
│      ├─> Check subscription active?                            │
│      ├─> Check days until expiry                               │
│      └─> Redirect if expired                                   │
│      ↓                                                           │
│  [4] Membership Status Check                                    │
│      ├─> Check not suspended                                   │
│      ├─> Check invitation still valid                          │
│      └─> Check role exists                                     │
│      ↓                                                           │
│  [5] Permission Decorator                                       │
│      ├─> Check role has permission                             │
│      ├─> check feature available in plan                       │
│      └─> Check workspace_edit, team_invite, etc. perms        │
│      ↓                                                           │
│  [6] Object Permission Check                                    │
│      ├─> Can user access THIS document/record?                │
│      ├─> Filter data to only what user can see               │
│      └─> Check data created_by or has_permission              │
│      ↓                                                           │
│  [7] Feature Gating                                            │
│      ├─> Is this feature in user's plan?                      │
│      ├─> Show locked UI if unavailable                        │
│      └─> Upsell if interested                                 │
│      ↓                                                           │
│  ✅ GRANTED - Execute View                                      │
│      ↓                                                           │
│  [8] Audit Logging                                             │
│      ├─> Log action, user, IP, timestamp                      │
│      ├─> Log what changed (before/after)                      │
│      └─> Store in audit log                                   │
│                                                                   │
│  ❌ DENIED - Show Error or Redirect                             │
│      ├─> 404 for not found                                    │
│      ├─> Redirect to billing for feature locked              │
│      └─> Log denial attempt                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## User Flow Comparison

### Current (Confusing)

```
Visitor
  ↓
[Home Page]
  ├─ "Sign In" button
  └─ "Sign Up" button
  ↓
[Sign In / Sign Up Form]
  ↓
[Dashboard] ← User lands here confused
  │
  ├─ "Create Company"        ← Should I do this?
  ├─ "My Companies" (empty)
  ├─ "Invitations" (maybe?)
  ├─ "Billing"               ← What plan am I on?
  └─ "Settings"
  │
  ├─ User sees links but unsure
  ├─ No guidance on next step
  ├─ May create duplicate company
  └─ May not set workspace → gets errors
  ↓
[Workspace Setup]
  ├─ Manually select workspace
  ├─ Now what?
  └─ Surprise: You're in a different UI!
  ↓
[App] (now showing tenant.html)
  ├─ Different navigation
  ├─ Different styling
  └─ Different behavior
```

### Proposed (Clear Path)

```
Visitor
  ↓
[Home Page]
  ↓
[Sign In / Sign Up Form]
  ↓
[Onboarding Wizard] ✨ NEW
  ├─ Step 1: Email Verification (auto)
  ├─ Step 2: Profile Setup (name, timezone, pic)
  ├─ Step 3: Company Setup (name, type, tax info)
  ├─ Step 4: Plan Selection (see features, pricing)
  ├─ Step 5: Billing Setup (payment method)
  └─ Progress bar shows 5/5 ✓
  ↓
[Dashboard - Smart Routing]
  ├─ Has workspace set?
  │  ├─ YES & Single workspace → Auto-enter
  │  └─ YES & Multiple → Show workspace switcher
  └─ NO → Show "Create New" or "Join Existing"
  ↓
[Workspace Selector] (only if > 1)
  ├─ Shows all user's workspaces
  ├─ Shows user's role in each
  ├─ Can create new from here
  └─ One click to enter
  ↓
[In Workspace]
  ├─ Header shows current workspace
  ├─ Quick access to workspace switcher
  ├─ All navigation items shown based on role
  ├─ Features locked by plan clearly shown
  └─ Consistent UI across all modules
  ↓
[Tenant Dashboard]
  ├─ Ready to use!
  └─ No confusion
```

---

## UI/UX Comparison

### Current (Inconsistent)

```
PUBLIC AREA
┌──────────────────────────────────────┐
│  [Home] [Pricing] [About]            │
│  [Sign In] [Sign Up]                 │
│                                      │
│  Nice branding, modern design        │
│                                      │
│  Login page...                       │
│  Dashboard...                        │
│                                      │
│  Some pages use _base.html:          │
│  - Home page                         │
│  - Dashboard                         │
│  - Profile settings                  │
│                                      │
│  Styling: Bootstrap 5, nice colors   │
└──────────────────────────────────────┘
           BUT...

TENANT AREA
┌──────────────────────────────────────┐
│  Loan | Sales | Purchase | Accounts  │ ← Different nav!
│                                      │
│  Some pages use tenant.html:         │
│  - Loan management                   │
│  - Sales invoices                    │
│  - Purchase invoices                 │
│  - Accounting                        │
│                                      │
│  Different header style              │
│  Different sidebar                   │
│  Different colors/spacing            │
│                                      │
│  Styling: Inconsistent with public   │
│                                      │
│  Maintenance nightmare:              │
│  - HTML duplication                  │
│  - CSS duplication                   │
│  - Brand inconsistency               │
│  - Hard to add new features          │
└──────────────────────────────────────┘

Permission Issues:
- All users see all navigation items
- No indication of feature restrictions
- Can't see why you can't access something
- Empty states not handled
```

### Proposed (Unified & Smart)

```
EVERYWHERE
┌──────────────────────────────────────────┐
│ [Rokkad] [Dashboard] [Data] [Team]...    │ ← Single nav
│                    📦 Your Company       │ ← Workspace indicator
│                    [Switch]              │
│                                          │
│ Modern, consistent design across all     │
│                                          │
│ Unified base.html template:              │
│ - Home/public area                       │
│ - Dashboard                              │
│ - All workspace-specific pages           │
│ - Single source of truth                 │
│                                          │
│ Smart Navigation:                        │
│ ├─ [Dashboard]         (always)          │
│ ├─ [Data]              (if can_view)     │
│ │  ├─ Loans            (if girvi_view)   │
│ │  ├─ Sales            (if sales_view)   │
│ │  ├─ Purchase         (if purchase_view)│
│ │  └─ Accounting       (if dea_view)     │
│ ├─ [Team]              (if team_view)    │
│ ├─ [Billing]           (if billing_view) │
│ └─ [Settings]          (if settings_edit)│
│                                          │
│ Feature Gates:                           │
│ ├─ [Advanced Reports]  (Pro plan req.)   │
│ ├─ [API Access]        (Business plan)   │
│ └─ [Accounting Module] (locked 🔒)       │
│                                          │
│ Consistent Colors/Typography everywhere │
│ Easy to add new features                │
└──────────────────────────────────────────┘
```

---

## Data Model Comparison

### Current Issues

```
CustomUser
  ↓ (1:1) ↓
UserProfile
  workspace → Company (FK)
  
  
Issue: User can manually set workspace
       without validation


Membership
  user → CustomUser (FK)
  company → Company (FK)
  role → Role (FK)
  date_joined → DateTime
  
  
Issue: No suspension tracking
       No permission mapping
       Can't disable access


Subscription
  user → CustomUser (1:1) ← Issue: Should be per-company!
  plan → Plan (FK)
  start_date → Date
  end_date → Date
  is_active → Boolean
  
  
Issue: One subscription per USER, not per COMPANY
       Multiple workspaces = unclear subscription
       Can't have per-workspace billing


Role
  name → CharField
  permissions → M2M(DjangoPermission) ← Not used properly
  
  
Issue: Role-permission relationship not utilized
       No custom permissions defined
       All permissions Django built-in ones
```

### Proposed Structure

```
CustomUser
  ↓ (1:1) ↓
UserProfile
  workspace → Company (FK, optional) ✨ Renamed for clarity
  timezone → CharField
  profile_picture → ImageField
  phone_number → CharField
  address → CharField
  onboarding_completed → Boolean ✨ NEW


Membership
  user → CustomUser (FK)
  company → Company (FK)
  role → Role (FK)
  date_joined → DateTime
  is_suspended → Boolean ✨ NEW: Can suspend without deleting
  date_suspended → DateTime ✨ NEW: Track when/if suspended
  suspended_reason → TextField ✨ NEW: Why suspended?


Subscription
  company → Company (1:1) ✨ FIXED: Per-workspace, not per-user!
  plan → Plan (FK)
  start_date → Date
  end_date → Date
  is_active → Boolean
  canceled_at → DateTime ✨ NEW: Track cancellation
  auto_renew → Boolean ✨ NEW: Renewal preference


Role
  name → CharField
  permissions → M2M(Permission) ✨ Maps to permission codenames
  description → TextField
  ← Now properly mapped to custom permissions


Permission ✨ NEW: Custom permission system
  codename → CharField (workspace_view, team_invite, etc)
  name → CharField (human readable)
  category → CharField (workspace, team, data, billing)
  description → TextField


AuditLog ✨ NEW: Track all sensitive operations
  timestamp → DateTime
  user → FK(CustomUser)
  action → CharField (login, create_company, delete_loan, etc)
  resource_type → CharField (Company, Loan, Invoice, etc)
  resource_id → CharField
  workspace → FK(Company, nullable)
  changes → JSONField (before/after values)
  ip_address → GenericIPAddressField
  user_agent → TextField


OnboardingProgress ✨ NEW: Track signup flow
  user → FK(CustomUser, 1:1)
  current_step → IntegerField (1-5)
  completed_steps → JSONField ([1, 2, 3, ...])
  company_created → Boolean
  subscription_active → Boolean
  completed_at → DateTime
```

---

## Authorization Flow Comparison

### Current (Simple but Weak)

```
Request comes in
  ↓
Is user authenticated? (NO) → Redirect to login
  ↓ (YES)
@roles_required(['Owner', 'Admin']) ← Only check!
  ↓
Check: membership.role.name == 'Owner' or 'Admin'  
  ↓ (MATCH)
Grant access to view
  ↓
Execute code (no further checks)
  ↓
Log the action? (NO) ← No audit trail!
```

### Proposed (Robust & Secure)

```
Request comes in
  ↓
[1] Is user authenticated? (NO) → 404
    ↓ (YES)
[2] Is workspace set? (NO) → Redirect to select
    ↓ (YES)
[3] Is user member of workspace? (NO) → 404
    ↓ (YES)
[4] Is subscription active? (NO) → Redirect to billing
    ↓ (YES)
[5] Is user suspended? (YES) → Redirect to "account suspended"
    ↓ (NO)
[6] @permission_required('workspace_view') ← Check permission!
    ↓
[7] Check: membership.role.permissions.contains('workspace_view')
    ↓ (NO)
    └─> Return 404 "Requires permission"
    ↓ (YES)
[8] @feature_required('girvi', 'write') ← Check plan!
    ↓
[9] Check: Plan includes 'girvi write' feature
    ↓ (NO)
    └─> Return feature_locked page
    ↓ (YES)
[10] @object_permission_required('edit') ← Check object!
     ↓
[11] Check: User can edit THIS specific record
     ↓ (NO)
     └─> Return 404 "Can't edit"
     ↓ (YES)
[12] Execute view  
     ↓
[13] 📝 AuditLog.log(action, user, resource, ip, agent)
     ↓
✅ Return response
```

---

## Impact Summary

| Aspect | Current | Proposed | Impact |
|--------|---------|----------|--------|
| **Authorization** | Weak (role name only) | Strong (permission-based) | ⬆️ Security |
| **Audit Trail** | None | Comprehensive | ⬆️ Compliance |
| **Subscription Enforcement** | Not checked | Validated per-request | ⬆️ Revenue Protection |
| **User Onboarding** | None | 5-step wizard | ⬆️ Conversion |
| **Template Management** | 2 templates (duplication) | 1 unified template | ⬆️ Maintainability |
| **Feature Gating** | Manual (code) | UI-based & automatic | ⬆️ UX |
| **Data Access Control** | None (all or nothing) | Row-level permissions | ⬆️ Security |
| **Suspension Logic** | Delete or nothing | Suspend without delete | ⬆️ Flexibility |
| **User Routing** | Manual | Smart/automatic | ⬆️ UX |
| **Time to implement** | - | 2-3 weeks | ✅ Reasonable |

---

## ROI Calculation

### Security Value Prevented
- **Risk of unauthorized access:** $50K-$500K (depending on data value)
- **Compliance violations:** $25K-$250K+ (GDPR, etc.)
- **Audit failures:** $10K+ (if required for contracts)
- **Data breach impact:** $100K-$1M+ (reputation, legal)

**Total prevented:** Potentially $200K-$2M+

### Business Value Enabled
- **Improved conversion:** 20-30% higher onboarding completion (+$X/month)
- **Better onboarding:** 10-15% higher retention (+$X/month)
- **Feature-based upsells:** Ability to sell Pro/Business tiers (new revenue stream)
- **Reduced support:** Clear onboarding = fewer support tickets (-20% estimated)
- **Faster feature development:** Unified templates = 30% faster additions

**Total added value:** Potentially $X/month indefinitely

### Cost-Benefit
- **Implementation cost:** 2-3 weeks dev time = ~$20K-$40K
- **Payback period:** 1-3 months (purely from risk mitigation)
- **Ongoing benefit:** Lower support, higher retention, faster features

**ROI:** Strongly positive

---

