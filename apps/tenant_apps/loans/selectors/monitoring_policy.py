"""Shared monitoring policy resolution for valuation and risk."""

from apps.tenant_apps.loans.models import LoanMonitoringPolicy
from apps.tenant_apps.loans.models import current_tenant_workspace_id
from django.utils import timezone


class LoanRiskAssessmentError(ValueError):
    pass


def resolve_monitoring_policy(*, workspace_id, license_id, as_of_date):
    base = LoanMonitoringPolicy.objects.filter(
        workspace_id=workspace_id, effective_from__lte=as_of_date
    ).filter(effective_until__isnull=True) | LoanMonitoringPolicy.objects.filter(
        workspace_id=workspace_id,
        effective_from__lte=as_of_date,
        effective_until__gte=as_of_date,
    )
    for scope_license in dict.fromkeys((license_id, None)):
        matches = tuple(
            base.filter(license_id=scope_license).order_by(
                "-version", "-effective_from"
            )[:2]
        )
        if (
            len(matches) > 1
            and matches[0].effective_from == matches[1].effective_from
            and matches[0].supersedes_id != matches[1].pk
        ):
            prior = matches[0].supersedes
            while prior is not None and prior.version > matches[1].version:
                prior = prior.supersedes
            if prior is None or prior.pk != matches[1].pk:
                raise LoanRiskAssessmentError(
                    "Monitoring policy resolution is ambiguous for this date."
                )
        if matches:
            if matches[0].scope_action == LoanMonitoringPolicy.ScopeAction.RETIRE:
                continue
            return matches[0]
    raise LoanRiskAssessmentError("No monitoring policy applies to this loan and date.")


def current_monitoring_context(series):
    """Read-only entry disclosure; neither agreement defaults nor approval."""
    if series is None:
        return None
    if current_tenant_workspace_id() != series.workspace_id:
        raise ValueError("Monitoring setup requires the series' active Workspace.")
    try:
        policy = resolve_monitoring_policy(
            workspace_id=series.workspace_id,
            license_id=series.license_id,
            as_of_date=timezone.localdate(),
        )
    except LoanRiskAssessmentError as exc:
        return {"policy": None, "error": str(exc)}
    return {"policy": policy, "error": ""}
