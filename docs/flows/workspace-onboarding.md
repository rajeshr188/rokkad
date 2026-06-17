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

## Team And Invitation Flow

Owners manage elevated roles. Admins can help with ordinary team setup only within the permissions granted to them; they cannot grant Owner/Admin roles or bypass last-owner protections. Invitation acceptance creates membership through orgs control-plane services and should write audit events using the normalized `TEAM_*` action vocabulary.

## Workspace Creation Guardrails

Workspace creation must validate the derived schema/domain name before tenant provisioning. Unsafe, empty, reserved, or colliding schema/domain values should fail early with a clear form error.

Archived sources are in [archive/django-project](../archive/django-project/), [archive/orgs](../archive/orgs/), and [archive/onboarding](../archive/onboarding/).
