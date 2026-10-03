from django.db import migrations, models


LABEL_GUARD = r"""
CREATE FUNCTION loans_khata_label_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE a loans_khataaccount%ROWTYPE; i loans_khatacollateralitem%ROWTYPE;
  row jsonb; ids bigint[]; actual_ids bigint[]; expected_state text; slug text; label_mode text;
BEGIN
  SELECT * INTO a FROM loans_khataaccount WHERE id=NEW.account_id AND workspace_id=NEW.workspace_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Khata label account Workspace mismatch'; END IF;
  SELECT c.slug INTO slug FROM orgs_company c WHERE c.id=NEW.workspace_id;
  label_mode := NEW.payload->>'mode';
  IF NEW.kind<>'LABEL' OR NEW.source_operation_id IS NOT NULL
    OR NEW.request_sha256 !~ '^[a-f0-9]{64}$' OR NEW.payload_sha256 !~ '^[a-f0-9]{64}$'
    OR NEW.artifact_sha256 !~ '^[a-f0-9]{64}$' OR NEW.renderer_version<>'khata-label-v1'
    OR NEW.artifact <> 'loans/khata/'||NEW.workspace_id||'/documents/'||NEW.account_id||'/'||NEW.request_key||'.pdf'
    OR NEW.payload->>'schema' IS DISTINCT FROM 'khata-label/1'
    OR NEW.payload->>'kind' IS DISTINCT FROM 'LABEL'
    OR NEW.payload->>'workspace_id' IS DISTINCT FROM NEW.workspace_id::text
    OR NEW.payload->>'account_id' IS DISTINCT FROM a.id::text
    OR NEW.payload->>'account_number' IS DISTINCT FROM a.account_number
    OR NEW.payload->>'public_id' IS DISTINCT FROM a.public_id::text
    OR NEW.payload->'borrower'->>'id' IS DISTINCT FROM a.borrower_id::text
    OR NEW.payload->>'as_of' IS DISTINCT FROM NEW.as_of::text
    OR NEW.payload->>'source_sequence' IS DISTINCT FROM NEW.source_sequence::text
    OR NEW.source_sequence<>COALESCE((SELECT max(sequence) FROM loans_khataoperation WHERE account_id=a.id),0)
    OR NEW.payload->>'scan_path' IS DISTINCT FROM '/w/'||slug||'/loans/khata/accounts/'||a.public_id||'/scan/'
    OR jsonb_typeof(NEW.payload->'items') IS DISTINCT FROM 'array'
    OR label_mode IS NULL OR label_mode NOT IN ('ONE','ALL','EACH')
  THEN RAISE EXCEPTION 'Invalid khata label identity or source metadata'; END IF;
  SELECT array_agg((e->>'id')::bigint ORDER BY (e->>'id')::bigint) INTO ids FROM jsonb_array_elements(NEW.payload->'items') e;
  IF COALESCE(cardinality(ids),0) NOT BETWEEN 1 AND 100
    OR cardinality(ids)<>(SELECT count(DISTINCT v) FROM unnest(ids) v)
    OR (label_mode='ONE' AND cardinality(ids)<>1)
  THEN RAISE EXCEPTION 'Invalid khata label item selection'; END IF;
  SELECT array_agg(c.id ORDER BY c.id) INTO actual_ids FROM loans_khatacollateralitem c
    WHERE c.account_id=a.id AND c.workspace_id=NEW.workspace_id AND NOT EXISTS
    (SELECT 1 FROM loans_khataoperation o WHERE o.account_id=a.id AND o.item_id=c.id AND o.kind IN ('HANDOVER','RETURN'));
  IF label_mode IN ('ALL','EACH') AND ids IS DISTINCT FROM actual_ids
  THEN RAISE EXCEPTION 'Combined khata labels must include every held item'; END IF;
  FOR row IN SELECT e FROM jsonb_array_elements(NEW.payload->'items') e LOOP
    SELECT * INTO i FROM loans_khatacollateralitem WHERE id=(row->>'id')::bigint AND account_id=a.id AND workspace_id=NEW.workspace_id;
    IF NOT FOUND OR NOT (i.id=ANY(actual_ids))
      OR row->>'public_id' IS DISTINCT FROM i.public_id::text
      OR row->>'received_operation_id' IS DISTINCT FROM i.received_operation_id::text
      OR row->>'description' IS DISTINCT FROM i.description
      OR row->>'metal' IS DISTINCT FROM i.metal
      OR row->>'quantity' IS DISTINCT FROM i.quantity::text
      OR row->>'gross_weight' IS DISTINCT FROM i.gross_weight::text
      OR row->>'net_weight' IS DISTINCT FROM i.net_weight::text
      OR row->>'purity' IS DISTINCT FROM i.purity::text
      OR row->>'storage_reference' IS DISTINCT FROM i.storage_reference
      OR row->>'scan_path' IS DISTINCT FROM '/w/'||slug||'/loans/khata/items/'||i.public_id||'/scan/'
    THEN RAISE EXCEPTION 'Khata label must preserve its own held item identity'; END IF;
    SELECT CASE WHEN EXISTS(SELECT 1 FROM loans_khatacollateralselection s
      JOIN loans_khataoperation o ON o.id=s.operation_id WHERE s.item_id=i.id AND s.role='OUT'
      AND NOT EXISTS(SELECT 1 FROM loans_khataoperation c WHERE c.correction_of_id=o.id))
      THEN 'Return pending' ELSE 'Held' END INTO expected_state;
    IF row->>'custody' IS DISTINCT FROM expected_state THEN RAISE EXCEPTION 'Khata label custody mismatch'; END IF;
  END LOOP;
  RETURN NEW;
END $$;
DROP TRIGGER khata_document_guard ON loans_khatadocumentissue;
CREATE TRIGGER khata_document_guard BEFORE INSERT ON loans_khatadocumentissue
  FOR EACH ROW WHEN (NEW.kind <> 'LABEL') EXECUTE FUNCTION loans_khata_document_guard();
CREATE TRIGGER khata_document_immutable_guard BEFORE UPDATE OR DELETE ON loans_khatadocumentissue
  FOR EACH ROW EXECUTE FUNCTION loans_khata_document_guard();
CREATE TRIGGER khata_label_guard BEFORE INSERT ON loans_khatadocumentissue
  FOR EACH ROW WHEN (NEW.kind = 'LABEL') EXECUTE FUNCTION loans_khata_label_guard();
"""

