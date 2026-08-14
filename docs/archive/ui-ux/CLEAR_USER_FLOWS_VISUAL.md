---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Clear User Flows - Visual Guide

**Companion to:** ARCHITECTURE_ASSESSMENT_AND_RECOMMENDATION.md  
**Purpose:** Provide clear visual representation of all user flows

---

## Flow 1: New User Registration â†’ First Workspace

### Current State (Confusing)
```
User â†’ Signup
    â†“
Email Verification
    â†“
Login
    â†“
pages.Dashboard() â† Redirects to workspace_home
    â†“
orgs.workspace_home() â† Shows workspace list (but user has none)
    â†“
User confused: "Where do I create workspace?"
    â†“
Finds "Create Company" button
    â†“
orgs.company_create()
    â†“
Company created
    â†“
Back to workspace_home
    â†“
Clicks workspace
    â†“
orgs.workspace_select() â† Sets active workspace
    â†“
pages.company_dashboard() â† Finally at dashboard
```

**Total Redirects:** 6-7 redirects, 3 apps involved

---

### After Refactor (Clear)
```
User â†’ Signup
    â†“
Email Verification
    â†“
Login
    â†“
@onboarding_required decorator â† Checks OnboardingProgress.is_complete
    â†“
apps.onboarding.onboarding_start() â† Entry point
    â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ STEP 1: Profile Setup                               â”‚
â”‚ URL: /onboarding/profile/                           â”‚
â”‚ View: onboarding_profile()                          â”‚
â”‚ Template: onboarding/step_profile.html              â”‚
â”‚                                                     â”‚
â”‚ [Name] [Phone] [Profile Picture]                   â”‚
â”‚                                                     â”‚
â”‚ Progress: â–ˆâ–ˆâ–ˆâ–ˆâ–‘â–‘â–‘â–‘ 25%                              â”‚
â”‚                         [Skip] [Continue â†’]         â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
    â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ STEP 2: Create Your Workspace                      â”‚
â”‚ URL: /onboarding/company/                           â”‚
â”‚ View: onboarding_company()                          â”‚
â”‚ Template: onboarding/step_company.html              â”‚
â”‚                                                     â”‚
â”‚ [Workspace Name] [Industry] [Timezone]             â”‚
â”‚                                                     â”‚
â”‚ Info: You'll be assigned as Owner with full access â”‚
â”‚ Progress: â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–‘â–‘ 50%                            â”‚
â”‚                         [Back] [Create Workspace â†’] â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
    â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ STEP 3: Invite Team Members (Optional)             â”‚
â”‚ URL: /onboarding/team/                              â”‚
â”‚ View: onboarding_team()                             â”‚
â”‚ Template: onboarding/step_team.html                 â”‚
â”‚                                                     â”‚
â”‚ [Email 1] [Role â–¼]  [+ Add Another]                â”‚
â”‚                                                     â”‚
â”‚ Progress: â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆ 75%                          â”‚
â”‚                [Skip for now] [Send Invites â†’]     â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
    â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ STEP 4: Choose Your Plan                           â”‚
â”‚ URL: /onboarding/tour/ or /subscriptions/plans/     â”‚
â”‚ View: onboarding_tour() â†’ redirects to plan_list    â”‚
â”‚ Template: subscriptions/plan_list.html              â”‚
â”‚                                                     â”‚
â”‚ â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â” â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â” â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”                â”‚
â”‚ â”‚ Basic   â”‚ â”‚ Pro     â”‚ â”‚Enterpriseâ”‚                â”‚
â”‚ â”‚ $29/mo  â”‚ â”‚ $99/mo  â”‚ â”‚ Custom  â”‚                â”‚
â”‚ â”‚ [Select]â”‚ â”‚ [Select]â”‚ â”‚ [Contact]â”‚                â”‚
â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                â”‚
â”‚                                                     â”‚
â”‚ Progress: â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆ 100%                     â”‚
â”‚                    [Start Free Trial] [Select Plan â†’]â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
    â†“
Onboarding Complete!
OnboardingProgress.is_complete = True
    â†“
pages.Dashboard() â† Smart router
    â†“
Has workspace? Yes!
    â†“
apps.orgs.workspace_dashboard(workspace_id)
    â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ â”Œâ”€â”€â”€ Rokkad â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â” â”‚
â”‚ â”‚ [Logo] ðŸ“¦ My Workspace â–¼  ðŸ””â”‚ðŸ‘¤ User â–¼        â”‚ â”‚
â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜ â”‚
â”‚                                                     â”‚
â”‚ â”Œâ”€Sidebarâ”€â”€â”€â”€â”  â”Œâ”€Main Contentâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”â”‚
â”‚ â”‚ Dashboard   â”‚  â”‚ Welcome to My Workspace!       â”‚â”‚
â”‚ â”‚ Team        â”‚  â”‚                                â”‚â”‚
â”‚ â”‚ Loans       â”‚  â”‚ â”Œâ”€â”€â”€â”€â”€â”€â” â”Œâ”€â”€â”€â”€â”€â”€â” â”Œâ”€â”€â”€â”€â”€â”€â”   â”‚â”‚
â”‚ â”‚ Settings    â”‚  â”‚ â”‚ Team â”‚ â”‚Activeâ”‚ â”‚ Data â”‚   â”‚â”‚
â”‚ â”‚ Billing     â”‚  â”‚ â”‚  5   â”‚ â”‚ Plan â”‚ â”‚1,234 â”‚   â”‚â”‚
â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â”‚ â””â”€â”€â”€â”€â”€â”€â”˜ â””â”€â”€â”€â”€â”€â”€â”˜ â””â”€â”€â”€â”€â”€â”€â”˜   â”‚â”‚
â”‚                  â”‚                                â”‚â”‚
â”‚                  â”‚ Recent Activity:               â”‚â”‚
â”‚                  â”‚ â€¢ John added new loan          â”‚â”‚
â”‚                  â”‚ â€¢ Sarah updated contact        â”‚â”‚
â”‚                  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

**Total Redirects:** 1 redirect, all in onboarding app

---

## Flow 2: Existing User Login â†’ Dashboard

### Current State (Confusing)
```
User â†’ Login
    â†“
