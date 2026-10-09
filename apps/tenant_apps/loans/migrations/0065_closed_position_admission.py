"""Unknown original terms are permitted only for an immutable closed position."""
from importlib import import_module
from django.db import migrations, models
import django.db.models.deletion

OLD_ARCHIVE = import_module("apps.tenant_apps.loans.migrations.0062_terminal_position_evidence").NEW
# Keep the old admission branches intact. The new branch binds the exact retained
# JSON and position event instead of pretending a recorded disbursal exists.
NEW_ARCHIVE = OLD_ARCHIVE.replace(" IF NEW.archive_evidence_id IS NOT NULL THEN", """
 IF NEW.document->>'profile'='loan-closed-position-admission/1' THEN
  IF NEW.archive_evidence_id IS NOT NULL THEN
   SELECT * INTO a FROM loans_historicalloanevidence WHERE id=NEW.archive_evidence_id AND workspace_id=NEW.workspace_id;
   IF NOT FOUND OR NEW.source_namespace IS DISTINCT FROM a.source_namespace
    OR NEW.document#>>'{archive,id}' IS DISTINCT FROM a.id::text
    OR NEW.document#>>'{archive,sha256}' IS DISTINCT FROM a.source_sha256
    OR NEW.document#>'{position,retained_evidence}' IS DISTINCT FROM a.document
   THEN RAISE EXCEPTION 'Invalid closed-position archive binding'; END IF;
  ELSIF NEW.document->'archive' IS DISTINCT FROM 'null'::jsonb
    OR NEW.document#>'{position,retained_evidence}' IS DISTINCT FROM 'null'::jsonb
  THEN RAISE EXCEPTION 'Missing closed-position retained evidence'; END IF;
  RETURN NEW;
 END IF;
 IF NEW.archive_evidence_id IS NOT NULL THEN""", 1)
assert NEW_ARCHIVE != OLD_ARCHIVE

