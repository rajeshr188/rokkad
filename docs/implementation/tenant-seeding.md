---
status: active
owner: project
updated: 2026-06-18
tags: [implementation, tenant, seeding]
related: [../flows/workspace-onboarding.md, ../domain/workspace-auth.md, ../domain/party.md]
---

# Tenant Seeding

Tenant setup should make required system data available before business workflows depend on it.

## Required Areas

- Workspace/company defaults.
- Roles, permissions, and team setup.
- Dynamic preferences.
- DEA account roots, voucher types, and posting rules.
- Party role types, including customer, supplier, borrower, lender, employee, broker, bank, and portal customer.
- Commodity/rates prerequisites, including rate sources.
- Subscription/access defaults.

## Workspace Provisioning Checks

Workspace creation should build a safe tenant schema name from the workspace name, reject reserved names such as `public`, and check schema/domain collisions before saving. Owner membership creation and audit logging belong in orgs control-plane services.

The first dashboard should surface setup/readiness state through selectors and facades rather than letting orgs query tenant business models directly.

## Principle

Missing setup should produce a visible setup action or self-healing seed path. It should not silently produce zero values or confusing business validation errors.

## Party Roles

Canonical Party roles are Workspace-owned seed data. They are created by `seed_party_roles` and included in `seed_workspace_defaults` unless `--skip-party` is supplied.

The seed is idempotent and uses stable system keys so future accounting and workflow code can resolve roles by key instead of display label.

Sources are archived in [archive/django-project](../archive/django-project/) and [archive/root/tenant-seeding-management-command-plan](../archive/root/tenant-seeding-management-command-plan.md).