django-allauth â†’ account_login_redirect()
    â†“
pages.Dashboard()
    â†“
return redirect('workspace_home')
    â†“
orgs.workspace_home()
    â†“
if user.profile.workspace exists:
    return redirect('company_dashboard')
    â†“
pages.company_dashboard()
    â†“
Finally at dashboard!
```

**Total Redirects:** 4 redirects

---

### After Refactor (Clear)
```
User â†’ Login
    â†“
django-allauth â†’ account_login_redirect()
    â†“
pages.Dashboard() â† Smart router
    â†“
Decision tree:
â”œâ”€ Has workspace? â†’ workspace_dashboard(workspace_id) [1 redirect]
â”œâ”€ Has memberships? â†’ workspace_list() [1 redirect]
â””â”€ No memberships? â†’ workspace_create() [1 redirect]
    â†“
Done! (Maximum 1 redirect)
```

---

## Flow 3: Workspace Selection (Multiple Workspaces)

### URL: `/workspace/` (was `/orgs/company/list/`)
### View: `workspace_list()` (was `workspace_home()`)
### Template: `workspace/list.html`

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ Your Workspaces                         [+ New Workspace]â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                         â”‚
â”‚ â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”            â”‚
â”‚ â”‚ ðŸ¢ ABC Corporation                       â”‚            â”‚
â”‚ â”‚ Role: Owner â”‚ Team: 12 â”‚ Last used: 2h  â”‚            â”‚
â”‚ â”‚ [Select â†’] [View Details]               â”‚            â”‚
â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜            â”‚
â”‚                                                         â”‚
â”‚ â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”            â”‚
â”‚ â”‚ ðŸ¢ XYZ Ltd                               â”‚            â”‚
â”‚ â”‚ Role: Admin â”‚ Team: 5 â”‚ Last used: 3d   â”‚            â”‚
â”‚ â”‚ [Select â†’] [View Details]               â”‚            â”‚
â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜            â”‚
â”‚                                                         â”‚
â”‚ â”Œâ”€ Pending Invitations (2) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”            â”‚
â”‚ â”‚ â€¢ Acme Inc invited you as Member         â”‚            â”‚
â”‚ â”‚   [Accept] [Decline]                     â”‚            â”‚
â”‚ â”‚ â€¢ Tech Corp invited you as Admin         â”‚            â”‚
â”‚ â”‚   [Accept] [Decline]                     â”‚            â”‚
â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜            â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

**User Actions:**
1. Click "Select" â†’ `workspace_select(workspace_id)` â†’ Sets active workspace â†’ `workspace_dashboard(workspace_id)`
2. Click "View Details" â†’ `workspace_detail(workspace_id)` â†’ Shows team, settings, etc.
3. Click "+ New Workspace" â†’ `workspace_create()`
4. Click "Accept" invitation â†’ `team_accept_invitation(key)` â†’ Creates membership â†’ Sets active workspace â†’ `workspace_dashboard(workspace_id)`

---

## Flow 4: Team Management

### URL: `/workspace/<id>/team/`
### View: `team_detail()` (new - consolidates membership views)
### Template: `workspace/team/team.html`

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ Team Management - ABC Corporation                      â”‚
â”‚                                          [+ Invite Member]â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                         â”‚
â”‚ â”Œâ”€ Team Members â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â” â”‚
â”‚ â”‚                                                      â”‚ â”‚
â”‚ â”‚ â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”â”‚ â”‚
â”‚ â”‚ â”‚ ðŸ‘¤ John Doe (You)                                â”‚â”‚ â”‚
â”‚ â”‚ â”‚ john@example.com                                 â”‚â”‚ â”‚
â”‚ â”‚ â”‚ [Owner â–¼] ðŸ”’                                     â”‚â”‚ â”‚
â”‚ â”‚ â”‚ Joined: Jan 15, 2026                             â”‚â”‚ â”‚
â”‚ â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜â”‚ â”‚
â”‚ â”‚                                                      â”‚ â”‚
â”‚ â”‚ â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”â”‚ â”‚
â”‚ â”‚ â”‚ ðŸ‘¤ Jane Smith                         [âœï¸ ] [ðŸ—‘ï¸]  â”‚â”‚ â”‚
â”‚ â”‚ â”‚ jane@example.com                                 â”‚â”‚ â”‚
â”‚ â”‚ â”‚ [Admin â–¼]  â† Click to change role                â”‚â”‚ â”‚
â”‚ â”‚ â”‚ Joined: Feb 10, 2026                             â”‚â”‚ â”‚
â”‚ â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜â”‚ â”‚
â”‚ â”‚                                                      â”‚ â”‚
â”‚ â”‚ â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”â”‚ â”‚
â”‚ â”‚ â”‚ ðŸ‘¤ Bob Wilson                         [âœï¸ ] [ðŸ—‘ï¸]  â”‚â”‚ â”‚
â”‚ â”‚ â”‚ bob@example.com                                  â”‚â”‚ â”‚
â”‚ â”‚ â”‚ [Member â–¼]                                       â”‚â”‚ â”‚
â”‚ â”‚ â”‚ Joined: Feb 20, 2026                             â”‚â”‚ â”‚
â”‚ â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜â”‚ â”‚
â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜ â”‚
â”‚                                                         â”‚
â”‚ â”Œâ”€ Pending Invitations â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â” â”‚
â”‚ â”‚                                                    â”‚ â”‚
â”‚ â”‚ â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”â”‚ â”‚
â”‚ â”‚ â”‚ ðŸ“§ alice@example.com                    [Cancel]â”‚â”‚ â”‚
â”‚ â”‚ â”‚ Role: Admin | Invited by: You                  â”‚â”‚ â”‚
â”‚ â”‚ â”‚ Sent: Feb 25, 2026 | Expires in 5 days         â”‚â”‚ â”‚
â”‚ â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜â”‚ â”‚
â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜ â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
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
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ Billing & Subscription                                 â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                         â”‚
â”‚ â”Œâ”€ Current Plan â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â” â”‚
â”‚ â”‚                                                      â”‚ â”‚
â”‚ â”‚ Pro Plan                            [Upgrade Plan]  â”‚ â”‚
â”‚ â”‚ $99.00 / month                                       â”‚ â”‚
â”‚ â”‚                                                      â”‚ â”‚
â”‚ â”‚ Status: Active âœ“                                     â”‚ â”‚
â”‚ â”‚ Next billing: March 15, 2026                         â”‚ â”‚
â”‚ â”‚                                                      â”‚ â”‚
â”‚ â”‚ Features Included:                                   â”‚ â”‚
â”‚ â”‚ âœ“ Advanced Reporting                                 â”‚ â”‚
â”‚ â”‚ âœ“ API Access                                         â”‚ â”‚
â”‚ â”‚ âœ“ Up to 20 team members                              â”‚ â”‚
â”‚ â”‚ âœ“ Priority Support                                   â”‚ â”‚
â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜ â”‚
â”‚                                                         â”‚
â”‚ â”Œâ”€ Payment Method â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â” â”‚
â”‚ â”‚ Visa â€¢â€¢â€¢â€¢ 4242                     [Update Method]  â”‚ â”‚
â”‚ â”‚ Expires: 12/2027                                     â”‚ â”‚
â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜ â”‚
â”‚                                                         â”‚
â”‚ â”Œâ”€ Billing History â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â” â”‚
â”‚ â”‚                                                      â”‚ â”‚
â”‚ â”‚ Feb 15, 2026  â”‚ $99.00  â”‚ Paid âœ“   â”‚ [ðŸ“„ Invoice]  â”‚ â”‚
â”‚ â”‚ Jan 15, 2026  â”‚ $99.00  â”‚ Paid âœ“   â”‚ [ðŸ“„ Invoice]  â”‚ â”‚
â”‚ â”‚ Dec 15, 2025  â”‚ $99.00  â”‚ Paid âœ“   â”‚ [ðŸ“„ Invoice]  â”‚ â”‚
â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜ â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

**Permission-Based Access:**
- **View billing** (`billing_view`): Owner, Admin
- **Edit billing** (`billing_edit`): Owner only

**Middleware Protection:**
```python
# SubscriptionValidationMiddleware (already exists)
# Checks on every request to tenant URLs:

