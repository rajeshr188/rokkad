from django.db import migrations


RATE_MODELS = ("RateSource", "Rate")


def backfill_workspace(apps, schema_editor):
    tenant = getattr(schema_editor.connection, "tenant", None)
    workspace_id = getattr(tenant, "pk", None)
    if not workspace_id:
        has_unowned_rows = any(
            apps.get_model("rates", model_name).objects.filter(
                workspace_id__isnull=True
            ).exists()
            for model_name in RATE_MODELS
        )
        if not has_unowned_rows:
            return
        raise RuntimeError(
            "Rates Workspace backfill found unowned rows without an explicit "
            "tenant Workspace."
        )

    for model_name in RATE_MODELS:
        apps.get_model("rates", model_name).objects.filter(
            workspace_id__isnull=True
        ).update(workspace_id=workspace_id)


class Migration(migrations.Migration):
    dependencies = [("rates", "0003_add_workspace_ownership")]

    operations = [
        migrations.RunPython(backfill_workspace, migrations.RunPython.noop),
    ]
