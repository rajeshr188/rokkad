"""Retain direct agreement revisions without changing original approval evidence."""
from django.db import migrations, models


GUARD = """
CREATE FUNCTION loans_corrected_agreement_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE prior loans_pawnloandisbursalsnapshot%ROWTYPE;
 e loans_pawnloanevent%ROWTYPE; c jsonb;
BEGIN
 IF NEW.basis<>'CORRECTED' THEN RETURN NEW; END IF;
 c:=NEW.evidence->'agreement_correction';
 SELECT * INTO prior FROM loans_pawnloandisbursalsnapshot
 WHERE id=(c->>'disbursal_snapshot_id')::bigint AND loan_id=NEW.loan_id AND workspace_id=NEW.workspace_id;
 IF NOT FOUND THEN RAISE EXCEPTION 'Corrected agreement requires its own retained source snapshot'; END IF;
 SELECT * INTO e FROM loans_pawnloanevent
 WHERE id=NEW.loan_event_id AND loan_id=NEW.loan_id AND workspace_id=NEW.workspace_id;
 IF NOT FOUND OR e.event_kind<>'DISBURSAL'
 OR c->>'schema' IS DISTINCT FROM 'loan-agreement-correction/1'
 OR c->>'role' IS DISTINCT FROM 'AGREEMENT'
 OR (c->>'revision')::integer IS DISTINCT FROM COALESCE((prior.evidence#>>'{agreement_correction,revision}')::integer,1)+1
 OR c->>'source_event_id' IS DISTINCT FROM prior.loan_event_id::text
 OR e.payload->'agreement_correction' IS DISTINCT FROM c
 OR e.payload#>>'{disbursal,basis}' IS DISTINCT FROM 'CORRECTED'
 OR e.payload#>>'{disbursal,policy_snapshot_id}' IS DISTINCT FROM NEW.policy_snapshot_id::text
 OR NEW.approval_snapshot_id IS DISTINCT FROM prior.approval_snapshot_id
 OR NEW.created_by_id IS NULL OR NEW.created_by_id IS DISTINCT FROM e.created_by_id
 OR COALESCE(length(trim(c->>'reason')),0)=0 OR COALESCE(length(trim(c->>'reference')),0)=0
 OR COALESCE(length(c->>'request_sha256'),0)<>64
 OR COALESCE(length(c->>'request_key'),0) NOT BETWEEN 1 AND 80
 OR NOT EXISTS (SELECT 1 FROM loans_loanpolicysnapshot p WHERE p.id=NEW.policy_snapshot_id
   AND p.loan_id=NEW.loan_id AND p.workspace_id=NEW.workspace_id AND p.basis='ORIGINATION')
 OR (SELECT to_jsonb(p)-ARRAY['id','loan_id','workspace_id','created_at'] FROM loans_loanpolicysnapshot p WHERE p.id=NEW.policy_snapshot_id)
    IS DISTINCT FROM (SELECT to_jsonb(p)-ARRAY['id','loan_id','workspace_id','created_at'] FROM loans_loanpolicysnapshot p WHERE p.id=prior.policy_snapshot_id)
 OR NOT EXISTS (SELECT 1 FROM loans_pawnloanevent r WHERE r.reversal_of_id=prior.loan_event_id
   AND r.workspace_id=NEW.workspace_id AND r.loan_id=NEW.loan_id
   AND r.payload#>>'{agreement_correction,request_key}'=c->>'request_key')
 OR NEW.evidence->'tranches' IS DISTINCT FROM e.payload#>'{disbursal,tranches}'
 OR (e.payload#>>'{values,principal}')::numeric IS DISTINCT FROM NEW.gross_principal
 OR (e.payload#>>'{values,advance_interest}')::numeric IS DISTINCT FROM NEW.advance_interest
 OR (e.payload#>>'{values,fees}')::numeric IS DISTINCT FROM NEW.deducted_fees
 OR (e.payload#>>'{values,net_cash}')::numeric IS DISTINCT FROM NEW.net_disbursed
 OR NEW.gross_principal<>NEW.net_disbursed+NEW.advance_interest+NEW.deducted_fees
 THEN RAISE EXCEPTION 'Corrected agreement evidence does not reconcile'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER loans_corrected_agreement_guard BEFORE INSERT ON loans_pawnloandisbursalsnapshot
FOR EACH ROW EXECUTE FUNCTION loans_corrected_agreement_guard();
CREATE FUNCTION loans_agreement_correction_log_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.metadata ? 'agreement_correction' OR (TG_OP='UPDATE' AND NEW.metadata ? 'agreement_correction')
 THEN RAISE EXCEPTION 'Agreement correction evidence is append only'; END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
END $$;
CREATE TRIGGER loans_agreement_correction_log_guard BEFORE UPDATE OR DELETE ON loans_loanchangelog
FOR EACH ROW EXECUTE FUNCTION loans_agreement_correction_log_guard();
CREATE UNIQUE INDEX loans_agreement_correction_request_uniq
ON loans_loanchangelog (workspace_id,loan_id,(metadata#>>'{agreement_correction,request_key}'))
WHERE metadata ? 'agreement_correction';
"""


def refuse_populated_reverse(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT EXISTS(SELECT 1 FROM loans_pawnloandisbursalsnapshot WHERE basis='CORRECTED')")
        if cursor.fetchone()[0]:
            raise RuntimeError("Retained corrected agreements require compatible readers; stop new writes instead of downgrading.")


class Migration(migrations.Migration):
    dependencies = [("loans", "0078_collateral_fact_corrections")]
    operations = [
        migrations.RemoveConstraint(model_name="pawnloandisbursalsnapshot", name="loans_disbursal_approval_basis"),
        migrations.AlterField(model_name="pawnloandisbursalsnapshot", name="basis", field=models.CharField(
            choices=[("APPROVED", "Approved lending decision"), ("RECORDED", "Previously paid on paper"),
                ("CORRECTED", "Reviewed correction of original lending facts")], default="APPROVED", max_length=16)),
        migrations.AddConstraint(model_name="pawnloandisbursalsnapshot", constraint=models.CheckConstraint(
            condition=models.Q(basis__in=("APPROVED", "CORRECTED"), approval_snapshot__isnull=False)
                | models.Q(basis="RECORDED", approval_snapshot__isnull=True), name="loans_disbursal_approval_basis")),
        migrations.RemoveConstraint(model_name="pawnloaninterestaccrual", name="loans_accrual_loan_period_uniq"),
        migrations.AddField(model_name="pawnloaninterestaccrual", name="agreement_revision", field=models.PositiveIntegerField(default=1)),
        migrations.AddConstraint(model_name="pawnloaninterestaccrual", constraint=models.UniqueConstraint(
            fields=("loan", "period_number", "agreement_revision"), name="loans_accrual_loan_period_revision_uniq")),
        migrations.RunSQL(GUARD, """
DROP INDEX loans_agreement_correction_request_uniq;
DROP TRIGGER loans_agreement_correction_log_guard ON loans_loanchangelog;
DROP FUNCTION loans_agreement_correction_log_guard();
DROP TRIGGER loans_corrected_agreement_guard ON loans_pawnloandisbursalsnapshot;
DROP FUNCTION loans_corrected_agreement_guard();
"""),
        migrations.RunPython(migrations.RunPython.noop, refuse_populated_reverse),
    ]
