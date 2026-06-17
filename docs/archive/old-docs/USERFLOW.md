---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Rokkad â€” Complete User Flow

> **Architecture Note:** Rokkad uses `django-tenants` for multi-tenancy. There is a **public schema** (control plane â€” accounts, workspaces, billing, invitations) and a **tenant schema** per workspace (data plane â€” customers, loans, transactions). Every user navigates both planes during their lifecycle.

---

## 1. Landing Page

**URL:** `/`

The visitor lands on the public marketing page (`HomePageView`). From here they can:
- Sign up for a new account
- Log in to an existing account
- Read about the product (About, FAQ, Pricing, etc.)

---

## 2. Signup

**URL:** `/accounts/signup/`

Powered by **django-allauth**. Two paths:

| Path | Description |
|------|-------------|
| Email/Password | Standard allauth signup form. User provides email + password. Email verification may be required depending on `ACCOUNT_EMAIL_VERIFICATION` setting. |
| Google OAuth | `/accounts/google/login/` â€” one-click sign-in via Google. Allauth creates the user on first login. |

After a successful signup, allauth's `ACCOUNT_SIGNUP_REDIRECT_URL` / `LOGIN_REDIRECT_URL` fires. The user lands at `/onboarding/start/` (if onboarding is enabled) or directly at the workspace selector.

---

## 3. Onboarding (First-time Users)

**Base URL:** `/onboarding/`

A 5-step wizard that runs once per user (`OnboardingProgress` model tracks completion):

| Step | URL | Description |
|------|-----|-------------|
| 1 | `/onboarding/profile/` | Set display name, avatar |
| 2 | `/onboarding/company/` | Create the first workspace (company name, logo, address) |
| 3 | `/onboarding/team/` | Optionally invite team members |
| 4 | `/onboarding/tour/` | Optional product tour preferences |
| 5 | `/onboarding/complete/` | Summary & redirect to workspace |

- Each step can be skipped via `/onboarding/skip/`.
- `OnboardingProgress.is_complete` is checked on every step; if already done, the user is redirected to the workspace selector.
- When the workspace is created in step 2, the system:
  1. Provisions a new PostgreSQL **tenant schema** for the workspace.
  2. Optionally clones from a template schema (`ONBOARDING_TEMPLATE_SCHEMA`).
  3. Seeds defaults (`seed_tenant_defaults` management command).
  4. Creates a `Membership` record with the **Owner** role for the creating user.
  5. Sets `profile.workspace = new_company`.

---

## 4. Login (Returning Users)

**URL:** `/accounts/login/`

Also powered by allauth. On successful login:

1. Allauth calls `LOGIN_REDIRECT_URL` (default `/orgs/workspace/`).
2. `workspace_selector` view checks `profile.workspace`:
   - If a valid non-public workspace is already stored **and** the user still has membership â†’ redirect straight to `workspace_dashboard`.
   - Otherwise â†’ show the **Workspace Selector** page.

---

## 5. Workspace Selector

**URL:** `/orgs/workspace/` (name: `workspace_selector`)

Shown when no workspace is pre-selected. Displays:
- All workspaces the user is a member of (ordered by most recently updated).
- Pending invitations (filtered to non-expired only).
- A "Create Workspace" button.

If the user clicks a workspace card â†’ goes to `workspace_select`.

> **Short-circuit:** If `profile.workspace` is already set to a valid workspace the user belongs to, `workspace_selector` immediately redirects to `workspace_dashboard` (skipping this page), unless `?show_all=1` is appended in the URL.

---

## 6. Workspace Switch / Select

**URL:** `/orgs/workspace/<workspace_id>/select/` (name: `workspace_select`)

This is the **canonical switch mechanism**. What happens:

1. Fetch the `Company` by ID; 404 if deleted.
2. Call `_assert_workspace_access` â€” verifies user has an active `Membership` (or is a platform admin). If not â†’ redirect to selector.
3. Call `profile.set_workspace(workspace)` â€” persists the chosen workspace FK on the user's `Profile`.
4. Write an `AuditLog` entry (`WORKSPACE_SWITCH`).
5. Flash a success toast.
6. Redirect to `workspace_dashboard` (or to `?next=` URL if provided).

`/profile/switch/workspace/<id>/` is an alias that calls the same view via a redirect.

---

## 7. Workspace Dashboard

**URL:** `/orgs/workspace/<workspace_id>/dashboard/` (name: `workspace_dashboard`)

