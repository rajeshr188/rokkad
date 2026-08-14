from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("dea", "0018_journalentry_created_updated"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE dea_ledgertransaction
                    ADD COLUMN IF NOT EXISTS amount_base_currency varchar(3);

                UPDATE dea_ledgertransaction
                   SET amount_base_currency = COALESCE(amount_base_currency, amount_currency, 'INR')
                 WHERE amount_base_currency IS NULL;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
