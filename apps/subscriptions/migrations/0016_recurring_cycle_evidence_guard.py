from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("subscriptions", "0015_recurring_paid_cycle")]
    operations = [migrations.RunSQL(
        sql="""
        CREATE FUNCTION subscriptions_guard_recurring_cycle() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'Recurring paid cycle evidence is immutable'; END IF;
          IF NOT EXISTS (
            SELECT 1 FROM subscriptions_invoice i
            JOIN subscriptions_subscription s ON s.id = i.subscription_id
            JOIN subscriptions_recurringagreement a ON a.id = NEW.agreement_id
            JOIN subscriptions_payment p ON p.invoice_id = i.id
            WHERE i.id = NEW.invoice_id AND s.company_id = a.workspace_id
              AND i.status = 'paid' AND i.checkout_snapshot->>'kind' = 'recurring'
              AND i.checkout_snapshot->>'agreement_id' = a.id::text
              AND i.checkout_snapshot->>'provider_invoice_id' = NEW.provider_invoice_id
              AND NEW.evidence->>'payment_id' = p.razorpay_payment_id
              AND NEW.evidence->>'order_id' = i.razorpay_order_id
              AND p.amount = i.total_amount AND p.status = 'captured'
          ) THEN RAISE EXCEPTION 'Recurring cycle must match its Workspace paid invoice and payment'; END IF;
          RETURN NEW;
        END; $$;
        CREATE TRIGGER recurring_cycle_evidence_guard BEFORE INSERT OR UPDATE OR DELETE
        ON subscriptions_recurringcycle FOR EACH ROW EXECUTE FUNCTION subscriptions_guard_recurring_cycle();

        CREATE FUNCTION subscriptions_guard_recurring_payment() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF EXISTS (SELECT 1 FROM subscriptions_recurringcycle WHERE invoice_id = OLD.invoice_id) THEN
            IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Recurring payment evidence cannot be deleted'; END IF;
            IF NEW.invoice_id IS DISTINCT FROM OLD.invoice_id OR
               NEW.razorpay_payment_id IS DISTINCT FROM OLD.razorpay_payment_id OR
               NEW.razorpay_order_id IS DISTINCT FROM OLD.razorpay_order_id OR
               NEW.amount IS DISTINCT FROM OLD.amount OR NEW.payment_date IS DISTINCT FROM OLD.payment_date THEN
              RAISE EXCEPTION 'Recurring payment identity and amount are immutable';
            END IF;
          END IF;
          IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
          RETURN NEW;
        END; $$;
        CREATE TRIGGER recurring_payment_evidence_guard BEFORE UPDATE OR DELETE
        ON subscriptions_payment FOR EACH ROW EXECUTE FUNCTION subscriptions_guard_recurring_payment();

        CREATE FUNCTION subscriptions_guard_recurring_invoice() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF EXISTS (SELECT 1 FROM subscriptions_recurringcycle WHERE invoice_id = OLD.id) AND (
             NEW.status <> 'paid' OR NEW.paid_at IS DISTINCT FROM OLD.paid_at OR
             NEW.razorpay_payment_id IS DISTINCT FROM OLD.razorpay_payment_id) THEN
            RAISE EXCEPTION 'Recurring paid invoice evidence cannot be rewritten';
          END IF;
          RETURN NEW;
        END; $$;
        CREATE TRIGGER recurring_invoice_evidence_guard BEFORE UPDATE
        ON subscriptions_invoice FOR EACH ROW EXECUTE FUNCTION subscriptions_guard_recurring_invoice();
        """,
        reverse_sql="""
        DROP TRIGGER recurring_invoice_evidence_guard ON subscriptions_invoice;
        DROP FUNCTION subscriptions_guard_recurring_invoice();
        DROP TRIGGER recurring_payment_evidence_guard ON subscriptions_payment;
        DROP FUNCTION subscriptions_guard_recurring_payment();
        DROP TRIGGER recurring_cycle_evidence_guard ON subscriptions_recurringcycle;
        DROP FUNCTION subscriptions_guard_recurring_cycle();
        """,
    )]
