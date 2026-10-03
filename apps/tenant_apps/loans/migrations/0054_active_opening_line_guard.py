from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("loans", "0053_dated_custody_restatements")]
    operations = [migrations.RunSQL("""
CREATE FUNCTION loans_active_opening_line_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 PERFORM 1 FROM loans_pawncollateralitem WHERE id=NEW.collateral_item_id FOR UPDATE;
 IF EXISTS(SELECT 1 FROM loans_pawnloanprincipalopeningline line
   WHERE line.collateral_item_id=NEW.collateral_item_id AND line.loan_event_id<>NEW.loan_event_id
   AND NOT EXISTS(SELECT 1 FROM loans_pawnloanevent reverse WHERE reverse.reversal_of_id=line.loan_event_id))
 THEN RAISE EXCEPTION 'An item can have only one active renewal principal opening'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER loans_active_opening_line_guard BEFORE INSERT ON loans_pawnloanprincipalopeningline
FOR EACH ROW EXECUTE FUNCTION loans_active_opening_line_guard();
""", "DROP TRIGGER loans_active_opening_line_guard ON loans_pawnloanprincipalopeningline; DROP FUNCTION loans_active_opening_line_guard();")]
