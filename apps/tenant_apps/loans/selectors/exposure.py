from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from apps.tenant_apps.loans.domain import (
    LoanRepaymentStructure,
)
from apps.tenant_apps.loans.models import PawnLoan, current_tenant_workspace_id
from .obligation_state import (
    ObligationAmount,
    calculate_obligation_state_as_of,
    get_active_repayment_schedule_as_of,
)


class PawnLoanExposureError(ValueError):
    pass


ExposureComponent = ObligationAmount


@dataclass(frozen=True)
class PawnLoanExposure:
    loan_id: int
    as_of_date: date
    original_principal: Decimal
    principal_repaid: Decimal
    principal_outstanding: Decimal
    recorded_interest: Decimal
    projected_interest: Decimal
    fees_and_penalties: Decimal
    due_now: ExposureComponent
    overdue: ExposureComponent
    recorded_total_due: Decimal
    total_economic_exposure: Decimal
    cash_receivable_basis: Decimal
    maturity_payoff: Decimal
    ltv_exposure_basis: Decimal
    projection_periods: tuple[tuple[date, date, Decimal], ...]
    provenance: tuple[str, ...]
    integrity_findings: tuple[str, ...]
    ltv_basis_label: str = ""
    principal_history_basis: str = "ORIGINAL_PAYOUT"
    financial_history_from: date | None = None
    servicing_profile: str = ""


def get_pawn_loan_exposure(loan_id: int, *, as_of_date: date) -> PawnLoanExposure:
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PawnLoanExposureError("PawnLoan exposure requires an active tenant schema.")
    try:
        loan = PawnLoan.objects.select_related(
            "product_version__product", "policy_snapshot"
        ).get(pk=loan_id, workspace_id=workspace_id)
    except PawnLoan.DoesNotExist as exc:
        raise PawnLoanExposureError("PawnLoan was not found in the active workspace.") from exc

    from .continuation import resolve_loan_continuation
    try:
        position = resolve_loan_continuation(loan, as_of_date=as_of_date, include_legacy_projection=True)
    except ValueError as exc:
        raise PawnLoanExposureError(str(exc)) from exc
    balance = position.recorded_balance
    plan = position.recognition
    continuation = plan.calculation if plan.adapter == "OPENING_CHECKPOINT" else None
    previews = plan.projection_periods
    projected_interest = plan.additional_interest
    active_schedule = get_active_repayment_schedule_as_of(loan, as_of_date)
    if continuation and not balance.financially_settled and (active_schedule is None or active_schedule.source_event_id != continuation.opening_event_id):
        raise PawnLoanExposureError("Opening exposure requires remaining obligations linked to its migration opening.")
    obligation_state = calculate_obligation_state_as_of(active_schedule, as_of_date)
    due_now = obligation_state.due_now
    overdue = obligation_state.overdue
    scheduled_remaining = obligation_state.remaining
    findings = list(obligation_state.integrity_findings)
    cash_receivable_basis = (
        balance.principal_outstanding + balance.fees_outstanding
    )
    recorded_total = balance.total_due
    total_economic = recorded_total + projected_interest
    maturity_payoff = scheduled_remaining.total + balance.fees_outstanding
    is_bullet = loan.product_version.repayment_structure in {
        LoanRepaymentStructure.SINGLE_PAYMENT_BULLET.value,
        LoanRepaymentStructure.PERIODIC_INTEREST_BULLET.value,
        LoanRepaymentStructure.FLEXIBLE_PARTIAL_PAYMENT.value,
    }
    ltv_basis = maturity_payoff if is_bullet else total_economic
    if scheduled_remaining.principal != balance.principal_outstanding:
        findings.append(
            "Scheduled remaining principal does not equal recorded principal outstanding."
        )
    if recorded_total != (
        balance.principal_outstanding
        + balance.interest_outstanding
        + balance.fees_outstanding
    ):
        findings.append("Recorded total due does not equal its balance components.")
    provenance = (
        "recorded:event-fold-v1",
        f"projection:{plan.projection_rule}",
        f"contract:{loan.product_version.calculation_contract_version}",
        "due:active-obligation-fold-v1",
        f"schedule:{obligation_state.schedule_fingerprint or 'none'}",
    )
    return PawnLoanExposure(
        loan_id=loan.pk,
        as_of_date=as_of_date,
        original_principal=loan.principal_amount if plan.adapter == "VERIFIED_TERMINAL_POSITION" else balance.opening_principal if continuation else balance.principal_disbursed,
        principal_repaid=balance.principal_paid,
        principal_outstanding=balance.principal_outstanding,
        recorded_interest=balance.interest_outstanding,
        projected_interest=projected_interest,
        fees_and_penalties=balance.fees_outstanding,
        due_now=due_now,
        overdue=overdue,
        recorded_total_due=recorded_total,
        total_economic_exposure=total_economic,
        cash_receivable_basis=cash_receivable_basis,
        maturity_payoff=maturity_payoff,
        ltv_exposure_basis=ltv_basis,
        projection_periods=previews,
        provenance=provenance,
        integrity_findings=tuple(findings),
        ltv_basis_label="Maturity payoff" if is_bullet else "Economic exposure",
        principal_history_basis="VERIFIED_TERMINAL_POSITION" if plan.adapter == "VERIFIED_TERMINAL_POSITION" else "OPENING_CHECKPOINT" if continuation else "ORIGINAL_PAYOUT",
        financial_history_from=position.contract.financial_history_from,
        servicing_profile=position.contract.profile,
    )
