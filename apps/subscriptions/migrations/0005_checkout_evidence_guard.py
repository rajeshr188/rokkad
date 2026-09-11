from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("subscriptions", "0004_invoice_checkout_key_invoice_checkout_snapshot_and_more")]
    operations = [migrations.RunSQL(
        sql="""
        CREATE FUNCTION subscriptions_guard_checkout() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.checkout_snapshot <> '{}'::jsonb AND (
            NEW.checkout_snapshot IS DISTINCT FROM OLD.checkout_snapshot OR
            NEW.checkout_key IS DISTINCT FROM OLD.checkout_key OR
            NEW.subscription_id IS DISTINCT FROM OLD.subscription_id OR
            NEW.invoice_number IS DISTINCT FROM OLD.invoice_number OR
            NEW.base_amount IS DISTINCT FROM OLD.base_amount OR
            NEW.overage_amount IS DISTINCT FROM OLD.overage_amount OR
            NEW.subtotal IS DISTINCT FROM OLD.subtotal OR
            NEW.gst_rate IS DISTINCT FROM OLD.gst_rate OR
            NEW.gst_amount IS DISTINCT FROM OLD.gst_amount OR
            NEW.total_amount IS DISTINCT FROM OLD.total_amount OR
            (OLD.razorpay_order_id IS NOT NULL AND
             NEW.razorpay_order_id IS DISTINCT FROM OLD.razorpay_order_id)
          ) THEN
            RAISE EXCEPTION 'Checkout evidence cannot be rewritten';
          END IF;
          RETURN NEW;
        END;
        $$;
        CREATE TRIGGER subscriptions_checkout_evidence_guard
        BEFORE UPDATE ON subscriptions_invoice FOR EACH ROW
        EXECUTE FUNCTION subscriptions_guard_checkout();
        """,
        reverse_sql="""
        DROP TRIGGER subscriptions_checkout_evidence_guard ON subscriptions_invoice;
        DROP FUNCTION subscriptions_guard_checkout();
        """,
    )]
