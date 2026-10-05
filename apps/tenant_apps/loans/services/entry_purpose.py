"""Current entry preference; never changes authorization or saved loan terms."""
from django.db.models import Q
from django.utils import timezone
from apps.tenant_apps.loans.models import LoanLicense, LoanSeries, PawnLoanEconomicPolicy


def default_entry_purpose(*, workspace, series_id=None, license_id=None):
    if series_id:
        series = LoanSeries.objects.filter(workspace=workspace, pk=series_id).first()
        if series is None:
            raise ValueError("Select a series in this Workspace.")
        license_id = series.license_id
    if license_id and not LoanLicense.objects.filter(workspace=workspace, pk=license_id).exists():
        raise ValueError("Select a license in this Workspace.")
    day = timezone.localdate()
    rows = PawnLoanEconomicPolicy.objects.filter(workspace=workspace, is_active=True,
        effective_from__lte=day).filter(Q(effective_until__isnull=True) | Q(effective_until__gte=day))
    for scope in (Q(series_id=series_id) if series_id else None,
                  Q(series__isnull=True, license_id=license_id) if license_id else None,
                  Q(series__isnull=True, license__isnull=True)):
        if scope is None:
            continue
        policy = rows.filter(scope).order_by("-effective_from", "-revision", "-pk").first()
        if policy and policy.default_entry_purpose != "INHERIT":
            return policy.default_entry_purpose
    return "DIRECT"
