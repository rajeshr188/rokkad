---
status: active
owner: project
updated: 2026-06-17
tags: [flows, workspace, onboarding, invitations]
related: [../domain/workspace-auth.md, ../domain/subscriptions.md, ../implementation/tenant-seeding.md]
---

# Workspace Onboarding

Workspace onboarding covers company creation, invitation acceptance, team setup, tenant provisioning, seed data, subscription setup, and the first usable dashboard state.

## Flow

1. User signs in or accepts invitation.
2. Workspace/company is created or selected.
3. Tenant schema/context is provisioned.
4. Required seeds are applied: permissions, preferences, DEA basics, voucher types, rates prerequisites.
5. Subscription/access state is checked.
6. User lands on a dashboard with setup actions surfaced.

Archived sources are in [archive/django-project](../archive/django-project/), [archive/orgs](../archive/orgs/), and [archive/onboarding](../archive/onboarding/).
