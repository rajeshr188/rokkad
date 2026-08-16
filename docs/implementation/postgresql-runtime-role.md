---
status: active
owner: project
updated: 2026-08-17
tags: [postgresql, rls, tenancy, deployment]
related: [../adr/2026-08-14-shared-schema-workspace-rls-tenancy.md, ../plans/django-tenants-removal.md]
---

# PostgreSQL Runtime Role

Rokkad uses two database identities:

- the migration owner creates and alters database objects;
- the runtime role serves web requests and workers and must never own tables,
  be a superuser, or have `BYPASSRLS`.

Run the following as the migration owner after replacing the role name and
setting its password through the deployment secret manager. Do not store the
password in Git.

```sql
CREATE ROLE rokkad_runtime
    LOGIN
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOREPLICATION
    NOBYPASSRLS;

GRANT CONNECT ON DATABASE rokkad TO rokkad_runtime;
GRANT USAGE ON SCHEMA public TO rokkad_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE
    ON ALL TABLES IN SCHEMA public TO rokkad_runtime;
GRANT USAGE, SELECT
    ON ALL SEQUENCES IN SCHEMA public TO rokkad_runtime;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO rokkad_runtime;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO rokkad_runtime;
```

Set `DB_RUNTIME_USER` and `DB_RUNTIME_PASSWORD` for web/worker connections.
Set the separate `DB_MIGRATION_USER` and `DB_MIGRATION_PASSWORD` owner
credentials only in the migration environment. Never grant ownership or
`BYPASSRLS` to make a failing application query pass.

Run schema migrations explicitly through the owner-only settings module:

```powershell
python manage.py migrate --settings django_project.settings.migration --noinput
```

Ordinary commands, the web server, and workers use the default development or
production settings and therefore the restricted runtime role.

The test runner needs owner authority only to create and drop its disposable
database. Run it with `--settings django_project.settings.test`; adversarial
RLS tests explicitly switch their DML to restricted roles.

Verify the deployed connection with:

```powershell
python manage.py check --deploy --database default
```

The deployment check fails if the connected role is a superuser, bypasses RLS,
or owns a protected Workspace table. The ordinary metadata check also verifies
that every model in the active RLS rollout registry has enabled and forced RLS
and the canonical policy.
