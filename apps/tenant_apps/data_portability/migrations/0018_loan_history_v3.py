from importlib import import_module
from django.db import migrations, models

guard = import_module("apps.tenant_apps.data_portability.migrations.0017_loan_history_v2").guard


class Migration(migrations.Migration):
    dependencies = [("data_portability", "0017_loan_history_v2")]
    operations = [
        migrations.AlterField(model_name="loanhistorybatch", name="profile",
            field=models.CharField(default="loan-history/1", max_length=32, choices=[
                ("loan-history/1", "Complete history v1"), ("loan-history/2", "Complete history v2"),
                ("loan-history/3", "Complete history v3 (inclusive monthly contract)"),
                ("legacy-opening/1", "Legacy opening")])),
        migrations.RunSQL(guard("'loan-history/1','loan-history/2','loan-history/3'"),
            """DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM data_portability_loanhistorybatch WHERE profile='loan-history/3')
            THEN RAISE EXCEPTION 'Cannot remove v3 support while v3 batches exist'; END IF;
            END; $$;""" + guard("'loan-history/1','loan-history/2'")),
    ]
