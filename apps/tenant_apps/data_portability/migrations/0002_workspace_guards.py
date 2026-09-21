from django.db import migrations
from apps.tenancy.rls import EnableWorkspaceRLSForApp


SQL = """
CREATE FUNCTION portability_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Portability evidence cannot be deleted';
    END IF;
    IF TG_OP = 'UPDATE' AND NEW.workspace_id <> OLD.workspace_id THEN
        RAISE EXCEPTION 'Portability ownership is immutable';
    END IF;
    IF TG_TABLE_NAME IN ('data_portability_partyidentity', 'data_portability_sourceidentity',
                         'data_portability_workspacenamespace') AND TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'Portable identities are immutable';
    END IF;
    IF TG_TABLE_NAME = 'data_portability_partyidentity' THEN
        IF NOT EXISTS (SELECT 1 FROM party_party p WHERE p.id=NEW.party_id AND p.workspace_id=NEW.workspace_id)
        THEN RAISE EXCEPTION 'Party identity must share Workspace'; END IF;
    ELSIF TG_TABLE_NAME = 'data_portability_sourceidentity' THEN
        IF NOT EXISTS (SELECT 1 FROM data_portability_partyidentity i
                       WHERE i.id=NEW.identity_id AND i.workspace_id=NEW.workspace_id)
        THEN RAISE EXCEPTION 'Source identity must share Workspace'; END IF;
    ELSIF TG_TABLE_NAME = 'data_portability_importbatch' THEN
        IF TG_OP = 'UPDATE' THEN
            IF OLD.state IN ('COMPLETED', 'CANCELLED') THEN
                RAISE EXCEPTION 'Finished batches are immutable';
            END IF;
            IF (NEW.public_id,NEW.source_name,NEW.source_type,NEW.source_system,NEW.source_sha256,
                NEW.source_bytes,NEW.contract_version,NEW.headers,NEW.created_by_id,NEW.created_at)
                IS DISTINCT FROM
               (OLD.public_id,OLD.source_name,OLD.source_type,OLD.source_system,OLD.source_sha256,
                OLD.source_bytes,OLD.contract_version,OLD.headers,OLD.created_by_id,OLD.created_at)
            THEN RAISE EXCEPTION 'Source batch evidence is immutable'; END IF;
        END IF;
        IF NEW.state NOT IN ('NEEDS_MAPPING','READY','COMPLETED','CANCELLED')
        THEN RAISE EXCEPTION 'Invalid import state'; END IF;
        IF NEW.state = 'COMPLETED' AND (NEW.committed_at IS NULL OR NEW.committed_by_id IS NULL
                                      OR NEW.approval_digest = '')
        THEN RAISE EXCEPTION 'Completion requires approval and actor evidence'; END IF;
    ELSIF TG_TABLE_NAME = 'data_portability_importrow' THEN
        IF NOT EXISTS (SELECT 1 FROM data_portability_importbatch b
            WHERE b.id=NEW.batch_id AND b.workspace_id=NEW.workspace_id
              AND b.state NOT IN ('COMPLETED','CANCELLED'))
        THEN RAISE EXCEPTION 'Staging requires an unfinished matching Workspace batch'; END IF;
        IF TG_OP = 'UPDATE' AND (OLD.committed_at IS NOT NULL OR
            (NEW.batch_id,NEW.source_row) IS DISTINCT FROM (OLD.batch_id,OLD.source_row))
        THEN RAISE EXCEPTION 'Committed import provenance is immutable'; END IF;
        IF NEW.identity_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM data_portability_partyidentity i
            WHERE i.id=NEW.identity_id AND i.workspace_id=NEW.workspace_id)
        THEN RAISE EXCEPTION 'Import result must share Workspace'; END IF;
        IF (NEW.committed_at IS NULL) <> (NEW.identity_id IS NULL)
        THEN RAISE EXCEPTION 'Import result requires identity and commit time together'; END IF;
    END IF;
    RETURN NEW;
END $$;

CREATE FUNCTION portability_completion_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE batch_key bigint;
BEGIN
    IF TG_TABLE_NAME = 'data_portability_importbatch' THEN batch_key := NEW.id;
    ELSE batch_key := NEW.batch_id; END IF;
    IF EXISTS (SELECT 1 FROM data_portability_importbatch WHERE id=batch_key AND state='COMPLETED') THEN
        IF NOT EXISTS (SELECT 1 FROM data_portability_importrow WHERE batch_id=batch_key)
           OR EXISTS (SELECT 1 FROM data_portability_importrow WHERE batch_id=batch_key AND committed_at IS NULL)
        THEN RAISE EXCEPTION 'Completed batch requires all row results'; END IF;
    ELSIF EXISTS (SELECT 1 FROM data_portability_importrow WHERE batch_id=batch_key AND committed_at IS NOT NULL)
    THEN RAISE EXCEPTION 'Committed rows require a completed batch'; END IF;
    RETURN NULL;
END $$;
"""
TABLES = ("importbatch", "importrow", "partyidentity", "sourceidentity", "workspacenamespace")
for table in TABLES:
    SQL += f"""
    CREATE TRIGGER portability_{table}_guard BEFORE INSERT OR UPDATE OR DELETE
    ON data_portability_{table} FOR EACH ROW EXECUTE FUNCTION portability_guard();
    """
for table in ("importbatch", "importrow"):
    SQL += f"""
    CREATE CONSTRAINT TRIGGER portability_{table}_complete AFTER INSERT OR UPDATE
    ON data_portability_{table} DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION portability_completion_guard();
    """

REVERSE = "\n".join(f"DROP TRIGGER portability_{t}_complete ON data_portability_{t};" for t in ("importbatch", "importrow"))
REVERSE += "\n" + "\n".join(f"DROP TRIGGER portability_{t}_guard ON data_portability_{t};" for t in TABLES)
REVERSE += "\nDROP FUNCTION portability_completion_guard(); DROP FUNCTION portability_guard();"


class Migration(migrations.Migration):
    dependencies = [("data_portability", "0001_initial")]
    operations = [EnableWorkspaceRLSForApp(), migrations.RunSQL(SQL, REVERSE)]
