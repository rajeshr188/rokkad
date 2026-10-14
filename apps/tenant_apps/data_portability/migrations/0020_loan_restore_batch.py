import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone
from apps.tenancy.rls import EnableWorkspaceRLS
from apps.tenant_apps.data_portability.models import loan_restore_source_path


GUARD = """
CREATE FUNCTION portability_loan_restore_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE item jsonb;
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Loan restore history is retained'; END IF;
 IF NEW.profile NOT IN ('loan-opening-export/1','loan-opening-export/2','loan-opening-export/3','loan-opening-export/4',
  'loan-servicing-bundle/1','loan-closed-position/1','loan-closed-position-bundle/1')
 OR NEW.source_sha256 !~ '^[0-9a-f]{64}$' OR NEW.state NOT IN ('STAGED','READY','COMPLETED','CANCELLED')
 THEN RAISE EXCEPTION 'Invalid restore profile, source or state'; END IF;
 IF TG_OP='INSERT' THEN
  IF NEW.state<>'STAGED' OR NEW.mapping<>'{}'::jsonb OR NEW.preview<>'{}'::jsonb OR NEW.results<>'[]'::jsonb
   OR NEW.approval_digest<>'' OR NEW.committed_at IS NOT NULL OR NEW.committed_by_id IS NOT NULL
  THEN RAISE EXCEPTION 'Restore begins with unreviewed staging'; END IF;
 ELSE
  IF OLD.state IN ('COMPLETED','CANCELLED') THEN RAISE EXCEPTION 'Finished restores are immutable'; END IF;
  IF NEW.workspace_id<>OLD.workspace_id OR NEW.public_id<>OLD.public_id OR NEW.profile<>OLD.profile
   OR NEW.created_by_id<>OLD.created_by_id OR NEW.created_at<>OLD.created_at OR NEW.source_sha256<>OLD.source_sha256
   OR (NEW.source<>OLD.source AND NOT (NEW.state='CANCELLED' AND NEW.source=''))
   OR (NEW.document IS DISTINCT FROM OLD.document AND NOT (NEW.state='CANCELLED' AND NEW.document='{}'::jsonb))
  THEN RAISE EXCEPTION 'Staged restore source is immutable'; END IF;
  IF NEW.state='COMPLETED' AND OLD.state<>'READY' THEN RAISE EXCEPTION 'Review is required'; END IF;
 END IF;
 IF NEW.state='CANCELLED' THEN
  IF NEW.source<>'' OR NEW.document<>'{}'::jsonb OR NEW.mapping<>'{}'::jsonb OR NEW.preview<>'{}'::jsonb
   OR NEW.approval_digest<>'' THEN RAISE EXCEPTION 'Cancellation clears staged values'; END IF;
 ELSE
  IF NEW.source IS DISTINCT FROM ('loan_restore/'||NEW.workspace_id||'/'||NEW.public_id||'/source')
   OR jsonb_typeof(NEW.document->'loans') IS DISTINCT FROM 'array'
   OR jsonb_array_length(NEW.document->'loans') NOT BETWEEN 1 AND 20
  THEN RAISE EXCEPTION 'Invalid restore file reference or loan inventory'; END IF;
 END IF;
 IF NEW.state IN ('READY','COMPLETED') AND (NEW.approval_digest !~ '^[0-9a-f]{64}$'
   OR NEW.mapping='{}'::jsonb OR NEW.preview='{}'::jsonb)
 THEN RAISE EXCEPTION 'Exact restore review is required'; END IF;
 IF jsonb_typeof(NEW.results) IS DISTINCT FROM 'array' THEN RAISE EXCEPTION 'Invalid restore results'; END IF;
 IF NEW.state='COMPLETED' THEN
  IF NEW.committed_at IS NULL OR NEW.committed_by_id IS NULL
   OR jsonb_array_length(NEW.results)<>jsonb_array_length(NEW.document->'loans')
   OR (SELECT count(DISTINCT x) FROM jsonb_array_elements(NEW.results) x)<>jsonb_array_length(NEW.results)
  THEN RAISE EXCEPTION 'Complete restore needs exact distinct results and actor'; END IF;
  FOR item IN SELECT value FROM jsonb_array_elements(NEW.results) LOOP
   IF jsonb_typeof(item)<>'number' OR item::text !~ '^[1-9][0-9]*$'
    OR NOT EXISTS (SELECT 1 FROM loans_historicalloanimport h WHERE h.loan_id=(item::text)::bigint AND h.workspace_id=NEW.workspace_id)
   THEN RAISE EXCEPTION 'Restore result must be an accepted origin in this Workspace'; END IF;
  END LOOP;
 ELSE
  IF NEW.results<>'[]'::jsonb OR NEW.committed_at IS NOT NULL OR NEW.committed_by_id IS NOT NULL
  THEN RAISE EXCEPTION 'Unfinished restore cannot claim results'; END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER portability_loan_restore_guard BEFORE INSERT OR UPDATE OR DELETE ON data_portability_loanrestorebatch
FOR EACH ROW EXECUTE FUNCTION portability_loan_restore_guard();
"""


class Migration(migrations.Migration):
    dependencies = [('data_portability', '0019_loan_history_v4'), ('loans', '0068_compact_closed_position_evidence'),
                    migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='LoanRestoreBatch', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('public_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
            ('profile', models.CharField(max_length=32)),
            ('source', models.FileField(blank=True, max_length=255, upload_to=loan_restore_source_path)),
            ('source_sha256', models.CharField(max_length=64)), ('document', models.JSONField()),
            ('mapping', models.JSONField(default=dict)), ('preview', models.JSONField(default=dict)),
            ('approval_digest', models.CharField(blank=True, max_length=64)),
            ('state', models.CharField(default='STAGED', max_length=12, choices=[(s,s) for s in ('STAGED','READY','COMPLETED','CANCELLED')])),
            ('results', models.JSONField(default=list)), ('created_at', models.DateTimeField(default=timezone.now, editable=False)),
            ('committed_at', models.DateTimeField(null=True)),
            ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL)),
            ('committed_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL)),
            ('workspace', models.ForeignKey(editable=False, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='orgs.company')),
        ], options={'constraints': [models.UniqueConstraint(fields=('workspace','source_sha256'), condition=~models.Q(state='CANCELLED'), name='port_restore_source_active_uniq')]}),
        EnableWorkspaceRLS('LoanRestoreBatch'),
        migrations.RunSQL(GUARD, """DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM data_portability_loanrestorebatch)
            THEN RAISE EXCEPTION 'Cannot remove restore support while retained batches exist'; END IF;
            END; $$;
            DROP TRIGGER portability_loan_restore_guard ON data_portability_loanrestorebatch;
            DROP FUNCTION portability_loan_restore_guard();"""),
    ]
