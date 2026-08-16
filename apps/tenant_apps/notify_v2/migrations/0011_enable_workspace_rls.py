from django.db import migrations

from apps.tenancy.rls import EnableWorkspaceRLS


class Migration(migrations.Migration):
    dependencies = [
        ("notify_v2", "0010_remove_webhook_tenant_schema"),
    ]

    operations = [
        EnableWorkspaceRLS("NotificationArtifact"),
        EnableWorkspaceRLS("NotificationAttemptLog"),
        EnableWorkspaceRLS("NotificationBatch"),
        EnableWorkspaceRLS("NotificationEvent"),
        EnableWorkspaceRLS("NotificationEventType"),
        EnableWorkspaceRLS("NotificationJob"),
        EnableWorkspaceRLS("NotificationPolicy"),
        EnableWorkspaceRLS("NotificationRecipient"),
        EnableWorkspaceRLS("NotificationTemplate"),
        EnableWorkspaceRLS("WhatsAppCloudIntegration"),
        EnableWorkspaceRLS("WhatsAppCloudWebhookReceipt"),
    ]