1. Is subscription attached to workspace? 
   NO â†’ Redirect to /subscriptions/plans/
   
2. Is subscription active?
   NO â†’ Redirect to /subscriptions/dashboard/ with warning
   
3. Is subscription expiring soon (< 7 days)?
   YES â†’ Show warning banner
```

---

## Flow 6: Invitation Acceptance (External User)

### Entry: User receives email with invitation link
### URL: `/invitations/<key>/accept/`
### View: `team_accept_invitation()` (was `CustomAcceptInvite`)

```
Email:
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ You've been invited to join ABC Corporation at Rokkad  â”‚
â”‚                                                         â”‚
â”‚ John Doe has invited you to join their workspace       â”‚
â”‚ as an Admin.                                            â”‚
â”‚                                                         â”‚
â”‚ [Accept Invitation]  [Decline]                          â”‚
â”‚                                                         â”‚
â”‚ This invitation expires on March 7, 2026                â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

User clicks "Accept Invitation"
    â†“
Is user logged in?
â”œâ”€ NO â†’ Redirect to login with ?next=/invitations/abc123/accept/
â”‚   â†“
â”‚   User logs in or signs up
â”‚   â†“
â”‚   Redirect back to /invitations/abc123/accept/
â”‚
â””â”€ YES â†’ Continue to acceptance page
    â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ Accept Invitation                                       â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                         â”‚
