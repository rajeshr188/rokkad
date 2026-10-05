"""Additive immutable per-loan future-capture choice; prior reviews stay mixed."""
from django.db import migrations, models
from django.db.models.fields.json import KeyTextTransform, KeyTransform

FORWARD = """

CREATE OR REPLACE FUNCTION loans_transaction_review_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'Transaction reviews are immutable'; END IF;
 IF NEW.source_fingerprint !~ '^[0-9a-f]{64}$' OR btrim(NEW.source_reference) = '' OR btrim(NEW.request_key) = ''
 OR NOT EXISTS (SELECT 1 FROM loans_pawnloan l WHERE l.id=NEW.loan_id AND l.workspace_id=NEW.workspace_id
   AND l.state IN ('ACTIVE','CLOSED') AND NEW.through_date >= l.loan_date)
 THEN RAISE EXCEPTION 'Invalid transaction review binding'; END IF;
 IF NEW.future_capture NOT IN ('PAPER_MIXED','ROKKAD_ONLY') THEN
  RAISE EXCEPTION 'Invalid future capture mode'; END IF;
 IF NEW.future_capture='PAPER_MIXED' THEN
  IF NEW.capture_state <> '' OR NEW.capture_event_id IS NOT NULL OR NEW.capture_contract_fingerprint <> '' THEN
   RAISE EXCEPTION 'Mixed capture cannot retain a transition checkpoint'; END IF;
 ELSE
  IF NEW.capture_contract_fingerprint !~ '^[0-9a-f]{64}$' OR NOT NEW.confirmed_complete OR NEW.capture_state <> 'ACTIVE' OR NEW.capture_event_id IS NULL
   OR NOT EXISTS (SELECT 1 FROM loans_pawnloan l WHERE l.id=NEW.loan_id AND l.workspace_id=NEW.workspace_id AND l.state='ACTIVE')
   OR NEW.capture_event_id IS DISTINCT FROM (SELECT max(e.id) FROM loans_pawnloanevent e WHERE e.loan_id=NEW.loan_id AND e.workspace_id=NEW.workspace_id)
   OR EXISTS (SELECT 1 FROM loans_pawnloanevent e WHERE e.loan_id=NEW.loan_id AND e.workspace_id=NEW.workspace_id AND e.effective_date>NEW.through_date)
  THEN RAISE EXCEPTION 'Invalid Rokkad-only capture checkpoint'; END IF;
 END IF;
 RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION loans_notice_review_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP = 'UPDATE' AND OLD.transaction_review_id IS DISTINCT FROM NEW.transaction_review_id
 THEN RAISE EXCEPTION 'Notice transaction review cannot be replaced'; END IF;
 IF NEW.transaction_review_id IS NOT NULL THEN
  IF NOT EXISTS (SELECT 1 FROM loans_loantransactionreview r
    WHERE r.id=NEW.transaction_review_id AND r.loan_id=NEW.loan_id AND r.workspace_id=NEW.workspace_id
      AND r.confirmed_complete AND NEW.payload_snapshot#>>'{transaction_review,review_id}'=r.id::text
      AND (NEW.payload_snapshot#>>'{transaction_review,source_fingerprint}'=r.source_fingerprint
       OR (r.future_capture='ROKKAD_ONLY'
         AND NEW.payload_snapshot#>>'{transaction_review,status}'='ROKKAD_ONLY'
         AND NEW.payload_snapshot#>>'{transaction_review,checked_source_fingerprint}'=r.source_fingerprint)))
    OR NEW.source_risk_event_id IS NULL OR NEW.source_risk_alert_id IS NULL
  THEN RAISE EXCEPTION 'Invalid notice transaction review binding'; END IF;
  IF TG_OP='UPDATE' AND (NEW.payload_snapshot IS DISTINCT FROM OLD.payload_snapshot
    OR NEW.loan_id IS DISTINCT FROM OLD.loan_id OR NEW.workspace_id IS DISTINCT FROM OLD.workspace_id)
  THEN RAISE EXCEPTION 'Reviewed notice content is immutable'; END IF;
 END IF;
 RETURN NEW;
END; $$;
"""
REVERSE = """

CREATE OR REPLACE FUNCTION loans_transaction_review_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'Transaction reviews are immutable'; END IF;
 IF NEW.source_fingerprint !~ '^[0-9a-f]{64}$' OR btrim(NEW.source_reference) = '' OR btrim(NEW.request_key) = ''
 OR NOT EXISTS (SELECT 1 FROM loans_pawnloan l WHERE l.id=NEW.loan_id AND l.workspace_id=NEW.workspace_id
   AND l.state IN ('ACTIVE','CLOSED') AND NEW.through_date >= l.loan_date)
 THEN RAISE EXCEPTION 'Invalid transaction review binding'; END IF;
 RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION loans_notice_review_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP = 'UPDATE' AND OLD.transaction_review_id IS DISTINCT FROM NEW.transaction_review_id
 THEN RAISE EXCEPTION 'Notice transaction review cannot be replaced'; END IF;
 IF NEW.transaction_review_id IS NOT NULL THEN
  IF NOT EXISTS (SELECT 1 FROM loans_loantransactionreview r
    WHERE r.id=NEW.transaction_review_id AND r.loan_id=NEW.loan_id AND r.workspace_id=NEW.workspace_id
      AND r.confirmed_complete AND NEW.payload_snapshot#>>'{transaction_review,review_id}'=r.id::text
      AND NEW.payload_snapshot#>>'{transaction_review,source_fingerprint}'=r.source_fingerprint)
    OR NEW.source_risk_event_id IS NULL OR NEW.source_risk_alert_id IS NULL
  THEN RAISE EXCEPTION 'Invalid notice transaction review binding'; END IF;
  IF TG_OP='UPDATE' AND (NEW.payload_snapshot IS DISTINCT FROM OLD.payload_snapshot
    OR NEW.loan_id IS DISTINCT FROM OLD.loan_id OR NEW.workspace_id IS DISTINCT FROM OLD.workspace_id)
  THEN RAISE EXCEPTION 'Reviewed notice content is immutable'; END IF;
 END IF;
 RETURN NEW;
END; $$;
"""


