---
status: active
owner: girvi
updated: 2026-08-07
tags: [girvi, destructive, schema-reset, runbook, migrations]
related:
  - ../plans/girvi-audit-followup-plan.md
  - testing-and-migrations.md
  - ../../AGENTS.md
---

# Girvi Destructive Schema Reset Runbook

## Purpose

This runbook executes Wave 4 of the Girvi destructive cleanup track on branch
`dea-kiss`.

It resets Girvi tenant artifacts in explicitly approved non-production schemas,
rebuilds from current migrations, and validates the canonical runtime surface.

## Scope and Risk

- This is destructive for target tenant schemas.
- Existing Girvi data in target schemas is expected to be lost.
- This runbook must never be used on production tenants.

## Preconditions

1. Branch and code
   - Active branch is `dea-kiss`.
   - Working tree is reviewed and intentional.
2. Target schemas
   - Explicit list of non-production tenant schemas is approved.
   - Example: `jcl1`, `jsk`, `test`, or dedicated disposable schemas.
3. Backup tooling
   - `pg_dump` and `psql` are available.
4. Application access freeze
   - Girvi mutation endpoints are disabled for the reset window.

## Required Variables

Set these variables before running commands:

```powershell
$DB_NAME = "<db_name>"
$DB_USER = "<db_user>"
$DB_HOST = "<db_host>"
$DB_PORT = "<db_port>"
$TARGET_SCHEMAS = @("<schema1>", "<schema2>")
$BACKUP_DIR = "backup\girvi_reset_$(Get-Date -Format yyyyMMdd_HHmmss)"
New-Item -ItemType Directory -Force -Path $BACKUP_DIR | Out-Null
```

If your environment uses password auth via env var:

```powershell
$env:PGPASSWORD = "<db_password>"
```

## Step 1: Preflight

1. Record current migration intent for Girvi in each approved schema:

```powershell
.\.venv314\Scripts\python.exe manage.py makemigrations girvi --check --dry-run
foreach ($schema in $TARGET_SCHEMAS) {
  .\.venv314\Scripts\python.exe manage.py migrate_schemas --tenant --schema $schema --plan --noinput | Tee-Object -FilePath "$BACKUP_DIR\${schema}_migrate_plan_before.txt"
}
```

2. Record target schemas:

```powershell
$TARGET_SCHEMAS | Out-File "$BACKUP_DIR\target_schemas.txt"
```

3. Optional table inventory snapshot per schema:

```powershell
foreach ($schema in $TARGET_SCHEMAS) {
  $sql = @"
SELECT tablename
FROM pg_tables
WHERE schemaname = '$schema' AND tablename LIKE 'girvi_%'
ORDER BY tablename;
"@
  $sql | psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -v ON_ERROR_STOP=1 | Out-File "$BACKUP_DIR\${schema}_girvi_tables_before.txt"
}
```

## Step 2: Backup (Mandatory)

Create schema-scoped dumps before any destructive action:

```powershell
foreach ($schema in $TARGET_SCHEMAS) {
  pg_dump -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -n $schema -Fc -f "$BACKUP_DIR\${schema}.dump"
}
```

Record backup artifacts:

```powershell
Get-ChildItem $BACKUP_DIR | Select-Object Name, Length, LastWriteTime | Out-File "$BACKUP_DIR\backup_manifest.txt"
```

## Step 3: Drop Girvi Tables and Migration State Per Schema

This step removes Girvi data and clears Girvi migration history only in target
schemas.

```powershell
foreach ($schema in $TARGET_SCHEMAS) {
  $sql = @"
DO $$
DECLARE table_list text;
BEGIN
  SELECT string_agg(format('%I.%I', schemaname, tablename), ', ')
    INTO table_list
  FROM pg_tables
  WHERE schemaname = '$schema' AND tablename LIKE 'girvi_%';

  IF table_list IS NOT NULL THEN
    EXECUTE 'DROP TABLE ' || table_list;
  END IF;
END
$$;

DELETE FROM "$schema".django_migrations
WHERE app = 'girvi';
"@

  $sql | psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -v ON_ERROR_STOP=1
}
```

The single non-cascading `DROP TABLE` statement removes Girvi's internally
related tables together. It must fail if an object outside the Girvi table set
depends on them. Do not add `CASCADE`; investigate and explicitly include any
approved dependent reset scope instead.

## Step 4: Rebuild Girvi Schema via Tenant Migrations

Run tenant migrations from current codebase for each approved schema only:

```powershell
foreach ($schema in $TARGET_SCHEMAS) {
  .\.venv314\Scripts\python.exe manage.py migrate_schemas --tenant --schema $schema --noinput | Tee-Object -FilePath "$BACKUP_DIR\${schema}_migrate_after_reset.txt"
}
```

## Step 5: Post-Reset Validation

1. Verify Girvi migration rows exist again per schema:

```powershell
foreach ($schema in $TARGET_SCHEMAS) {
  $sql = @"
SELECT app, name
FROM "$schema".django_migrations
WHERE app = 'girvi'
ORDER BY id;
"@
  $sql | psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -v ON_ERROR_STOP=1 | Out-File "$BACKUP_DIR\${schema}_girvi_migrations_after.txt"
}
```

2. Run focused behavioral tests:

```powershell
.\.venv314\Scripts\python.exe manage.py test \
  apps.tenant_apps.girvi.tests.test_loan_creation_service \
  apps.tenant_apps.girvi.tests.test_transition_commands \
  apps.tenant_apps.girvi.tests.test_transition_command_behaviors \
  apps.tenant_apps.girvi.tests.test_loan_flow_matrix
```

3. Optional feature-gate coupling check used during Wave 3:

```powershell
.\.venv314\Scripts\python.exe manage.py test apps.tenant_apps.loans.tests.test_feature_gate
```

## Step 6: Publish Reset Ledger

After successful reset and validation, update `docs/STATUS.md` with:

- target schema names;
- backup manifest path;
- migration commands run;
- focused test command and result.

Keep command logs under the backup folder as evidence.

## Rollback

Rollback is backup restore only.

1. Stop application writes to affected schemas.
2. Restore the schema dump for each target schema.
3. Re-run tenant health checks and focused Girvi tests.

Example restore pattern:

```powershell
# Example only; adjust to your restore policy/environment.
# Drop and recreate schema, then restore from the .dump artifact.
```

Do not attempt partial row/table surgery to recover reset mistakes.

## Stop Conditions

Stop immediately if any of the following occurs:

- a target schema is discovered to be production;
- a backup artifact is missing or corrupt;
- commands affect schemas outside `$TARGET_SCHEMAS`;
- tenant migration rebuild fails;
- focused verification tests fail.

Escalate with logs and backup manifest.
