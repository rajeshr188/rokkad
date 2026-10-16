"""Bind supported recorded-position notices without inventing book reviews."""
from importlib import import_module
from django.db import migrations, models
from django.db.models.fields.json import KeyTextTransform, KeyTransform
from django.db.models.functions import Coalesce


PREFIX = "CREATE OR REPLACE FUNCTION loans_notice_review_guard()"
PREVIOUS = PREFIX + import_module(
    "apps.tenant_apps.loans.migrations.0060_review_future_capture"
).FORWARD.split(PREFIX, 1)[1]
CURRENT = PREVIOUS.replace(" RETURN NEW;", """
 IF NEW.payload_snapshot#>>'{transaction_review,contract}' = 'recorded-position-coverage/1' THEN
  IF NEW.transaction_review_id IS NOT NULL
    OR NEW.source_risk_event_id IS NULL OR NEW.source_risk_alert_id IS NULL
    OR (NEW.payload_snapshot#>>'{transaction_review,complete}') IS DISTINCT FROM 'true'
    OR (NEW.payload_snapshot#>>'{transaction_review,status}') IS DISTINCT FROM 'RECORDED_POSITION'
    OR COALESCE(NEW.payload_snapshot#>>'{transaction_review,source_fingerprint}', '') !~ '^[0-9a-f]{64}$'
  THEN RAISE EXCEPTION 'Invalid recorded position notice binding'; END IF;
 END IF;
 IF TG_OP='UPDATE' AND OLD.payload_snapshot#>>'{transaction_review,contract}' = 'recorded-position-coverage/1'
  AND (NEW.payload_snapshot IS DISTINCT FROM OLD.payload_snapshot
    OR NEW.loan_id IS DISTINCT FROM OLD.loan_id OR NEW.workspace_id IS DISTINCT FROM OLD.workspace_id
    OR NEW.source_risk_event_id IS DISTINCT FROM OLD.source_risk_event_id
    OR NEW.source_risk_alert_id IS DISTINCT FROM OLD.source_risk_alert_id)
 THEN RAISE EXCEPTION 'Recorded position notice content is immutable'; END IF;
 RETURN NEW;""")
REVERSE = """
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM loans_pawnloannotice
   WHERE payload_snapshot#>>'{transaction_review,contract}'='recorded-position-coverage/1')
 THEN RAISE EXCEPTION 'Retained position notices require compatible readers'; END IF;
END; $$;
""" + PREVIOUS


class Migration(migrations.Migration):
    dependencies = [("loans", "0089_monitoring_policy_lifecycle")]
    operations = [
        migrations.RemoveConstraint(model_name="pawnloannotice", name="loans_risk_notice_intent_uniq"),
        migrations.AddConstraint(model_name="pawnloannotice", constraint=models.UniqueConstraint(
            models.F("source_risk_event"), models.F("notice_kind"), models.F("channel"), models.F("notification_template_version"),
            Coalesce(KeyTextTransform("correction_id", KeyTransform("borrower_identity", "payload_snapshot")),
                models.Value("0"), output_field=models.CharField()),
            Coalesce(KeyTextTransform("correction_id", KeyTransform("agreement_identity", "payload_snapshot")),
                models.Value("0"), output_field=models.CharField()),
            Coalesce(KeyTextTransform("source_fingerprint", KeyTransform("transaction_review", "payload_snapshot")),
                models.Value("0"), output_field=models.CharField()),
            condition=models.Q(source_risk_event__isnull=False, transaction_review__isnull=True),
            name="loans_risk_notice_intent_uniq")),
        migrations.RunSQL(CURRENT, REVERSE),
    ]
