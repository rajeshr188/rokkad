"""Loans-owned send-time guards for messages relying on reviewed paper records."""
from django.db import transaction
from django.utils import timezone
from apps.tenant_apps.loans.models import PawnLoan, PawnLoanNotice, PawnLoanCommunicationConsent
from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_completeness, transaction_fingerprint


def notice_balance(loan, day):
    from apps.tenant_apps.loans.selectors.servicing_contract import get_servicing_position
    return get_servicing_position(loan, as_of_date=day, operation="NOTICE").balance


def notice_transaction_evidence(loan, day):
    coverage = transaction_completeness(loan, day)
    if not coverage.complete:
        raise ValueError(coverage.message)
    if not coverage.required:
        return None
    evidence = dict(**coverage.evidence(), source_fingerprint=transaction_fingerprint(loan))
    if coverage.status == "ROKKAD_ONLY":
        evidence["checked_source_fingerprint"] = loan.transaction_reviews.get(pk=coverage.review_id).source_fingerprint
    return evidence


@transaction.atomic
def dispatch_with_transaction_review(job, deliver):
    """Used by Notify's common dispatch boundary, including direct retries/batches.

    Hold the loan aggregate lock through the provider attempt so a concurrent
    receipt/correction cannot change reviewed debt between validation and dispatch.
    """
    from apps.tenant_apps.loans.models import current_tenant_workspace_id
    if current_tenant_workspace_id() != job.workspace_id:
        raise ValueError("Notice delivery requires the job's active Workspace context.")
    notice = PawnLoanNotice.objects.filter(workspace_id=job.workspace_id, notification_job_id=job.pk).first()
    if notice is None:
        return deliver()
    loan = PawnLoan.objects.select_for_update().get(pk=notice.loan_id, workspace_id=job.workspace_id)
    coverage = transaction_completeness(loan, timezone.localdate())
    if not coverage.required and not notice.payload_snapshot.get("transaction_review"):
        return deliver()
    # Concurrent workers may hold stale job objects; the loan lock serializes the
    # provider attempt and this refresh observes the first worker's result.
    job.refresh_from_db()
    if job.status in ("SENT", "CANCELLED"):
        return job.status == "SENT"
    reason = _blocker(notice, loan, coverage, job)
    if reason:
        job.mark_failed(reason=reason)
        return False
    return deliver()


def _blocker(notice, loan, coverage, job):
    if loan.state != "ACTIVE" or not coverage.complete:
        return "Paper transaction review no longer supports delivery. " + coverage.message
    if notice.scheduled_for > timezone.now():
        return "This notice is scheduled for a future time."
    frozen = notice.payload_snapshot.get("transaction_review") or {}
    if (frozen.get("review_id") != coverage.review_id
        or frozen.get("source_fingerprint") != transaction_fingerprint(loan)):
        return "Loan activity or its paper review changed. Prepare a new reminder."
    rows = notice.payload_snapshot.get("loans") or []
    if len(rows) != 1 or rows[0].get("as_of_date") != timezone.localdate().isoformat():
        return "This reminder's amount is from another date. Prepare a current reminder."
    if not notice.source_risk_alert_id:
        return "Paper reminders require a reviewed risk-notice intent."
    if notice.source_risk_alert.status != "OPEN":
        return "The source risk alert is no longer open. Prepare a current reminder if needed."
    from apps.tenant_apps.loans.selectors.risk_portfolio import snapshot_is_current
    from apps.tenant_apps.loans.models import LoanRiskSnapshot
    if not snapshot_is_current(LoanRiskSnapshot.objects.filter(loan=loan).first(), timezone.localdate()):
        return "Reassess current loan risk before delivery."
    if not PawnLoanCommunicationConsent.objects.filter(workspace_id=loan.workspace_id,
        party_id=loan.borrower_id, channel=notice.channel, service_notices_allowed=True, opted_out_at__isnull=True).exists():
        return "Borrower service-notice consent no longer permits delivery."
    from apps.tenant_apps.loans.models import PawnLoanCommunicationPolicy
    policy = PawnLoanCommunicationPolicy.objects.filter(workspace_id=loan.workspace_id).first()
    from .risk_communication_readiness import _in_quiet_hours, _provider_ready
    if policy and _in_quiet_hours(policy, timezone.localtime().time()):
        return "Delivery is paused during Workspace quiet hours."
    if not _provider_ready(notice.channel):
        return "The delivery provider is not ready."
    recipient = loan.borrower.primary_email if notice.channel == "EMAIL" else loan.borrower.primary_phone
    frozen_recipient = notice.recipient_email if notice.channel == "EMAIL" else notice.recipient_phone
    job_recipient = job.event.recipient.email if notice.channel == "EMAIL" else job.event.recipient.phone
    if not recipient or recipient.strip() != frozen_recipient or job_recipient != frozen_recipient:
        return "Borrower contact details changed. Prepare a new reminder."
    from apps.tenant_apps.notify_v2.services.delivery_service import render_job_message
    subject, body = render_job_message(job)
    preview = notice.payload_snapshot.get("communication_evidence", {}).get("preview", {})
    if preview.get("subject") != subject or preview.get("body") != body:
        return "The delivery message differs from its confirmed preview. Prepare a new reminder."
    if notice.channel == "WHATSAPP":
        from apps.tenant_apps.notify_v2.services.delivery_service import build_whatsapp_cloud_payload
        current_payload, _ = build_whatsapp_cloud_payload(job=job, recipient_phone=job_recipient, body=body)
        if preview.get("provider_payload") != current_payload:
            return "The WhatsApp provider template differs from its confirmed preview. Prepare a new reminder."
    balance = notice_balance(loan, timezone.localdate())
    from decimal import Decimal
    for key, amount in (("principal_due", balance.principal_outstanding), ("interest_due", balance.interest_outstanding),
                        ("fees_due", balance.fees_outstanding), ("total_due", balance.total_due)):
        if Decimal(rows[0].get(key, "-1")) != amount:
            return "The current collection amount changed. Prepare a new reminder."
    return None
