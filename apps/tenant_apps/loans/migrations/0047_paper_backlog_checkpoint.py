import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from apps.tenancy.rls import EnableWorkspaceRLS


class Migration(migrations.Migration):
    dependencies = [("loans", "0046_merge_khata_series_status"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="PaperBacklogCheckpoint", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("book_reference", models.CharField(max_length=160)),
            ("through_date", models.DateField()),
            ("last_page_reference", models.CharField(max_length=160)),
            ("state", models.CharField(max_length=16, choices=[("IN_PROGRESS", "Entry in progress"), ("ENTERED", "Entry finished for this book/date"), ("NEEDS_REVIEW", "Needs reconciliation")])),
            ("note", models.CharField(max_length=500, blank=True)),
            ("request_key", models.CharField(max_length=120)),
            ("recorded_at", models.DateTimeField(auto_now_add=True)),
            ("recorded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
            ("workspace", models.ForeignKey(editable=False, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="orgs.company")),
        ], options={"ordering": ("-id",), "constraints": [models.UniqueConstraint(fields=("workspace", "request_key"), name="loans_backlog_request_unique")]}),
        EnableWorkspaceRLS("PaperBacklogCheckpoint"),
        migrations.RunSQL("""
CREATE FUNCTION loans_backlog_checkpoint_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'Backlog checkpoints are immutable'; END IF;
 IF btrim(NEW.book_reference) = '' OR btrim(NEW.last_page_reference) = '' OR btrim(NEW.request_key) = ''
 OR NEW.state NOT IN ('IN_PROGRESS', 'ENTERED', 'NEEDS_REVIEW')
 THEN RAISE EXCEPTION 'Invalid backlog checkpoint'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER loans_backlog_checkpoint_guard BEFORE INSERT OR UPDATE OR DELETE ON loans_paperbacklogcheckpoint
FOR EACH ROW EXECUTE FUNCTION loans_backlog_checkpoint_guard();
""", "DROP TRIGGER loans_backlog_checkpoint_guard ON loans_paperbacklogcheckpoint; DROP FUNCTION loans_backlog_checkpoint_guard();"),
    ]
