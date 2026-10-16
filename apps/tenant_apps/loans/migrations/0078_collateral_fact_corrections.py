from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("loans", "0077_corrected_borrower_notice_intent")]
    operations = [
        migrations.AlterField(
            model_name="loanchangelog", name="event_kind",
            field=models.CharField(max_length=40, choices=[
                ("DRAFT_CREATED", "Draft Created"), ("DRAFT_UPDATED", "Draft Updated"),
                ("BORROWER_CORRECTED", "Borrower Corrected"), ("COLLATERAL_CORRECTED", "Collateral Corrected"),
                ("LICENSE_TRANSFERRED", "License Transferred"), ("APPROVED", "Approved"),
                ("RETURNED_TO_DRAFT", "Returned To Draft"), ("CANCELLED", "Cancelled"), ("DISBURSED", "Disbursed"),
                ("REPAYMENT_RECORDED", "Repayment Recorded"), ("ACCRUAL_FINALIZED", "Accrual Finalized"),
                ("INTEREST_CAPITALIZED", "Interest Capitalized"), ("RELEASE_COMPLETED", "Release Completed"),
                ("AUCTION_INITIATED", "Auction Initiated"), ("AUCTION_STARTED", "Auction Started"),
                ("AUCTION_CANCELLED", "Auction Cancelled"), ("AUCTION_COMPLETED", "Auction Completed"),
                ("AUCTION_REVERSED", "Auction Reversed"), ("RENEWAL_COMPLETED", "Renewal Completed"),
                ("RENEWAL_SUCCESSOR_ACTIVATED", "Renewal Successor Activated"), ("RENEWAL_REVERSED", "Renewal Reversed"),
                ("CLOSED", "Closed"), ("REVERSAL_RECORDED", "Reversal Recorded"),
            ]),
        ),
        migrations.RunSQL("""
CREATE FUNCTION loans_collateral_correction_log_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE evidence jsonb;
BEGIN
 IF TG_OP <> 'INSERT' THEN
   IF OLD.event_kind = 'COLLATERAL_CORRECTED' OR OLD.metadata ? 'collateral_correction' THEN
     RAISE EXCEPTION 'Collateral correction evidence is immutable';
   END IF;
   IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
   IF NEW.event_kind = 'COLLATERAL_CORRECTED' OR NEW.metadata ? 'collateral_correction' THEN
     RAISE EXCEPTION 'Collateral correction evidence must be appended';
   END IF;
   RETURN NEW;
 END IF;
 IF NEW.event_kind <> 'COLLATERAL_CORRECTED' AND NOT NEW.metadata ? 'collateral_correction' THEN RETURN NEW; END IF;
 evidence := NEW.metadata->'collateral_correction';
 IF NEW.event_kind <> 'COLLATERAL_CORRECTED' OR evidence->>'schema' IS DISTINCT FROM 'collateral-fact-correction/1'
   OR NEW.actor_id IS NULL OR NEW.from_state NOT IN ('ACTIVE','CLOSED') OR NEW.to_state IS DISTINCT FROM NEW.from_state
   OR coalesce(btrim(NEW.reason), '') = '' OR coalesce(btrim(evidence->>'reference'), '') = ''
   OR evidence->>'reason' IS DISTINCT FROM NEW.reason OR coalesce(btrim(evidence->>'request_key'), '') = ''
   OR coalesce(evidence->>'request_sha256', '') !~ '^[0-9a-f]{64}$'
   OR coalesce(evidence->>'source_fingerprint', '') !~ '^[0-9a-f]{64}$'
   OR jsonb_typeof(evidence->'item_id') IS DISTINCT FROM 'number'
   OR jsonb_typeof(evidence->'before') IS DISTINCT FROM 'object'
   OR jsonb_typeof(evidence->'after') IS DISTINCT FROM 'object'
   OR evidence->'before' = evidence->'after'
   OR jsonb_typeof(evidence->'valuation_changed') IS DISTINCT FROM 'boolean'
   OR jsonb_typeof(evidence->'appraisal_version') IS DISTINCT FROM 'number'
   OR NOT EXISTS (SELECT 1 FROM loans_pawncollateralitem WHERE id=(evidence->>'item_id')::bigint
       AND loan_id=NEW.loan_id AND workspace_id=NEW.workspace_id)
 THEN RAISE EXCEPTION 'Invalid or foreign collateral correction evidence'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER loans_collateral_correction_log_guard BEFORE INSERT OR UPDATE OR DELETE ON loans_loanchangelog
FOR EACH ROW EXECUTE FUNCTION loans_collateral_correction_log_guard();
CREATE UNIQUE INDEX loans_collateral_correction_request_idx ON loans_loanchangelog
 (workspace_id, loan_id, (metadata#>>'{collateral_correction,request_key}')) WHERE event_kind='COLLATERAL_CORRECTED';
CREATE FUNCTION loans_corrected_collateral_identity_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='UPDATE' AND NEW.id=OLD.id AND NEW.loan_id=OLD.loan_id AND NEW.workspace_id=OLD.workspace_id THEN RETURN NEW; END IF;
 IF EXISTS (SELECT 1 FROM loans_loanchangelog WHERE workspace_id=OLD.workspace_id AND loan_id=OLD.loan_id
   AND event_kind='COLLATERAL_CORRECTED' AND (metadata#>>'{collateral_correction,item_id}')::bigint=OLD.id)
 THEN RAISE EXCEPTION 'Corrected collateral identities must be retained'; END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER loans_corrected_collateral_identity_guard BEFORE UPDATE OR DELETE ON loans_pawncollateralitem
FOR EACH ROW EXECUTE FUNCTION loans_corrected_collateral_identity_guard();
""", """
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM loans_loanchangelog WHERE event_kind='COLLATERAL_CORRECTED') THEN
   RAISE EXCEPTION 'Retained collateral correction evidence prevents downgrade';
 END IF;
END; $$;
DROP INDEX loans_collateral_correction_request_idx;
DROP TRIGGER loans_collateral_correction_log_guard ON loans_loanchangelog;
DROP FUNCTION loans_collateral_correction_log_guard();
DROP TRIGGER loans_corrected_collateral_identity_guard ON loans_pawncollateralitem;
DROP FUNCTION loans_corrected_collateral_identity_guard();
"""),
    ]
