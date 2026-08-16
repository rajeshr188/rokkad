from django.db import migrations


NOTIFY_MODELS = (
    "NotificationArtifact",
    "NotificationAttemptLog",
    "NotificationBatch",
    "NotificationEvent",
    "NotificationEventType",
    "NotificationJob",
    "NotificationPolicy",
    "NotificationRecipient",
    "NotificationTemplate",
    "WhatsAppCloudWebhookReceipt",
)


def backfill_workspace(apps, schema_editor):
    tenant = getattr(schema_editor.connection, "tenant", None)
    workspace_id = getattr(tenant, "pk", None)
    if not workspace_id:
        has_unowned_rows = any(
            apps.get_model("notify_v2", model_name).objects.filter(
                workspace_id__isnull=True
            ).exists()
            for model_name in NOTIFY_MODELS
        )
        if not has_unowned_rows:
            return
        raise RuntimeError(
            "Notify v2 Workspace backfill found unowned rows without an explicit "
            "tenant Workspace."
        )

    for model_name in NOTIFY_MODELS:
        apps.get_model("notify_v2", model_name).objects.filter(
            workspace_id__isnull=True
        ).update(workspace_id=workspace_id)


class Migration(migrations.Migration):
    dependencies = [("notify_v2", "0007_remove_notificationjob_notify_v2_unique_job_per_event_channel_and_more")]

    operations = [migrations.RunPython(backfill_workspace, migrations.RunPython.noop)]
