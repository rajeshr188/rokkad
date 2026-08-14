"""
Add 'created' and 'updated' columns to dea_journalentry.

The prod DB already has these columns (NOT NULL) but they were never tracked by
a Django migration — causing null-constraint violations on insert.

Uses RunSQL with ADD COLUMN IF NOT EXISTS so this migration is safe to run
against both:
  - Fresh schemas (columns don't exist yet → they get added with a NOW() default
    that satisfies the NOT NULL constraint for any pre-existing rows, then the
    column default is dropped so Django's auto_now_add/auto_now take over).
  - Prod-loaded schemas (columns already exist → IF NOT EXISTS is a no-op).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dea", "0017_alter_account_account_number"),
    ]

    operations = [
        # ── Database layer ──────────────────────────────────────────────────
        # Safe for prod (IF NOT EXISTS) and fresh schemas (adds the column).
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE dea_journalentry
                            ADD COLUMN IF NOT EXISTS created
                                timestamp with time zone NOT NULL DEFAULT NOW(),
                            ADD COLUMN IF NOT EXISTS updated
                                timestamp with time zone NOT NULL DEFAULT NOW();

                        -- Remove the transient DB-level default so Django's
                        -- auto_now_add / auto_now are the sole source of truth.
                        ALTER TABLE dea_journalentry
                            ALTER COLUMN created DROP DEFAULT,
                            ALTER COLUMN updated DROP DEFAULT;
                    """,
                    reverse_sql="""
                        ALTER TABLE dea_journalentry
                            DROP COLUMN IF EXISTS created,
                            DROP COLUMN IF EXISTS updated;
                    """,
                ),
            ],
            # ── ORM / state layer ────────────────────────────────────────────
            state_operations=[
                migrations.AddField(
                    model_name="journalentry",
                    name="created",
                    field=models.DateTimeField(auto_now_add=True),
                    preserve_default=False,
                ),
                migrations.AddField(
                    model_name="journalentry",
                    name="updated",
                    field=models.DateTimeField(auto_now=True),
                ),
            ],
        ),
    ]
