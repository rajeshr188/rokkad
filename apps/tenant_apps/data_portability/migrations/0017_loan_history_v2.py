from django.db import migrations, models


def guard(profiles):
    return f"""
CREATE OR REPLACE FUNCTION portability_loan_profile_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.profile NOT IN ({profiles},'legacy-opening/1')
 OR (TG_OP='UPDATE' AND NEW.profile IS DISTINCT FROM OLD.profile)
 THEN RAISE EXCEPTION 'Loan import profile is immutable and must be supported'; END IF;
 IF NEW.result_id IS NOT NULL AND NOT EXISTS (
   SELECT 1 FROM loans_historicalloanimport r WHERE r.id=NEW.result_id AND
   ((NEW.profile='legacy-opening/1' AND r.document=NEW.document->'opening') OR
    (NEW.profile IN ({profiles}) AND r.document=NEW.document)))
 THEN RAISE EXCEPTION 'Loan import result must match its exact profile document'; END IF;
 RETURN NEW;
END; $$;
"""


class Migration(migrations.Migration):
    dependencies = [('data_portability', '0016_guidedopeningbatch')]
    operations = [
        migrations.AlterField(model_name='loanhistorybatch', name='profile',
            field=models.CharField(choices=[('loan-history/1', 'Complete history v1'),
                ('loan-history/2', 'Complete history v2'), ('legacy-opening/1', 'Legacy opening')],
                default='loan-history/1', max_length=32)),
        migrations.RunSQL(guard("'loan-history/1','loan-history/2'"),
            """DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM data_portability_loanhistorybatch WHERE profile='loan-history/2')
            THEN RAISE EXCEPTION 'Cannot remove v2 support while v2 batches exist'; END IF;
            END; $$;""" + guard("'loan-history/1'")),
    ]
