"""Standing paper agreement defaults; no historical valuation or approval."""

from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Q
from django.utils import timezone

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.domain.origination_capabilities import (
    supports_paper_monthly_terms,
)
from .economic_policies import (
    PawnEconomicPolicyError,
    resolve_pawn_loan_economic_policy,
    resolve_pawn_metal_interest_rate_policy,
    resolve_pawn_loan_fee_policies,
)


def paper_entry_terms(*, workspace, series, day, metal, principal=None):
    if series.workspace_id != workspace.pk:
        raise ValueError("Select a series in this Workspace.")
    values, messages, sources = {}, [], []
    try:
        policy = resolve_pawn_loan_economic_policy(
            workspace_id=workspace.pk,
            license_id=series.license_id,
            series_id=series.pk,
            as_of_date=day,
        )
        if not supports_paper_monthly_terms(
            **{
                key: getattr(policy, key)
                for key in (
                    "interest_method",
                    "partial_month_method",
                    "advance_interest_periods",
                    "currency_quantum",
                )
            }
        ):
            messages.append(
                "The dated setup uses calculation rules outside this paper profile. Record the actual supported agreement as an exception; do not substitute these rules."
            )
        else:
            values.update(
                advance_months=policy.advance_interest_periods,
                tenure=policy.default_tenure_months,
                currency_quantum=str(policy.currency_quantum.normalize()),
            )
            sources.append(f"Agreement policy {policy.pk} revision {policy.revision}")
    except PawnEconomicPolicyError:
        messages.append(
            "No dated digital agreement setup covers this loan. Enter its actual standing terms as an exception."
        )
    try:
        rate = resolve_pawn_metal_interest_rate_policy(
            workspace_id=workspace.pk,
            license_id=series.license_id,
            series_id=series.pk,
            metal=metal,
            as_of_date=day,
        )
        values["rate"] = rate.monthly_interest_rate
        sources.append(f"Monthly rate {rate.pk}")
    except PawnEconomicPolicyError:
        messages.append(
            "Enter the actual agreed monthly rate; no dated rate setup is available."
        )
    fees = resolve_pawn_loan_fee_policies(
        workspace_id=workspace.pk, license_id=series.license_id, as_of_date=day
    )
    if not fees:
        values["document_charge"] = Decimal("0")
    elif (
        len(fees) == 1
        and fees[0].deducted_at_disbursal
        and fees[0].code in {"DOCUMENT_CHARGE", "DOC", "DOCUMENT", "DOC_FEE"}
    ):
        fee = fees[0]
        if fee.calculation_type == "FIXED":
            values["document_charge"] = fee.value.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        elif principal is not None:
            values["document_charge"] = (principal * fee.value / 100).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        sources.append(f"Document fee {fee.pk}")
    else:
        messages.append(
            "Configured fees exceed the supported deducted document charge. Enter the actual supported charge as an exception."
        )
    reference = paper_valuation_reference(workspace=workspace, series=series, day=day)
    if reference:
        values.update(reference["values"])
    else:
        messages.append(
            "Choose the saved valuation fallback/reference; no economic reference setup is available."
        )
    return dict(values=values, messages=messages, sources=sources, reference=reference)


def paper_valuation_reference(*, workspace, series, day):
    """Known configuration reference, independently of current monitoring.

    Prefer the already applicable dated setup; expired historical setup need not
    be recreated today just to record paper. The retained current-setup fallback
    remains explicit compatibility evidence, never an original lending decision.
    Missing both leaves reference entry explicit instead of manufacturing a limit.
    """
    if series.workspace_id != workspace.pk:
        raise ValueError("Select a series in this Workspace.")
    for reference_day in dict.fromkeys((day, timezone.localdate())):
        try:
            policy = resolve_pawn_loan_economic_policy(
                workspace_id=workspace.pk,
                license_id=series.license_id,
                series_id=series.pk,
                as_of_date=reference_day,
            )
        except PawnEconomicPolicyError:
            continue
        basis = (
            "Dated setup reference"
            if reference_day == day
            else "Entry-day setup fallback"
        )
        reason = (
            f"{basis}: economic policy {policy.pk}, revision {policy.revision}, "
            f"effective {reference_day.isoformat()}. Current monitoring is separate; "
            "original approval/appraisal is not established."
        )
        return dict(
            policy_id=policy.pk,
            basis=basis,
            reference_date=reference_day,
            values=dict(
                monitoring_method=policy.valuation_method,
                monitoring_ltv=policy.maximum_ltv_ratio,
                monitoring_reason=reason,
            ),
        )
    return None


def paper_source_license_revision(*, workspace, series, day):
    """Use dated retained evidence only when its mapping is unambiguous."""
    if series.workspace_id != workspace.pk:
        raise ValueError("Select a series in this Workspace.")
    candidates = list(
        m.LoanLicenseRevision.objects.filter(
            workspace=workspace,
            license_id=series.license_id,
            issued_on__lte=day,
            expires_on__gte=day,
        )
        .exclude(kind=m.LoanLicenseRevision.Kind.LEGACY_REFERENCE)
        .order_by("pk")[:2]
    )
    return candidates[0] if len(candidates) == 1 else None


def preferred_paper_product(*, workspace, day):
    candidates = (
        m.LoanProductVersion.objects.filter(
            workspace=workspace,
            product__is_active=True,
            status="ACTIVE",
            repayment_structure="FLEXIBLE_PARTIAL_PAYMENT",
            amortisation_method="NONE",
        )
        .filter(Q(available_from__isnull=True) | Q(available_from__lte=day))
        .filter(Q(available_until__isnull=True) | Q(available_until__gte=day))
    )
    choices = list(candidates.order_by("pk")[:2])
    return choices[0] if len(choices) == 1 else None
