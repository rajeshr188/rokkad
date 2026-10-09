"""Standing paper agreement defaults; no historical valuation or approval."""
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Q
from django.utils import timezone

from apps.tenant_apps.loans import models as m
from .economic_policies import (
    PawnEconomicPolicyError, resolve_pawn_loan_economic_policy,
    resolve_pawn_metal_interest_rate_policy, resolve_pawn_loan_fee_policies,
)


def paper_entry_terms(*, workspace, series, day, metal, principal=None):
    if series.workspace_id != workspace.pk:
        raise ValueError("Select a series in this Workspace.")
    values, messages, sources = {}, [], []
    try:
        policy = resolve_pawn_loan_economic_policy(workspace_id=workspace.pk,
            license_id=series.license_id, series_id=series.pk, as_of_date=day)
        if (policy.interest_method != "SIMPLE" or policy.partial_month_method != "FULL_MONTH"
                or policy.advance_interest_periods not in (0, 1) or policy.currency_quantum not in (Decimal("0.01"), Decimal("1"))):
            messages.append("The dated setup uses calculation rules outside this paper profile. Record the actual supported agreement as an exception; do not substitute these rules.")
        else:
            values.update(advance_months=policy.advance_interest_periods, tenure=policy.default_tenure_months,
                          currency_quantum=str(policy.currency_quantum.normalize()))
            sources.append(f"Agreement policy {policy.pk} revision {policy.revision}")
    except PawnEconomicPolicyError:
        messages.append("No dated digital agreement setup covers this loan. Enter its actual standing terms as an exception.")
    try:
        rate = resolve_pawn_metal_interest_rate_policy(workspace_id=workspace.pk,
            license_id=series.license_id, series_id=series.pk, metal=metal, as_of_date=day)
        values["rate"] = rate.monthly_interest_rate
        sources.append(f"Monthly rate {rate.pk}")
    except PawnEconomicPolicyError:
        messages.append("Enter the actual agreed monthly rate; no dated rate setup is available.")
    fees = resolve_pawn_loan_fee_policies(workspace_id=workspace.pk, license_id=series.license_id, as_of_date=day)
    if not fees:
        values["document_charge"] = Decimal("0")
    elif len(fees) == 1 and fees[0].deducted_at_disbursal and fees[0].code in {"DOCUMENT_CHARGE", "DOC", "DOCUMENT", "DOC_FEE"}:
        fee = fees[0]
        if fee.calculation_type == "FIXED":
            values["document_charge"] = fee.value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        elif principal is not None:
            values["document_charge"] = (principal * fee.value / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        sources.append(f"Document fee {fee.pk}")
    else:
        messages.append("Configured fees exceed the supported deducted document charge. Enter the actual supported charge as an exception.")
    try:
        monitoring = resolve_pawn_loan_economic_policy(workspace_id=workspace.pk,
            license_id=series.license_id, series_id=series.pk, as_of_date=timezone.localdate())
        values.update(monitoring_method=monitoring.valuation_method,
            monitoring_ltv=monitoring.maximum_ltv_ratio,
            monitoring_reason=f"Standing current monitoring policy {monitoring.pk}, revision {monitoring.revision}; original paper advance is not reapproved.")
    except PawnEconomicPolicyError:
        messages.append("Choose the current monitoring basis; no current setup is available.")
    return dict(values=values, messages=messages, sources=sources)


def paper_source_license_revision(*, workspace, series, day):
    """Use dated retained evidence only when its mapping is unambiguous."""
    if series.workspace_id != workspace.pk:
        raise ValueError("Select a series in this Workspace.")
    candidates = list(m.LoanLicenseRevision.objects.filter(
        workspace=workspace, license_id=series.license_id,
        issued_on__lte=day, expires_on__gte=day,
    ).exclude(kind=m.LoanLicenseRevision.Kind.LEGACY_REFERENCE).order_by("pk")[:2])
    return candidates[0] if len(candidates) == 1 else None


def preferred_paper_product(*, workspace, day):
    candidates = m.LoanProductVersion.objects.filter(workspace=workspace, product__is_active=True,
        status="ACTIVE", repayment_structure="FLEXIBLE_PARTIAL_PAYMENT", amortisation_method="NONE"
    ).filter(Q(available_from__isnull=True) | Q(available_from__lte=day)
    ).filter(Q(available_until__isnull=True) | Q(available_until__gte=day))
    choices = list(candidates.order_by("pk")[:2])
    return choices[0] if len(choices) == 1 else None
