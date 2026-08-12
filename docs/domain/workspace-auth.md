---
status: active
owner: project
updated: 2026-06-17
tags: [domain, workspace, auth, authorization]
related: [../flows/workspace-onboarding.md, ../implementation/tenant-seeding.md, ../implementation/dynamic-preferences.md]
---

# Workspace, Auth, Authorization

Workspace/company management controls tenant context, team membership, permissions, invitations, onboarding, workspace switching, middleware safety, and dynamic preferences.

## Principles

- Tenant context must be explicit and reliable.
- Workspace switching should avoid recursion and stale context.
- Permission checks should be centralized and understandable.
- Platform-admin override behavior is an accepted decision; see [ADR](../adr/platform-admin-override-policy.md).
- Sidebar navigation source of truth is an accepted decision; see [ADR](../adr/sidebar-navigation-source-of-truth.md).

## Role Policy

`apps.orgs.services.role_policy` is the boundary for workspace role escalation and membership safety. Owners can grant Owner/Admin roles when they have the appropriate team-invitation permission. Admins and regular members cannot self-promote, promote others to Owner/Admin, demote the last owner, remove the last owner, or leave as owner without transferring ownership first.

Invitation forms must filter role choices through the same policy. Duplicate invitations should fail with validation errors, not returned exception objects.

## Dashboard Boundary

The orgs dashboard owns control-plane status only: team count, pending invitations, subscription/setup state, workspace readiness, and links to setup actions. Tenant business metrics must come through the owning app boundary:

- Contacts through `apps.tenant_apps.contact.facade`.
- Girvi loan/collateral summaries through `apps.tenant_apps.girvi.facade`.
- Rates setup/current-rate summaries through `apps.tenant_apps.rates.facade`.

Orgs must not create accounting postings, mutate inventory, or directly own tenant-business calculations.

## Workspace lifecycle

Ordinary Owner-facing removal is a recoverable archive, never a tenant-schema
drop. Archiving requires the Owner to enter the exact workspace name, sets
`is_deleted=True`, removes the workspace from normal selection and tenant
access, and preserves all business, document, loan, accounting, membership,
and configuration records. The Owner or a platform administrator may restore
the same workspace and schema from the archived-workspaces screen.

Permanent deletion remains an explicitly guarded platform operation through
`Company.hard_delete()` and must not be exposed as an ordinary workspace
settings action.

Archived workspace/auth sources are preserved in [archive/orgs](../archive/orgs/), [archive/django-project](../archive/django-project/), and [archive/multi-tenant](../archive/multi-tenant/).