This is the **primary landing page** after selecting a workspace. It shows:

- Workspace name, logo, subscription status.
- Quick stats (team size, active loans, etc.).
- Role-gated quick-action cards:
  - **All roles:** access to customers, loans, transactions, reports.
  - **Owner only:** Billing / subscription card, Company Settings card, Preferences.
  - **Owner / Admin:** Team management, Invite members.

The context processor (`context_processors.py`) injects `user_role` and `role_name` into every template so navigation items are shown/hidden by role without extra DB queries.

---

## 8. Navigation & Layout

Two distinct layouts are used:

| Layout | Template | Used For |
|--------|----------|----------|
| **Management** | `templates/layouts/management.html` | Public-schema pages (workspace selector, profile, billing, invitations) |
| **Tenant / Workspace** | `templates/tenant.html` / `templates/_base.html` | Workspace data pages (customers, loans, etc.) |

The sidebar (`templates/components/navigation/sidebar.html`) is dynamically rendered based on `role_name`:
- **Owner:** sees Company Settings, Preferences, Billing links.
- **Admin/Member:** these links are hidden.

---

## 9. Multi-Workspace Usage

A user can be a member of multiple workspaces (each with a different role). To switch:

1. Click the workspace name / avatar in the top-nav or sidebar.
2. Choose "Switch Workspace" â†’ `/orgs/workspace/` (selector, `?show_all=1`).
3. Click any workspace card â†’ `workspace_select` sets new active workspace.
4. Redirected to that workspace's dashboard.

To return to the public control-plane without a workspace selected:
- `/profile/clear/workspace/` resets `profile.workspace` to the public `Company` and redirects to the selector.

---

## 10. Invitation Flow

### Sending an Invitation (Owner / Admin)

1. Navigate to **Company Settings â†’ Team** (`/orgs/workspace/<id>/`).
2. Click "Invite Member" â†’ `/orgs/team/invite/<workspace_id>/`.
3. Fill in invitee's email and select a role.
4. On submit, `control_plane.send_team_invitation()`:
   - Creates a `CompanyInvitation` record.
   - Sends an invitation email with a signed token link.
5. Redirect to `team_invite_success` page.

### Receiving / Accepting

**Path A â€” Invitee clicks email link:**
- URL: `/invitations/<key>/` (django-invitations `AcceptInvite` view, overridden as `CompanyInvitationAccept`).
- If not logged in â†’ redirect to login, then back to accept URL.
- On acceptance: `control_plane.accept_invitation()` is called, which:
  1. Sets `invitation.accepted = True`, `status = ACCEPTED`, `responded_at = now()`.
  2. Creates a `Membership` (user â†” workspace â†” role).
  3. Sets `profile.workspace` to the invited workspace.
- Redirect to `workspace_dashboard`.

**Path B â€” Invitee logs in and sees pending invitations:**
- URL: `/orgs/team/invitations/` (name: `team_invitations`).
- POST with `action=accept` and `invitation_id` â†’ same `control_plane.accept_invitation()` path.
- POST with `action=decline` â†’ invitation marked `DECLINED`.

Invitations can be revoked by the inviter or any Owner/Admin via `/orgs/invitations/<id>/delete/`.

---

## 11. Role & Permission System

Three built-in roles (seeded per workspace):

| Role | Key Permissions |
|------|----------------|
| **Owner** | All permissions including billing, delete workspace, transfer ownership, preferences |
| **Admin** | Invite/remove members, change roles, edit workspace settings (not billing/preferences) |
| **Member** | Read-only + customer/loan operations; no team management |

Permissions are checked at two levels:
- **Backend:** `_assert_workspace_access(required_permissions={...})` raises `PermissionDenied` (â†’ 403).
- **Template:** `{% if role_name == 'Owner' %}` / `{% if user_role == 'Owner' %}` hides UI elements.

---

## 12. Billing (Owner Only)

**URL:** `/subscriptions/` (name: `subscriptions:dashboard`)

Accessible **only to the workspace Owner**. Enforced by `BillingPermissionMixin` which checks `BILLING_ROLE_NAMES = {"Owner"}`. Non-owners receive a 403 and the link is hidden in all navigation templates.

Key subscription pages:
- `/subscriptions/` â€” dashboard showing current plan, expiry, usage.
- `/subscriptions/checkout/<plan_id>/` â€” subscribe to a plan.
- `/subscriptions/payment/` â€” payment details.

