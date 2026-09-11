from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.tenant_apps.loans.domain import PawnLoanNoticeChannel, PawnLoanNoticeKind, PawnLoanState
from apps.tenant_apps.loans.models import (
    LoanRiskAlert,
    LoanRiskSnapshot,
    PawnLoanCommunicationConsent,
    PawnLoanCommunicationPolicy,
    PawnLoanNotice,
    current_tenant_workspace_id,
)
from apps.tenant_apps.notify_v2.models import NotificationTemplate
from apps.tenant_apps.loans.selectors.risk_portfolio import snapshot_is_current
from apps.tenant_apps.notify_v2.services.whatsapp_integration import get_whatsapp_cloud_credentials


@dataclass(frozen=True)
class RiskCommunicationBlocker:
    code: str
    message: str


@dataclass(frozen=True)
class RiskCommunicationChannelReadiness:
    channel: str
    eligible: bool
    blockers: tuple[RiskCommunicationBlocker, ...]
    recipient: str
    template: object | None


@dataclass(frozen=True)
class RiskAlertCommunicationReadiness:
    alert: LoanRiskAlert
    notice_kind: str | None
    eligible: bool
    blockers: tuple[RiskCommunicationBlocker, ...]
    channels: tuple[RiskCommunicationChannelReadiness, ...]
    policy: object | None


@dataclass(frozen=True)
class EmailProviderReadiness:
    ready: bool
    backend: str
    sender: str
    message: str


_ALERT_NOTICE = {
    LoanRiskAlert.Kind.DPD_WORSENING: (
        PawnLoanNoticeKind.OVERDUE_NOTICE.value,
        "pawn_loan.overdue_notice",
    ),
    LoanRiskAlert.Kind.MATURITY: (
        PawnLoanNoticeKind.REPAYMENT_REMINDER.value,
        "pawn_loan.repayment_reminder",
    ),
}


def assess_risk_alert_communication_readiness(alert_id: int, *, locale="en"):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise ValueError("Risk communication readiness requires an active tenant schema.")
    alert = LoanRiskAlert.objects.select_related(
        "loan__borrower", "source_event", "loan__risk_snapshot"
    ).get(pk=alert_id, workspace_id=workspace_id)
    mapping = _ALERT_NOTICE.get(alert.alert_kind)
    policy = PawnLoanCommunicationPolicy.objects.filter(workspace_id=workspace_id).first()
    blockers = []
    if alert.status != LoanRiskAlert.Status.OPEN:
        blockers.append(_block("ALERT_NOT_OPEN", "This risk alert is no longer open."))
    if alert.loan.state != PawnLoanState.ACTIVE.value:
        blockers.append(_block("LOAN_NOT_ACTIVE", "Borrower risk notices require an active PawnLoan."))
    if mapping is None:
        blockers.append(_block("NOTICE_KIND_UNAPPROVED", "This risk category has no approved borrower notice workflow."))
    snapshot = _snapshot(alert)
    if not snapshot_is_current(snapshot, timezone.localdate()):
        blockers.append(_block("RISK_NOT_CURRENT", "Refresh this loan to a current risk assessment before communication."))
    elif not _snapshot_supports(alert.alert_kind, snapshot):
        blockers.append(_block("RISK_NO_LONGER_SUPPORTS_NOTICE", "The current risk state no longer supports this borrower notice."))
    channels = tuple(
        _assess_channel(alert, mapping, channel.value, locale, policy)
        for channel in PawnLoanNoticeChannel
    ) if mapping else ()
    return RiskAlertCommunicationReadiness(
        alert=alert,
        notice_kind=mapping[0] if mapping else None,
        eligible=not blockers and any(row.eligible for row in channels),
        blockers=tuple(blockers),
        channels=channels,
        policy=policy,
    )


