from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("subscriptions", "0006_paymentrefund")]
    operations = [migrations.RunSQL(
        sql="""
        CREATE FUNCTION subscriptions_guard_refund() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'Processed refund evidence cannot be rewritten or deleted';
        END;
        $$;
        CREATE TRIGGER subscriptions_refund_evidence_guard
        BEFORE UPDATE OR DELETE ON subscriptions_paymentrefund FOR EACH ROW
        EXECUTE FUNCTION subscriptions_guard_refund();
        """,
        reverse_sql="""
        DROP TRIGGER subscriptions_refund_evidence_guard ON subscriptions_paymentrefund;
        DROP FUNCTION subscriptions_guard_refund();
        """,
    )]
