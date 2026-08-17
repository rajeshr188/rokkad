from django.db import migrations, models
import django.utils.timezone


def map_deleted_flag(apps, schema_editor):
    Company = apps.get_model("orgs", "Company")
    Company.objects.filter(is_deleted=True).update(lifecycle_state="ARCHIVED")


class Migration(migrations.Migration):
    dependencies = [("orgs", "0002_workspace_ownership_and_membership_integrity")]

    operations = [
        migrations.AddField(
            model_name="company",
            name="lifecycle_state",
            field=models.CharField(
                choices=[
                    ("ACTIVE", "Active"),
                    ("SUSPENDED", "Suspended"),
                    ("ARCHIVED", "Archived"),
                    ("DELETION_PENDING", "Deletion pending"),
                ],
                db_index=True,
                default="ACTIVE",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="company",
            name="lifecycle_changed_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name="company",
            name="lifecycle_reason",
            field=models.TextField(blank=True),
        ),
        migrations.RunPython(map_deleted_flag, migrations.RunPython.noop),
        migrations.RemoveField(model_name="company", name="is_deleted"),
    ]