def _assess_channel(alert, mapping, channel, locale, policy):
    notice_kind, event_key = mapping
    blockers = []
    recipient = alert.loan.borrower.primary_email if channel == "EMAIL" else alert.loan.borrower.primary_phone
    if not (recipient or "").strip():
        blockers.append(_block("CONTACT_MISSING", f"The borrower has no {channel.lower()} contact."))
    consent = PawnLoanCommunicationConsent.objects.filter(
        workspace_id=alert.workspace_id, party_id=alert.loan.borrower_id, channel=channel
    ).first()
    if consent is None:
        blockers.append(_block("CONSENT_MISSING", f"Explicit {channel.lower()} service-notice consent is not recorded."))
    elif not consent.permits_service_notice:
        blockers.append(_block("CONSENT_BLOCKED", f"The borrower has not permitted {channel.lower()} service notices or has opted out."))
    template = NotificationTemplate.objects.filter(
        event_type__key=event_key, channel=channel, locale=locale, is_active=True,
        event_type__is_active=True,
    ).order_by("-version").first()
    if template is None:
        blockers.append(_block("TEMPLATE_MISSING", f"No active {channel.lower()} template exists for locale {locale}."))
    elif channel == "WHATSAPP" and not _has_whatsapp_provider_template(template):
        blockers.append(_block("WHATSAPP_TEMPLATE_UNAPPROVED", "The WhatsApp template has no approved Cloud API template name."))
    if not _provider_ready(channel):
        blockers.append(_block("PROVIDER_NOT_READY", f"A real {channel.lower()} delivery provider is not configured."))
    if policy and _in_quiet_hours(policy, timezone.localtime().time()):
        blockers.append(_block("QUIET_HOURS", f"Manual borrower communication is paused during workspace quiet hours ({policy.quiet_hours_start:%H:%M}-{policy.quiet_hours_end:%H:%M})."))
    if policy and policy.cooldown_days and PawnLoanNotice.objects.filter(
        loan__borrower_id=alert.loan.borrower_id,
        notice_kind=notice_kind,
        channel=channel,
        source_risk_alert__isnull=False,
        created_at__gte=timezone.now() - timedelta(days=policy.cooldown_days),
    ).exclude(source_risk_event=alert.source_event).exists():
        blockers.append(_block("COOLDOWN_ACTIVE", f"A {channel.lower()} {notice_kind.lower().replace('_', ' ')} was created for this borrower within the {policy.cooldown_days}-day cooldown."))
    if template and PawnLoanNotice.objects.filter(
        source_risk_event=alert.source_event,
        notice_kind=notice_kind,
        channel=channel,
        notification_template_version=template.version,
    ).exists():
        blockers.append(_block("NOTICE_ALREADY_EXISTS", "This risk event already has the same notice, channel, and template version."))
    return RiskCommunicationChannelReadiness(channel, not blockers, tuple(blockers), recipient or "", template)


def _provider_ready(channel):
    if channel == "EMAIL":
        backend = (getattr(settings, "EMAIL_BACKEND", "") or "").lower()
        simulated = any(name in backend for name in ("console", "dummy", "locmem", "filebased"))
        return bool(backend and not simulated and getattr(settings, "DEFAULT_FROM_EMAIL", ""))
    if channel == "SMS":
        return False
    if channel == "WHATSAPP":
        workspace_id = current_tenant_workspace_id()
        try:
            credentials = get_whatsapp_cloud_credentials(workspace_id) if workspace_id else None
        except Exception:
            return False
        return bool(credentials and all((credentials.phone_number_id, credentials.access_token,
                                         credentials.webhook_verify_token, credentials.app_secret)))
    return False


def _has_whatsapp_provider_template(template):
    sample_payload = getattr(template, "sample_payload", {})
    config = sample_payload.get("whatsapp_template") if isinstance(sample_payload, dict) else {}
    return bool((config or {}).get("name") or (getattr(template, "layout_key", "") or "").strip())


def _in_quiet_hours(policy, current_time):
    start, end = policy.quiet_hours_start, policy.quiet_hours_end
    if not start or not end:
        return False
    if start < end:
        return start <= current_time < end
    return current_time >= start or current_time < end


def get_email_provider_readiness():
    backend = (getattr(settings, "EMAIL_BACKEND", "") or "").strip()
    sender = (getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").strip()
    simulated = any(name in backend.lower() for name in ("console", "dummy", "locmem", "filebased"))
    if not backend:
        message = "No email backend is configured."
    elif simulated:
        message = "A development/test email backend is configured; borrower delivery is blocked."
    elif not sender:
        message = "DEFAULT_FROM_EMAIL is missing."
    else:
        message = "A real email backend and sender address are configured."
    return EmailProviderReadiness(bool(backend and sender and not simulated), backend, sender, message)


def _snapshot(alert):
    try:
        return alert.loan.risk_snapshot
    except LoanRiskSnapshot.DoesNotExist:
        return None


def _snapshot_supports(kind, snapshot):
    if kind == LoanRiskAlert.Kind.DPD_WORSENING:
        return (snapshot.days_past_due or 0) > 0
    if kind == LoanRiskAlert.Kind.MATURITY:
        return bool(set(snapshot.flags or ()) & {"MATURITY_APPROACHING", "PAST_MATURITY"})
    return False


def _block(code, message):
    return RiskCommunicationBlocker(code, message)


__all__ = ["EmailProviderReadiness", "RiskAlertCommunicationReadiness", "RiskCommunicationChannelReadiness", "assess_risk_alert_communication_readiness", "get_email_provider_readiness"]
