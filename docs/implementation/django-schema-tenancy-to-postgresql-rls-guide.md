---
status: active
owner: project
updated: 2026-08-17
tags: [django, postgresql, rls, multi-tenancy, migration, runbook]
related: [../adr/2026-08-14-shared-schema-workspace-rls-tenancy.md, postgresql-runtime-role.md, ../constitution.md]
---

# Migrating Django Schema Tenancy to Shared-Schema PostgreSQL RLS

This guide is for a Django SaaS application that currently isolates tenants in
separate PostgreSQL schemas and needs to move to one shared schema protected by
PostgreSQL row-level security (RLS).

It is intentionally reusable. Names such as `Workspace` and
`workspace_id` can be replaced with `Tenant`, `Organization`, or the equivalent
concept in another project.

RLS is not a smaller version of schema tenancy. It changes the isolation key
from the database schema selected by the connection to a required ownership
column on every tenant-owned row. A safe migration must replace every place
where the old schema silently provided identity.

## 1. Decide Whether This Migration Is Appropriate

Shared-schema RLS is a good fit when:

- all tenants use substantially the same model structure;
- cross-tenant operations are rare and can use an audited privileged path;
- tenant identity can be represented by a stable database key;
- PostgreSQL is a firm platform requirement;
- the team is prepared to test raw SQL, bulk writes, jobs, admin, imports, and
  connection reuse—not only ordinary model views.

Do not begin solely to remove a dependency. First decide what replaces all the
security properties that dependency currently provides.

The migration is more difficult when production data must be retained. In a
development-stage project, rebuilding an empty database is usually safer than
preserving years of transitional migration history. In production, use an
explicit data-migration and cutover plan; never reinterpret existing schema
rows as shared rows without attaching and validating ownership.

## 2. Define the Target Invariants

Write and accept an ADR before implementation. At minimum, require:

1. Every tenant-owned concrete table has a direct, non-null `workspace_id`.
2. No Workspace context exposes no tenant rows.
3. A Workspace context exposes only rows owned by that Workspace.
4. Inserts and updates cannot assign another Workspace.
5. Tenant relationships cannot cross Workspace boundaries.
6. The web/worker database role is not a superuser, cannot bypass RLS, and owns
   no protected table.
7. RLS is enabled and forced on every protected table.
8. HTTP requests, tasks, commands, imports, admin, and tests establish context
   through one canonical API.
9. Migration credentials are unavailable to web and worker processes.
10. A fresh database can be built with ordinary Django migrations.

Keep authorization separate from isolation:

- RLS answers, “Which Workspace owns this row?”
- membership and RBAC answer, “May this user perform this action?”
- subscriptions answer, “Is this feature enabled?”
- domain services enforce business rules.

Do not encode ordinary user permissions into tenant RLS policies.

## 3. Inventory Before Editing

Create a machine-checkable inventory of every concrete model in apps that are
currently tenant-scoped. For each model, record:

- database table;
- direct Workspace field, derived ownership, or no ownership;
- uniqueness constraints;
- foreign keys and many-to-many through tables;
- generic foreign keys;
- unmanaged models and SQL views;
- custom managers and unscoped querysets;
- triggers, procedures, and database functions;
- cache keys, file paths, logs, tasks, commands, fixtures, and imports;
- references to schema names, schema context managers, tenant middleware, and
  tenant-aware database routers.

Derived ownership is not enough. A child row that can be traced to a parent
still needs its own `workspace_id` if PostgreSQL must filter that table before a
join. This also makes raw SQL and bulk operations enforceable.

Useful searches include:

```bash
rg -n "schema_name|set_tenant|schema_context|tenant_context|migrate_schemas"
rg -n "TENANT_APPS|SHARED_APPS|DATABASE_ROUTERS|django_tenants"
rg -n "bulk_create|bulk_update|update\(|raw\(|cursor\(|RunSQL"
rg -n "cache|upload_to|storage|task|delay\(|apply_async|management.commands"
```

Do not trust a manually maintained model count. Derive the registry from
Django's app registry and fail CI when a new tenant model is not registered.

## 4. Establish a Recovery Point

Before structural changes:

1. Commit the working state.
2. Tag or record the commit hash.
3. Back up databases that contain data worth preserving.
4. Confirm the backup can be restored.
5. Record the old migration graph and installed package versions.
6. Identify which data is authoritative and which development data may be
   discarded.

Do not mix the irreversible database reset with the first code change. Keep a
Git-level recovery point and a database-level recovery point.

## 5. Introduce Direct Ownership

Create an abstract base model or a strict project convention:

```python
class WorkspaceOwnedModel(models.Model):
    workspace = models.ForeignKey(
        "orgs.Workspace",
        on_delete=models.PROTECT,
        related_name="+",
        editable=False,
    )

    class Meta:
        abstract = True
```

The field should normally be non-null and protected from accidental Workspace
deletion. Avoid a default Workspace. A default converts missing context into
silent data leakage.

For an existing production database, use expand/backfill/contract migrations:

1. Add a nullable ownership field.
2. Backfill from the old schema identity or a validated parent relationship.
3. Reject ambiguous and orphaned rows.
4. Add indexes and Workspace-scoped constraints.
5. Make the field non-null.

For an empty development rebuild, generate the final non-null field directly
in the clean baseline after the runtime model conversion is proven.

### Workspace-scoped uniqueness

A schema-local unique key such as `code` becomes a shared-schema constraint:

```python
models.UniqueConstraint(
    fields=["workspace", "code"],
    name="orders_workspace_code_uniq",
)
```

Audit `unique=True`, `unique_together`, conditional constraints, sequence
allocators, human-readable document numbers, provider IDs, idempotency keys,
and webhook replay keys.

### Relationship integrity

Python validation improves errors but is not a database security boundary.
For critical relationships, enforce same-Workspace ownership in the database,
usually with composite keys or equivalent triggers/constraints:

```text
child(workspace_id, parent_id)
    -> parent(workspace_id, id)
```

At minimum, service/model validation must reject mixed Workspace objects, and
adversarial database tests must cover bypass paths.

## 6. Build One Canonical Workspace Context

Use one API for requests, tasks, commands, and tests. It should:

- require a positive numeric Workspace ID;
- open a transaction;
- set a transaction-local PostgreSQL value;
- reject conflicting nested contexts;
- restore or clear context after success, exceptions, and rollback;
- keep application context and database context synchronized.

Example:

```python
from contextlib import contextmanager
from django.db import connection, transaction


@contextmanager
def workspace_context(workspace_id):
    workspace_id = int(workspace_id)
    if workspace_id <= 0:
        raise ValueError("workspace_id must be positive")

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('app.workspace_id', %s, true)",
                [str(workspace_id)],
            )
        yield
```

The third argument to `set_config` must be `true`, making the value local to
the transaction. A session-level value can leak across pooled or reused
connections.

The production implementation also needs application-side context tracking,
conflicting-nesting protection, and tests for exception/rollback cleanup.

## 7. Add Canonical PostgreSQL Policies

For every protected table:

```sql
ALTER TABLE example ENABLE ROW LEVEL SECURITY;
ALTER TABLE example FORCE ROW LEVEL SECURITY;

CREATE POLICY workspace_isolation ON example
USING (
    workspace_id = NULLIF(
        current_setting('app.workspace_id', true), ''
    )::bigint
)
WITH CHECK (
    workspace_id = NULLIF(
        current_setting('app.workspace_id', true), ''
    )::bigint
);
```

Why each part matters:

- `ENABLE ROW LEVEL SECURITY` activates policies for ordinary roles.
- `FORCE ROW LEVEL SECURITY` also subjects table owners unless PostgreSQL's
  broader bypass rules apply.
- `current_setting(..., true)` does not error when context is missing.
- `NULLIF(..., '')::bigint` fails closed to no matching rows.
- `USING` protects reads, updates, and deletes.
- `WITH CHECK` protects inserts and new values produced by updates.

Create a reusable Django migration operation instead of copying SQL into many
migrations. Keep policy names and expressions canonical so metadata checks can
detect drift.

## 8. Split Migration and Runtime Database Roles

RLS is not genuinely active if Django connects as a superuser, a role with
`BYPASSRLS`, or a protected-table owner.

Create a restricted runtime role as the migration owner or database operator:

```sql
CREATE ROLE app_runtime
    LOGIN
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOREPLICATION
    NOBYPASSRLS;

GRANT CONNECT ON DATABASE app_db TO app_runtime;
GRANT USAGE ON SCHEMA public TO app_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE
    ON ALL TABLES IN SCHEMA public TO app_runtime;
GRANT USAGE, SELECT
    ON ALL SEQUENCES IN SCHEMA public TO app_runtime;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_runtime;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO app_runtime;
```

Use separate settings or deployment jobs:

- migration settings: object owner; used only by `migrate` and controlled
  schema operations;
- runtime settings: restricted role; used by web processes, workers, scheduled
  commands, and ordinary shells;
- test settings: an owner may create/drop disposable test databases, while
  adversarial DML assumes a temporary restricted role.

Never fix an RLS error by granting table ownership or `BYPASSRLS` to the
runtime role.

## 9. Convert Runtime Boundaries