â”‚ You've been invited to:                                 â”‚
â”‚                                                         â”‚
â”‚ â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”â”‚
â”‚ â”‚ ðŸ¢ ABC Corporation                                    â”‚â”‚
â”‚ â”‚                                                       â”‚â”‚
â”‚ â”‚ Role: Admin                                           â”‚â”‚
â”‚ â”‚ Invited by: John Doe (john@example.com)               â”‚â”‚
â”‚ â”‚ Invitation sent: Feb 25, 2026                         â”‚â”‚
â”‚ â”‚                                                       â”‚â”‚
â”‚ â”‚ As an Admin, you will be able to:                    â”‚â”‚
â”‚ â”‚ âœ“ View and manage workspace data                      â”‚â”‚
â”‚ â”‚ âœ“ Invite other team members                           â”‚â”‚
â”‚ â”‚ âœ“ View billing information                            â”‚â”‚
â”‚ â”‚ âœ— Delete workspace (Owner only)                       â”‚â”‚
â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜â”‚
â”‚                                                         â”‚
â”‚              [Accept & Join] [Decline]                  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

User clicks "Accept & Join"
    â†“
Backend:
1. Verify invitation is valid (not expired, not accepted)
2. Check if user already a member (skip if yes)
3. Create Membership record
4. Mark invitation as accepted
5. Set workspace as active in user profile
6. Send notification email to inviter
7. Log audit entry
    â†“
