PostgreSQL RLS policies exist and are correct, but the database user Django currently connects as is `postgres`. That user is a superuser and owns the tables, so PostgreSQL allows it to bypass RLS.

In other words:

```text
RLS policies installed:       yes
RLS forced on all 95 tables:  yes
Django using restricted role: no
Effective runtime isolation:  not yet
```

## Why the current connection is unsafe

Your development settings currently contain roughly:

```python
DATABASES = {
    "default": {
        "NAME": "rokkad_shared_dev",
        "USER": "postgres",
        ...
    }
}
```

`postgres` is normally a PostgreSQL superuser. PostgreSQL superusers always bypass row-level security. `FORCE ROW LEVEL SECURITY` affects table owners, but it does not constrain a superuser.

Therefore, a bug such as this could still expose every workspace:

```python
Party.objects.all()
```

Under the current `postgres` connection, that query may return Parties from every workspace, even when `app.workspace_id` is missing.

Under a properly restricted role, the same query returns:

- only the active workspace’s rows when `workspace_context()` is active;
- zero rows when no workspace context exists.

## Required two-role design

You need separate database identities.

| Role | Used for | Capabilities |
|---|---|---|
| Migration owner | `migrate`, schema changes | Owns and alters tables |
| Runtime role | Web requests, workers, commands | Reads/writes data but cannot bypass RLS |

The migration owner can remain `postgres` during development.

The runtime role could be named:

```text
rokkad_runtime
```

It must have:

```text
NOSUPERUSER
NOCREATEDB
NOCREATEROLE
NOREPLICATION
NOBYPASSRLS
```

It must also not own any application tables.

## How runtime isolation works

For every workspace request, the middleware enters:

```python
with workspace_context(workspace_id):
    ...
```

That starts a transaction and executes the equivalent of:

```sql
SELECT set_config('app.workspace_id', '42', true);
```

Every protected table has a policy equivalent to:

```sql
USING (
    workspace_id =
    NULLIF(current_setting('app.workspace_id', true), '')::bigint
)
WITH CHECK (
    workspace_id =
    NULLIF(current_setting('app.workspace_id', true), '')::bigint
)
```

The resulting behavior is:

| Operation | Result |
|---|---|
| Read Workspace 42 rows under context 42 | Allowed |
| Read Workspace 43 rows under context 42 | Hidden |
| Update/delete Workspace 43 rows under context 42 | Hidden |
| Insert a row owned by Workspace 43 under context 42 | Rejected |
| Query without workspace context | No tenant rows |
| Raw SQL that forgets workspace filtering | Still isolated |

This protection is enforced by PostgreSQL, beneath Django’s ORM.

## Why the password must be managed separately

`rokkad_runtime` needs a login password, but that password must not be committed to Git or placed in tracked settings.

A local environment configuration could use:

```env
DB_RUNTIME_USER=rokkad_runtime
DB_RUNTIME_PASSWORD=<generated-secret>
```

The migration-owner credentials should remain separate:

```env
DB_MIGRATION_USER=postgres
DB_MIGRATION_PASSWORD=<owner-secret>
```

This prevents the web application from silently receiving migration-owner authority.

## Intended workflow

Normal application execution:

```text
Django web server
    → connects as rokkad_runtime
    → cannot bypass RLS
    → workspace_context sets app.workspace_id
    → PostgreSQL enforces isolation
```

Migration execution:

```text
Django migrate command
    → explicitly uses migration-owner settings
    → connects as postgres
    → can create/alter tables and policies
```

The runtime role should never be granted table ownership, superuser access, or `BYPASSRLS` merely to fix an application error.

## What still needs implementation

The remaining work is:

1. Create `rokkad_runtime` with a securely generated password.
2. Grant it access to the database, public schema, tables, and sequences.
3. Configure ordinary Django development/runtime settings to use it.
4. Create separate owner-only migration settings or migration environment variables.
5. Run:

```powershell
python manage.py check --deploy --database default
```

6. Run application and isolation tests through the restricted connection.
7. Verify missing workspace context returns no business rows.

The SQL and operational procedure are documented in [postgresql-runtime-role.md](C:\Users\rajes\OneDrive\Desktop\rokkad\docs\implementation\postgresql-runtime-role.md).

Until that role separation is complete, the project has a correct RLS design and database schema, but the running application still possesses enough PostgreSQL privilege to bypass the isolation boundary.