GUARD = """
CREATE FUNCTION loans_closed_position_event_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE l loans_pawnloan%ROWTYPE;
BEGIN
 SELECT * INTO l FROM loans_pawnloan WHERE id=NEW.loan_id AND workspace_id=NEW.workspace_id;
 IF l.is_imported_closed_position THEN
  IF NEW.event_kind<>'MIGRATION_OPENING' OR NEW.reversal_of_id IS NOT NULL
   OR EXISTS (SELECT 1 FROM loans_pawnloanevent WHERE loan_id=l.id)
   OR NEW.payload#>>'{opening,profile}' IS DISTINCT FROM 'loan-closed-position-evidence/1'
   OR NEW.payload->'values' IS DISTINCT FROM '{"principal":"0","interest":"0","fees":"0"}'::jsonb
  THEN RAISE EXCEPTION 'Closed position cannot acquire invented financial actions'; END IF;
 ELSIF NEW.payload#>>'{opening,profile}'='loan-closed-position-evidence/1'
 THEN RAISE EXCEPTION 'Closed-position evidence requires its closed-position loan'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER loans_closed_position_event_guard BEFORE INSERT ON loans_pawnloanevent
FOR EACH ROW EXECUTE FUNCTION loans_closed_position_event_guard();

CREATE FUNCTION loans_closed_position_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.is_imported_closed_position OR NEW.is_imported_closed_position THEN
  RAISE EXCEPTION 'Accepted closed-position loan is immutable; ordinary origin cannot be relabelled';
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER loans_closed_position_immutable BEFORE UPDATE ON loans_pawnloan
FOR EACH ROW EXECUTE FUNCTION loans_closed_position_immutable();

CREATE FUNCTION loans_closed_position_complete() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE l loans_pawnloan%ROWTYPE; e loans_pawnloanevent%ROWTYPE; o loans_historicalloanimport%ROWTYPE;
 d jsonb; a jsonb; expected_source text;
BEGIN
 SELECT * INTO l FROM loans_pawnloan WHERE id=NEW.id;
 IF NOT l.is_imported_closed_position THEN RETURN NEW; END IF;
 SELECT * INTO e FROM loans_pawnloanevent WHERE loan_id=l.id AND workspace_id=l.workspace_id;
 SELECT * INTO o FROM loans_historicalloanimport WHERE loan_id=l.id AND workspace_id=l.workspace_id;
 a := e.payload#>'{opening,review}'; d := a->'position';
 expected_source := CASE WHEN d#>>'{source,system}' LIKE 'legacy:%'
   THEN split_part(d#>>'{source,system}',':',3)||':'||(d#>>'{source,loan_id}')
   ELSE 'closed:'||encode(sha256(convert_to(char_length(d#>>'{source,system}')::text||':'||
     (d#>>'{source,system}')||(d#>>'{source,loan_id}'),'UTF8')),'hex') END;
 IF l.state<>'CLOSED' OR e.id IS NULL OR o.id IS NULL
  OR (SELECT count(*) FROM loans_pawnloanevent WHERE loan_id=l.id)<>1
  OR EXISTS (SELECT 1 FROM loans_pawncollateralitem WHERE loan_id=l.id)
  OR o.document IS DISTINCT FROM a OR o.source_sha256 IS NULL
  OR a->>'profile' IS DISTINCT FROM 'loan-closed-position-admission/1'
  OR d->>'profile' IS DISTINCT FROM 'loan-closed-position/1'
  OR d->>'earlier_history' IS DISTINCT FROM 'UNAVAILABLE'
  OR d#>>'{position,state}' IS DISTINCT FROM 'CLOSED'
  OR d#>>'{position,currency}' IS DISTINCT FROM 'INR'
  OR d#>>'{position,principal}' IS DISTINCT FROM '0'
  OR d#>>'{position,interest}' IS DISTINCT FROM '0'
  OR d#>>'{position,fees}' IS DISTINCT FROM '0'
  OR COALESCE(d#>>'{position,custody}','') NOT IN ('RETURNED_TO_BORROWER','UNKNOWN')
  OR COALESCE(d#>>'{position,basis}','') NOT IN ('SOURCE_RELEASE_MEANING','OWNER_CLOSED_POSITION')
  OR COALESCE(btrim(d#>>'{position,evidence_reference}'),'')=''
  OR (d#>>'{position,as_of}')::date IS DISTINCT FROM e.effective_date
  OR e.effective_date>CURRENT_DATE
  OR (d#>>'{loan,closed_on}')::date>e.effective_date
  OR (d#>>'{loan,original_date}')::date>e.effective_date
  OR (d#>>'{loan,closed_on}')::date<(d#>>'{loan,original_date}')::date
  OR (d#>>'{loan,original_date}')::date IS DISTINCT FROM l.loan_date
  OR d#>>'{loan,number}' IS DISTINCT FROM l.loan_number
  OR (d#>>'{loan,original_principal}')::numeric IS DISTINCT FROM l.principal_amount
  OR (d#>>'{loan,monthly_rate}')::numeric IS DISTINCT FROM l.monthly_interest_rate
  OR (d#>>'{loan,tenure_months}')::int IS DISTINCT FROM l.tenure_months
  OR a->'mapping' IS DISTINCT FROM jsonb_build_object('workspace_id',l.workspace_id,'borrower_id',l.borrower_id,
     'series_id',l.series_id,'license_id',l.license_id)
  OR o.source_namespace::text IS DISTINCT FROM d#>>'{source,namespace}'
  OR o.source_id IS DISTINCT FROM expected_source
  OR e.payload#>>'{source_identity,loan_id}' IS DISTINCT FROM l.id::text
  OR e.payload->>'effective_date' IS DISTINCT FROM e.effective_date::text
  OR e.payload->>'event_kind' IS DISTINCT FROM 'MIGRATION_OPENING'
  OR e.payload->>'currency' IS DISTINCT FROM 'INR'
  OR e.payload->'contract_version' IS DISTINCT FROM '1'::jsonb
  OR e.payload#>'{opening,item_mapping}' IS DISTINCT FROM '{}'::jsonb
 THEN RAISE EXCEPTION 'Closed position requires exact immutable origin, original facts and zero checkpoint'; END IF;
 RETURN NEW;
END; $$;
CREATE CONSTRAINT TRIGGER loans_closed_position_complete AFTER INSERT ON loans_pawnloan
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW WHEN (NEW.is_imported_closed_position)
EXECUTE FUNCTION loans_closed_position_complete();

CREATE FUNCTION loans_closed_position_item_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF EXISTS (SELECT 1 FROM loans_pawnloan WHERE id=NEW.loan_id AND is_imported_closed_position)
 THEN RAISE EXCEPTION 'Closed-position collateral claims remain retained source evidence'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER loans_closed_position_item_guard BEFORE INSERT OR UPDATE ON loans_pawncollateralitem
FOR EACH ROW EXECUTE FUNCTION loans_closed_position_item_guard();
"""
REVERSE = """
DROP TRIGGER loans_closed_position_item_guard ON loans_pawncollateralitem;
DROP FUNCTION loans_closed_position_item_guard();
DROP TRIGGER loans_closed_position_complete ON loans_pawnloan;
DROP FUNCTION loans_closed_position_complete();
DROP TRIGGER loans_closed_position_immutable ON loans_pawnloan;
DROP FUNCTION loans_closed_position_immutable();
DROP TRIGGER loans_closed_position_event_guard ON loans_pawnloanevent;
DROP FUNCTION loans_closed_position_event_guard();
"""

