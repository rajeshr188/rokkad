from django.db import migrations, models


GUARD = """
CREATE FUNCTION loans_guard_creation_submission() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.creation_submission_id IS NOT NULL THEN
            RAISE EXCEPTION 'A submitted loan must retain its identity; cancel instead of deleting';
        END IF;
        RETURN OLD;
    END IF;
    IF NEW.creation_submission_id IS DISTINCT FROM OLD.creation_submission_id
       OR (OLD.creation_submission_id IS NOT NULL AND NEW.workspace_id <> OLD.workspace_id) THEN
        RAISE EXCEPTION 'Loan creation submission identity is immutable';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER loans_creation_submission_guard BEFORE UPDATE OR DELETE ON loans_pawnloan
FOR EACH ROW EXECUTE FUNCTION loans_guard_creation_submission();
"""


class Migration(migrations.Migration):
    dependencies = [("loans", "0026_collateral_quantity_and_interest_override")]
    operations = [
        migrations.AddField(model_name="pawnloan", name="creation_submission_id",
            field=models.UUIDField(blank=True, editable=False, null=True)),
        migrations.AddConstraint(model_name="pawnloan", constraint=models.UniqueConstraint(
            fields=("workspace", "creation_submission_id"),
            condition=models.Q(creation_submission_id__isnull=False), name="loans_draft_submission_uniq")),
        migrations.RunSQL(GUARD, "DROP TRIGGER loans_creation_submission_guard ON loans_pawnloan; DROP FUNCTION loans_guard_creation_submission();"),
    ]
