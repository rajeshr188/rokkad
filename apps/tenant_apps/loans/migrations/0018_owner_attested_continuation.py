"""Owner-attested continuation retains source and numbering safeguards.

Forward-only once an attestation exists; never activate existing rows implicitly.
"""
from django.db import migrations, models


GUARDS = r"""
CREATE OR REPLACE FUNCTION loans_guard_legacy_revision_kind() RETURNS trigger AS $$
DECLARE legacy boolean;
BEGIN
    SELECT is_legacy_reference INTO legacy FROM loans_loanlicense
      WHERE id = NEW.license_id AND workspace_id = NEW.workspace_id FOR UPDATE;
    IF NEW.kind IN ('VERIFICATION', 'ATTESTATION') THEN
        IF legacy IS DISTINCT FROM TRUE OR NEW.created_by_id IS NULL
           OR NEW.issuing_authority = ''
           OR (NEW.verification_evidence->>'profile') IS DISTINCT FROM 'legacy-license-continuation/1'
           OR (NEW.verification_evidence->'confirmed_complete') IS DISTINCT FROM 'true'::jsonb
           OR COALESCE(NEW.verification_evidence->>'source_sha256', '') !~ '^[0-9a-f]{64}$'
           OR COALESCE(NEW.verification_evidence->>'source_reference', '') = ''
           OR COALESCE(NEW.verification_evidence->>'source_as_of', '') !~ '^\d{4}-\d{2}-\d{2}$'
           OR jsonb_typeof(NEW.verification_evidence->'sequences') IS DISTINCT FROM 'array'
           OR NOT EXISTS (
               SELECT 1 FROM loans_loanlicenserevision r
               WHERE r.license_id = NEW.license_id AND r.workspace_id = NEW.workspace_id
                 AND r.kind = 'LEGACY_REFERENCE'
                 AND r.id::text = NEW.verification_evidence->>'previous_revision_id'
                 AND r.revision_number = NEW.revision_number - 1
           ) THEN
            RAISE EXCEPTION 'Legacy continuation requires complete source and numbering evidence';
        END IF;
        IF NEW.kind = 'VERIFICATION' AND (
            NEW.supporting_document = '' OR NEW.sha256 !~ '^[0-9a-f]{64}$' OR NEW.byte_size <= 0
        ) THEN
            RAISE EXCEPTION 'Verified continuation requires a supporting document';
        END IF;
        IF NEW.kind = 'ATTESTATION' AND (
            NEW.supporting_document <> '' OR NEW.sha256 <> '' OR NEW.byte_size <> 0
            OR NEW.original_filename <> '' OR NEW.mime_type <> ''
            OR (NEW.verification_evidence->'document_deferred') IS DISTINCT FROM 'true'::jsonb
            OR (NEW.verification_evidence->>'validity_basis') IS DISTINCT FROM 'owner_attested'
            OR jsonb_typeof(NEW.verification_evidence->'document_deferral_reason') IS DISTINCT FROM 'string'
            OR length(trim(COALESCE(NEW.verification_evidence->>'document_deferral_reason', ''))) NOT BETWEEN 1 AND 1000
            OR NOT EXISTS (SELECT 1 FROM orgs_company w
                           WHERE w.id = NEW.workspace_id AND w.owner_id = NEW.created_by_id)
        ) THEN
            RAISE EXCEPTION 'Document deferral requires owner attestation, a reason and no substitute document';
        END IF;
        IF jsonb_array_length(NEW.verification_evidence->'sequences') = 0 OR EXISTS (
            SELECT 1 FROM loans_loannumbersequence s
            JOIN loans_loanseries series ON series.id = s.series_id
            WHERE series.license_id = NEW.license_id AND NOT EXISTS (
                SELECT 1 FROM jsonb_array_elements(NEW.verification_evidence->'sequences') e
                WHERE e->>'sequence_id' = s.id::text AND e->>'series_id' = s.series_id::text
                  AND e->>'kind' = s.document_kind AND e->>'prefix' = s.prefix
                  AND e->>'width' = s.width::text AND e->>'maximum' = s.maximum_number::text
                  AND e->>'next_number' = s.next_number::text
                  AND e->>'last_used' = (s.next_number - 1)::text
            )
        ) THEN
            RAISE EXCEPTION 'Continuation numbering evidence must match all reserved sequences';
        END IF;
    ELSIF legacy IS NULL OR legacy <> (NEW.kind = 'LEGACY_REFERENCE') THEN
        RAISE EXCEPTION 'Legacy reference and current licence revisions must remain separate';
    END IF;
    RETURN NEW;
END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION loans_guard_legacy_license_identity() RETURNS trigger AS $$
BEGIN
    IF NEW.is_legacy_reference IS DISTINCT FROM OLD.is_legacy_reference THEN
        IF NOT OLD.is_legacy_reference OR NOT NEW.is_active
           OR NEW.license_number IS DISTINCT FROM OLD.license_number
           OR NEW.name IS DISTINCT FROM OLD.name
           OR NOT EXISTS (
              SELECT 1 FROM loans_loanlicenserevision r
              WHERE r.license_id = NEW.id AND r.workspace_id = NEW.workspace_id
                AND r.kind IN ('VERIFICATION', 'ATTESTATION') AND r.license_number = NEW.license_number
                AND r.name = NEW.name AND r.issued_on = NEW.issued_on
                AND r.expires_on = NEW.expires_on AND r.issuing_authority = NEW.issuing_authority
                AND r.created_by_id = NEW.updated_by_id
                AND r.revision_number = (SELECT MAX(revision_number)
                    FROM loans_loanlicenserevision WHERE license_id = NEW.id)
           ) THEN
            RAISE EXCEPTION 'Legacy reference identity requires an audited continuation revision';
        END IF;
    END IF;
    RETURN NEW;
END; $$ LANGUAGE plpgsql;
"""


class Migration(migrations.Migration):
    dependencies = [("loans", "0017_license_printed_business_details")]
    operations = [
        migrations.AlterField(model_name="loanlicenserevision", name="kind",
            field=models.CharField(max_length=16, choices=[
                ("INITIAL", "Initial issue"), ("AMENDMENT", "Amendment"),
                ("RENEWAL", "Renewal"), ("LEGACY_REFERENCE", "Legacy reference (validity unknown)"),
                ("VERIFICATION", "Verified legacy license continuation"),
                ("ATTESTATION", "Owner attestation (document pending)")])),
        migrations.RunSQL(GUARDS),
    ]
