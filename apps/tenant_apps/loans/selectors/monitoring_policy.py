"""Shared monitoring policy resolution for valuation and risk."""

from apps.tenant_apps.loans.models import LoanMonitoringPolicy


class LoanRiskAssessmentError(ValueError):
    pass


def resolve_monitoring_policy(*, workspace_id, license_id, as_of_date):
    base = LoanMonitoringPolicy.objects.filter(workspace_id=workspace_id, effective_from__lte=as_of_date).filter(effective_until__isnull=True) | LoanMonitoringPolicy.objects.filter(workspace_id=workspace_id, effective_from__lte=as_of_date, effective_until__gte=as_of_date)
    for scope_license in (license_id, None):
        matches = tuple(base.filter(license_id=scope_license).order_by("-effective_from", "-version")[:2])
        if (len(matches) > 1 and matches[0].effective_from == matches[1].effective_from
                and matches[0].supersedes_id != matches[1].pk):
            raise LoanRiskAssessmentError("Monitoring policy resolution is ambiguous for this date.")
        if matches:
            return matches[0]
    raise LoanRiskAssessmentError("No monitoring policy applies to this loan and date.")


