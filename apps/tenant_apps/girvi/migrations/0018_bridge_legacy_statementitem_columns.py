from django.db import migrations


LEGACY_STATEMENTITEM_COLUMNS_SQL = """
DO $$
BEGIN
    IF to_regclass('girvi_statementitem') IS NOT NULL THEN
        ALTER TABLE girvi_statementitem
            ADD COLUMN IF NOT EXISTS descrepancy_type varchar(20) NULL;

        ALTER TABLE girvi_statementitem
            ADD COLUMN IF NOT EXISTS auto_generated boolean NOT NULL DEFAULT FALSE;
    END IF;
END
$$;
"""


class Migration(migrations.Migration):
    """Bridge older tenant schemas whose physical StatementItem table predates current fields."""

    dependencies = [
        ("girvi", "0017_loan_interest_accrual"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=LEGACY_STATEMENTITEM_COLUMNS_SQL,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[],
        ),
    ]
