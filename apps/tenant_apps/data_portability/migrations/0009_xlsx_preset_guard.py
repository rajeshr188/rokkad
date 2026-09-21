from django.db import migrations

SQL = """CREATE OR REPLACE FUNCTION portability_batch_preset_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.mapping_preset_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM data_portability_mappingpresetversion p
        WHERE p.id=NEW.mapping_preset_id AND p.workspace_id=NEW.workspace_id
        AND NEW.source_type IN ('csv','xlsx') AND p.profile=NEW.contract_version
        AND p.source_system=NEW.source_system AND p.mapping=NEW.mapping
        AND p.headers @> NEW.headers AND p.headers <@ NEW.headers)
    THEN RAISE EXCEPTION 'Batch preset must match Workspace, source, headers, profile and mapping'; END IF;
    RETURN NEW;
END $$;
"""

REVERSE = """DO $$ BEGIN IF EXISTS (SELECT 1 FROM data_portability_importbatch WHERE source_type='xlsx' AND mapping_preset_id IS NOT NULL) THEN RAISE EXCEPTION 'Cannot remove retained XLSX preset associations'; END IF; END $$;
CREATE OR REPLACE FUNCTION portability_batch_preset_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.mapping_preset_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM data_portability_mappingpresetversion p
        WHERE p.id=NEW.mapping_preset_id AND p.workspace_id=NEW.workspace_id
        AND NEW.source_type='csv' AND p.profile=NEW.contract_version
        AND p.source_system=NEW.source_system AND p.mapping=NEW.mapping
        AND p.headers @> NEW.headers AND p.headers <@ NEW.headers)
    THEN RAISE EXCEPTION 'Batch preset must match Workspace, source, headers, profile and mapping'; END IF;
    RETURN NEW;
END $$;
"""


class Migration(migrations.Migration):
    dependencies = [("data_portability", "0008_mappingpresetversion_importbatch_mapping_preset_and_more")]
    operations = [migrations.RunSQL(SQL, REVERSE)]
