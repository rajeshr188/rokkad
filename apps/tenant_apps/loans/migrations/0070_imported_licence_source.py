"""Imported regulatory claims remain distinct from local approval/attestation."""
from importlib import import_module
from django.db import migrations, models

OLD = import_module('apps.tenant_apps.loans.migrations.0018_owner_attested_continuation').GUARDS.split('CREATE OR REPLACE FUNCTION loans_guard_legacy_license_identity')[0]
POINT = "    IF NEW.kind IN ('VERIFICATION', 'ATTESTATION') THEN"
NEW = OLD.replace(POINT, """
    IF NEW.kind='IMPORTED_SOURCE' THEN
        IF NEW.created_by_id IS NULL OR EXISTS (SELECT 1 FROM loans_loanlicense WHERE id=NEW.license_id AND is_active)
           OR NEW.verification_evidence->>'profile' IS DISTINCT FROM 'licence-source-transfer/1'
           OR jsonb_typeof(NEW.verification_evidence) IS DISTINCT FROM 'object'
           OR (SELECT count(*) FROM jsonb_object_keys(NEW.verification_evidence))<>5
           OR COALESCE(NEW.verification_evidence->>'namespace','') !~ '^[0-9a-f-]{36}$'
           OR COALESCE(NEW.verification_evidence->>'source_id','') !~ '^[1-9][0-9]*$'
           OR COALESCE(NEW.verification_evidence->>'source_kind','') NOT IN
              ('INITIAL','AMENDMENT','RENEWAL','LEGACY_REFERENCE','VERIFICATION','ATTESTATION','IMPORTED_SOURCE')
           OR jsonb_typeof(NEW.verification_evidence->'original_evidence') IS DISTINCT FROM 'object'
           OR octet_length(NEW.verification_evidence::text)>1048576
        THEN RAISE EXCEPTION 'Imported licence needs source-only evidence and inactive lending'; END IF;
        RETURN NEW;
    END IF;
"""+POINT)
assert NEW != OLD
APPROVAL = """
CREATE FUNCTION loans_check_imported_source_approval() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF EXISTS (SELECT 1 FROM loans_pawnloan l JOIN loans_loanlicenserevision r ON r.id=l.license_revision_id
  WHERE l.id=NEW.loan_id AND r.kind='IMPORTED_SOURCE') THEN
  IF COALESCE(NEW.payload#>>'{historical_approval,reference}','') NOT LIKE 'servicing-source:%'
    OR NOT EXISTS (SELECT 1 FROM loans_historicalloanimport h WHERE h.loan_id=NEW.loan_id AND h.workspace_id=NEW.workspace_id
      AND h.references#>>'{portable,document,profile}' IN ('loan-servicing-bundle/1','loan-servicing-bundle/2','loan-servicing-bundle/3','loan-servicing-bundle/4'))
  THEN RAISE EXCEPTION 'Imported licence source evidence cannot approve new lending'; END IF;
 END IF;
 RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER loans_imported_source_approval_guard AFTER INSERT ON loans_pawnloanapprovalsnapshot
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION loans_check_imported_source_approval();
"""
REVERSE = """DO $$ BEGIN
IF EXISTS (SELECT 1 FROM loans_loanlicenserevision WHERE kind='IMPORTED_SOURCE')
THEN RAISE EXCEPTION 'Imported regulatory evidence must remain supported'; END IF;
END; $$;
DROP TRIGGER loans_imported_source_approval_guard ON loans_pawnloanapprovalsnapshot;
DROP FUNCTION loans_check_imported_source_approval();
"""+OLD


class Migration(migrations.Migration):
    dependencies=[('loans','0069_retained_zero_opening_item')]
    operations=[migrations.AlterField(model_name='loanlicenserevision',name='kind',field=models.CharField(max_length=16,
        choices=[('INITIAL','Initial issue'),('AMENDMENT','Amendment'),('RENEWAL','Renewal'),
        ('LEGACY_REFERENCE','Legacy reference (validity unknown)'),('VERIFICATION','Verified legacy license continuation'),
        ('ATTESTATION','Owner attestation (document pending)'),('IMPORTED_SOURCE','Imported source evidence (review for new lending)')])),
        migrations.RemoveConstraint(model_name='loanlicenserevision',name='loans_licrev_validity_evidence'),
        migrations.AddConstraint(model_name='loanlicenserevision',constraint=models.CheckConstraint(
            condition=models.Q(kind__in=('LEGACY_REFERENCE','IMPORTED_SOURCE'),issued_on__isnull=True,expires_on__isnull=True)
            | (~models.Q(kind='LEGACY_REFERENCE')&models.Q(issued_on__isnull=False,expires_on__isnull=False)),
            name='loans_licrev_validity_evidence')),
        migrations.RunSQL(NEW+APPROVAL,REVERSE)]