### HTTP middleware

Middleware should:

1. resolve a global Workspace from the host or URL;
2. authenticate and authorize membership;
3. enter `workspace_context(workspace.id)`;
4. execute the downstream request;
5. always close the context on response or exception.

Do not keep calling schema-switching methods behind compatibility names. A
temporary `request.tenant` alias may ease migration, but the database boundary
must already be the Workspace context.

### Tasks and workers

Every tenant task payload must carry `workspace_id`. The task must enter the
context before loading tenant data. Do not serialize a schema name as the
security identity.

### Management commands and imports

Require an explicit Workspace ID for tenant operations. Wrap each independent
unit in `workspace_context`. For all-Workspace commands, iterate global
Workspace rows outside tenant context and enter a separate context per item.

### Admin

Ordinary admin screens must be Workspace-bound. Cross-Workspace administration
needs a separate, explicit, audited privileged path; it must not temporarily
disable RLS on a normal request connection.

### Files, cache, logs, and external IDs

Replace schema-derived namespaces with stable Workspace IDs:

```text
workspaces/<workspace_id>/uploads/...
workspace:<workspace_id>:rate-cache
workspace_id=<id> in structured logs
```

Provider configuration, webhook IDs, replay keys, and idempotency keys must be
Workspace-owned or globally unique by deliberate design.

## 10. Convert Apps in Dependency Order

Use small vertical slices rather than changing all models at once. A practical
order is:

1. Workspace/control-plane models;
2. context primitive and middleware;
3. small reference-data aggregate as the RLS proof;
4. identity/counterparty aggregate;
5. notifications and provider evidence;
6. large transactional/domain aggregate;
7. jobs, commands, admin, files, caches, views, and triggers;
8. migration baseline and database rebuild;
9. tenant-library removal.

For each app, close the same gate:

- every concrete table has direct ownership;
- uniqueness is Workspace-scoped;
- relationships reject mixed ownership;
- RLS is enabled and forced;
- missing context sees zero rows;
- same context sees only owned rows;
- cross-Workspace SELECT/INSERT/UPDATE/DELETE fail or affect zero rows;
- raw SQL and bulk ORM paths are covered;
- app tests pass under the new context.

## 11. Treat Bulk Operations as a Separate Risk

`bulk_create`, `bulk_update`, and queryset `update` bypass model `save()`.
Signals may also be skipped. Therefore:

- explicitly populate `workspace_id` on objects passed to `bulk_create`;
- ensure child rows copy ownership from a validated parent;
- rely on `WITH CHECK` to reject spoofed Workspace IDs;
- test bulk inserts and updates under a restricted role;
- inspect every high-throughput and import path.

Finding ordinary form saves working does not prove bulk safety.

## 12. Rewrite Database Objects

Inventory and update:

- triggers;
- materialized and ordinary views;
- stored procedures/functions;
- partial indexes;
- generated columns;
- raw reporting SQL;
- sequence allocation logic;
- database constraints.

Every trigger that creates a child row must copy and validate Workspace
ownership. Every view must project `workspace_id` and remain safe when queried
under RLS. Security-definer functions require special review because they may
bypass caller expectations.

## 13. Rebuild Migrations Safely

Only rewrite migration history when the project has no production migration
compatibility requirement or a separately approved cutover makes it safe.

Recommended development-stage order:

1. Finish runtime conversion first.
2. Commit a recovery point containing the complete old graph.
3. Inventory required seeds, triggers, views, constraints, and data migrations.
4. Remove old project migration files on the migration branch.
5. Generate compact initial model migrations.
6. Add explicit RLS migrations after table creation.
7. Add audited trigger/view/constraint migrations after model state.
8. Run `makemigrations --check --dry-run`.
9. Migrate a new, explicitly named empty rehearsal database from zero.
10. Compare the resulting database metadata with the model registry.

Do not test a new baseline by pointing at the normal development database.
Use a settings module with a database-name prefix guard, for example requiring
`baseline_rehearsal_`.

For production data, do not squash away the migration path. Use expand,
backfill, validation, constraint, and cutover phases with rehearsed rollback.

## 14. Remove the Schema-Tenancy Library Last

Remove only after the shared-schema database and runtime pass isolation gates:

- package dependency;
- PostgreSQL tenant backend;
- database router;
- tenant/domain mixins;
- `SHARED_APPS`/`TENANT_APPS` split;
- schema middleware and context managers;
- schema-aware test runner/cases;
- schema provisioning, cloning, deletion, and migration commands;
- tenant storage/static finders;
- schema cache/log helpers;
- compatibility aliases and stale tests;
- active documentation instructing operators to run tenant-schema commands.

