from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, ROUND_DOWN
from django.utils import timezone

from apps.tenant_apps.rates.facade import RATE_FOUND, get_latest_commodity_valuation_rate
from apps.tenant_apps.loans.domain import CollateralCustodyState, ValuationMethod, calculate_ltv
from apps.tenant_apps.loans.models import CollateralAppraisal, PawnLoan, current_tenant_workspace_id
from .exposure import get_pawn_loan_exposure
from .monitoring_inputs import MonitoringValuationInputs, resolve_monitoring_valuation_inputs
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
            "APPRAISAL_BEFORE_CORRECTION": "Earlier appraisals describe the uncorrected collateral details. Record a fresh appraisal.",
            "SAVED_VALUATION_METHOD_UNAVAILABLE": "Choose a current monitoring method; no saved loan method is available.",
            "MONITORING_POLICY_UNAVAILABLE": "Configure a monitoring policy to assess freshness.",
            "CUSTODY_NOT_ELIGIBLE": "This collateral's custody state is excluded from coverage.",
            "INCOMPLETE_LOWER_OF_EVIDENCE": "Both a metal price and approved appraisal are required.",
        }
        return tuple(messages.get(code, code.replace("_", " ").capitalize()) for code in self.blockers)


@dataclass(frozen=True)
class PawnLoanCollateralObservation:
    loan_id: int
    as_of_date: date
    items: tuple[CollateralItemValuation, ...]
    eligible_collateral_value: Decimal | None
    inputs: MonitoringValuationInputs
    evidence_at: datetime
    next_evidence_at: datetime | None


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
    valuation_method: str = ""
    valuation_basis: str = "ORIGINAL_AGREEMENT"
    original_valuation_method: str = ""
    evidence_at: datetime | None = None
    next_evidence_at: datetime | None = None
    currency_quantum: Decimal | None = None
    precision_source: str = ""
    reference_limit_source: str = ""

    @property
    def valuation_method_label(self):
        return self.valuation_method.replace("_", " ").capitalize()

    @property
    def saved_valuation_method_label(self):
        return self.original_valuation_method.replace("_", " ").capitalize()


