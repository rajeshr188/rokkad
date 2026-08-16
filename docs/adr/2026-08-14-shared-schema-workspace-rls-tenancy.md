---
status: accepted
owner: project
updated: 2026-08-14
tags: [adr, tenancy, postgresql, rls, workspace, migration]
related: [../implementation/tenancy-architecture-audit-rls-vs-django-tenants.md, ../plans/django-tenants-removal.md, ../constitution.md, ../STATUS.md]
---

# Shared-Schema Workspace Tenancy With PostgreSQL RLS

Date: 2026-08-14
Status: Accepted
Owners: Project Owner, Platform Architecture

## Summary

Rokkad will replace `django-tenants` schema-per-tenant isolation with one
shared PostgreSQL schema. Every tenant-owned concrete row will carry a direct,
non-null `workspace_id`; PostgreSQL Row Level Security (RLS) will be the tenant
isolation boundary. Django membership and RBAC remain the action-authorization
boundary.

This is a development-stage rebuild. No production tenant data or schema-era
migration compatibility must be preserved. The migration may establish a clean
project migration baseline and recreate the development database after seed and
reference-data dependencies are inventoried.

This decision supersedes the schema-tenancy target in
`docs/architecture/SAAS_TARGET_ARCHITECTURE.md` and the hybrid timing
recommendation in the earlier tenancy audit when this ADR is accepted. It does
not supersede domain decisions about accounting immutability, source evidence,
reversals, Loans/Girvi coexistence, or legacy Notify retirement.

## Current State

1. `orgs.Company` inherits `TenantMixin`; `orgs.Domain` inherits `DomainMixin`.
2. `SHARED_APPS` and `TENANT_APPS` decide where models are migrated.
3. Django uses `django_tenants.postgresql_backend` and `TenantSyncRouter`.
4. `SecureWorkspaceMiddleware` resolves a Company, validates membership, calls
   `connection.set_tenant()`, and exposes `request.tenant`.
5. Most tenant-app models have no Workspace FK; the active PostgreSQL schema is
   their only ownership boundary.
6. Tests, seeds, commands, tasks, storage, cache keys, logs, SQL views, and
   triggers contain schema-specific assumptions.

Removing `django-tenants` before replacing these boundaries would mix customer,
loan, accounting, inventory, and notification data across workspaces.

## Target State

### Global control plane

- `Workspace` is an ordinary global Django model with a stable numeric primary
  key and immutable routing slug.
- User, WorkspaceDomain, Membership, Role, invitations, subscriptions, billing,
  and onboarding remain global/control-plane data.
- Global authentication occurs before tenant database context is established.
- `UserProfile.workspace` is a navigation preference, never authorization or
  database context.

### Tenant-owned rows

- Every concrete tenant-owned table has `workspace_id BIGINT NOT NULL`.
- Child/evidence tables store direct ownership even when ownership is derivable
  from a parent.
- Important tenant relationships use database-enforced same-workspace
  constraints, normally composite `(workspace_id, foreign_id)` foreign keys.
- Schema-local uniqueness becomes explicit Workspace-scoped uniqueness.

### Database isolation

- Every tenant table has RLS enabled and forced.
- The ordinary Django runtime role is not a table owner, superuser, or
  `BYPASSRLS` role.
- The migration-owner role owns and alters database objects but is not used by
  web requests or workers.
- The tenant policy compares `workspace_id` with a transaction-local
  `app.workspace_id` PostgreSQL setting in both `USING` and `WITH CHECK`.
- Missing context returns no tenant rows. Invalid context fails closed.

### Runtime context

One canonical API owns the transaction and database setting:

```python
with workspace_context(workspace_id):
    ...
```

It uses `transaction.atomic()` and transaction-local `set_config`. HTTP
middleware wraps downstream request execution in this context. Tasks and
commands receive an explicit Workspace identity and use the same primitive.

### Responsibility separation