def refuse_loss(apps, schema_editor):
    review = apps.get_model("loans", "LoanTransactionReview")
    notice = apps.get_model("loans", "PawnLoanNotice")
    if notice._base_manager.using(schema_editor.connection.alias).filter(source_risk_event__isnull=False,
        transaction_review__isnull=False).values("source_risk_event", "notice_kind", "channel", "notification_template_version",
        "transaction_review").annotate(n=models.Count("pk")).filter(n__gt=1).exists():
        raise RuntimeError("Cannot remove retained position-specific notice intents.")
    if review._base_manager.using(schema_editor.connection.alias).filter(future_capture="ROKKAD_ONLY").exists():
        raise RuntimeError("Cannot remove retained Rokkad-only capture evidence.")


class Migration(migrations.Migration):
    dependencies = [("loans", '0059_opening_origin_exclusivity')]
    operations = [
        migrations.AddField(model_name="loantransactionreview", name="future_capture",
            field=models.CharField(max_length=16, default="PAPER_MIXED", choices=[("PAPER_MIXED", "Paper or mixed capture"), ("ROKKAD_ONLY", "All future activity in Rokkad")])),
        migrations.AddField(model_name="loantransactionreview", name="capture_state", field=models.CharField(max_length=16, blank=True, default="")),
        migrations.AddField(model_name="loantransactionreview", name="capture_event_id", field=models.PositiveBigIntegerField(null=True, blank=True)),
        migrations.AddField(model_name="loantransactionreview", name="capture_contract_fingerprint", field=models.CharField(max_length=64, blank=True, default="")),
        migrations.RemoveConstraint(model_name="pawnloannotice", name="loans_review_notice_intent_uniq"),
        migrations.AddConstraint(model_name="pawnloannotice", constraint=models.UniqueConstraint(
            models.F("source_risk_event"), models.F("notice_kind"), models.F("channel"), models.F("notification_template_version"), models.F("transaction_review"),
            KeyTextTransform("source_fingerprint", KeyTransform("transaction_review", "payload_snapshot")),
            condition=models.Q(source_risk_event__isnull=False, transaction_review__isnull=False), name="loans_review_notice_intent_uniq")),
        migrations.RunSQL(FORWARD, REVERSE),
        migrations.RunPython(migrations.RunPython.noop, refuse_loss),
    ]