# These existing roots represent operational agreements/actions, not retained
# source claims. They cannot be attached to a position-only closed admission.
OPERATIONAL_ROOTS = (
    "loans_loanpolicysnapshot", "loans_pawnloanapprovalsnapshot", "loans_pawnloandisbursalsnapshot",
    "loans_repaymentscheduleversion", "loans_pawnloanrelease", "loans_pawnloaninterestaccrual",
)
GUARD += """
CREATE FUNCTION loans_closed_position_operational_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF EXISTS (SELECT 1 FROM loans_pawnloan WHERE id=NEW.loan_id AND is_imported_closed_position)
 THEN RAISE EXCEPTION 'Closed-position admission cannot acquire an operational agreement or transaction'; END IF;
 RETURN NEW;
END; $$;
"""
for table in OPERATIONAL_ROOTS:
    GUARD += f"CREATE TRIGGER closed_position_operational_guard BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION loans_closed_position_operational_guard();\n"
    REVERSE += f"DROP TRIGGER closed_position_operational_guard ON {table};\n"
REVERSE += "DROP FUNCTION loans_closed_position_operational_guard();\n"


class Migration(migrations.Migration):
    dependencies = [("loans", "0064_completed_closure_batch_guards")]
    operations = [
        migrations.AddField("pawnloan", "is_imported_closed_position", models.BooleanField(default=False, editable=False)),
        migrations.AlterField("pawnloan", "product_version", models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="pawn_loans", to="loans.loanproductversion")),
        migrations.AlterField("pawnloan", "principal_amount", models.DecimalField(max_digits=18, decimal_places=2, null=True)),
        migrations.AlterField("pawnloan", "monthly_interest_rate", models.DecimalField(max_digits=9, decimal_places=6, null=True)),
        migrations.AlterField("pawnloan", "loan_date", models.DateField(default=import_module("django.utils.timezone").localdate, db_index=True, null=True)),
        migrations.AlterField("pawnloan", "tenure_months", models.PositiveIntegerField(default=3, null=True)),
        migrations.AddConstraint("pawnloan", models.CheckConstraint(
            condition=(models.Q(is_imported_closed_position=True, state="CLOSED", product_version__isnull=True,
                policy_snapshot__isnull=True, disbursal_snapshot__isnull=True, license_revision__isnull=True)
                | models.Q(is_imported_closed_position=False, principal_amount__isnull=False,
                    monthly_interest_rate__isnull=False, tenure_months__isnull=False, loan_date__isnull=False, product_version__isnull=False)),
            name="loans_pawn_position_or_complete")),
        migrations.RunSQL(NEW_ARCHIVE, OLD_ARCHIVE),
        migrations.RunSQL(GUARD, REVERSE),
    ]