- RLS answers: which Workspace owns this row?
- Membership/RBAC answers: may this user perform this action?
- Subscription/entitlements answer: has this Workspace purchased the feature?
- Services enforce accounting, lifecycle, evidence, and cross-aggregate rules.

RLS policies will not encode ordinary application roles or permissions.

## Non-Negotiable Invariants

1. No Workspace context means no tenant data.
2. The runtime database role cannot bypass RLS.
3. Every tenant row has exactly one Workspace owner.
4. Tenant-owned relationships cannot cross Workspace boundaries.
5. Background jobs use the same database context as HTTP requests.
6. Posted accounting evidence remains immutable and corrections remain
   reversal-based.
7. Workspace archive never mutates or deletes business/accounting evidence.
8. Ordinary platform administration never disables RLS on the runtime path.
9. New tenant models cannot ship without ownership, RLS, and verification.

## Cutover Strategy

There is no dual-write or production data migration. The implementation will:

1. establish the Workspace/RLS infrastructure and restricted roles;
2. prove it on a small tenant aggregate;
3. convert tenant apps in dependency order;
4. rewrite SQL views, triggers, jobs, commands, files, caches, and tests;
5. generate a clean migration baseline;
6. recreate the development database;
7. remove schema tenancy and `django-tenants`;
8. run adversarial isolation and domain-integrity gates.

`django-tenants` remains installed until the replacement database can boot and
pass isolation tests. Compatibility layers that preserve schema tenancy are not
part of the target.

## Migration History And Data

- Existing migrations remain historical evidence in Git.
- New clean initial migrations may replace schema-era project migrations.
- Required reference data must be represented by deterministic seed code or
  reviewed fixtures before the reset.
- Existing local database dumps are not assumed authoritative unless the owner
  explicitly identifies data to retain.

## Platform-Wide Operations

Cross-Workspace operations use either:

1. global projection/control-plane tables; or
2. an explicit, audited privileged database alias and role.

The normal request connection never gains conditional RLS bypass.

## Automated Drift Protection

The tenancy infrastructure will provide:

- a registry derived from `WorkspaceOwnedModel` concrete descendants;
- reusable migration operations for RLS and composite Workspace constraints;
- database-backed Django system checks for ownership columns, nullability,
  RLS, FORCE RLS, policy identity, indexes, and runtime-role safety;
- CI tests proving registry and PostgreSQL metadata agree.

## Verification Gates

### Gate 1: Foundation proof

- restricted runtime role verified;
- missing context exposes no proof-table rows;
- SELECT/INSERT/UPDATE/DELETE isolation passes;
- reused connections and rollback do not leak context.

### Gate 2: Domain conversion

- every tenant model has direct ownership;
- Workspace-scoped uniqueness is explicit;
- critical composite relationships reject cross-Workspace references;
- all SQL views and triggers are Workspace-aware.

### Gate 3: Runtime conversion

- HTTP, tasks, commands, admin, imports, storage, cache, and logging carry
  explicit Workspace identity;
- no business service reads schema state;
- no tenant test relies on schema creation or `TenantTestCase`.

### Gate 4: Removal

- a clean database builds with the standard PostgreSQL backend;
- adversarial two-Workspace tests pass under the runtime role;
- accounting and inventory reconciliation gates pass;
- repository searches find no unintended live `django-tenants` or schema
  context dependency;
- the dependency, backend, router, mixins, settings, and schema utilities are
  removed.

## Rollback

Before package removal, rollback is Git-level: return to the last schema-tenancy
commit and rebuild its development database. After the clean baseline is
accepted, schema tenancy is retired rather than maintained as a runtime fallback.

## Completion Criteria

1. Every explicit verification gate passes.
2. `django-tenants` is absent from dependencies and runtime imports.
3. Standard Django migrations build a clean shared-schema database.
4. No-context/no-data and cross-Workspace integrity are database-proven.
5. Documentation describes only the shared-schema runtime as current.

## Review Trigger

Revisit this decision if production data must be preserved before cutover, the
Workspace primary-key type changes, or PostgreSQL ceases to be the runtime
database.
