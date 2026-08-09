from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("girvi", "0032_alter_girvipostingoutboxevent_event_type"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE OR REPLACE FUNCTION girvi_guard_loan_repayment()
                RETURNS trigger
                LANGUAGE plpgsql
                AS $$
                DECLARE
                    original girvi_loanrepayment%ROWTYPE;
                BEGIN
                    IF TG_OP IN ('UPDATE', 'DELETE') THEN
                        RAISE EXCEPTION 'Loan repayment evidence is immutable.';
                    END IF;
                    IF NEW.reversal_of_id IS NULL THEN
                        RETURN NEW;
                    END IF;
                    SELECT * INTO original
                    FROM girvi_loanrepayment
                    WHERE id = NEW.reversal_of_id;
                    IF NOT FOUND OR original.reversal_of_id IS NOT NULL THEN
                        RAISE EXCEPTION 'A repayment reversal requires an unreversed original repayment.';
                    END IF;
                    IF NEW.given_loan_id IS DISTINCT FROM original.given_loan_id
                       OR NEW.taken_loan_id IS DISTINCT FROM original.taken_loan_id
                       OR NEW.direction IS DISTINCT FROM original.direction
                       OR NEW.total_amount IS DISTINCT FROM original.total_amount
                       OR NEW.principal_amount IS DISTINCT FROM original.principal_amount
                       OR NEW.interest_amount IS DISTINCT FROM original.interest_amount THEN
                        RAISE EXCEPTION 'A repayment reversal must exactly compensate the original repayment.';
                    END IF;
                    RETURN NEW;
                END;
                $$;

                CREATE TRIGGER girvi_loan_repayment_guard
                BEFORE INSERT OR UPDATE OR DELETE
                ON girvi_loanrepayment
                FOR EACH ROW
                EXECUTE FUNCTION girvi_guard_loan_repayment();
            """,
            reverse_sql="""
                DROP TRIGGER IF EXISTS girvi_loan_repayment_guard
                ON girvi_loanrepayment;
                DROP FUNCTION IF EXISTS girvi_guard_loan_repayment();
            """,
        ),
    ]