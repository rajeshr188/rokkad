"""Keep preparation identity separate from a permanently issued loan number."""

from django.db import migrations, models

FORWARD = """
CREATE FUNCTION loans_guard_number_stage() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP = 'UPDATE' THEN
   IF NEW.workspace_id IS DISTINCT FROM OLD.workspace_id THEN
     RAISE EXCEPTION 'Loan identity cannot move Workspaces' USING ERRCODE='23514';
   END IF;
   IF OLD.loan_number IS NOT NULL AND NEW.loan_number IS DISTINCT FROM OLD.loan_number THEN
     -- A retained unissued opening alias is not an externally issued register
     -- number. Preserve only the existing verified source-number adoption path.
     IF OLD.state <> 'ACTIVE' OR NEW.state <> 'ACTIVE'
       OR (to_jsonb(NEW) - ARRAY['loan_number','updated_by_id','updated_at']) IS DISTINCT FROM
          (to_jsonb(OLD) - ARRAY['loan_number','updated_by_id','updated_at'])
       OR NOT EXISTS (SELECT 1 FROM loans_historicalloanimport h
         WHERE h.loan_id=OLD.id AND h.workspace_id=OLD.workspace_id
         AND h.document->>'profile'='loan-opening-commit/1'
         AND h.document#>>'{review,source,number}'=NEW.loan_number
         AND OLD.loan_number='H/' || replace(h.source_namespace::text,'-','') || '/' ||
           substr(encode(sha256(convert_to('PAWN_LOAN','UTF8') || decode('00','hex') ||
             convert_to(h.source_id,'UTF8')),'hex'),1,20))
       OR NOT EXISTS (SELECT 1 FROM loans_pawnloanevent WHERE loan_id=OLD.id AND event_kind='MIGRATION_OPENING')
       OR EXISTS (SELECT 1 FROM loans_pawnloanevent WHERE loan_id=OLD.id AND event_kind<>'MIGRATION_OPENING')
       OR EXISTS (SELECT 1 FROM loans_loandocumentissue WHERE workspace_id=OLD.workspace_id
         AND source_type='PawnLoan' AND source_id=OLD.id::text)
       OR EXISTS (SELECT 1 FROM loans_pawncollaterallabelissue l JOIN loans_pawncollateralitem i
         ON i.id=l.collateral_item_id WHERE i.loan_id=OLD.id AND l.action='PRINT') THEN
       RAISE EXCEPTION 'Issued loan numbers cannot be replaced or recycled' USING ERRCODE='23514';
     END IF;
   END IF;
   IF (NEW.license_id, NEW.series_id, NEW.product_version_id) IS DISTINCT FROM
      (OLD.license_id, OLD.series_id, OLD.product_version_id) THEN
     IF OLD.loan_number IS NOT NULL OR OLD.state <> 'DRAFT' OR NEW.state <> 'DRAFT'
       OR EXISTS (SELECT 1 FROM loans_pawnloanapprovalsnapshot WHERE loan_id=OLD.id)
       OR EXISTS (SELECT 1 FROM loans_pawnloanevent WHERE loan_id=OLD.id)
       OR EXISTS (SELECT 1 FROM loans_pawnloanrenewal WHERE source_loan_id=OLD.id OR successor_loan_id=OLD.id)
       OR EXISTS (SELECT 1 FROM loans_pawncollateralitem i WHERE i.loan_id=OLD.id AND (
          i.custody_state <> 'IN_VAULT'
          OR EXISTS (SELECT 1 FROM loans_fundingloandraftcollateral x WHERE x.collateral_item_id=i.id)
          OR EXISTS (SELECT 1 FROM loans_fundingpledgeitem x WHERE x.collateral_item_id=i.id)
          OR EXISTS (SELECT 1 FROM loans_pawncollateralstoragemovement x WHERE x.collateral_item_id=i.id)
          OR EXISTS (SELECT 1 FROM loans_pawncollateralcustodyevent x WHERE x.collateral_item_id=i.id))) THEN
       RAISE EXCEPTION 'Only unnumbered preparations can change register or product' USING ERRCODE='23514';
     END IF;
   END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER loans_number_stage_guard BEFORE UPDATE ON loans_pawnloan
FOR EACH ROW EXECUTE FUNCTION loans_guard_number_stage();
CREATE FUNCTION loans_guard_numbered_approval() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM loans_pawnloan WHERE id=NEW.loan_id
   AND workspace_id=NEW.workspace_id AND loan_number IS NOT NULL) THEN
   RAISE EXCEPTION 'Approval requires an issued loan number' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER loans_numbered_approval_guard BEFORE INSERT ON loans_pawnloanapprovalsnapshot
FOR EACH ROW EXECUTE FUNCTION loans_guard_numbered_approval();
"""

REVERSE = """
DROP TRIGGER loans_numbered_approval_guard ON loans_pawnloanapprovalsnapshot;
DROP FUNCTION loans_guard_numbered_approval();
DROP TRIGGER loans_number_stage_guard ON loans_pawnloan;
DROP FUNCTION loans_guard_number_stage();
"""


def require_numbered_rows(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT EXISTS(SELECT 1 FROM loans_pawnloan WHERE loan_number IS NULL)"
        )
        if cursor.fetchone()[0]:
            raise RuntimeError(
                "Cannot downgrade while unnumbered preparations are retained; restore the matching application/database boundary."
            )


class Migration(migrations.Migration):
    dependencies = [("loans", "0093_loan_entry_preference")]
    operations = [
        migrations.AlterField(
            model_name="pawnloan",
            name="loan_number",
            field=models.CharField(max_length=64, null=True, blank=True, default=None),
        ),
        migrations.AddConstraint(
            model_name="pawnloan",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    loan_number__isnull=True, state__in=("DRAFT", "CANCELLED")
                )
                | (models.Q(loan_number__isnull=False) & ~models.Q(loan_number="")),
                name="loans_pawn_number_stage",
            ),
        ),
        migrations.RunSQL(FORWARD, REVERSE),
        migrations.RunPython(migrations.RunPython.noop, require_numbered_rows),
    ]
