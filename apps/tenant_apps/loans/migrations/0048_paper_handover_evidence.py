from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("loans", "0047_paper_backlog_checkpoint")]
    operations = [migrations.RunSQL("""
CREATE FUNCTION loans_paper_handover_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE r loans_pawnloanrelease%ROWTYPE; l loans_pawnloan%ROWTYPE; ids jsonb;
BEGIN
 IF TG_OP <> 'INSERT' AND OLD.metadata->>'profile' = 'paper-handover-confirmation/1'
 THEN RAISE EXCEPTION 'Paper handover evidence is immutable'; END IF;
 IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
 IF NEW.metadata->>'profile' = 'paper-handover-confirmation/1' THEN
  IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'Paper handover evidence must be appended'; END IF;
  SELECT * INTO l FROM loans_pawnloan WHERE id=NEW.loan_id AND workspace_id=NEW.workspace_id;
  SELECT * INTO r FROM loans_pawnloanrelease WHERE id=(NEW.metadata->>'release_id')::bigint
    AND loan_id=NEW.loan_id AND workspace_id=NEW.workspace_id;
  ids := NEW.metadata->'custody_event_ids';
  IF l.id IS NULL OR l.state <> 'CLOSED' OR r.id IS NULL OR NEW.actor_id IS NULL
    OR NEW.event_kind <> 'RELEASE_COMPLETED' OR NEW.metadata->>'facts_sha256' !~ '^[0-9a-f]{64}$'
    OR btrim(COALESCE(NEW.metadata->>'request_key','')) = ''
    OR btrim(COALESCE(NEW.metadata#>>'{facts,recipient}','')) = ''
    OR btrim(COALESCE(NEW.metadata#>>'{facts,reference}','')) = ''
    OR (NEW.metadata#>>'{facts,date}')::date < r.effective_date
    OR jsonb_typeof(ids) IS DISTINCT FROM 'array' OR jsonb_array_length(ids)=0
  THEN RAISE EXCEPTION 'Invalid paper handover evidence'; END IF;
  IF (SELECT count(*) FROM loans_pawncollateralcustodyevent c
      JOIN loans_pawncollateralitem i ON i.id=c.collateral_item_id
      WHERE c.id IN (SELECT value::bigint FROM jsonb_array_elements_text(ids))
      AND c.release_id=r.id AND c.workspace_id=NEW.workspace_id AND i.loan_id=NEW.loan_id
      AND c.from_state='PAPER_CLOSED' AND c.to_state='WITH_CUSTOMER'
      AND c.effective_date=(NEW.metadata#>>'{facts,date}')::date
      AND c.actor_id=NEW.actor_id) <> jsonb_array_length(ids)
  THEN RAISE EXCEPTION 'Paper handover must retain matching custody evidence'; END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER loans_paper_handover_guard BEFORE INSERT OR UPDATE OR DELETE ON loans_loanchangelog
FOR EACH ROW EXECUTE FUNCTION loans_paper_handover_guard();
CREATE UNIQUE INDEX loans_paper_handover_request_uniq ON loans_loanchangelog
 (loan_id, (metadata->>'request_key')) WHERE metadata->>'profile'='paper-handover-confirmation/1';
""", "DROP INDEX loans_paper_handover_request_uniq; DROP TRIGGER loans_paper_handover_guard ON loans_loanchangelog; DROP FUNCTION loans_paper_handover_guard();")]
