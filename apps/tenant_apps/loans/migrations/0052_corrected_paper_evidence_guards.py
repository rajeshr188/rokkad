from importlib import import_module
from django.db import migrations


handover = import_module("apps.tenant_apps.loans.migrations.0048_paper_handover_evidence").Migration.operations[0].sql
handover = handover[:handover.index("CREATE TRIGGER")].replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION")
corrected_handover = handover.replace("ids jsonb;", "ids jsonb; closing_day date;").replace(
    "  ids := NEW.metadata->'custody_event_ids';",
    """  SELECT COALESCE((SELECT e.effective_date FROM loans_pawnloanevent e
      WHERE e.loan_id=NEW.loan_id AND e.workspace_id=NEW.workspace_id AND e.event_kind='RELEASE_RECEIPT'
      AND e.payload#>>'{history_correction,role}'='SETTLEMENT'
      AND (e.payload#>>'{history_correction,root_event_id}')::bigint=r.loan_event_id
      AND NOT EXISTS(SELECT 1 FROM loans_pawnloanevent x WHERE x.reversal_of_id=e.id)
      ORDER BY e.id DESC LIMIT 1),r.effective_date) INTO closing_day;
  ids := NEW.metadata->'custody_event_ids';""").replace("< r.effective_date", "< closing_day")
log_guard = import_module("apps.tenant_apps.loans.migrations.0049_recorded_contract_correction_log").Migration.operations[0].sql
log_guard = log_guard[:log_guard.index("CREATE TRIGGER")].replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION")


class Migration(migrations.Migration):
    dependencies = [("loans", "0051_renewal_opening_revisions")]
    operations = [migrations.RunSQL(corrected_handover + log_guard.replace("= 'CONTRACT'", "IN ('CONTRACT','SETTLEMENT_FACTS')"),
        handover + log_guard)]
