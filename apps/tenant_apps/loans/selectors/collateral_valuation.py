from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_DOWN
from django.utils import timezone

from apps.tenant_apps.rates.facade import RATE_FOUND, get_latest_commodity_valuation_rate
from apps.tenant_apps.loans.domain import CollateralCustodyState, ValuationMethod, calculate_ltv
from apps.tenant_apps.loans.models import CollateralAppraisal, PawnLoan, current_tenant_workspace_id
from .exposure import get_pawn_loan_exposure
from .monitoring_policy import LoanRiskAssessmentError, resolve_monitoring_policy
from apps.tenant_apps.loans.domain.valuation_freshness import evidence_freshness


@dataclass(frozen=True)
class CollateralItemValuation:
    collateral_item_id: int
    calculated_value: Decimal | None
    appraisal_value: Decimal | None
    selected_value: Decimal | None
    rate_id: int | None
    appraisal_id: int | None
    custody_eligible: bool
    blockers: tuple[str, ...]
    rate_effective_at: object = None
    appraisal_effective_at: object = None
    rate_age_days: int | None = None
    appraisal_age_days: int | None = None
    rate_status: str = "MISSING"
    appraisal_status: str = "MISSING"

    @property
    def blocker_messages(self):
        messages = {
            "STALE_RATE": "The metal price is older than the policy allows.",
            "STALE_APPRAISAL": "The appraisal is older than the policy allows.",
            "MISSING_RATE": "A usable metal price is required.",
            "MISSING_APPRAISAL": "An approved appraisal is required.",
            "MONITORING_POLICY_UNAVAILABLE": "Configure a monitoring policy to assess freshness.",
            "CUSTODY_NOT_ELIGIBLE": "This collateral's custody state is excluded from coverage.",
            "INCOMPLETE_LOWER_OF_EVIDENCE": "Both a metal price and approved appraisal are required.",
        }
        return tuple(messages.get(code, code.replace("_", " ").capitalize()) for code in self.blockers)


@dataclass(frozen=True)
class PawnLoanCollateralValuation:
    loan_id: int
    as_of_date: date
    items: tuple[CollateralItemValuation, ...]
    eligible_collateral_value: Decimal | None
    ltv: object
    compliance_profile: str
    monitoring_policy_id: int | None = None
    rate_freshness_days: int | None = None
    appraisal_freshness_days: int | None = None
    policy_error: str = ""


def get_pawn_loan_collateral_valuation(loan_id, *, as_of_date, _exposure=None):
    """Private prepared inputs are reused only within one source-checked refresh."""
    workspace_id = current_tenant_workspace_id()
    loan = PawnLoan.objects.select_related("policy_snapshot").prefetch_related("collateral_items").get(pk=loan_id, workspace_id=workspace_id)
    if _exposure is not None and (_exposure.loan_id != loan.pk or _exposure.as_of_date != as_of_date):
        raise ValueError("Prepared exposure must match the scoped loan and assessment date.")
    method = ValuationMethod(loan.policy_snapshot.valuation_method)
    quantum = Decimal(str(loan.policy_snapshot.currency_quantum))
    policy_error = ""
    try:
        policy = resolve_monitoring_policy(workspace_id=workspace_id, license_id=loan.license_id, as_of_date=as_of_date)
    except LoanRiskAssessmentError as exc:
        policy, policy_error = None, str(exc)
    results = []
    for item in loan.collateral_items.all():
        eligible = item.custody_state in {CollateralCustodyState.IN_VAULT.value, CollateralCustodyState.WITH_FUNDING_LENDER.value}
        blockers = [] if eligible else ["CUSTODY_NOT_ELIGIBLE"]
        if policy is None:
            blockers.append("MONITORING_POLICY_UNAVAILABLE")
        elif item.custody_state not in policy.eligible_custody_states:
            eligible = False
            if "CUSTODY_NOT_ELIGIBLE" not in blockers:
                blockers.append("CUSTODY_NOT_ELIGIBLE")
        lookup = get_latest_commodity_valuation_rate(commodity_code=item.metal, as_of=as_of_date)
        calculated = None
        if lookup.status == RATE_FOUND and lookup.rate.buying_rate.is_finite() and lookup.rate.buying_rate > 0:
            calculated = (lookup.rate.buying_rate * item.net_weight * item.purity_percentage / Decimal("100")).quantize(quantum, rounding=ROUND_DOWN)
        appraisal = CollateralAppraisal.objects.filter(collateral_item=item, effective_at__date__lte=as_of_date, status=CollateralAppraisal.Status.APPROVED).order_by("-effective_at", "-version").first()
        appraisal_value = appraisal.appraised_value if appraisal else None
        rate_at = lookup.rate.effective_at if lookup.rate else None
        appraisal_at = appraisal.effective_at if appraisal else None
        rate_status, rate_age = evidence_freshness(value=getattr(lookup.rate, "buying_rate", None),
            effective_date=timezone.localtime(rate_at).date() if rate_at else None, as_of_date=as_of_date,
            maximum_age_days=policy.rate_freshness_days if policy else None)
        appraisal_status, appraisal_age = evidence_freshness(value=appraisal_value,
            effective_date=timezone.localtime(appraisal_at).date() if appraisal_at else None, as_of_date=as_of_date,
            maximum_age_days=policy.appraisal_freshness_days if policy else None)
        if method != ValuationMethod.LATEST_APPRAISAL and rate_status != "CURRENT":
            blockers.append(f"{rate_status}_RATE")
        if method != ValuationMethod.CALCULATED_METAL_VALUE and appraisal_status != "CURRENT":
            blockers.append(f"{appraisal_status}_APPRAISAL")
        if method == ValuationMethod.CALCULATED_METAL_VALUE:
            selected = calculated
            if selected is None: blockers.append(lookup.status)
        elif method == ValuationMethod.LATEST_APPRAISAL:
            selected = appraisal_value
            if selected is None: blockers.append("MISSING_APPRAISAL")
        else:
            selected = min(calculated, appraisal_value) if calculated is not None and appraisal_value is not None else None
            if selected is None: blockers.append("INCOMPLETE_LOWER_OF_EVIDENCE")
        results.append(CollateralItemValuation(item.pk, calculated, appraisal_value, selected if not blockers else None,
            getattr(lookup.rate, "pk", None), appraisal.pk if appraisal else None, eligible, tuple(dict.fromkeys(blockers)),
            rate_at, appraisal_at, rate_age, appraisal_age, rate_status, appraisal_status))
    blockers = tuple(code for row in results for code in row.blockers)
    total = None if blockers else sum((row.selected_value for row in results), Decimal("0"))
    exposure = _exposure if _exposure is not None else get_pawn_loan_exposure(loan.pk, as_of_date=as_of_date)
    ltv = calculate_ltv(exposure=exposure.ltv_exposure_basis, collateral_value=total, allowed_ltv_ratio=loan.policy_snapshot.maximum_ltv_ratio, blockers=blockers)
    # ``policy_snapshot`` is the reverse side of LoanPolicySnapshot.loan, so
    # PawnLoan has no generated ``policy_snapshot_id`` attribute. Use the
    # related snapshot's primary key for stable provenance.
    return PawnLoanCollateralValuation(loan.pk, as_of_date, tuple(results), total, ltv,
        f"loan-policy-snapshot:{loan.policy_snapshot.pk}", policy.pk if policy else None,
        policy.rate_freshness_days if policy else None, policy.appraisal_freshness_days if policy else None, policy_error)
