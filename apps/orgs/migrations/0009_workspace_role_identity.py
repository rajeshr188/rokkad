from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("orgs", "0008_companyinvitation_role_fingerprint_workspacerole_and_more")]
    operations = [migrations.RunSQL(
        """
        CREATE FUNCTION orgs_workspace_role_identity_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.workspace_id IS DISTINCT FROM OLD.workspace_id OR NEW.role_id IS DISTINCT FROM OLD.role_id THEN
            RAISE EXCEPTION 'Workspace role identity is immutable' USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END; $$;
        CREATE TRIGGER orgs_workspace_role_identity BEFORE UPDATE ON orgs_workspacerole
        FOR EACH ROW EXECUTE FUNCTION orgs_workspace_role_identity_guard();
        """,
        "DROP TRIGGER orgs_workspace_role_identity ON orgs_workspacerole; DROP FUNCTION orgs_workspace_role_identity_guard();",
    )]
