from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("standalone_accounting", "0010_controlled_period_lifecycle")]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE OR REPLACE FUNCTION standalone_accounting_guard_period_transition()
                RETURNS trigger LANGUAGE plpgsql AS $$
                DECLARE latest_from varchar(24); latest_to varchar(24);
                BEGIN
                    IF TG_TABLE_NAME = 'standalone_accounting_accountingperiodtransition' THEN
                        IF TG_OP IN ('UPDATE', 'DELETE') THEN
                            RAISE EXCEPTION 'Accounting period transition evidence is immutable.';
                        END IF;
                        RETURN NEW;
                    END IF;
                    IF NEW.status = OLD.status THEN RETURN NEW; END IF;
                    IF NOT ((OLD.status = 'OPEN' AND NEW.status IN ('ADJUSTMENT_ONLY','CLOSED'))
                       OR (OLD.status = 'ADJUSTMENT_ONLY' AND NEW.status = 'CLOSED')
                       OR (OLD.status = 'CLOSED' AND NEW.status IN ('ADJUSTMENT_ONLY','LOCKED'))) THEN
                        RAISE EXCEPTION 'Invalid accounting period transition.';
                    END IF;
                    SELECT from_status, to_status INTO latest_from, latest_to
                    FROM standalone_accounting_accountingperiodtransition
                    WHERE period_id = OLD.id ORDER BY occurred_at DESC, id DESC LIMIT 1;
                    IF latest_from IS DISTINCT FROM OLD.status OR latest_to IS DISTINCT FROM NEW.status THEN
                        RAISE EXCEPTION 'Accounting period transition requires current audit evidence.';
                    END IF;
                    RETURN NEW;
                END; $$;
            """,
            reverse_sql=migrations.RunSQL.noop,
        )
    ]
