"""Allow audited duplicate consolidation; financial and source evidence stay frozen."""
from importlib import import_module
from django.db import migrations


prior = import_module("apps.tenant_apps.loans.migrations.0075_recorded_borrower_correction")
OLD_CORRECTION = prior.Migration.operations[1].sql.split("CREATE TRIGGER loans_borrower_correction_log_guard")[0]
OLD_CORRECTION = OLD_CORRECTION.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)
NEW_CORRECTION = OLD_CORRECTION.replace(
    "OR NEW.actor_id IS NULL OR NEW.from_state <> 'ACTIVE' OR NEW.to_state <> 'ACTIVE'",
    """OR NEW.actor_id IS NULL
   OR (coalesce(evidence->>'party_merge','false') <> 'true' AND (NEW.from_state <> 'ACTIVE' OR NEW.to_state <> 'ACTIVE'))
   OR (evidence->>'party_merge' = 'true' AND (
      NEW.from_state IS DISTINCT FROM NEW.to_state
      OR NOT EXISTS (SELECT 1 FROM loans_pawnloan l JOIN party_party p ON p.id=l.borrower_id
         JOIN party_party t ON t.id=(evidence#>>'{after,id}')::bigint
         WHERE l.id=NEW.loan_id AND l.workspace_id=NEW.workspace_id AND l.state=NEW.from_state
           AND p.workspace_id=l.workspace_id AND t.workspace_id=l.workspace_id
           AND p.id=(evidence#>>'{before,id}')::bigint AND p.status='ARCHIVED' AND t.status<>'ARCHIVED'
           AND p.metadata->>'merged_into_party_id'=t.id::text
           AND t.metadata->'merged_from_party_ids' @> jsonb_build_array(p.id))))"""
)
assert NEW_CORRECTION != OLD_CORRECTION

OLD_CLOSED = import_module("apps.tenant_apps.loans.migrations.0065_closed_position_admission").GUARD
OLD_CLOSED = OLD_CLOSED[OLD_CLOSED.index("CREATE FUNCTION loans_closed_position_immutable()"):OLD_CLOSED.index("CREATE TRIGGER loans_closed_position_immutable")]
OLD_CLOSED = OLD_CLOSED.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)
NEW_CLOSED = OLD_CLOSED.replace(
    "IF OLD.is_imported_closed_position OR NEW.is_imported_closed_position THEN",
    """IF OLD.is_imported_closed_position AND NEW.is_imported_closed_position
   AND (to_jsonb(NEW)-'borrower_id')=(to_jsonb(OLD)-'borrower_id')
   AND EXISTS (SELECT 1 FROM loans_loanchangelog c WHERE c.loan_id=OLD.id AND c.workspace_id=OLD.workspace_id
      AND c.event_kind='BORROWER_CORRECTED' AND c.metadata#>>'{borrower_correction,party_merge}'='true'
      AND c.metadata#>>'{borrower_correction,before,id}'=OLD.borrower_id::text
      AND c.metadata#>>'{borrower_correction,after,id}'=NEW.borrower_id::text)
 THEN RETURN NEW; END IF;
 IF OLD.is_imported_closed_position OR NEW.is_imported_closed_position THEN"""
)

OLD_KHATA = import_module("apps.tenant_apps.loans.migrations.0037_khata_custody_settlement").FOUNDATION
NEW_KHATA = OLD_KHATA.replace("ELSIF TG_TABLE_NAME = 'loans_khataaccount' THEN", """
              ELSIF TG_TABLE_NAME = 'loans_khataaccount' THEN
                IF TG_OP='UPDATE' AND NEW.borrower_id<>OLD.borrower_id
                  AND (to_jsonb(NEW)-'borrower_id')=(to_jsonb(OLD)-'borrower_id')
                  AND EXISTS (SELECT 1 FROM party_party p JOIN party_party t ON t.id=NEW.borrower_id
                    WHERE p.id=OLD.borrower_id AND p.workspace_id=OLD.workspace_id AND t.workspace_id=OLD.workspace_id
                      AND p.status='ARCHIVED' AND t.status<>'ARCHIVED'
                      AND p.metadata->>'merged_into_party_id'=t.id::text
                      AND t.metadata->'merged_from_party_ids' @> jsonb_build_array(p.id))
                  AND EXISTS (SELECT 1 FROM orgs_auditlog a WHERE a.company_id=OLD.workspace_id
                    AND a.user_id IS NOT NULL AND a.action='DATA_UPDATE' AND a.success
                    AND a.data->'party_merge'=jsonb_build_object('source_id',OLD.borrower_id,
                      'target_id',NEW.borrower_id,'khata_account_id',OLD.id))
                THEN RETURN NEW; END IF;""")
assert NEW_KHATA != OLD_KHATA

AUDIT = """
CREATE FUNCTION loans_party_merge_audit_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.data ? 'party_merge' OR (TG_OP='UPDATE' AND NEW.data ? 'party_merge') THEN
   RAISE EXCEPTION 'Party merge account audit must be appended and retained';
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER loans_party_merge_audit_guard BEFORE UPDATE OR DELETE ON orgs_auditlog
FOR EACH ROW EXECUTE FUNCTION loans_party_merge_audit_guard();
"""
REVERSE = """
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM loans_loanchangelog WHERE metadata#>>'{borrower_correction,party_merge}'='true')
    OR EXISTS (SELECT 1 FROM orgs_auditlog WHERE data ? 'party_merge') THEN
   RAISE EXCEPTION 'Retained Party consolidation evidence prevents downgrade';
 END IF;
END; $$;
DROP TRIGGER loans_party_merge_audit_guard ON orgs_auditlog;
DROP FUNCTION loans_party_merge_audit_guard();
""" + OLD_CORRECTION + OLD_CLOSED + OLD_KHATA


class Migration(migrations.Migration):
    dependencies = [("loans", "0077_corrected_borrower_notice_intent")]
    operations = [migrations.RunSQL(NEW_CORRECTION + NEW_CLOSED + NEW_KHATA + AUDIT, REVERSE)]
