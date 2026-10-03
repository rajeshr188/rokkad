"""Reuse the isolated, immutable financial-origin registry for archive admission."""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("loans", "0041_recorded_origination_basis")]
    operations = [
        migrations.AddField(model_name="historicalloanimport", name="archive_evidence",
            field=models.OneToOneField(null=True, blank=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="financial_admission", to="loans.historicalloanevidence")),
        migrations.RunSQL("""
CREATE FUNCTION loans_archive_admission_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE a loans_historicalloanevidence%ROWTYPE;
BEGIN
 IF NEW.archive_evidence_id IS NOT NULL THEN
  SELECT * INTO a FROM loans_historicalloanevidence WHERE id=NEW.archive_evidence_id AND workspace_id=NEW.workspace_id;
  IF NOT FOUND OR NEW.source_namespace IS DISTINCT FROM a.source_namespace
   OR NEW.document->>'profile' IS DISTINCT FROM 'archive-admission/1'
   OR NEW.document#>>'{archive,sha256}' IS DISTINCT FROM a.source_sha256
   OR NEW.document#>>'{archive,id}' IS DISTINCT FROM a.id::text
   OR NEW.source_id IS DISTINCT FROM (CASE WHEN a.source_system LIKE 'legacy:%'
     THEN split_part(a.source_system, ':', 3)||':'||a.source_id ELSE a.source_id END)
   OR NOT EXISTS (SELECT 1 FROM loans_pawnloan l JOIN loans_loanpolicysnapshot p ON p.loan_id=l.id
     JOIN loans_pawnloandisbursalsnapshot d ON d.loan_id=l.id
     WHERE l.id=NEW.loan_id AND l.workspace_id=NEW.workspace_id AND l.state='CLOSED' AND p.basis='RECORDED_CONTRACT'
       AND d.evidence#>>'{recording,archive_admission,id}'=a.id::text
       AND d.evidence#>>'{recording,archive_admission,sha256}'=a.source_sha256)
  THEN RAISE EXCEPTION 'Invalid archive admission binding'; END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER loans_archive_admission_guard BEFORE INSERT ON loans_historicalloanimport
FOR EACH ROW EXECUTE FUNCTION loans_archive_admission_guard();
""", "DROP TRIGGER loans_archive_admission_guard ON loans_historicalloanimport; DROP FUNCTION loans_archive_admission_guard();"),
    ]
