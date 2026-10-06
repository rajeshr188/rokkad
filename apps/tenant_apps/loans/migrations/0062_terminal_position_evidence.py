"""A terminal checkpoint is a sole immutable position, never a settlement."""
from importlib import import_module
from django.db import migrations

OLD = import_module("apps.tenant_apps.loans.migrations.0061_multi_item_archive_admission").NEW
NEW = OLD.replace("('archive-admission/1','archive-admission/2')", "('archive-admission/1','archive-admission/2','archive-terminal-admission/1')").replace(
    "OR NOT EXISTS (SELECT 1 FROM loans_pawnloan l JOIN loans_loanpolicysnapshot p ON p.loan_id=l.id",
    "OR NOT ((NEW.document->>'profile' IN ('archive-admission/1','archive-admission/2') AND EXISTS (SELECT 1 FROM loans_pawnloan l JOIN loans_loanpolicysnapshot p ON p.loan_id=l.id", 1).replace(
    "AND d.evidence#>>'{recording,archive_admission,sha256}'=a.source_sha256)",
    """AND d.evidence#>>'{recording,archive_admission,sha256}'=a.source_sha256))
    OR (NEW.document->>'profile'='archive-terminal-admission/1' AND EXISTS (
      SELECT 1 FROM loans_pawnloan l JOIN loans_loanpolicysnapshot p ON p.id=l.policy_snapshot_id
      JOIN loans_pawnloanevent e ON e.loan_id=l.id AND e.workspace_id=l.workspace_id
      WHERE l.id=NEW.loan_id AND l.workspace_id=NEW.workspace_id AND l.state='CLOSED'
       AND p.basis='RECORDED_CONTRACT' AND e.event_kind='MIGRATION_OPENING'
       AND e.payload#>>'{opening,profile}'='loan-terminal-evidence/1'
       AND e.payload#>>'{opening,review,admission_sha256}'=NEW.source_sha256
       AND e.payload#>>'{opening,review,archive,id}'=a.id::text
       AND e.payload#>>'{opening,review,archive,sha256}'=a.source_sha256
       AND e.payload->'values'='{"principal":"0","interest":"0","fees":"0"}'::jsonb)))""")

GUARD = """
CREATE FUNCTION loans_terminal_position_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE l loans_pawnloan%ROWTYPE;
BEGIN
 IF EXISTS (SELECT 1 FROM loans_pawnloanevent e WHERE e.loan_id=NEW.loan_id AND e.workspace_id=NEW.workspace_id
   AND e.payload#>>'{opening,profile}'='loan-terminal-evidence/1')
 THEN RAISE EXCEPTION 'Terminal checkpoint cannot acquire invented financial transactions'; END IF;
 IF NEW.payload#>>'{opening,profile}'='loan-terminal-evidence/1' THEN
  SELECT * INTO l FROM loans_pawnloan WHERE id=NEW.loan_id AND workspace_id=NEW.workspace_id;
  IF NOT FOUND OR l.state<>'CLOSED' OR NEW.event_kind<>'MIGRATION_OPENING' OR NEW.reversal_of_id IS NOT NULL
   OR EXISTS (SELECT 1 FROM loans_pawnloanevent WHERE loan_id=l.id)
   OR NEW.payload->'values' IS DISTINCT FROM '{"principal":"0","interest":"0","fees":"0"}'::jsonb
   OR NEW.payload#>>'{opening,review,profile}' IS DISTINCT FROM 'loan-terminal-review/1'
   OR NEW.payload#>>'{opening,review,data,closed_on}' IS DISTINCT FROM NEW.effective_date::text
   OR NEW.payload#>>'{opening,review,mapping,workspace_id}' IS DISTINCT FROM l.workspace_id::text
   OR NEW.payload#>>'{source_identity,loan_id}' IS DISTINCT FROM l.id::text
   OR NEW.payload#>'{opening,review,data,confirmed_closed}' IS DISTINCT FROM 'true'::jsonb
   OR NEW.payload#>'{opening,review,data,confirmed_agreement}' IS DISTINCT FROM 'true'::jsonb
   OR NOT EXISTS (SELECT 1 FROM loans_loanpolicysnapshot WHERE id=l.policy_snapshot_id
       AND loan_id=l.id AND workspace_id=l.workspace_id AND basis='RECORDED_CONTRACT' AND policy_version=2)
  THEN RAISE EXCEPTION 'Invalid verified terminal checkpoint'; END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER loans_terminal_position_guard BEFORE INSERT ON loans_pawnloanevent
FOR EACH ROW EXECUTE FUNCTION loans_terminal_position_guard();

CREATE FUNCTION loans_terminal_state_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.state<>'CLOSED' AND EXISTS (SELECT 1 FROM loans_pawnloanevent e WHERE e.loan_id=NEW.id
   AND e.workspace_id=NEW.workspace_id AND e.payload#>>'{opening,profile}'='loan-terminal-evidence/1')
 THEN RAISE EXCEPTION 'Terminal checkpoint cannot be reopened as a reversed settlement'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER loans_terminal_state_guard BEFORE UPDATE ON loans_pawnloan
FOR EACH ROW EXECUTE FUNCTION loans_terminal_state_guard();
"""
REVERSE = """
DROP TRIGGER loans_terminal_state_guard ON loans_pawnloan;
DROP FUNCTION loans_terminal_state_guard();
DROP TRIGGER loans_terminal_position_guard ON loans_pawnloanevent;
DROP FUNCTION loans_terminal_position_guard();
"""


class Migration(migrations.Migration):
    dependencies = [("loans", "0061_multi_item_archive_admission")]
    operations = [migrations.RunSQL(NEW, OLD), migrations.RunSQL(GUARD, REVERSE)]
