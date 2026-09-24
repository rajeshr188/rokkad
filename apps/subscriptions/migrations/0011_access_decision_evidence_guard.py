from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("subscriptions", "0010_workspaceaccessdecision")]
    operations = [migrations.RunSQL(
        sql="""
        CREATE FUNCTION subscriptions_guard_access_decision() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
          RAISE EXCEPTION 'Workspace access decision evidence cannot be rewritten or deleted';
        END; $$;
        CREATE TRIGGER subscriptions_access_decision_guard
        BEFORE UPDATE OR DELETE ON subscriptions_workspaceaccessdecision FOR EACH ROW
        EXECUTE FUNCTION subscriptions_guard_access_decision();
        """,
        reverse_sql="""
        DROP TRIGGER subscriptions_access_decision_guard ON subscriptions_workspaceaccessdecision;
        DROP FUNCTION subscriptions_guard_access_decision();
        """,
    )]
