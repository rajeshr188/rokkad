from django.db import migrations


FORWARD_SQL = """
CREATE OR REPLACE FUNCTION loans_guard_collateral_photo_mutation()
RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' AND EXISTS (
        SELECT 1
        FROM loans_pawncollateralitem item
        JOIN loans_pawnloan loan ON loan.id = item.loan_id
        WHERE item.id = OLD.collateral_item_id AND loan.state = 'DRAFT'
    ) THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'collateral photograph evidence is immutable after draft';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION loans_guard_collateral_label_mutation()
RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' AND EXISTS (
        SELECT 1
        FROM loans_pawncollateralitem item
        JOIN loans_pawnloan loan ON loan.id = item.loan_id
        WHERE item.id = OLD.collateral_item_id AND loan.state = 'DRAFT'
    ) THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'collateral label evidence is immutable after draft';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS loans_photo_immutable ON loans_pawncollateralphoto;
CREATE TRIGGER loans_photo_immutable
BEFORE UPDATE OR DELETE ON loans_pawncollateralphoto
FOR EACH ROW EXECUTE FUNCTION loans_guard_collateral_photo_mutation();

DROP TRIGGER IF EXISTS loans_label_immutable ON loans_pawncollaterallabelissue;
CREATE TRIGGER loans_label_immutable
BEFORE UPDATE OR DELETE ON loans_pawncollaterallabelissue
FOR EACH ROW EXECUTE FUNCTION loans_guard_collateral_label_mutation();
"""


REVERSE_SQL = """
DROP TRIGGER IF EXISTS loans_photo_immutable ON loans_pawncollateralphoto;
DROP TRIGGER IF EXISTS loans_label_immutable ON loans_pawncollaterallabelissue;
DROP FUNCTION IF EXISTS loans_guard_collateral_photo_mutation();
DROP FUNCTION IF EXISTS loans_guard_collateral_label_mutation();

CREATE TRIGGER loans_photo_immutable
BEFORE UPDATE OR DELETE ON loans_pawncollateralphoto
FOR EACH ROW EXECUTE FUNCTION loans_reject_collateral_evidence_mutation();
CREATE TRIGGER loans_label_immutable
BEFORE UPDATE OR DELETE ON loans_pawncollaterallabelissue
FOR EACH ROW EXECUTE FUNCTION loans_reject_collateral_evidence_mutation();
"""


def apply_guards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(FORWARD_SQL)


def restore_guards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(REVERSE_SQL)

