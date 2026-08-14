from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.utils import timezone

from apps.tenant_apps.notify_v2.models import NotificationJob, WhatsAppCloudWebhookReceipt
from .whatsapp_integration import get_whatsapp_cloud_credentials, get_whatsapp_cloud_integration, WhatsAppIntegrationError


@dataclass(frozen=True)
class WhatsAppCloudReadiness:
    ready: bool
    blockers: tuple[str, ...]
    receipt_count: int
    unknown_receipt_count: int
    unreconciled_job_count: int


def assess_whatsapp_cloud_readiness(*, receipt_grace=timedelta(hours=24)):
    blockers = []
    workspace_id = getattr(getattr(connection, "tenant", None), "pk", None)
    if getattr(connection, "schema_name", "public") == "public" or not workspace_id:
        blockers.append("WhatsApp readiness must run inside a tenant schema.")
    integration = get_whatsapp_cloud_integration(workspace_id) if workspace_id else None
    if integration is None:
        blockers.append("WhatsApp Cloud is not configured for this workspace.")
    elif not integration.is_enabled:
        blockers.append("WhatsApp Cloud is not enabled for this workspace.")
    else:
        try:
            credentials = get_whatsapp_cloud_credentials(workspace_id)
        except (ImproperlyConfigured, WhatsAppIntegrationError) as exc:
            blockers.append(str(exc))
        else:
            if credentials is None or not all((credentials.phone_number_id, credentials.access_token, credentials.webhook_verify_token, credentials.app_secret)):
                blockers.append("Workspace WhatsApp Cloud credentials are incomplete.")
    receipts = WhatsAppCloudWebhookReceipt.objects.all()
    unknown_count = receipts.filter(
        processing_status=WhatsAppCloudWebhookReceipt.ProcessingStatus.UNKNOWN_JOB
    ).count()
    if unknown_count:
        blockers.append(f"{unknown_count} authenticated webhook receipt(s) do not match a tenant WhatsApp job.")
    cutoff = timezone.now() - receipt_grace
    unreconciled_count = NotificationJob.objects.filter(
        channel=NotificationJob.Channel.WHATSAPP,
        status=NotificationJob.Status.SENT,
        sent_at__lt=cutoff,
        whatsapp_webhook_receipts__isnull=True,
    ).count()
    if unreconciled_count:
        blockers.append(f"{unreconciled_count} WhatsApp job(s) have no callback after the reconciliation grace period.")
    return WhatsAppCloudReadiness(
        ready=not blockers,
        blockers=tuple(blockers),
        receipt_count=receipts.count(),
        unknown_receipt_count=unknown_count,
        unreconciled_job_count=unreconciled_count,
    )


__all__ = ["WhatsAppCloudReadiness", "assess_whatsapp_cloud_readiness"]
