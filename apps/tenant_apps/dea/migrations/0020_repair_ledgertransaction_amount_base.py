from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("dea", "0019_repair_ledgertransaction_amount_base_currency"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE dea_ledgertransaction
                    ADD COLUMN IF NOT EXISTS amount_base numeric(13,3) NULL;

                UPDATE dea_ledgertransaction
                   SET amount_base = amount
                 WHERE amount_base IS NULL;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