def get_pawn_loan_collateral_observation(loan_id, *, as_of_date, evidence_at=None, _inputs=None):
    """Read current collateral evidence independently of debt or original approval."""
    now = timezone.now()
    live = as_of_date == timezone.localdate(now)
    if evidence_at is None:
        # Dated reads restate available knowledge at the local day's end.
        evidence_at = now if live else timezone.make_aware(datetime.combine(as_of_date, time.max))
    if (not isinstance(evidence_at, datetime) or timezone.is_naive(evidence_at)
            or timezone.localdate(evidence_at) != as_of_date
            or (live and evidence_at > now)):
        raise ValueError("Evidence cutoff must be an aware instant on the assessment date, no later than now for live monitoring.")
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise ValueError("Collateral observation requires an active Workspace context.")
    loan = PawnLoan.objects.select_related("policy_snapshot").prefetch_related("collateral_items").get(pk=loan_id, workspace_id=workspace_id)
    inputs = _inputs or resolve_monitoring_valuation_inputs(loan, as_of_date=as_of_date)
    if (not isinstance(inputs, MonitoringValuationInputs) or inputs.loan_id != loan.pk
            or inputs.as_of_date != as_of_date or (inputs.policy is not None
                and (inputs.policy.workspace_id != workspace_id
                    or inputs.policy.license_id not in (None, loan.license_id)))):
        raise ValueError("Prepared monitoring inputs must match this loan, date and Workspace.")
    policy, method, quantum = inputs.policy, inputs.method, inputs.currency_quantum
    items = tuple(loan.collateral_items.all())
    appraisal_rows = CollateralAppraisal.objects.filter(
        workspace_id=workspace_id, collateral_item_id__in=[item.pk for item in items],
        status=CollateralAppraisal.Status.APPROVED,
    )
    appraisals = {row.collateral_item_id: row for row in appraisal_rows.filter(
        effective_at__lte=evidence_at,
    ).order_by("collateral_item_id", "-effective_at", "-version").distinct("collateral_item_id")}
    changes = []
    if live and method != ValuationMethod.CALCULATED_METAL_VALUE:
        next_appraisal = (appraisal_rows.filter(effective_at__gt=evidence_at)
            .order_by("effective_at").values_list("effective_at", flat=True).first())
        if next_appraisal is not None:
            changes.append(next_appraisal)
    results, rates = [], {}
    from apps.tenant_apps.loans.services.collateral_corrections import invalidated_appraisal_versions
    invalidated = invalidated_appraisal_versions(loan)
    for item in items:
        eligible = item.custody_state in {CollateralCustodyState.IN_VAULT.value, CollateralCustodyState.WITH_FUNDING_LENDER.value}
        blockers = [] if eligible else ["CUSTODY_NOT_ELIGIBLE"]
        if method is None:
            blockers.append("SAVED_VALUATION_METHOD_UNAVAILABLE")
        if policy is None:
            blockers.append("MONITORING_POLICY_UNAVAILABLE")
        elif item.custody_state not in policy.eligible_custody_states:
            eligible = False
            if "CUSTODY_NOT_ELIGIBLE" not in blockers:
                blockers.append("CUSTODY_NOT_ELIGIBLE")
        if item.metal not in rates:
            lookup = get_latest_commodity_valuation_rate(commodity_code=item.metal, as_of=evidence_at,
                include_next_effective_at=live and method != ValuationMethod.LATEST_APPRAISAL)
            rates[item.metal] = lookup
            if lookup.next_effective_at is not None:
                changes.append(lookup.next_effective_at)
        lookup = rates[item.metal]
        calculated = None
        if lookup.status == RATE_FOUND and lookup.rate.buying_rate.is_finite() and lookup.rate.buying_rate > 0:
            calculated = (lookup.rate.buying_rate * item.net_weight * item.purity_percentage / Decimal("100")).quantize(quantum, rounding=ROUND_DOWN)
        appraisal = appraisals.get(item.pk)
        if appraisal and appraisal.version <= invalidated.get(item.pk, -1):
            if method != ValuationMethod.CALCULATED_METAL_VALUE:
                blockers.append("APPRAISAL_BEFORE_CORRECTION")
            appraisal = None
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
    total = None if blockers or method is None or policy is None else sum((row.selected_value for row in results), Decimal("0"))
    return PawnLoanCollateralObservation(loan.pk, as_of_date, tuple(results), total,
        inputs, evidence_at, min(changes, default=None))


def get_pawn_loan_collateral_valuation(loan_id, *, as_of_date, evidence_at=None, _exposure=None):
    """Combine the current observation with supported debt, without reapproval."""
    if _exposure is not None and (_exposure.loan_id != loan_id or _exposure.as_of_date != as_of_date):
        raise ValueError("Prepared exposure must match the scoped loan and assessment date.")
    observed = get_pawn_loan_collateral_observation(loan_id, as_of_date=as_of_date, evidence_at=evidence_at)
    inputs, policy = observed.inputs, observed.inputs.policy
    exposure = _exposure if _exposure is not None else get_pawn_loan_exposure(loan_id, as_of_date=as_of_date)
    blockers = tuple(code for row in observed.items for code in row.blockers)
    if exposure.integrity_findings:
        blockers += ("FINANCIAL_EVIDENCE_INCONSISTENT",)
    ltv = calculate_ltv(exposure=exposure.ltv_exposure_basis,
        collateral_value=observed.eligible_collateral_value,
        allowed_ltv_ratio=inputs.reference_ltv_ratio, blockers=blockers)
    return PawnLoanCollateralValuation(loan_id, as_of_date, observed.items, observed.eligible_collateral_value, ltv,
        inputs.compatibility_identity, policy.pk if policy else None,
        policy.rate_freshness_days if policy else None, policy.appraisal_freshness_days if policy else None, inputs.policy_error,
        inputs.method.value if inputs.method else "", inputs.valuation_basis, inputs.saved_method,
        observed.evidence_at, observed.next_evidence_at, inputs.currency_quantum,
        inputs.precision_source, inputs.reference_limit_source)
