"""Known zero debt belongs to custody, only with an accepted checkpoint origin."""
from django.db import migrations, models

GUARD = r"""
CREATE FUNCTION loans_validate_zero_opening_item() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE item loans_pawncollateralitem%ROWTYPE;
BEGIN
 SELECT * INTO item FROM loans_pawncollateralitem WHERE id=NEW.id AND workspace_id=NEW.workspace_id;
 IF NOT FOUND OR item.allocated_principal IS DISTINCT FROM 0 THEN RETURN NULL; END IF;
 IF NOT EXISTS (
  SELECT 1 FROM loans_pawnloanevent e
  JOIN loans_historicalloanimport h ON h.loan_id=e.loan_id AND h.workspace_id=e.workspace_id
  CROSS JOIN LATERAL jsonb_array_elements(e.payload#>'{opening,review,collateral}') c
  WHERE e.loan_id=item.loan_id AND e.workspace_id=item.workspace_id AND e.event_kind='MIGRATION_OPENING'
   AND e.payload#>>'{opening,profile}'='loan-opening-evidence/1'
   AND e.payload#>>'{opening,review,profile}' IN ('loan-opening-review/4','loan-opening-review/5')
   AND e.payload#>>ARRAY['opening','item_mapping',c->>'id']=item.id::text
   AND (c->>'remaining_principal')::numeric=0 AND (c->>'original_principal')::numeric>0
   AND NOT EXISTS (SELECT 1 FROM loans_pawnloanevent other
     WHERE other.loan_id=e.loan_id AND other.event_kind IN ('DISBURSAL','RENEWAL_OPENING'))
 ) THEN RAISE EXCEPTION 'Zero initial item debt requires an accepted explicit opening checkpoint'; END IF;
 RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER loans_zero_opening_item_guard AFTER INSERT OR UPDATE ON loans_pawncollateralitem
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION loans_validate_zero_opening_item();
"""

REVERSE = """
DO $$ BEGIN
IF EXISTS (SELECT 1 FROM loans_pawncollateralitem WHERE allocated_principal=0)
THEN RAISE EXCEPTION 'Retained zero-debt checkpoint collateral must remain supported'; END IF;
END; $$;
DROP TRIGGER loans_zero_opening_item_guard ON loans_pawncollateralitem;
DROP FUNCTION loans_validate_zero_opening_item();
"""


class Migration(migrations.Migration):
    dependencies = [('loans','0068_compact_closed_position_evidence')]
    operations = [
        migrations.RemoveConstraint(model_name='pawncollateralitem',name='loans_item_allocation_positive'),
        migrations.AddConstraint(model_name='pawncollateralitem',constraint=models.CheckConstraint(
            condition=models.Q(allocated_principal__isnull=True)|models.Q(allocated_principal__gte=0),
            name='loans_item_allocation_nonnegative')),
        migrations.RunSQL(GUARD, REVERSE),
    ]
