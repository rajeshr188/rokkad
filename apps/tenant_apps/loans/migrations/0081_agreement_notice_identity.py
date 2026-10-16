"""Bind new reminders to the reviewed financial agreement without replaying old ones."""

import django.db.models.fields.json
import django.db.models.functions.comparison
from django.db import migrations, models


GUARD = """
CREATE FUNCTION loans_notice_agreement_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE correction_id bigint;
BEGIN
 IF TG_OP='UPDATE' THEN
  IF (OLD.payload_snapshot ? 'agreement_identity' OR NEW.payload_snapshot ? 'agreement_identity')
    AND NEW.payload_snapshot IS DISTINCT FROM OLD.payload_snapshot
  THEN RAISE EXCEPTION 'Agreement-bound notice evidence is immutable'; END IF;
  RETURN NEW;
 END IF;
 SELECT max(id) INTO correction_id FROM loans_loanchangelog
 WHERE loan_id=NEW.loan_id AND workspace_id=NEW.workspace_id
 AND (metadata ? 'agreement_correction' OR metadata#>>'{history_correction,operation}'='CONTRACT');
 IF (correction_id IS NULL AND NEW.payload_snapshot ? 'agreement_identity')
 OR (correction_id IS NOT NULL AND NEW.payload_snapshot->'agreement_identity'
     IS DISTINCT FROM jsonb_build_object('correction_id',correction_id))
 THEN RAISE EXCEPTION 'Notice must retain its current reviewed agreement identity'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER loans_notice_agreement_guard BEFORE INSERT OR UPDATE ON loans_pawnloannotice
FOR EACH ROW EXECUTE FUNCTION loans_notice_agreement_guard();
"""


class Migration(migrations.Migration):

    dependencies = [
        ('loans', '0080_opening_checkpoint_corrections'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='pawnloannotice',
            name='loans_risk_notice_intent_uniq',
        ),
        migrations.AddConstraint(
            model_name='pawnloannotice',
            constraint=models.UniqueConstraint(models.F('source_risk_event'), models.F('notice_kind'), models.F('channel'), models.F('notification_template_version'), django.db.models.functions.comparison.Coalesce(django.db.models.fields.json.KeyTextTransform('correction_id', django.db.models.fields.json.KeyTransform('borrower_identity', 'payload_snapshot')), models.Value('0'), output_field=models.CharField()), django.db.models.functions.comparison.Coalesce(django.db.models.fields.json.KeyTextTransform('correction_id', django.db.models.fields.json.KeyTransform('agreement_identity', 'payload_snapshot')), models.Value('0'), output_field=models.CharField()), condition=models.Q(('source_risk_event__isnull', False), ('transaction_review__isnull', True)), name='loans_risk_notice_intent_uniq'),
        ),
        migrations.RunSQL(GUARD, """
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM loans_pawnloannotice WHERE source_risk_event_id IS NOT NULL
   AND transaction_review_id IS NULL AND notification_template_version IS NOT NULL
   GROUP BY source_risk_event_id,notice_kind,channel,notification_template_version,
     COALESCE(payload_snapshot#>>'{borrower_identity,correction_id}','0') HAVING count(*)>1)
 THEN RAISE EXCEPTION 'Agreement-bound notice evidence prevents downgrade'; END IF;
END; $$;
DROP TRIGGER loans_notice_agreement_guard ON loans_pawnloannotice;
DROP FUNCTION loans_notice_agreement_guard();
"""),
    ]
