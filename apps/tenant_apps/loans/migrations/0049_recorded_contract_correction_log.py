from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("loans", "0048_paper_handover_evidence")]
    operations = [migrations.RunSQL("""
CREATE FUNCTION loans_contract_correction_log_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.metadata#>>'{history_correction,operation}' = 'CONTRACT'
 THEN RAISE EXCEPTION 'Contract correction evidence is immutable'; END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 IF NEW.metadata#>>'{history_correction,operation}' = 'CONTRACT'
 THEN RAISE EXCEPTION 'Contract correction evidence must be appended'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER loans_contract_correction_log_guard BEFORE UPDATE OR DELETE ON loans_loanchangelog
FOR EACH ROW EXECUTE FUNCTION loans_contract_correction_log_guard();
""", "DROP TRIGGER loans_contract_correction_log_guard ON loans_loanchangelog; DROP FUNCTION loans_contract_correction_log_guard();")]
