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

Archived workspace/auth sources are preserved in [archive/orgs](../archive/orgs/), [archive/django-project](../archive/django-project/), and [archive/multi-tenant](../archive/multi-tenant/).
