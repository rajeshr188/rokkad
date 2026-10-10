"""Versioned source references for future positions; no posted JSON is rewritten."""
from importlib import import_module

from django.db import migrations


prior = import_module("apps.tenant_apps.loans.migrations.0065_closed_position_admission")
business_date = import_module("apps.tenant_apps.loans.migrations.0067_closed_position_business_date")
OLD_ARCHIVE = prior.NEW_ARCHIVE
COMPACT_ARCHIVE = """
 IF NEW.document->>'profile'='loan-closed-position-admission/2' THEN
  IF NEW.document#>'{position,retained_evidence}' IS DISTINCT FROM 'null'::jsonb
  THEN RAISE EXCEPTION 'Compact position cannot embed retained source'; END IF;
  IF NEW.archive_evidence_id IS NOT NULL THEN
   SELECT * INTO a FROM loans_historicalloanevidence WHERE id=NEW.archive_evidence_id AND workspace_id=NEW.workspace_id;
   IF NOT FOUND OR NEW.source_namespace IS DISTINCT FROM a.source_namespace
    OR NEW.document#>>'{archive,id}' IS DISTINCT FROM a.id::text
    OR NEW.document#>>'{archive,sha256}' IS DISTINCT FROM a.source_sha256
    OR NEW.document#>>'{position,source,namespace}' IS DISTINCT FROM a.source_namespace::text
    OR NEW.document#>>'{position,source,system}' IS DISTINCT FROM a.source_system
    OR NEW.document#>>'{position,source,loan_id}' IS DISTINCT FROM a.source_id
    OR jsonb_typeof(NEW.document->'archive') IS DISTINCT FROM 'object'
    OR (SELECT count(*) FROM jsonb_object_keys(NEW.document->'archive'))<>3
    OR jsonb_typeof(NEW.document#>'{archive,id}') IS DISTINCT FROM 'number'
    OR jsonb_typeof(NEW.document#>'{archive,snapshots}') IS DISTINCT FROM 'array'
    OR jsonb_array_length(NEW.document#>'{archive,snapshots}')=0
    OR NOT NEW.document#>'{archive,snapshots}' @> jsonb_build_array(jsonb_build_array(a.id,a.source_sha256))
   THEN RAISE EXCEPTION 'Invalid compact closed-position archive binding'; END IF;
   IF EXISTS (
    SELECT 1 FROM jsonb_array_elements(NEW.document#>'{archive,snapshots}') pair
    WHERE jsonb_typeof(pair) IS DISTINCT FROM 'array' OR jsonb_array_length(pair)<>2
     OR jsonb_typeof(pair->0) IS DISTINCT FROM 'number'
     OR jsonb_typeof(pair->1) IS DISTINCT FROM 'string'
     OR NOT EXISTS (SELECT 1 FROM loans_historicalloanevidence s
      WHERE s.id::text=pair->>0 AND s.workspace_id=NEW.workspace_id AND s.source_sha256=pair->>1
       AND s.source_namespace=a.source_namespace AND s.source_system=a.source_system AND s.source_id=a.source_id
       AND (s.document#>'{facts,loan_number}'='null'::jsonb OR s.document#>'{facts,loan_number}'=NEW.document#>'{position,loan,number}')
       AND (s.document#>'{facts,opened_on}'='null'::jsonb OR s.document#>'{facts,opened_on}'=NEW.document#>'{position,loan,original_date}')
       AND (s.document#>'{facts,closed_on}'='null'::jsonb OR s.document#>'{facts,closed_on}'=NEW.document#>'{position,loan,closed_on}')
       AND (s.document#>'{facts,original_principal}'='null'::jsonb OR s.document#>'{facts,original_principal}'=NEW.document#>'{position,loan,original_principal}')
       AND (s.document#>'{facts,borrower_reference}'='null'::jsonb OR s.document#>'{facts,borrower_reference}'=NEW.document#>'{position,loan,borrower_reference}')
       AND (s.document#>'{facts,reported_balance}'='null'::jsonb OR (s.document#>>'{facts,reported_balance}')::numeric=0))
   ) OR (SELECT count(*) FROM jsonb_array_elements(NEW.document#>'{archive,snapshots}'))<>
        (SELECT count(DISTINCT pair->>0) FROM jsonb_array_elements(NEW.document#>'{archive,snapshots}') pair)
   THEN RAISE EXCEPTION 'Invalid compact closed-position source snapshot'; END IF;
  ELSIF NEW.document->'archive' IS DISTINCT FROM 'null'::jsonb
  THEN RAISE EXCEPTION 'Missing compact closed-position retained evidence'; END IF;
  RETURN NEW;
 END IF;
"""
NEW_ARCHIVE = OLD_ARCHIVE.replace(" IF NEW.document->>'profile'='loan-closed-position-admission/1' THEN",
    COMPACT_ARCHIVE + " IF NEW.document->>'profile'='loan-closed-position-admission/1' THEN", 1)

start = prior.GUARD.index("CREATE FUNCTION loans_closed_position_event_guard()")
end = prior.GUARD.index("CREATE TRIGGER loans_closed_position_event_guard", start)
OLD_EVENT = prior.GUARD[start:end].replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)
NEW_EVENT = OLD_EVENT.replace(
    "NEW.payload#>>'{opening,profile}' IS DISTINCT FROM 'loan-closed-position-evidence/1'",
    "COALESCE(NEW.payload#>>'{opening,profile}','') NOT IN ('loan-closed-position-evidence/1','loan-closed-position-evidence/2')"
).replace("NEW.payload#>>'{opening,profile}'='loan-closed-position-evidence/1'",
    "NEW.payload#>>'{opening,profile}' IN ('loan-closed-position-evidence/1','loan-closed-position-evidence/2')")
OLD_COMPLETE = business_date.forward
NEW_COMPLETE = OLD_COMPLETE.replace("OR a->>'profile' IS DISTINCT FROM 'loan-closed-position-admission/1'", """
  OR NOT ((a->>'profile'='loan-closed-position-admission/1' AND e.payload#>>'{opening,profile}'='loan-closed-position-evidence/1')
       OR (a->>'profile'='loan-closed-position-admission/2' AND e.payload#>>'{opening,profile}'='loan-closed-position-evidence/2'
        AND d->'retained_evidence'='null'::jsonb))
  OR a->>'profile' IS NULL OR e.payload#>>'{opening,profile}' IS NULL
""")
assert NEW_ARCHIVE != OLD_ARCHIVE and NEW_EVENT != OLD_EVENT and NEW_COMPLETE != OLD_COMPLETE

# Old guards cannot read/authorize compact evidence. Refuse a schema rollback
# rather than leaving unsupported posted origins in place.
ROLLBACK_CHECK = """
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM loans_historicalloanimport WHERE document->>'profile'='loan-closed-position-admission/2')
 THEN RAISE EXCEPTION 'Compact positions require compatible guards/readers; rollback refused'; END IF;
END; $$;
"""


class Migration(migrations.Migration):
    dependencies = [("loans", "0067_closed_position_business_date")]
    operations = [migrations.RunSQL(NEW_ARCHIVE + NEW_EVENT + NEW_COMPLETE,
        ROLLBACK_CHECK + OLD_ARCHIVE + OLD_EVENT + OLD_COMPLETE)]
