"""Read-only readiness and reconciliation for the manual risk-email pilot."""

from dataclasses import dataclass

from apps.tenant_apps.loans.models import PawnLoanNotice, current_tenant_workspace_id
from apps.tenant_apps.loans.selectors.notices import build_pawn_loan_notice_rows
from .risk_communication_readiness import get_email_provider_readiness


@dataclass(frozen=True)
class RiskEmailPilotReport:
    provider: object
    notice_count: int
    sent_count: int
    failed_count: int
    pending_count: int
    evidence_issues: tuple[str, ...]

    @property
    def ready(self):
        return self.provider.ready and not self.evidence_issues


def assess_risk_email_pilot():
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise ValueError("Risk email pilot assessment requires an active tenant schema.")
    notices = tuple(PawnLoanNotice.objects.filter(
        workspace_id=workspace_id,
        channel="EMAIL",
        source_risk_alert__isnull=False,
    ).select_related("loan", "source_risk_alert", "source_risk_event").order_by("-created_at", "-pk"))
    rows = build_pawn_loan_notice_rows(notices)
    issues = []
    for row in rows:
        notice = row.notice
        evidence = notice.payload_snapshot.get("communication_evidence") or {}
        preview = evidence.get("preview") or {}
        if not evidence.get("consent") or not preview.get("subject") or not preview.get("body"):
            issues.append(f"Notice #{notice.pk} is missing frozen consent or preview evidence.")
        if row.status == "SENT":
            expected = f"Subject: {preview.get('subject', '')}\n\n{preview.get('body', '')}".strip()
            if row.artifact is None:
                issues.append(f"Sent notice #{notice.pk} has no rendered artifact.")
            elif row.artifact.rendered_text.strip() != expected:
                issues.append(f"Notice #{notice.pk} rendered artifact differs from its confirmed preview.")
    return RiskEmailPilotReport(
        provider=get_email_provider_readiness(),
        notice_count=len(rows),
        sent_count=sum(row.status == "SENT" for row in rows),
        failed_count=sum(row.status in {"FAILED", "MISSING"} for row in rows),
        pending_count=sum(row.status not in {"SENT", "FAILED", "MISSING"} for row in rows),
        evidence_issues=tuple(issues),
    )


__all__ = ["RiskEmailPilotReport", "assess_risk_email_pilot"]
