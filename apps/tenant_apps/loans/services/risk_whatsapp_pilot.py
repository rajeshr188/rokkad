"""Tenant-scoped acceptance read model for manual risk WhatsApp notices."""

from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from apps.tenant_apps.loans.models import PawnLoanNotice, current_tenant_workspace_id
from apps.tenant_apps.notify_v2.models import NotificationJob, WhatsAppCloudWebhookReceipt
from apps.tenant_apps.notify_v2.services.whatsapp_readiness import assess_whatsapp_cloud_readiness


@dataclass(frozen=True)
class RiskWhatsAppPilotRow:
    notice: object
    job: object | None
    receipts: tuple[object, ...]
    latest_status: str
    latest_received_at: object | None
    duplicate_count: int
    unresolved: bool
    diagnostic: str


@dataclass(frozen=True)
class RiskWhatsAppPilotReport:
    readiness: object
    rows: tuple[RiskWhatsAppPilotRow, ...]
    unknown_receipts: tuple[object, ...]
    submitted_count: int
    delivered_count: int
    read_count: int
    failed_count: int
    unresolved_count: int
    duplicate_count: int

    @property
    def accepted(self):
        return self.readiness.ready and not self.unknown_receipts and not self.unresolved_count and bool(self.rows)


def assess_risk_whatsapp_pilot(*, unresolved_after=timedelta(hours=24)):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise ValueError("Risk WhatsApp pilot assessment requires an active tenant schema.")
    notices = tuple(PawnLoanNotice.objects.filter(
        workspace_id=workspace_id,
        channel="WHATSAPP",
        source_risk_alert__isnull=False,
    ).select_related("loan", "loan__borrower", "source_risk_alert", "source_risk_event").order_by("-created_at", "-pk"))
    job_ids = tuple(notice.notification_job_id for notice in notices if notice.notification_job_id)
    jobs = {
        job.pk: job for job in NotificationJob.objects.filter(pk__in=job_ids).select_related("template")
    }
    receipts_by_job = {}
    for receipt in WhatsAppCloudWebhookReceipt.objects.filter(job_id__in=job_ids).order_by("job_id", "received_at", "pk"):
        receipts_by_job.setdefault(receipt.job_id, []).append(receipt)
    cutoff = timezone.now() - unresolved_after
    rows = []
    for notice in notices:
        job = jobs.get(notice.notification_job_id)
        receipts = tuple(receipts_by_job.get(notice.notification_job_id, ()))
        latest = receipts[-1] if receipts else None
        latest_status = latest.external_status if latest else (job.status.lower() if job else "missing")
        unresolved = latest_status not in {"delivered", "read"}
        if job is None:
            diagnostic = "The linked Notify job is missing."
        elif latest_status == "failed":
            diagnostic = job.failure_reason or "Meta reported delivery failure."
        elif not receipts and (job.sent_at or notice.created_at) < cutoff:
            diagnostic = "No authenticated callback was received within 24 hours."
        elif not receipts:
            diagnostic = "Awaiting authenticated callback."
        elif latest_status == "sent":
            diagnostic = "Meta accepted submission; awaiting delivered/read confirmation."
        else:
            diagnostic = "Latest authenticated callback received."
        rows.append(RiskWhatsAppPilotRow(
            notice=notice,
            job=job,
            receipts=receipts,
            latest_status=latest_status,
            latest_received_at=getattr(latest, "received_at", None),
            duplicate_count=sum(receipt.duplicate_count for receipt in receipts),
            unresolved=unresolved,
            diagnostic=diagnostic,
        ))
    unknown = tuple(WhatsAppCloudWebhookReceipt.objects.filter(
        processing_status=WhatsAppCloudWebhookReceipt.ProcessingStatus.UNKNOWN_JOB
    ).order_by("-received_at", "-pk")[:100])
    return RiskWhatsAppPilotReport(
        readiness=assess_whatsapp_cloud_readiness(receipt_grace=unresolved_after),
        rows=tuple(rows),
        unknown_receipts=unknown,
        submitted_count=len(rows),
        delivered_count=sum(row.latest_status == "delivered" for row in rows),
        read_count=sum(row.latest_status == "read" for row in rows),
        failed_count=sum(row.latest_status == "failed" for row in rows),
        unresolved_count=sum(row.unresolved for row in rows),
        duplicate_count=sum(row.duplicate_count for row in rows),
    )


__all__ = ["RiskWhatsAppPilotReport", "RiskWhatsAppPilotRow", "assess_risk_whatsapp_pilot"]
