from django.db import migrations, models
from django.utils.text import slugify


def backfill_workspace_slugs(apps, schema_editor):
    Company = apps.get_model("orgs", "Company")
    used = set()
    for company in Company.objects.order_by("pk"):
        base = slugify(company.schema_name or company.name)[:63]
        if not base:
            base = f"workspace-{company.pk}"
        candidate = base
        suffix = 2
        while candidate in used:
            marker = f"-{suffix}"
            candidate = f"{base[: 63 - len(marker)]}{marker}"
            suffix += 1
        company.slug = candidate
        company.save(update_fields=["slug"])
        used.add(candidate)


class Migration(migrations.Migration):
    dependencies = [("orgs", "0004_retire_pending_invitation_bridge")]

    operations = [
        migrations.AddField(
            model_name="company",
            name="slug",
            field=models.CharField(blank=True, max_length=63, null=True),
        ),
        migrations.RunPython(backfill_workspace_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="company",
            name="slug",
            field=models.SlugField(db_index=True, max_length=63, unique=True),
        ),
    ]
