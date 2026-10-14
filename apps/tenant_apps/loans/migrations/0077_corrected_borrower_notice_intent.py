from django.db import migrations, models
from django.db.models.fields.json import KeyTextTransform, KeyTransform
from django.db.models.functions import Coalesce


class Migration(migrations.Migration):
    dependencies = [('loans', '0076_merge_borrower_correction')]
    operations = [
        migrations.RemoveConstraint(model_name='pawnloannotice', name='loans_risk_notice_intent_uniq'),
        migrations.AddConstraint(model_name='pawnloannotice', constraint=models.UniqueConstraint(
            models.F('source_risk_event'), models.F('notice_kind'), models.F('channel'), models.F('notification_template_version'),
            Coalesce(KeyTextTransform('correction_id', KeyTransform('borrower_identity', 'payload_snapshot')),
                models.Value('0'), output_field=models.CharField()),
            condition=models.Q(source_risk_event__isnull=False, transaction_review__isnull=True),
            name='loans_risk_notice_intent_uniq')),
        migrations.RunSQL(migrations.RunSQL.noop, '''
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM loans_pawnloannotice
   WHERE source_risk_event_id IS NOT NULL AND transaction_review_id IS NULL
     AND notification_template_version IS NOT NULL
   GROUP BY source_risk_event_id, notice_kind, channel, notification_template_version
   HAVING count(*) > 1)
 THEN RAISE EXCEPTION 'Corrected borrower notice evidence prevents downgrade'; END IF;
END; $$;
'''),
    ]