Redirect to workspace_dashboard(workspace_id)
    â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ âœ… Welcome to ABC Corporation!                          â”‚
â”‚                                                         â”‚
â”‚ You've successfully joined as Admin.                    â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

---

## Flow 7: Permission-Based Navigation

### Sidebar Rendering (Dynamic)

```python
# Every page render calls:
{% render_sidebar %}
    â†“
Template tag checks user's role permissions
    â†“
Filters navigation items by permission requirements
    â†“
Renders only authorized items
```

**Example for different roles:**

### Owner View
```
â”Œâ”€ Navigation â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ ðŸ  Dashboard        â”‚ â† workspace_view
â”‚ ðŸ‘¥ Team             â”‚ â† team_view
â”‚ ðŸ’° Loans            â”‚ â† data_view
â”‚ ðŸ“ˆ Sales            â”‚ â† data_view
â”‚ ðŸ§® Accounting       â”‚ â† data_view
â”‚ âš™ï¸  Settings        â”‚ â† workspace_edit
â”‚ ðŸ’³ Billing          â”‚ â† billing_view
â”‚ ðŸ“Š Reports          â”‚ â† reports_view
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Admin View
```
â”Œâ”€ Navigation â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ ðŸ  Dashboard        â”‚ â† workspace_view
â”‚ ðŸ‘¥ Team             â”‚ â† team_view
â”‚ ðŸ’° Loans            â”‚ â† data_view
â”‚ ðŸ“ˆ Sales            â”‚ â† data_view
â”‚ ðŸ§® Accounting       â”‚ â† data_view
â”‚ âš™ï¸  Settings        â”‚ â† workspace_edit
â”‚ ðŸ’³ Billing          â”‚ â† billing_view (read-only)
â”‚ ðŸ“Š Reports          â”‚ â† reports_view
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Member View
```
â”Œâ”€ Navigation â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ ðŸ  Dashboard        â”‚ â† workspace_view
â”‚ ðŸ’° Loans            â”‚ â† data_view
â”‚ ðŸ“ˆ Sales            â”‚ â† data_view
â”‚ ðŸ§® Accounting       â”‚ â† data_view
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
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
    â†“
URL: /reports/advanced/
View: advanced_reports_view()
Decorators:
    @login_required
    @workspace_required
    @feature_required('advanced_reporting')  â† NEW
    @permission_required('reports_view')
    â†“
feature_required decorator checks:
    1. Get workspace subscription
    2. Check plan includes 'advanced_reporting'
    â†“
Is feature included?
â”œâ”€ YES â†’ Continue to view
â”‚   â†“
â”‚   permission_required decorator checks:
â”‚       Get user's role
â”‚       Check role has 'reports_view' permission
â”‚       â†“
â”‚   Has permission?
â”‚   â”œâ”€ YES â†’ Render advanced_reports.html
â”‚   â””â”€ NO â†’ Show 403 error
â”‚
â””â”€ NO â†’ Show upgrade prompt
    â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ ðŸ”’ Premium Feature                                      â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                         â”‚
â”‚ Advanced Reporting is available on Pro and Enterprise  â”‚
â”‚ plans.                                                  â”‚
â”‚                                                         â”‚
â”‚ With Advanced Reporting, you can:                       â”‚
â”‚ â€¢ Custom report builder                                 â”‚
â”‚ â€¢ 50+ pre-built templates                               â”‚
â”‚ â€¢ Schedule automated reports                            â”‚
â”‚ â€¢ Export to Excel, PDF                                  â”‚
â”‚                                                         â”‚
â”‚ Your current plan: Basic                                â”‚
â”‚                                                         â”‚
â”‚        [Upgrade to Pro] [Learn More]                    â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
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
- âŒ 6-7 redirects to reach dashboard
- âŒ Logic scattered across 3 apps
- âŒ Confusing URL patterns
- âŒ No visual permission indicators
- âŒ Hard to understand flow from code

### After:
- âœ… Maximum 1 redirect
- âœ… All workspace logic in `apps/orgs/`
- âœ… Consistent `/workspace/` URLs
- âœ… Permission-based UI components
- âœ… Clear, documented flows

---

**Next:** See ARCHITECTURE_ASSESSMENT_AND_RECOMMENDATION.md for implementation plan.


