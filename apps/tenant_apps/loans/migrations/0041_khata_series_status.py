from django.conf import settings
from django.core.validators import MaxLengthValidator
from django.db import migrations, models
import django.db.models.deletion

from apps.tenancy.rls import EnableWorkspaceRLS


SQL = """
CREATE FUNCTION loans_khata_series_status_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE s loans_khataseries%ROWTYPE; latest loans_khataseriesstatuschange%ROWTYPE;
  current_status text; old_status text; new_status text;
BEGIN
  IF TG_TABLE_NAME = 'loans_khataseriesstatuschange' THEN
    IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'Khata series status evidence is immutable'; END IF;
    SELECT * INTO s FROM loans_khataseries WHERE id=NEW.series_id FOR UPDATE;
    IF NOT FOUND OR s.workspace_id <> NEW.workspace_id THEN RAISE EXCEPTION 'Khata series status Workspace mismatch'; END IF;
    current_status := CASE WHEN s.retired_at IS NOT NULL THEN 'RETIRED' WHEN s.is_active THEN 'ACTIVE' ELSE 'PAUSED' END;
    SELECT * INTO latest FROM loans_khataseriesstatuschange WHERE series_id=s.id ORDER BY number DESC LIMIT 1;
    IF NEW.number <> COALESCE(latest.number,0)+1 OR NEW.from_status <> current_status
      OR current_status='RETIRED' OR btrim(NEW.reason)='' OR length(NEW.reason)>2000
      OR NEW.request_sha256 !~ '^[0-9a-f]{64}$'
    THEN RAISE EXCEPTION 'Invalid khata series status transition evidence'; END IF;
    RETURN NEW;
  END IF;
  IF TG_OP='INSERT' THEN
    IF NOT NEW.is_active OR NEW.retired_at IS NOT NULL THEN RAISE EXCEPTION 'New khata series must be active'; END IF;
  ELSIF NEW.is_active IS DISTINCT FROM OLD.is_active OR NEW.retired_at IS DISTINCT FROM OLD.retired_at THEN
    old_status := CASE WHEN OLD.retired_at IS NOT NULL THEN 'RETIRED' WHEN OLD.is_active THEN 'ACTIVE' ELSE 'PAUSED' END;
    new_status := CASE WHEN NEW.retired_at IS NOT NULL THEN 'RETIRED' WHEN NEW.is_active THEN 'ACTIVE' ELSE 'PAUSED' END;
    SELECT * INTO latest FROM loans_khataseriesstatuschange WHERE series_id=NEW.id ORDER BY number DESC LIMIT 1;
    IF old_status='RETIRED' OR latest.id IS NULL OR latest.from_status <> old_status OR latest.to_status <> new_status
      OR (new_status='RETIRED' AND NEW.retired_at IS DISTINCT FROM latest.created_at)
      OR (new_status<>'RETIRED' AND NEW.retired_at IS NOT NULL)
    THEN RAISE EXCEPTION 'Khata series status requires immutable transition evidence'; END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE FUNCTION loans_khata_series_status_project() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  UPDATE loans_khataseries SET is_active=(NEW.to_status='ACTIVE'),
    retired_at=CASE WHEN NEW.to_status='RETIRED' THEN NEW.created_at ELSE NULL END WHERE id=NEW.series_id;
  RETURN NEW;
END $$;
CREATE TRIGGER loans_khata_series_availability_guard BEFORE INSERT OR UPDATE ON loans_khataseries
  FOR EACH ROW EXECUTE FUNCTION loans_khata_series_status_guard();
CREATE TRIGGER loans_khata_series_status_guard BEFORE INSERT OR UPDATE OR DELETE ON loans_khataseriesstatuschange
  FOR EACH ROW EXECUTE FUNCTION loans_khata_series_status_guard();
CREATE TRIGGER loans_khata_series_status_project AFTER INSERT ON loans_khataseriesstatuschange
  FOR EACH ROW EXECUTE FUNCTION loans_khata_series_status_project();
"""
REVERSE = """
DROP TRIGGER loans_khata_series_status_project ON loans_khataseriesstatuschange;
DROP TRIGGER loans_khata_series_status_guard ON loans_khataseriesstatuschange;
DROP TRIGGER loans_khata_series_availability_guard ON loans_khataseries;
DROP FUNCTION loans_khata_series_status_project();
DROP FUNCTION loans_khata_series_status_guard();
"""


class Migration(migrations.Migration):
    dependencies = [("loans", "0040_khata_labels"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name="khataseries", name="retired_at", field=models.DateTimeField(blank=True, editable=False, null=True)),
        migrations.AddConstraint(model_name="khataseries", constraint=models.CheckConstraint(condition=models.Q(retired_at__isnull=True) | models.Q(is_active=False), name="khata_series_retired_inactive")),
        migrations.CreateModel(name="KhataSeriesStatusChange", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("number", models.PositiveIntegerField()),
            ("from_status", models.CharField(choices=[("ACTIVE", "Active"), ("PAUSED", "Paused"), ("RETIRED", "Retired")], max_length=7)),
            ("to_status", models.CharField(choices=[("ACTIVE", "Active"), ("PAUSED", "Paused"), ("RETIRED", "Retired")], max_length=7)),
            ("reason", models.TextField(validators=[MaxLengthValidator(2000)])),
            ("request_key", models.UUIDField()),
            ("request_sha256", models.CharField(max_length=64)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
            ("series", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="status_changes", to="loans.khataseries")),
            ("workspace", models.ForeignKey(editable=False, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="orgs.company")),
        ], options={"ordering": ("-number",), "constraints": [
            models.UniqueConstraint(fields=("workspace", "request_key"), name="khata_series_change_request_uniq"),
            models.UniqueConstraint(fields=("series", "number"), name="khata_series_change_number_uniq"),
            models.CheckConstraint(condition=models.Q(number__gte=1), name="khata_series_change_number_positive"),
            models.CheckConstraint(condition=models.Q(from_status="ACTIVE", to_status__in=("PAUSED", "RETIRED")) | models.Q(from_status="PAUSED", to_status__in=("ACTIVE", "RETIRED")), name="khata_series_transition_valid"),
        ]}),
        EnableWorkspaceRLS("KhataSeriesStatusChange"),
        migrations.RunSQL(SQL, REVERSE),
    ]
