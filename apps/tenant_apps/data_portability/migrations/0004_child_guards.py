from django.db import migrations
from apps.tenancy.rls import EnableWorkspaceRLS


SQL = """
CREATE FUNCTION portability_child_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Child provenance cannot be deleted'; END IF;
    IF TG_OP = 'UPDATE' AND NEW.workspace_id <> OLD.workspace_id
    THEN RAISE EXCEPTION 'Child ownership is immutable'; END IF;
    IF TG_TABLE_NAME = 'data_portability_childidentity' THEN
        IF TG_OP = 'UPDATE' AND (
            (NEW.public_id,NEW.parent_id,NEW.profile,NEW.created_at) IS DISTINCT FROM
            (OLD.public_id,OLD.parent_id,OLD.profile,OLD.created_at)
            OR (NEW.contact_id IS NOT NULL AND NEW.contact_id IS DISTINCT FROM OLD.contact_id)
            OR (NEW.address_id IS NOT NULL AND NEW.address_id IS DISTINCT FROM OLD.address_id))
        THEN RAISE EXCEPTION 'Child identity cannot be rebound'; END IF;
        IF NOT EXISTS (SELECT 1 FROM data_portability_partyidentity p
            WHERE p.id=NEW.parent_id AND p.workspace_id=NEW.workspace_id)
        THEN RAISE EXCEPTION 'Child parent must share Workspace'; END IF;
        IF NEW.profile NOT IN ('party-contact/1','party-address/1')
            OR (NEW.profile='party-contact/1' AND NEW.address_id IS NOT NULL)
            OR (NEW.profile='party-address/1' AND NEW.contact_id IS NOT NULL)
            OR (TG_OP='INSERT' AND NEW.contact_id IS NULL AND NEW.address_id IS NULL)
        THEN RAISE EXCEPTION 'Child profile and target must match'; END IF;
        IF NEW.contact_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM party_partycontactmethod c JOIN data_portability_partyidentity p ON p.party_id=c.party_id
            WHERE c.id=NEW.contact_id AND c.workspace_id=NEW.workspace_id AND p.id=NEW.parent_id)
        THEN RAISE EXCEPTION 'Contact must share Party and Workspace'; END IF;
        IF NEW.address_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM party_partyaddress c JOIN data_portability_partyidentity p ON p.party_id=c.party_id
            WHERE c.id=NEW.address_id AND c.workspace_id=NEW.workspace_id AND p.id=NEW.parent_id)
        THEN RAISE EXCEPTION 'Address must share Party and Workspace'; END IF;
    ELSIF TG_TABLE_NAME = 'data_portability_childsourceidentity' THEN
        IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'Child source evidence is immutable'; END IF;
        IF NOT EXISTS (SELECT 1 FROM data_portability_childidentity c
            WHERE c.id=NEW.identity_id AND c.workspace_id=NEW.workspace_id AND c.profile=NEW.profile)
        THEN RAISE EXCEPTION 'Child source must share Workspace and profile'; END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER portability_child_identity_guard BEFORE INSERT OR UPDATE OR DELETE
    ON data_portability_childidentity FOR EACH ROW EXECUTE FUNCTION portability_child_guard();
CREATE TRIGGER portability_child_source_guard BEFORE INSERT OR UPDATE OR DELETE
    ON data_portability_childsourceidentity FOR EACH ROW EXECUTE FUNCTION portability_child_guard();

CREATE FUNCTION portability_child_tombstone_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.contact_id IS NOT NULL AND NEW.contact_id IS NULL AND EXISTS (
        SELECT 1 FROM party_partycontactmethod WHERE id=OLD.contact_id)
    THEN RAISE EXCEPTION 'A live contact identity cannot be detached'; END IF;
    IF OLD.address_id IS NOT NULL AND NEW.address_id IS NULL AND EXISTS (
        SELECT 1 FROM party_partyaddress WHERE id=OLD.address_id)
    THEN RAISE EXCEPTION 'A live address identity cannot be detached'; END IF;
    RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER portability_child_tombstone_guard AFTER UPDATE
    ON data_portability_childidentity DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION portability_child_tombstone_guard();

CREATE FUNCTION portability_child_result_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE batch_profile text;
BEGIN
    SELECT contract_version INTO batch_profile FROM data_portability_importbatch WHERE id=NEW.batch_id;
    IF NEW.child_identity_id IS NOT NULL AND (NEW.committed_at IS NULL OR NOT EXISTS (
        SELECT 1 FROM data_portability_childidentity c WHERE c.id=NEW.child_identity_id
        AND c.workspace_id=NEW.workspace_id AND c.parent_id=NEW.identity_id AND c.profile=batch_profile))
    THEN RAISE EXCEPTION 'Child result must match parent, profile and Workspace'; END IF;
    IF NEW.committed_at IS NOT NULL AND batch_profile IN ('party-contact/1','party-address/1') AND NEW.child_identity_id IS NULL
    THEN RAISE EXCEPTION 'Child completion requires a child result'; END IF;
    IF batch_profile='party-master/1' AND NEW.child_identity_id IS NOT NULL
    THEN RAISE EXCEPTION 'Master result cannot reference child'; END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER portability_child_result_guard BEFORE INSERT OR UPDATE
    ON data_portability_importrow FOR EACH ROW EXECUTE FUNCTION portability_child_result_guard();
"""
REVERSE = """
DROP TRIGGER IF EXISTS portability_child_tombstone_guard ON data_portability_childidentity;
DROP FUNCTION IF EXISTS portability_child_tombstone_guard();
DROP TRIGGER portability_child_result_guard ON data_portability_importrow;
DROP FUNCTION portability_child_result_guard();
DROP TRIGGER portability_child_identity_guard ON data_portability_childidentity;
DROP TRIGGER portability_child_source_guard ON data_portability_childsourceidentity;
DROP FUNCTION portability_child_guard();
"""


class Migration(migrations.Migration):
    dependencies = [("data_portability", "0003_childidentity_importrow_child_identity_and_more")]
    operations = [EnableWorkspaceRLS("ChildIdentity"), EnableWorkspaceRLS("ChildSourceIdentity"), migrations.RunSQL(SQL, REVERSE)]
