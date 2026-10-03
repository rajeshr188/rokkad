from django.db import migrations, models
import django.db.models.deletion
from apps.tenant_apps.loans.db_guards.reversals import FORWARD_SQL


start = FORWARD_SQL.index("CREATE OR REPLACE FUNCTION loans_guard_funding_custody_insert()")
movement_guard = FORWARD_SQL[start:FORWARD_SQL.index("$$;", start)+3]
restatement_guard = movement_guard.replace("    IF projected_state IS DISTINCT FROM NEW.from_state THEN", """
    IF NEW.restatement_of_id IS NOT NULL THEN
        SELECT * INTO original FROM loans_pawncollateralcustodyevent WHERE id=NEW.restatement_of_id;
        IF original.id IS NULL OR original.workspace_id<>NEW.workspace_id
          OR original.collateral_item_id<>NEW.collateral_item_id OR NEW.actor_id IS NULL
          OR original.from_state<>NEW.from_state OR original.to_state<>NEW.to_state
          OR original.release_id IS DISTINCT FROM NEW.release_id OR original.renewal_id IS DISTINCT FROM NEW.renewal_id
          OR (NEW.release_id IS NULL AND NEW.renewal_id IS NULL)
          OR NEW.auction_id IS NOT NULL OR NEW.release_reversal_id IS NOT NULL OR NEW.renewal_reversal_id IS NOT NULL
          OR NEW.funding_pledge_id IS NOT NULL OR NEW.funding_return_id IS NOT NULL
          OR NEW.funding_pledge_reversal_id IS NOT NULL OR NEW.funding_return_reversal_id IS NOT NULL
          OR NEW.auction_reversal_id IS NOT NULL OR NEW.effective_date>CURRENT_DATE
          OR NOT EXISTS(SELECT 1 FROM loans_pawncollateralitem i JOIN loans_pawnloan l ON l.id=i.loan_id
              JOIN loans_loanpolicysnapshot p ON p.id=l.policy_snapshot_id
              WHERE i.id=NEW.collateral_item_id AND p.basis='RECORDED_CONTRACT')
        THEN RAISE EXCEPTION 'Invalid dated paper custody restatement'; END IF;
        RETURN NEW;
    END IF;
    IF projected_state IS DISTINCT FROM NEW.from_state THEN""")
binding_guard = """
CREATE FUNCTION loans_custody_restatement_binding() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE root_id bigint; owner_id bigint;
BEGIN
 IF NEW.restatement_of_id IS NULL THEN RETURN NEW; END IF;
 IF NEW.release_id IS NOT NULL THEN
  SELECT loan_event_id, loan_id INTO root_id, owner_id FROM loans_pawnloanrelease WHERE id=NEW.release_id;
 ELSE
  SELECT settlement_event_id, source_loan_id INTO root_id, owner_id FROM loans_pawnloanrenewal WHERE id=NEW.renewal_id;
 END IF;
 IF NOT EXISTS(SELECT 1 FROM loans_pawnloanevent e WHERE e.loan_id=owner_id AND e.workspace_id=NEW.workspace_id
   AND e.effective_date=NEW.effective_date AND e.created_by_id=NEW.actor_id
   AND e.payload#>>'{history_correction,schema}'='recorded-history-correction/1'
   AND e.payload#>>'{history_correction,role}'='SETTLEMENT'
   AND e.payload#>>'{history_correction,operation}' IN ('CONTRACT','SETTLEMENT_FACTS')
   AND btrim(COALESCE(e.payload#>>'{history_correction,reason}',''))<>''
   AND (e.payload#>>'{history_correction,root_event_id}')::bigint=root_id
   AND e.payload#>'{history_correction,custody_restatement,replacements}' @> to_jsonb(ARRAY[NEW.id])
   AND e.payload#>'{history_correction,custody_restatement,superseded}' @> to_jsonb(ARRAY[NEW.restatement_of_id])
   AND e.payload#>>'{history_correction,custody_restatement,actual_movement}'='false')
 THEN RAISE EXCEPTION 'Dated custody restatement requires its canonical financial correction'; END IF;
 RETURN NEW;
END; $$;
CREATE CONSTRAINT TRIGGER loans_custody_restatement_binding AFTER INSERT ON loans_pawncollateralcustodyevent
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION loans_custody_restatement_binding();
"""


class Migration(migrations.Migration):
    dependencies = [("loans", "0052_corrected_paper_evidence_guards")]
    operations = [migrations.AddField(model_name="pawncollateralcustodyevent", name="restatement_of",
        field=models.OneToOneField(null=True, blank=True, on_delete=django.db.models.deletion.PROTECT,
            related_name="dated_restatement", to="loans.pawncollateralcustodyevent")),
        migrations.RunSQL(restatement_guard+binding_guard,
            "DROP TRIGGER loans_custody_restatement_binding ON loans_pawncollateralcustodyevent; "
            "DROP FUNCTION loans_custody_restatement_binding();"+movement_guard)]
