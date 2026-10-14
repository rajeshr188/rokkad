"""Deferred return checks follow retained reversal evidence and its custody inverse."""
from django.db import migrations

FORWARD = r"""
CREATE FUNCTION loans_funding_reversed_return_consistent(return_id bigint, pledge_item_id bigint)
RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS (
  SELECT 1 FROM loans_fundingreturnreversal reversal
  JOIN loans_fundingpledgeitem item ON item.id=pledge_item_id
  WHERE reversal.funding_return_id=return_id
   AND EXISTS (SELECT 1 FROM loans_pawncollateralcustodyevent original
    JOIN loans_pawncollateralcustodyevent inverse ON inverse.collateral_item_id=original.collateral_item_id
     AND inverse.funding_return_id=original.funding_return_id
     AND inverse.funding_return_reversal_id=reversal.id
     AND inverse.from_state=original.to_state AND inverse.to_state=original.from_state AND inverse.id>original.id
    WHERE original.funding_return_id=return_id AND original.funding_return_reversal_id IS NULL
     AND original.collateral_item_id=item.collateral_item_id)
   AND (item.released_at IS NOT NULL) = (
    EXISTS (SELECT 1 FROM loans_fundingreturnitem later
     WHERE later.pledge_item_id=item.id
      AND NOT EXISTS (SELECT 1 FROM loans_fundingreturnreversal r WHERE r.funding_return_id=later.funding_return_id))
    OR EXISTS (SELECT 1 FROM loans_fundingpledgereversal r WHERE r.funding_pledge_id=item.funding_pledge_id)))
$$;
CREATE OR REPLACE FUNCTION loans_verify_funding_return_projection()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF EXISTS (SELECT 1 FROM loans_fundingreturnreversal WHERE funding_return_id=NEW.funding_return_id) THEN
  IF NOT loans_funding_reversed_return_consistent(NEW.funding_return_id,NEW.pledge_item_id) THEN
   RAISE EXCEPTION 'Reversed funding return needs exact inverse custody and final pledge projection.';
  END IF;
 ELSIF NOT EXISTS (SELECT 1 FROM loans_fundingpledgeitem WHERE id=NEW.pledge_item_id AND released_at IS NOT NULL) THEN
  RAISE EXCEPTION 'Funding return must release its pledge item in the same transaction.';
 END IF;
 RETURN NULL;
END; $$;
CREATE FUNCTION loans_verify_funding_return_reversal_projection()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM loans_fundingreturnitem WHERE funding_return_id=NEW.funding_return_id)
  OR EXISTS (SELECT 1 FROM loans_fundingreturnitem item WHERE item.funding_return_id=NEW.funding_return_id
   AND NOT loans_funding_reversed_return_consistent(item.funding_return_id,item.pledge_item_id)) THEN
  RAISE EXCEPTION 'Reversed funding return needs exact inverse custody and final pledge projection.';
 END IF;
 RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER loans_funding_return_reversal_projection_guard AFTER INSERT ON loans_fundingreturnreversal
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION loans_verify_funding_return_reversal_projection();
"""
REVERSE = r"""
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM loans_fundingreturnreversal) THEN
  RAISE EXCEPTION 'Retained funding return reversals need their final projection guard';
 END IF;
END; $$;
DROP TRIGGER loans_funding_return_reversal_projection_guard ON loans_fundingreturnreversal;
DROP FUNCTION loans_verify_funding_return_reversal_projection();
CREATE OR REPLACE FUNCTION loans_verify_funding_return_projection()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM loans_fundingpledgeitem WHERE id=NEW.pledge_item_id AND released_at IS NOT NULL) THEN
  RAISE EXCEPTION 'Funding return must release its pledge item in the same transaction.';
 END IF;
 RETURN NULL;
END; $$;
DROP FUNCTION loans_funding_reversed_return_consistent(bigint,bigint);
"""


class Migration(migrations.Migration):
    dependencies = [('loans','0070_imported_licence_source')]
    operations = [migrations.RunSQL(FORWARD,REVERSE)]