---

## 13. Workspace Settings & Preferences (Owner Only)

| Page | URL | Access |
|------|-----|--------|
| Company Details | `/orgs/workspace/<id>/` | All members (view), Owner (edit) |
| Edit Workspace | `/orgs/workspace/<id>/update/` | **Owner only** |
| Preferences | `/orgs/workspace/<id>/preferences/` | **Owner only** |
| Delete Workspace | `/orgs/workspace/<id>/delete/` | **Owner only** |

Both backend (`_assert_owner_access`) and template gating enforce Owner-only access.

---

## 14. Leaving / Removing from a Workspace

- **Member/Admin leaves:** `/orgs/workspace/<id>/leave/` â€” creates a self-removal; `profile.workspace` is cleared if it was this workspace.
- **Owner removes member:** Team management â†’ Remove button â†’ `team_remove_member` view.
- **Last owner protection:** The system prevents removing or demoting the last owner. A transfer must happen first.

---

## 15. Full Flow Diagram

```
Visitor
  â”‚
  â–¼
/ (Landing Page)
  â”‚
  â”œâ”€â”€â”€ /accounts/signup/ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
  â”‚                                             â”‚
  â””â”€â”€â”€ /accounts/login/  â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
       /accounts/google/login/                  â”‚
                                                â–¼
                                   /onboarding/start/  (first time)
                                        â”‚  (5 steps)
                                        â”‚  Step 2 creates workspace
                                        â”‚  + provisions tenant schema
                                        â”‚  + assigns Owner role
                                        â–¼
                              /orgs/workspace/  (Workspace Selector)
                                        â”‚
                          â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                          â”‚                              â”‚
                  Has valid workspace                No workspace /
                  in profile already                multiple workspaces
                          â”‚                              â”‚
                          â”‚                   Shows workspace cards
                          â”‚                   + pending invitations
                          â”‚                              â”‚
                          â”‚                   Click workspace card
                          â”‚                              â”‚
                          â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                                        â”‚
                          /orgs/workspace/<id>/select/
                          (sets profile.workspace, logs WORKSPACE_SWITCH)
                                        â”‚
                                        â–¼
                          /orgs/workspace/<id>/dashboard/
                          (Workspace Dashboard â€” role-gated UI)
                                        â”‚
              â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
              â”‚                         â”‚                        â”‚
           All Roles                 Owner Only             Owner/Admin
              â”‚                         â”‚                        â”‚
         Customers               Billing (/subscriptions/)   Team Mgmt
         Loans                   Preferences                 Invite Members
         Reports                 Edit/Delete Workspace       Change Roles
         Transactions
```

---

## 16. URL Quick Reference

| Name | URL Pattern | Description |
|------|-------------|-------------|
| `home` | `/` | Public landing page |
| `account_signup` | `/accounts/signup/` | Email signup |
| `account_login` | `/accounts/login/` | Login |
| `onboarding_start` | `/onboarding/start/` | Onboarding entry point |
| `workspace_selector` | `/orgs/workspace/` | Workspace picker (auto-redirects if workspace set) |
| `workspace_select` | `/orgs/workspace/<id>/select/` | Switch to a workspace |
| `workspace_dashboard` | `/orgs/workspace/<id>/dashboard/` | Main workspace dashboard |
| `workspace_create` | `/orgs/workspace/create/` | Create new workspace |
| `workspace_detail` | `/orgs/workspace/<id>/` | Workspace info & team list |
| `workspace_update` | `/orgs/workspace/<id>/update/` | Edit workspace (Owner) |
| `workspace_preferences` | `/orgs/workspace/<id>/preferences/` | Preferences (Owner) |
| `workspace_delete` | `/orgs/workspace/<id>/delete/` | Delete workspace (Owner) |
| `workspace_leave` | `/orgs/workspace/<id>/leave/` | Leave workspace |
| `team_invite` | `/orgs/team/invite/<id>/` | Send invitation (Owner/Admin) |
| `team_invitations` | `/orgs/team/invitations/` | Accept/decline invitations |
| `my_memberships` | `/orgs/profile/` | View all my workspaces |
| `switch_workspace` | `/profile/switch/workspace/<id>/` | Alias for workspace_select |
| `clear_workspace` | `/profile/clear/workspace/` | Reset active workspace |
| `subscriptions:dashboard` | `/subscriptions/` | Billing dashboard (Owner) |

