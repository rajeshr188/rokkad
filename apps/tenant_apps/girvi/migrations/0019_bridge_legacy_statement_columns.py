from django.db import migrations


LEGACY_STATEMENT_COLUMNS_SQL = """
DO $$
BEGIN
    IF to_regclass('girvi_statement') IS NOT NULL THEN
        ALTER TABLE girvi_statement
            ADD COLUMN IF NOT EXISTS completed_by_id bigint NULL;

        ALTER TABLE girvi_statement
            ADD COLUMN IF NOT EXISTS reopened_at timestamp with time zone NULL;

        ALTER TABLE girvi_statement
            ADD COLUMN IF NOT EXISTS reopened_by_id bigint NULL;

        ALTER TABLE girvi_statement
            ADD COLUMN IF NOT EXISTS statement_type varchar(20) NOT NULL DEFAULT 'REGULAR';

        ALTER TABLE girvi_statement
            ADD COLUMN IF NOT EXISTS status varchar(20) NOT NULL DEFAULT 'DRAFT';

        ALTER TABLE girvi_statement
            ADD COLUMN IF NOT EXISTS notes text NOT NULL DEFAULT '';
    END IF;
END
$$;
"""


class Migration(migrations.Migration):
    """Bridge older tenant schemas whose physical Statement table predates current fields."""

    dependencies = [
        ("girvi", "0018_bridge_legacy_statementitem_columns"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=LEGACY_STATEMENT_COLUMNS_SQL,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[],
        ),
    ]
