"""A checkpoint cannot coexist with a payout/renewal origin on the same loan."""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("loans", "0058_completed_legacy_payout")]
    operations = [migrations.RunSQL(r"""
CREATE FUNCTION loans_opening_origin_exclusivity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.event_kind IN ('MIGRATION_OPENING','DISBURSAL','RENEWAL_OPENING') THEN
  PERFORM 1 FROM loans_pawnloan WHERE id=NEW.loan_id AND workspace_id=NEW.workspace_id FOR UPDATE;
  IF EXISTS(SELECT 1 FROM loans_pawnloanevent e WHERE e.loan_id=NEW.loan_id AND e.workspace_id=NEW.workspace_id
    AND ((NEW.event_kind='MIGRATION_OPENING' AND e.event_kind IN ('DISBURSAL','RENEWAL_OPENING'))
      OR (NEW.event_kind IN ('DISBURSAL','RENEWAL_OPENING') AND e.event_kind='MIGRATION_OPENING')))
  THEN RAISE EXCEPTION 'A migration opening cannot coexist with a payout or renewal financial origin'; END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER loans_opening_origin_exclusivity BEFORE INSERT ON loans_pawnloanevent
FOR EACH ROW EXECUTE FUNCTION loans_opening_origin_exclusivity();
""", "DROP TRIGGER loans_opening_origin_exclusivity ON loans_pawnloanevent; DROP FUNCTION loans_opening_origin_exclusivity();")]