REVERSE = """
DROP TRIGGER khata_label_guard ON loans_khatadocumentissue;
DROP TRIGGER khata_document_immutable_guard ON loans_khatadocumentissue;
DROP TRIGGER khata_document_guard ON loans_khatadocumentissue;
CREATE TRIGGER khata_document_guard BEFORE INSERT OR UPDATE OR DELETE ON loans_khatadocumentissue
  FOR EACH ROW EXECUTE FUNCTION loans_khata_document_guard();
DROP FUNCTION loans_khata_label_guard();
"""


class Migration(migrations.Migration):
    dependencies = [("loans", "0039_khata_documents")]
    operations = [
        migrations.RemoveConstraint(model_name="khatadocumentissue", name="khata_document_source_valid"),
        migrations.AlterField(model_name="khatadocumentissue", name="kind", field=models.CharField(max_length=9,
            choices=[("OPERATION", "Source document"), ("STATEMENT", "Dated statement"), ("LABEL", "Collateral label")])),
        migrations.AddConstraint(model_name="khatadocumentissue", constraint=models.CheckConstraint(
            condition=models.Q(kind="OPERATION", source_operation__isnull=False)
                | models.Q(kind__in=("STATEMENT", "LABEL"), source_operation__isnull=True), name="khata_document_source_valid")),
        migrations.RunSQL(LABEL_GUARD, REVERSE),
    ]
