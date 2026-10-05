"""Permit evidenced past payouts without treating a legacy reference as a licence.

Forward-only once such origins exist; current lending and licence validity are
unchanged. A deferred check requires the validated recorded snapshot at commit.
"""
from django.db import migrations


GUARDS = r"""
CREATE OR REPLACE FUNCTION loans_guard_legacy_origination() RETURNS trigger AS $$
BEGIN
    IF NEW.event_kind = 'DISBURSAL' AND EXISTS (
        SELECT 1 FROM loans_pawnloan l JOIN loans_loanlicense r ON r.id=l.license_id
        LEFT JOIN loans_loanlicenserevision v ON v.id=l.license_revision_id
        WHERE l.id=NEW.loan_id AND l.workspace_id=NEW.workspace_id
          AND (r.is_legacy_reference OR v.kind='LEGACY_REFERENCE')
    ) AND NOT (
        NEW.created_by_id IS NOT NULL
        AND NEW.payload->'disbursal'->>'basis' IS NOT DISTINCT FROM 'RECORDED'
        AND NEW.payload->'disbursal'->'approval_snapshot_id' IS NOT DISTINCT FROM 'null'::jsonb
        AND NEW.payload->'recording'->>'schema' IS NOT DISTINCT FROM 'recorded-origination/1'
        AND NEW.payload->'recording'->'payout_already_occurred' IS NOT DISTINCT FROM 'true'::jsonb
        AND NEW.payload->'recording'->>'date_precision' IS NOT DISTINCT FROM 'DAY'
        AND NEW.payload->'recording'->>'occurred_on' IS NOT DISTINCT FROM NEW.effective_date::text
        AND COALESCE(length(trim(NEW.payload->'recording'->>'source_reference')),0) BETWEEN 1 AND 160
        AND EXISTS (
            SELECT 1 FROM loans_pawnloan l JOIN loans_loanpolicysnapshot p
              ON p.loan_id=l.id AND p.workspace_id=l.workspace_id
            WHERE l.id=NEW.loan_id AND l.workspace_id=NEW.workspace_id
              AND l.loan_date=NEW.effective_date AND p.basis='RECORDED_CONTRACT'
              AND p.id::text=NEW.payload->'disbursal'->>'policy_snapshot_id'
        )
    ) THEN
        RAISE EXCEPTION 'A legacy licence reference cannot authorize new disbursal; completed payout needs recorded contract evidence';
    END IF;
    RETURN NEW;
END; $$ LANGUAGE plpgsql;

CREATE FUNCTION loans_check_legacy_recorded_origin() RETURNS trigger AS $$
BEGIN
    IF NEW.event_kind='DISBURSAL' AND EXISTS (
        SELECT 1 FROM loans_pawnloan l JOIN loans_loanlicense r ON r.id=l.license_id
        LEFT JOIN loans_loanlicenserevision v ON v.id=l.license_revision_id
        WHERE l.id=NEW.loan_id AND l.workspace_id=NEW.workspace_id
          AND (r.is_legacy_reference OR v.kind='LEGACY_REFERENCE')
    ) AND NOT EXISTS (
        SELECT 1 FROM loans_pawnloandisbursalsnapshot s
        JOIN loans_loanpolicysnapshot p ON p.id=s.policy_snapshot_id
          AND p.loan_id=s.loan_id AND p.workspace_id=s.workspace_id
        WHERE s.loan_event_id=NEW.id AND s.loan_id=NEW.loan_id
          AND s.workspace_id=NEW.workspace_id AND s.basis='RECORDED'
          AND s.approval_snapshot_id IS NULL AND p.basis='RECORDED_CONTRACT'
          AND s.evidence->'recording'=NEW.payload->'recording'
    ) THEN
        RAISE EXCEPTION 'Legacy completed payout must commit with its validated recorded snapshot';
    END IF;
    RETURN NEW;
END; $$ LANGUAGE plpgsql;
CREATE CONSTRAINT TRIGGER loans_legacy_recorded_origin_complete
AFTER INSERT ON loans_pawnloanevent DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION loans_check_legacy_recorded_origin();
"""


class Migration(migrations.Migration):
    dependencies = [("loans", "0057_default_entry_purpose")]
    operations = [migrations.RunSQL(GUARDS)]