Repository searches should exclude clearly marked archives but cover active
Python, settings, templates, scripts, requirements, tests, and runbooks.

## 15. Verification Matrix

### Structural checks

- model registry equals protected-table registry;
- every model has a direct non-null Workspace FK;
- every protected table has an ownership index;
- every table has the canonical policy;
- RLS and FORCE RLS are enabled;
- migration drift is empty;
- no active schema-tenancy imports remain.

### Role checks

Verify the actual runtime connection:

```sql
SELECT current_user, rolsuper, rolbypassrls, rolcreatedb, rolcreaterole
FROM pg_roles
WHERE rolname = current_user;
```

Also verify it owns no protected table.

### Adversarial two-Workspace tests

Under the restricted role, prove:

- no context: SELECT returns zero;
- Workspace A: only A rows are visible;
- Workspace A cannot read/update/delete B rows;
- Workspace A cannot insert or reassign a row to B;
- raw SQL obeys the policy;
- aggregates, annotations, subqueries, prefetch, and related loading do not
  cross boundaries;
- bulk writes cannot spoof ownership;
- reused connections do not retain old context;
- exceptions and rollbacks clear context;
- tasks and commands behave identically to HTTP requests.

### Fresh database gate

On a new database:

```bash
python manage.py migrate --settings project.settings.migration --noinput
python manage.py check --settings project.settings.migration
python manage.py makemigrations --check --dry-run \
    --settings project.settings.migration
```

Then connect using runtime settings and run database/deployment checks. Seed
two deterministic Workspaces and one simple protected record per Workspace.
Prove positive same-Workspace access and negative cross-Workspace access.

## 16. Common Failure Modes

### “RLS is enabled, so we are safe”

False when Django connects as the table owner, a superuser, or a BYPASSRLS
role. Role separation is part of the feature, not deployment polish.

### Missing FORCE RLS

Table owners can bypass ordinary RLS behavior. Enable and force it, then still
keep the runtime role from owning tables.

### Session-level context leakage

`SET app.workspace_id = ...` persists on a reused connection. Use a
transaction-local setting and test connection reuse and rollback.

### Parent-derived ownership only

RLS cannot safely filter a child table before joining through its parent.
Store direct ownership on every protected concrete table.

### Model `save()` treated as the boundary

Bulk ORM, raw SQL, imports, and triggers bypass it. PostgreSQL `WITH CHECK` is
the final write boundary.

### Keeping the migration owner in local development

This makes local smoke tests lie. Use the restricted role for ordinary local
web and worker execution too.

### Removing the tenant package too early

The result is shared data without a replacement boundary. Convert ownership,
context, policies, roles, and runtime paths first.

### Restoring retired behavior to satisfy stale tests

Historical tests often assert old schema routing or deleted applications.
Classify and retire them. Do not weaken the target architecture to preserve an
obsolete snapshot.

### Rebuilding migrations mechanically

Autogenerated initial migrations do not capture custom triggers, views, seed
data, or policy operations unless those are explicitly restored and audited.

### Using RLS as authorization

RLS isolates Workspace rows. It does not replace membership, roles,
permissions, subscription checks, or domain invariants.

## 17. Rollback Strategy

Before the final cutover, rollback should be explicit:

- code rollback: return to the recorded schema-tenancy commit;
- database rollback: restore the verified pre-cutover backup;
- development baseline rollback: discard the new database and recreate from
  the old graph;
- production rollback: follow the approved dual-compatible deployment plan,
  not an improvised reverse migration.

After a development-only clean baseline is accepted and old databases are no
longer authoritative, treat schema tenancy as retired rather than maintaining
two runtime modes.

## 18. Definition of Done

The migration is complete only when:

1. A fresh checkout builds an empty database with ordinary Django migrations.
2. Every tenant-owned model has direct non-null ownership.
3. Every protected table has canonical enabled and forced RLS.
4. The runtime connection is restricted and owns no protected table.
5. No context exposes no tenant data.
6. Two-Workspace adversarial CRUD, raw SQL, bulk, connection-reuse, and
   rollback tests pass.
7. HTTP, tasks, commands, admin, imports, caches, files, and logs use explicit
   Workspace identity.
8. Schema-tenancy packages, backend, router, middleware, commands, and active
   guidance are removed.
9. Required domain suites pass without compatibility shims that bypass RLS.
10. Documentation records the current architecture, operator commands,
    recovery point, known risks, and deployment role contract.

The central lesson is simple: remove schema tenancy only after ownership,
context, policy, role, and verification boundaries exist. PostgreSQL RLS is the
last line of tenant isolation; explicit Workspace-aware application design is
everything leading up to it.
