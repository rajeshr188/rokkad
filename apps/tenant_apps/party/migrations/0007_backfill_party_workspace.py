from django.db import migrations


PARTY_MODELS = (
    "Party",
    "PartyAddress",
    "PartyCodeSequence",
    "PartyContactMethod",
    "PartyDocument",
    "PartyIdentifier",
    "PartyPortalAccess",
    "PartyRelationship",
    "PartyRole",
    "PartyRoleType",
)


def backfill_workspace(apps, schema_editor):
    tenant = getattr(schema_editor.connection, "tenant", None)
    workspace_id = getattr(tenant, "pk", None)
    if not workspace_id:
        has_unowned_rows = any(
            apps.get_model("party", model_name).objects.filter(
                workspace_id__isnull=True
            ).exists()
            for model_name in PARTY_MODELS
        )
        if not has_unowned_rows:
            return
        raise RuntimeError(
            "Party Workspace backfill found unowned rows without an explicit "
            "tenant Workspace."
        )

    for model_name in PARTY_MODELS:
        apps.get_model("party", model_name).objects.filter(
            workspace_id__isnull=True
        ).update(workspace_id=workspace_id)


class Migration(migrations.Migration):
    dependencies = [
        ("party", "0006_party_workspace_partyaddress_workspace_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_workspace, migrations.RunPython.noop),
    ]
