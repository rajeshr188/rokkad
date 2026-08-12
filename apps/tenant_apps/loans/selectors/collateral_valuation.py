from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_DOWN

from apps.tenant_apps.rates.facade import RATE_FOUND, get_latest_commodity_valuation_rate
from apps.tenant_apps.loans.domain import CollateralCustodyState, ValuationMethod, calculate_ltv
from apps.tenant_apps.loans.models import CollateralAppraisal, PawnLoan, current_tenant_workspace_id
from .exposure import get_pawn_loan_exposure


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


@dataclass(frozen=True)
class PawnLoanCollateralValuation:
    loan_id: int
    as_of_date: date
    items: tuple[CollateralItemValuation, ...]
    eligible_collateral_value: Decimal | None
    ltv: object
    compliance_profile: str


def get_pawn_loan_collateral_valuation(loan_id, *, as_of_date):
    workspace_id = current_tenant_workspace_id()
    loan = PawnLoan.objects.select_related("policy_snapshot").prefetch_related("collateral_items").get(pk=loan_id, workspace_id=workspace_id)
    method = ValuationMethod(loan.policy_snapshot.valuation_method)
    quantum = Decimal(str(loan.policy_snapshot.currency_quantum))
    results = []
    for item in loan.collateral_items.all():
        eligible = item.custody_state in {CollateralCustodyState.IN_VAULT.value, CollateralCustodyState.WITH_FUNDING_LENDER.value}
        blockers = [] if eligible else ["CUSTODY_NOT_ELIGIBLE"]
        lookup = get_latest_commodity_valuation_rate(commodity_code=item.metal, as_of=as_of_date)
        calculated = None
        if lookup.status == RATE_FOUND:
            calculated = (lookup.rate.buying_rate * item.net_weight * item.purity_percentage / Decimal("100")).quantize(quantum, rounding=ROUND_DOWN)
        appraisal = CollateralAppraisal.objects.filter(collateral_item=item, effective_at__date__lte=as_of_date, status=CollateralAppraisal.Status.APPROVED).order_by("-effective_at", "-version").first()
        # Compatibility for collateral captured after the appraisal schema was
        # introduced but before origination began persisting immutable rows.
        # The item field remains documented legacy evidence and is never
        # preferred over an approved appraisal record.
        appraisal_value = (
            appraisal.appraised_value
            if appraisal
            else item.latest_appraised_value
        )
        if method == ValuationMethod.CALCULATED_METAL_VALUE:
            selected = calculated
            if selected is None: blockers.append(lookup.status)
        elif method == ValuationMethod.LATEST_APPRAISAL:
            selected = appraisal_value
            if selected is None: blockers.append("MISSING_APPRAISAL")
        else:
            selected = min(calculated, appraisal_value) if calculated is not None and appraisal_value is not None else None
            if selected is None: blockers.append("INCOMPLETE_LOWER_OF_EVIDENCE")
        results.append(CollateralItemValuation(item.pk, calculated, appraisal_value, selected if eligible else None, getattr(lookup.rate, "pk", None), appraisal.pk if appraisal else None, eligible, tuple(blockers)))
    blockers = tuple(code for row in results for code in row.blockers)
    total = None if blockers else sum((row.selected_value for row in results), Decimal("0"))
    exposure = get_pawn_loan_exposure(loan.pk, as_of_date=as_of_date)
    ltv = calculate_ltv(exposure=exposure.ltv_exposure_basis, collateral_value=total, allowed_ltv_ratio=loan.policy_snapshot.maximum_ltv_ratio, blockers=blockers)
    # ``policy_snapshot`` is the reverse side of LoanPolicySnapshot.loan, so
    # PawnLoan has no generated ``policy_snapshot_id`` attribute. Use the
    # related snapshot's primary key for stable provenance.
    return PawnLoanCollateralValuation(loan.pk, as_of_date, tuple(results), total, ltv, f"loan-policy-snapshot:{loan.policy_snapshot.pk}")
