---
status: accepted
owner: project
updated: 2026-06-17
tags: [adr]
related: []
---

# Platform Admin Override Policy (Current and Future)

Date: 2026-05-01
Status: Accepted (Current Implementation)
Owners: Platform Architecture, Security, Tenant Framework

## Summary

This system currently applies a strict separation between tenant-level authorization and platform-level override authorization.

- Tenant-level access is controlled by workspace membership and role permissions.
- Platform-level override is restricted to Django superusers only.

This is an intentional policy to reduce ambiguity, avoid silent privilege escalation, and keep the authorization model easy to reason about while the multi-tenant stack stabilizes.

## Concepts

### Tenant Admin

Tenant admin authority applies inside one workspace (tenant schema).

Typical characteristics:

- Access is granted through Membership(user, company) with a role.
- Permissions are role-derived plus any role-attached permission codenames.
- Authorization checks are workspace-scoped.
- No cross-tenant override is implied.

Examples:

- Can manage team and workspace settings in their own tenant.
- Cannot access another tenant without membership.

### System Admin / Platform Admin

System admin authority applies across tenants and infrastructure concerns.

Current policy:

- A user is platform admin only if authenticated and is_superuser=True.
- Platform admin can bypass tenant membership checks as a controlled override.
- Platform admin gets full effective permission codename set plus admin_access.

## Current Design Decision

Decision:
Keep platform override as superuser-only for now.

Rationale:

1. Security clarity
   A single explicit override path is easier to audit and less error-prone.
2. Least surprise
   Tenant admin roles remain tenant-scoped and cannot accidentally gain cross-tenant powers.
3. Operational stability
   Existing tooling and incident workflows already understand superuser semantics.
4. Lower complexity
   Avoid introducing another global role model before requirements are fully clear.

## Where This Is Enforced

- apps/orgs/permissions.py

  - is_platform_admin(user)
  - get_effective_permissions(user, workspace)
  - get_workspace_role_name(user, workspace)

- apps/orgs/middleware_v2.py

  - Membership bypass uses is_platform_admin(user)

- django_project/context_processors.py

  - Template permission context uses canonical effective permission resolver

- apps/orgs/decorators_v2.py

  - View permission checks use canonical effective permission resolver

## Guardrails

- Membership remains mandatory for non-platform users.
- Platform override is centralized in one helper (is_platform_admin).
- Authorization surfaces (middleware, decorators, template context) share the same permission resolver.

## Future Evolution Path

If support staff or operations users need cross-tenant powers without full superuser rights:

1. Add an explicit platform-level role/flag
   Example: user.profile.is_platform_admin or dedicated global group.
2. Update only is_platform_admin(user)
   Do not duplicate override logic in middleware/decorators/context processors.
3. Add an explicit scope model
   Optional controls: read-only cross-tenant, support-only, audit-only.
4. Add mandatory audit entries for platform overrides
   Include acting user, target tenant, path/action, and reason code.
5. Add tests for all override permutations
   Superuser, platform-admin, tenant-admin, and non-member behaviors.

## Explicit Non-Goals (Current)

- Non-superuser global override users.
- Hidden fallback to profile-selected workspace for authorization decisions.
- Multiple competing permission resolvers.

## Review Trigger

Revisit this policy when either condition is true:

- A business requirement needs non-superuser cross-tenant support access.
- Compliance demands finer-grained global access controls than superuser provides.

