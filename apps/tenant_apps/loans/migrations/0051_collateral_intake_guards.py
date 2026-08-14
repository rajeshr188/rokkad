from django.db import migrations


FORWARD_SQL = """
CREATE OR REPLACE FUNCTION loans_guard_closed_intake_batch() RETURNS trigger AS $$
BEGIN
  IF OLD.status <> 'OPEN' THEN RAISE EXCEPTION 'closed collateral intake batches are immutable'; END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;
CREATE TRIGGER loans_intake_batch_guard BEFORE UPDATE OR DELETE ON loans_collateralintakebatch FOR EACH ROW EXECUTE FUNCTION loans_guard_closed_intake_batch();

CREATE OR REPLACE FUNCTION loans_guard_closed_intake_child() RETURNS trigger AS $$
DECLARE intake_status text;
BEGIN
  IF TG_TABLE_NAME = 'loans_collateralintakegroup' THEN
    SELECT status INTO intake_status FROM loans_collateralintakebatch WHERE id = OLD.batch_id;
  ELSIF TG_TABLE_NAME = 'loans_collateralintakeitem' THEN
    SELECT status INTO intake_status FROM loans_collateralintakebatch WHERE id = OLD.batch_id;
  ELSE
    SELECT batch.status INTO intake_status FROM loans_collateralintakebatch batch JOIN loans_collateralintakeitem item ON item.batch_id = batch.id WHERE item.id = OLD.item_id;
  END IF;
  IF intake_status <> 'OPEN' THEN RAISE EXCEPTION 'closed collateral intake evidence is immutable'; END IF;
  RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END; $$ LANGUAGE plpgsql;
CREATE TRIGGER loans_intake_group_guard BEFORE UPDATE OR DELETE ON loans_collateralintakegroup FOR EACH ROW EXECUTE FUNCTION loans_guard_closed_intake_child();
CREATE TRIGGER loans_intake_item_guard BEFORE UPDATE OR DELETE ON loans_collateralintakeitem FOR EACH ROW EXECUTE FUNCTION loans_guard_closed_intake_child();
CREATE TRIGGER loans_intake_photo_guard BEFORE UPDATE OR DELETE ON loans_collateralintakephoto FOR EACH ROW EXECUTE FUNCTION loans_guard_closed_intake_child();
"""

REVERSE_SQL = """
DROP TRIGGER IF EXISTS loans_intake_photo_guard ON loans_collateralintakephoto;
DROP TRIGGER IF EXISTS loans_intake_item_guard ON loans_collateralintakeitem;
DROP TRIGGER IF EXISTS loans_intake_group_guard ON loans_collateralintakegroup;
DROP TRIGGER IF EXISTS loans_intake_batch_guard ON loans_collateralintakebatch;
DROP FUNCTION IF EXISTS loans_guard_closed_intake_child();
DROP FUNCTION IF EXISTS loans_guard_closed_intake_batch();
"""


def forward(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(FORWARD_SQL)


def reverse(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(REVERSE_SQL)


class Migration(migrations.Migration):
    dependencies = [("loans", "0050_collateralintakebatch_collateralintakegroup_and_more")]
    operations = [migrations.RunPython(forward, reverse)]
