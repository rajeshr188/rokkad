from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("subscriptions", "0008_billingresolution")]
    operations = [migrations.RunSQL(
        sql="""
        CREATE FUNCTION subscriptions_guard_resolution() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'Final billing review evidence cannot be rewritten or deleted';
        END;
        $$;
        CREATE TRIGGER subscriptions_resolution_evidence_guard
        BEFORE UPDATE OR DELETE ON subscriptions_billingresolution FOR EACH ROW
        EXECUTE FUNCTION subscriptions_guard_resolution();
        """,
        reverse_sql="""
        DROP TRIGGER subscriptions_resolution_evidence_guard ON subscriptions_billingresolution;
        DROP FUNCTION subscriptions_guard_resolution();
        """,
    )]
