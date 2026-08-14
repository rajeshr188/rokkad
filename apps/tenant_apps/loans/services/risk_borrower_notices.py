from dataclasses import dataclass
import hashlib
import json
from types import SimpleNamespace

from django.db import transaction
from django.utils import timezone

from apps.tenant_apps.loans.models import LoanRiskAlert, current_tenant_workspace_id
from apps.tenant_apps.loans.selectors import get_pawn_loan_balance
from apps.tenant_apps.notify_v2.services.delivery_service import build_whatsapp_cloud_payload, render_job_message
from .pawn_notices import create_pawn_loan_notice
from .risk_communication_readiness import assess_risk_alert_communication_readiness


class RiskBorrowerNoticeError(ValueError):
    pass


@dataclass(frozen=True)
class RiskBorrowerNoticePreview:
    readiness: object
    channel: object
    subject: str
    body: str
    balance: object
    payload: dict
    fingerprint: str
    provider_payload: dict | None


def preview_risk_borrower_notice(alert_id, *, channel="EMAIL", locale="en"):
    channel = str(channel or "").strip().upper()
    if channel not in {"EMAIL", "WHATSAPP"}:
        raise RiskBorrowerNoticeError("Only email and WhatsApp are approved for manual risk communication.")
    readiness = assess_risk_alert_communication_readiness(alert_id, locale=locale)
    channel_readiness = next((row for row in readiness.channels if row.channel == channel), None)
    if readiness.blockers or channel_readiness is None or not channel_readiness.eligible:
        messages = [row.message for row in readiness.blockers]
        if channel_readiness:
            messages.extend(row.message for row in channel_readiness.blockers)
        raise RiskBorrowerNoticeError(" ".join(messages) or f"{channel.title()} communication is not ready.")
    balance = get_pawn_loan_balance(readiness.alert.loan_id, as_of_date=timezone.localdate())
    payload = _payload(readiness.alert, balance)
    recipient = SimpleNamespace(
        name_snapshot=readiness.alert.loan.borrower.display_name,
        email=channel_readiness.recipient if channel == "EMAIL" else "",
        phone=channel_readiness.recipient if channel == "WHATSAPP" else "",
    )
    event = SimpleNamespace(
        payload=payload,
        recipient=recipient,
        event_type=channel.template.event_type,
    )
    subject, body = render_job_message(SimpleNamespace(
        event=event, template=channel_readiness.template, channel=channel, batch=None,
    ))
    job = SimpleNamespace(event=event, template=channel_readiness.template, channel=channel, batch=None)
    provider_payload = build_whatsapp_cloud_payload(
        job=job, recipient_phone=channel_readiness.recipient, body=body
    )[0] if channel == "WHATSAPP" else None
    fingerprint = _fingerprint(readiness, channel_readiness, payload, subject, body, provider_payload)
    return RiskBorrowerNoticePreview(readiness, channel_readiness, subject, body, balance, payload, fingerprint, provider_payload)


@transaction.atomic
def create_risk_borrower_notice(alert_id, *, actor, expected_fingerprint, channel="EMAIL", locale="en"):
    alert = LoanRiskAlert.objects.select_for_update().get(
        pk=alert_id, workspace_id=current_tenant_workspace_id()
    )
    preview = preview_risk_borrower_notice(alert.pk, channel=channel, locale=locale)
    if not expected_fingerprint or expected_fingerprint != preview.fingerprint:
        raise RiskBorrowerNoticeError("The preview changed. Review the current message before confirming again.")
    request_key = f"risk-{alert.source_event_id}-{preview.readiness.notice_kind}-{preview.channel.channel.lower()}-v{preview.channel.template.version}"
    return create_pawn_loan_notice(
        alert.loan_id,
        notice_kind=preview.readiness.notice_kind,
        channel=preview.channel.channel,
        request_key=request_key[:120],
        actor=actor,
        dispatch_due=True,
        source_risk_alert=alert,
        notification_template=preview.channel.template,
        communication_evidence=_communication_evidence(preview, actor),
        payload_snapshot_override=preview.payload,
    )


