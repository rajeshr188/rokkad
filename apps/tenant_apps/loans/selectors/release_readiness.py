"""PawnLoan collateral valuation and release-settlement readiness."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

from apps.tenant_apps.rates.facade import (
    RATE_FOUND,
    get_latest_commodity_valuation_rate,
)
from apps.tenant_apps.loans.domain import (
    CollateralCustodyState,
    PawnLoanState,
    ValuationMethod,
)
from apps.tenant_apps.loans.models import (
    CollateralAppraisal,
    PawnLoan,
    current_tenant_workspace_id,
)
from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance


ZERO = Decimal("0")


class PawnLoanReleaseReadinessError(ValueError):
    pass


@dataclass(frozen=True)
class ReleaseReadinessBlocker:
    code: str
    message: str
    collateral_item_id: int | None = None


@dataclass(frozen=True)
class CollateralValuationSnapshot:
    collateral_item_id: int
    description: str
    metal: str
    net_weight: Decimal
    purity_percentage: Decimal
    latest_appraised_value: Decimal | None
    rate_id: int | None
    rate_per_unit: Decimal | None
    rate_timestamp: object | None
    rate_source_name: str
    calculated_metal_value: Decimal | None
    valuation_method: str
    valuation_amount: Decimal | None
    selected_for_release: bool
    custody_state: str


@dataclass(frozen=True)
class PawnLoanReleaseReadiness:
    loan_id: int
    as_of_date: date
    valuation_method: str
    maximum_ltv_ratio: Decimal
    item_valuations: tuple[CollateralValuationSnapshot, ...]
    selected_item_ids: tuple[int, ...]
    retained_item_ids: tuple[int, ...]
    selected_collateral_value: Decimal | None
    retained_collateral_value: Decimal | None
    fees_and_interest_settlement: Decimal
    principal_reduction_required: Decimal | None
    minimum_settlement: Decimal | None
    principal_after_minimum_settlement: Decimal | None
    retained_ltv_after_minimum_settlement: Decimal | None
    is_full_release: bool
    blockers: tuple[ReleaseReadinessBlocker, ...]

    @property
    def ready(self):
        return not self.blockers


def get_pawn_loan_release_readiness(
    loan_id: int,
    *,
    selected_item_ids,
    as_of_date: date,
) -> PawnLoanReleaseReadiness:
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PawnLoanReleaseReadinessError(
            "PawnLoan release readiness requires an active tenant schema."
        )
    try:
        loan = (
            PawnLoan.objects.select_related("policy_snapshot")
            .prefetch_related("collateral_items")
            .get(pk=loan_id, workspace_id=workspace_id)
        )
    except PawnLoan.DoesNotExist as exc:
        raise PawnLoanReleaseReadinessError(
            "PawnLoan was not found in the active workspace."
        ) from exc
    balance = get_pawn_loan_balance(loan.pk, as_of_date=as_of_date)
    collateral_items = tuple(loan.collateral_items.all())
    appraisal_values = {}
    appraisals = CollateralAppraisal.objects.filter(
        collateral_item_id__in=[item.pk for item in collateral_items],
        effective_at__date__lte=as_of_date,
        status=CollateralAppraisal.Status.APPROVED,
    ).order_by("collateral_item_id", "-effective_at", "-version")
    for appraisal in appraisals:
        appraisal_values.setdefault(
            appraisal.collateral_item_id, appraisal.appraised_value
        )
    return calculate_pawn_loan_release_readiness(
        loan,
        collateral_items=collateral_items,
        balance=balance,
        policy_snapshot=loan.policy_snapshot,
        selected_item_ids=selected_item_ids,
        as_of_date=as_of_date,
        appraisal_values=appraisal_values,
    )


def calculate_pawn_loan_release_readiness(
    loan,
    *,
    collateral_items,
    balance,
    policy_snapshot,
    selected_item_ids,
    as_of_date: date,
    rate_resolver=get_latest_commodity_valuation_rate,
    appraisal_values=None,
) -> PawnLoanReleaseReadiness:
    """Pure release quote except for its injected, public-facade rate lookup."""
    selected_ids = tuple(dict.fromkeys(int(value) for value in selected_item_ids))
    selected_set = set(selected_ids)
    items = tuple(collateral_items)
    appraisal_values = appraisal_values or {
        item.pk: getattr(item, "approved_appraisal_value", None) for item in items
    }
    item_ids = {item.pk for item in items}
    blockers = []
    if loan.state != PawnLoanState.ACTIVE.value:
        blockers.append(
            ReleaseReadinessBlocker(
                "LOAN_NOT_ACTIVE",
                "Only an active PawnLoan can release collateral.",
            )
        )
    if not selected_ids:
        blockers.append(
            ReleaseReadinessBlocker(
                "NO_COLLATERAL_SELECTED",
                "Select at least one collateral item for release.",
            )
        )
    for unknown_id in sorted(selected_set - item_ids):
        blockers.append(
            ReleaseReadinessBlocker(
                "COLLATERAL_NOT_FOUND",
                "Selected collateral does not belong to this PawnLoan.",
                unknown_id,
            )
        )
    if not balance.posting_ready:
        blockers.append(
            ReleaseReadinessBlocker(
                "ACCOUNTING_NOT_READY",
                "Resolve every pending or failed accounting event before release.",
            )
        )

    quantum = Decimal(str(policy_snapshot.currency_quantum))
    method = policy_snapshot.valuation_method
    rate_cache = {}
    valuations = []
    for item in items:
        selected = item.pk in selected_set
        if selected and item.custody_state == CollateralCustodyState.WITH_CUSTOMER.value:
            blockers.append(
                ReleaseReadinessBlocker(
                    "COLLATERAL_ALREADY_RELEASED",
                    "Collateral already returned to the customer cannot be released again.",
                    item.pk,
                )
            )
        if (
            selected
            and item.custody_state
            == CollateralCustodyState.WITH_FUNDING_LENDER.value
        ):
            blockers.append(
                ReleaseReadinessBlocker(
                    "COLLATERAL_WITH_FUNDING_LENDER",
                    "Collateral held by a funding lender cannot be released.",
                    item.pk,
                )
            )
        snapshot, item_blockers = _value_item(
            item,
            selected=selected,
            requires_valuation=(
                selected
                or item.custody_state
                != CollateralCustodyState.WITH_CUSTOMER.value
            ),
            method=method,
            as_of_date=as_of_date,
            quantum=quantum,
            rate_cache=rate_cache,
            rate_resolver=rate_resolver,
            appraisal_value=appraisal_values.get(item.pk),
        )
        valuations.append(snapshot)
        blockers.extend(item_blockers)

    valid_selection = bool(selected_ids) and selected_set <= item_ids
    complete_valuations = all(
        item.valuation_amount is not None
        for item in valuations
        if item.selected_for_release
        or item.custody_state != CollateralCustodyState.WITH_CUSTOMER.value
    )
    selected_value = None
    retained_value = None
    principal_reduction = None
    minimum_settlement = None
    principal_after = None
    retained_ltv = None
    fees_and_interest = _money(
        balance.fees_outstanding + balance.interest_outstanding,
        quantum,
    )
    if valid_selection and complete_valuations:
        selected_value = _money(
            sum(
                (
                    item.valuation_amount
                    for item in valuations
                    if item.selected_for_release
                ),
                ZERO,
            ),
            quantum,
        )
        retained_value = _money(
            sum(
                (
                    item.valuation_amount
                    for item in valuations
                    if not item.selected_for_release
                    and item.custody_state
                    != CollateralCustodyState.WITH_CUSTOMER.value
                ),
                ZERO,
            ),
            quantum,
        )
        allowed_principal = (retained_value * policy_snapshot.maximum_ltv_ratio).quantize(
            quantum,
            rounding=ROUND_DOWN,
        )
        principal_reduction = _money(
            max(ZERO, balance.principal_outstanding - allowed_principal),
            quantum,
        )
        minimum_settlement = _money(
            fees_and_interest + principal_reduction,
            quantum,
        )
        principal_after = _money(
            balance.principal_outstanding - principal_reduction,
            quantum,
        )
        if retained_value > 0:
            retained_ltv = principal_after / retained_value

    retained_ids = tuple(
        item.pk
        for item in items
        if item.pk not in selected_set
        and item.custody_state != CollateralCustodyState.WITH_CUSTOMER.value
    )
    return PawnLoanReleaseReadiness(
        loan_id=loan.pk,
        as_of_date=as_of_date,
        valuation_method=method,
        maximum_ltv_ratio=Decimal(str(policy_snapshot.maximum_ltv_ratio)),
        item_valuations=tuple(valuations),
        selected_item_ids=selected_ids,
        retained_item_ids=retained_ids,
        selected_collateral_value=selected_value,
        retained_collateral_value=retained_value,
        fees_and_interest_settlement=fees_and_interest,
        principal_reduction_required=principal_reduction,
        minimum_settlement=minimum_settlement,
        principal_after_minimum_settlement=principal_after,
        retained_ltv_after_minimum_settlement=retained_ltv,
        is_full_release=valid_selection and not retained_ids,
        blockers=tuple(blockers),
    )


def _value_item(
    item,
    *,
    selected,
    requires_valuation,
    method,
    as_of_date,
    quantum,
    rate_cache,
    rate_resolver,
    appraisal_value,
):
    blockers = []
    rate = None
    calculated = None
    needs_calculated = method in {
        ValuationMethod.CALCULATED_METAL_VALUE.value,
        ValuationMethod.LOWER_OF_CALCULATED_AND_APPRAISAL.value,
    }
    if requires_valuation:
        if item.metal not in rate_cache:
            rate_cache[item.metal] = rate_resolver(
                commodity_code=item.metal,
                as_of=as_of_date,
                currency="INR",
                purity="24k",
            )
        lookup = rate_cache[item.metal]
        if lookup.status == RATE_FOUND:
            rate = lookup.rate
            calculated = _money(
                Decimal(str(rate.buying_rate))
                * Decimal(str(item.net_weight))
                * Decimal(str(item.purity_percentage))
                / Decimal("100"),
                quantum,
            )
        elif needs_calculated:
            blockers.append(
                ReleaseReadinessBlocker(
                    f"METAL_RATE_{lookup.status}",
                    "A current 24K buying rate is required for collateral valuation.",
                    item.pk,
                )
            )

    appraisal = (
        _money(Decimal(str(appraisal_value)), quantum)
        if appraisal_value is not None
        else None
    )
    if requires_valuation and method in {
        ValuationMethod.LATEST_APPRAISAL.value,
        ValuationMethod.LOWER_OF_CALCULATED_AND_APPRAISAL.value,
    } and appraisal is None:
        blockers.append(
            ReleaseReadinessBlocker(
                "LATEST_APPRAISAL_REQUIRED",
                "A latest staff appraisal is required for collateral valuation.",
                item.pk,
            )
        )

    if not requires_valuation:
        amount = None
    elif method == ValuationMethod.CALCULATED_METAL_VALUE.value:
        amount = calculated
    elif method == ValuationMethod.LATEST_APPRAISAL.value:
        amount = appraisal
    elif method == ValuationMethod.LOWER_OF_CALCULATED_AND_APPRAISAL.value:
        amount = (
            min(calculated, appraisal)
            if calculated is not None and appraisal is not None
            else None
        )
    else:
        raise PawnLoanReleaseReadinessError("Unknown snapshotted valuation method.")
    return (
        CollateralValuationSnapshot(
            collateral_item_id=item.pk,
            description=item.description,
            metal=item.metal,
            net_weight=Decimal(str(item.net_weight)),
            purity_percentage=Decimal(str(item.purity_percentage)),
            latest_appraised_value=appraisal,
            rate_id=getattr(rate, "pk", None),
            rate_per_unit=(Decimal(str(rate.buying_rate)) if rate else None),
            rate_timestamp=getattr(rate, "timestamp", None),
            rate_source_name=str(rate.rate_source) if rate else "",
            calculated_metal_value=calculated,
            valuation_method=method,
            valuation_amount=amount,
            selected_for_release=selected,
            custody_state=item.custody_state,
        ),
        blockers,
    )


def _money(value, quantum):
    return Decimal(value).quantize(quantum, rounding=ROUND_HALF_UP)
