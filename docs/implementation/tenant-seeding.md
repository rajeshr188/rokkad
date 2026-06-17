---
status: active
owner: project
updated: 2026-06-17
tags: [implementation, tenant, seeding]
related: [../flows/workspace-onboarding.md, ../domain/workspace-auth.md]
---

# Tenant Seeding

Tenant setup should make required system data available before business workflows depend on it.

## Required Areas

- Workspace/company defaults.
- Roles, permissions, and team setup.
- Dynamic preferences.
- DEA account roots, voucher types, and posting rules.
- Commodity/rates prerequisites, including rate sources.
- Subscription/access defaults.

## Workspace Provisioning Checks

Workspace creation should build a safe tenant schema name from the workspace name, reject reserved names such as `public`, and check schema/domain collisions before saving. Owner membership creation and audit logging belong in orgs control-plane services.

The first dashboard should surface setup/readiness state through selectors and facades rather than letting orgs query tenant business models directly.

## Principle

Missing setup should produce a visible setup action or self-healing seed path. It should not silently produce zero values or confusing business validation errors.

Sources are archived in [archive/django-project](../archive/django-project/) and [archive/root/tenant-seeding-management-command-plan](../archive/root/tenant-seeding-management-command-plan.md).
