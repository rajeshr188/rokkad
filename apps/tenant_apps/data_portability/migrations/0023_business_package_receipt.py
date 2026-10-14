import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone
from apps.tenancy.rls import EnableWorkspaceRLS
from apps.tenant_apps.data_portability.models import business_package_source_path

GUARD = """
CREATE FUNCTION portability_business_package_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE item jsonb;
BEGIN
 IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'Business package receipts are immutable'; END IF;
 IF NEW.source_sha256 !~ '^[0-9a-f]{64}$' OR NEW.source_file_sha256 !~ '^[0-9a-f]{64}$'
 OR NEW.source IS DISTINCT FROM ('business_package/'||NEW.workspace_id||'/'||NEW.public_id||'/source.json')
 OR jsonb_typeof(NEW.summary) IS DISTINCT FROM 'object'
 OR NEW.summary->>'profile' IS DISTINCT FROM 'rokkad-business-package/1'
 OR jsonb_typeof(NEW.results) IS DISTINCT FROM 'array'
 OR jsonb_typeof(NEW.summary->'counts') IS DISTINCT FROM 'object'
 OR COALESCE(NEW.summary->'counts'->>'loans','') !~ '^[0-9]+$'
 OR (NEW.summary->'counts'->>'loans')::bigint<>jsonb_array_length(NEW.results)
 OR jsonb_array_length(NEW.results)>50000
 OR (SELECT count(DISTINCT x) FROM jsonb_array_elements(NEW.results) x)<>jsonb_array_length(NEW.results)
 THEN RAISE EXCEPTION 'Invalid business package receipt'; END IF;
 FOR item IN SELECT value FROM jsonb_array_elements(NEW.results) LOOP
  IF jsonb_typeof(item)<>'number' OR item::text !~ '^[1-9][0-9]*$'
  OR NOT EXISTS (SELECT 1 FROM loans_historicalloanimport h WHERE h.workspace_id=NEW.workspace_id AND h.loan_id=(item::text)::bigint)
  THEN RAISE EXCEPTION 'Package loan must have an accepted origin in this Workspace'; END IF;
 END LOOP;
 RETURN NEW;
END; $$;
CREATE TRIGGER portability_business_package_guard BEFORE INSERT OR UPDATE OR DELETE ON data_portability_businesspackagereceipt
FOR EACH ROW EXECUTE FUNCTION portability_business_package_guard();
"""


class Migration(migrations.Migration):
    dependencies = [('data_portability', '0022_accepted_party_reference_index'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='BusinessPackageReceipt', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('public_id', models.UUIDField(default=uuid.uuid4, unique=True, editable=False)),
            ('source_sha256', models.CharField(max_length=64)),
            ('source', models.FileField(upload_to=business_package_source_path, max_length=255)),
            ('source_file_sha256', models.CharField(max_length=64)),
            ('summary', models.JSONField()), ('results', models.JSONField(default=list)),
            ('created_at', models.DateTimeField(default=timezone.now, editable=False)),
            ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL)),
            ('workspace', models.ForeignKey(editable=False, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='orgs.company')),
        ], options={'constraints':[models.UniqueConstraint(fields=('workspace',), name='port_business_package_ws_uniq')]}),
        EnableWorkspaceRLS('BusinessPackageReceipt'),
        migrations.RunSQL(GUARD, """DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM data_portability_businesspackagereceipt) THEN RAISE EXCEPTION 'Retained package receipts prevent reversal'; END IF;
          END; $$;
          DROP TRIGGER portability_business_package_guard ON data_portability_businesspackagereceipt;
          DROP FUNCTION portability_business_package_guard();"""),
    ]