def _communication_evidence(preview, actor):
    consent = preview.readiness.alert.loan.borrower.pawn_loan_communication_consents.get(
        workspace_id=preview.readiness.alert.workspace_id, channel=preview.channel.channel
    )
    policy = preview.readiness.policy
    return {
        "source_risk_alert_id": preview.readiness.alert.pk,
        "source_risk_event_id": preview.readiness.alert.source_event_id,
        "risk_assessment_date": preview.readiness.alert.source_event.as_of_date.isoformat(),
        "template": {"id": preview.channel.template.pk, "name": preview.channel.template.name, "version": preview.channel.template.version, "locale": preview.channel.template.locale},
        "consent": {"id": consent.pk, "allowed": consent.service_notices_allowed, "evidence": consent.evidence, "decided_at": consent.updated_at.isoformat(), "opted_out_at": consent.opted_out_at.isoformat() if consent.opted_out_at else None},
        "confirmed_by_id": getattr(actor, "pk", None),
        "confirmed_at": timezone.now().isoformat(),
        "workspace_policy": {
            "id": getattr(policy, "pk", None),
            "preferred_channel": getattr(policy, "preferred_channel", "EMAIL"),
            "quiet_hours_start": str(getattr(policy, "quiet_hours_start", None) or ""),
            "quiet_hours_end": str(getattr(policy, "quiet_hours_end", None) or ""),
            "cooldown_days": getattr(policy, "cooldown_days", 0),
            "escalation_dpd": getattr(policy, "escalation_dpd", 30),
            "updated_at": getattr(policy, "updated_at", None).isoformat() if getattr(policy, "updated_at", None) else None,
        },
        "preview": {
            "channel": preview.channel.channel,
            "subject": preview.subject,
            "body": preview.body,
            "provider_payload": preview.provider_payload,
        },
    }


def _payload(alert, balance):
    return {
        "customer": {"name": alert.loan.borrower.display_name, "email": alert.loan.borrower.primary_email},
        "loans": [{
            "pk": alert.loan_id, "loan_id": alert.loan.loan_number,
            "as_of_date": timezone.localdate().isoformat(),
            "due_date": balance.due_date.isoformat(),
            "principal_due": str(balance.principal_outstanding),
            "interest_due": str(balance.interest_outstanding),
            "fees_due": str(balance.fees_outstanding), "total_due": str(balance.total_due),
        }],
        "loan_count": 1, "total_amount": str(balance.total_due),
        "event_key": "OVERDUE_NOTICE" if alert.alert_kind == LoanRiskAlert.Kind.DPD_WORSENING else "REPAYMENT_REMINDER",
        "generated_at": alert.source_event.occurred_at.isoformat(),
    }


def _fingerprint(readiness, channel, payload, subject, body, provider_payload=None):
    policy = getattr(readiness, "policy", None)
    evidence = {
        "alert_id": readiness.alert.pk,
        "event_id": readiness.alert.source_event_id,
        "template_id": channel.template.pk,
        "template_version": channel.template.version,
        "recipient": channel.recipient,
        "payload": payload,
        "subject": subject,
        "body": body,
        "provider_payload": provider_payload,
        "workspace_policy": {
            "id": getattr(policy, "pk", None),
            "preferred_channel": getattr(policy, "preferred_channel", "EMAIL"),
            "quiet_hours_start": str(getattr(policy, "quiet_hours_start", None) or ""),
            "quiet_hours_end": str(getattr(policy, "quiet_hours_end", None) or ""),
            "cooldown_days": getattr(policy, "cooldown_days", 0),
            "escalation_dpd": getattr(policy, "escalation_dpd", 30),
            "updated_at": getattr(policy, "updated_at", None),
        },
    }
    encoded = json.dumps(evidence, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


__all__ = ["RiskBorrowerNoticeError", "RiskBorrowerNoticePreview", "create_risk_borrower_notice", "preview_risk_borrower_notice"]
