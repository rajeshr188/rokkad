"""Separate recorded payout facts from contemporaneous lending approval."""
from django.db import migrations, models
import django.db.models.deletion


GUARD = """
CREATE FUNCTION loans_disbursal_basis_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p loans_loanpolicysnapshot%ROWTYPE; e loans_pawnloanevent%ROWTYPE;
  l loans_pawnloan%ROWTYPE; r jsonb;
BEGIN
  SELECT * INTO p FROM loans_loanpolicysnapshot WHERE id=NEW.policy_snapshot_id
    AND loan_id=NEW.loan_id AND workspace_id=NEW.workspace_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'Disbursal policy must belong to its loan and Workspace'; END IF;
  SELECT * INTO e FROM loans_pawnloanevent WHERE id=NEW.loan_event_id
    AND loan_id=NEW.loan_id AND workspace_id=NEW.workspace_id;
  IF NOT FOUND OR e.event_kind<>'DISBURSAL'
  THEN RAISE EXCEPTION 'Disbursal requires its own payout event'; END IF;
  IF NEW.basis='APPROVED' THEN
    IF p.basis<>'ORIGINATION' OR NEW.evidence ? 'recording'
      OR e.payload->'disbursal'->>'basis'='RECORDED'
    THEN RAISE EXCEPTION 'Approved disbursal cannot claim recorded contract evidence'; END IF;
  ELSIF NEW.basis='RECORDED' THEN
    SELECT * INTO l FROM loans_pawnloan WHERE id=NEW.loan_id AND workspace_id=NEW.workspace_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'Recorded payout requires its own loan'; END IF;
    r := NEW.evidence->'recording';
    IF p.basis<>'RECORDED_CONTRACT' OR NEW.created_by_id IS NULL
      OR NEW.created_by_id IS DISTINCT FROM e.created_by_id
      OR r->>'schema' IS DISTINCT FROM 'recorded-origination/1'
      OR r->>'payout_already_occurred' IS DISTINCT FROM 'true'
      OR r->>'date_precision' IS DISTINCT FROM 'DAY'
      OR r->>'occurred_on' IS DISTINCT FROM e.effective_date::text
      OR e.effective_date IS DISTINCT FROM l.loan_date
      OR COALESCE(length(trim(r->>'source_reference')),0) NOT BETWEEN 1 AND 160
      OR e.payload->'recording' IS DISTINCT FROM r
      OR e.payload->'disbursal'->>'basis' IS DISTINCT FROM 'RECORDED'
      OR e.payload->'disbursal'->>'approval_snapshot_id' IS NOT NULL
      OR e.payload->'disbursal'->>'policy_snapshot_id' IS DISTINCT FROM p.id::text
      OR r->'terms'->>'loan_number' IS DISTINCT FROM l.loan_number
      OR (r->'terms'->>'principal_amount')::numeric IS DISTINCT FROM NEW.gross_principal
      OR NEW.gross_principal IS DISTINCT FROM l.principal_amount
      OR (r->'terms'->>'monthly_interest_rate')::numeric IS DISTINCT FROM l.monthly_interest_rate
      OR (r->'terms'->>'tenure_months')::integer IS DISTINCT FROM l.tenure_months
      OR r->'monitoring'->>'valuation_method' IS DISTINCT FROM p.valuation_method
      OR (r->'monitoring'->>'maximum_ltv_ratio')::numeric IS DISTINCT FROM p.maximum_ltv_ratio
      OR (e.payload->'values'->>'principal')::numeric IS DISTINCT FROM NEW.gross_principal
      OR (e.payload->'values'->>'net_cash')::numeric IS DISTINCT FROM NEW.net_disbursed
      OR (e.payload->'values'->>'advance_interest')::numeric IS DISTINCT FROM NEW.advance_interest
      OR (e.payload->'values'->>'fees')::numeric IS DISTINCT FROM NEW.deducted_fees
      OR NEW.evidence->'tranches' IS DISTINCT FROM e.payload->'disbursal'->'tranches'
      OR NEW.gross_principal<>NEW.net_disbursed+NEW.advance_interest+NEW.deducted_fees
    THEN RAISE EXCEPTION 'Recorded payout requires matching contract, source and monitoring evidence'; END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER loans_disbursal_basis_guard BEFORE INSERT ON loans_pawnloandisbursalsnapshot
  FOR EACH ROW EXECUTE FUNCTION loans_disbursal_basis_guard();
"""


class Migration(migrations.Migration):
    dependencies = [("loans", "0040_khata_labels")]
    operations = [
        migrations.AddField(model_name="loanpolicysnapshot", name="basis",
            field=models.CharField(choices=[("ORIGINATION", "Origination policy"),
                ("RECORDED_CONTRACT", "Recorded contract and monitoring selection")], default="ORIGINATION", max_length=24)),
        migrations.AddConstraint(model_name="loanpolicysnapshot", constraint=models.CheckConstraint(
            condition=models.Q(basis__in=("ORIGINATION", "RECORDED_CONTRACT")), name="loans_policy_basis_valid")),
        migrations.AddField(model_name="pawnloandisbursalsnapshot", name="basis",
            field=models.CharField(choices=[("APPROVED", "Approved lending decision"),
                ("RECORDED", "Previously paid on paper")], default="APPROVED", max_length=16)),
        migrations.AlterField(model_name="pawnloandisbursalsnapshot", name="approval_snapshot",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="disbursal_snapshots", to="loans.pawnloanapprovalsnapshot")),
        migrations.AddConstraint(model_name="pawnloandisbursalsnapshot", constraint=models.CheckConstraint(
            condition=models.Q(basis="APPROVED", approval_snapshot__isnull=False)
                | models.Q(basis="RECORDED", approval_snapshot__isnull=True), name="loans_disbursal_approval_basis")),
        migrations.RunSQL(GUARD, """
            DROP TRIGGER loans_disbursal_basis_guard ON loans_pawnloandisbursalsnapshot;
            DROP FUNCTION loans_disbursal_basis_guard();
        """),
    ]
