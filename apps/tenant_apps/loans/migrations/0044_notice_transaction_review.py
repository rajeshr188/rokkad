import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("loans", "0043_loan_transaction_review")]
    operations = [
        migrations.AddField(model_name="pawnloannotice", name="transaction_review",
            field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="notices", to="loans.loantransactionreview")),
        migrations.RemoveConstraint(model_name="pawnloannotice", name="loans_risk_notice_intent_uniq"),
        migrations.AddConstraint(model_name="pawnloannotice", constraint=models.UniqueConstraint(
            fields=("source_risk_event", "notice_kind", "channel", "notification_template_version"),
            condition=models.Q(source_risk_event__isnull=False, transaction_review__isnull=True), name="loans_risk_notice_intent_uniq")),
        migrations.AddConstraint(model_name="pawnloannotice", constraint=models.UniqueConstraint(
            fields=("source_risk_event", "notice_kind", "channel", "notification_template_version", "transaction_review"),
            condition=models.Q(source_risk_event__isnull=False, transaction_review__isnull=False), name="loans_review_notice_intent_uniq")),
        migrations.RunSQL("""
CREATE FUNCTION loans_notice_review_guard() RETURNS trigger LANGUAGE plpgsql AS $$
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
CREATE TRIGGER loans_notice_review_guard BEFORE INSERT OR UPDATE ON loans_pawnloannotice
FOR EACH ROW EXECUTE FUNCTION loans_notice_review_guard();
""", "DROP TRIGGER loans_notice_review_guard ON loans_pawnloannotice; DROP FUNCTION loans_notice_review_guard();"),
    ]
