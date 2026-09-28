from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("subscriptions", "0013_recurring_agreement")]
    operations = [migrations.RunSQL(
        sql="""
        CREATE FUNCTION subscriptions_guard_recurring_fixed() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
          RAISE EXCEPTION 'Recurring binding and event evidence cannot be rewritten or deleted';
        END; $$;
        CREATE TRIGGER recurring_binding_evidence_guard
        BEFORE UPDATE OR DELETE ON subscriptions_recurringplanbinding FOR EACH ROW
        EXECUTE FUNCTION subscriptions_guard_recurring_fixed();
        CREATE TRIGGER recurring_event_evidence_guard
        BEFORE UPDATE OR DELETE ON subscriptions_recurringagreementevent FOR EACH ROW
        EXECUTE FUNCTION subscriptions_guard_recurring_fixed();

        CREATE FUNCTION subscriptions_guard_recurring_agreement() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'Recurring agreement evidence cannot be deleted';
          END IF;
          IF NEW.workspace_id IS DISTINCT FROM OLD.workspace_id OR
             NEW.binding_id IS DISTINCT FROM OLD.binding_id OR
             NEW.request_key IS DISTINCT FROM OLD.request_key OR
             NEW.request_snapshot IS DISTINCT FROM OLD.request_snapshot OR
             NEW.actor_id IS DISTINCT FROM OLD.actor_id OR
             NEW.created_at IS DISTINCT FROM OLD.created_at OR
             (OLD.provider_subscription_id IS NOT NULL AND
              NEW.provider_subscription_id IS DISTINCT FROM OLD.provider_subscription_id) OR
             (OLD.closed_at IS NOT NULL AND NEW IS DISTINCT FROM OLD) THEN
            RAISE EXCEPTION 'Recurring agreement identity and closed history cannot be rewritten';
          END IF;
          IF NEW.closed_at IS NOT NULL AND
             (NEW.state <> 'verified' OR NEW.provider_status NOT IN ('cancelled', 'completed', 'expired')) THEN
            RAISE EXCEPTION 'Only a verified terminal provider agreement can be closed';
          END IF;
          RETURN NEW;
        END; $$;
        CREATE TRIGGER recurring_agreement_evidence_guard
        BEFORE UPDATE OR DELETE ON subscriptions_recurringagreement FOR EACH ROW
        EXECUTE FUNCTION subscriptions_guard_recurring_agreement();
        """,
        reverse_sql="""
        DROP TRIGGER recurring_agreement_evidence_guard ON subscriptions_recurringagreement;
        DROP FUNCTION subscriptions_guard_recurring_agreement();
        DROP TRIGGER recurring_event_evidence_guard ON subscriptions_recurringagreementevent;
        DROP TRIGGER recurring_binding_evidence_guard ON subscriptions_recurringplanbinding;
        DROP FUNCTION subscriptions_guard_recurring_fixed();
        """,
    )]
