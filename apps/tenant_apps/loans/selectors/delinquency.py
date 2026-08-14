from dataclasses import dataclass
from datetime import date
from apps.tenant_apps.loans.domain.delinquency import (
    DelinquencyResult,
    UnpaidObligation,
    calculate_delinquency,
)
from apps.tenant_apps.loans.models import PawnLoan, current_tenant_workspace_id
from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance
from apps.tenant_apps.loans.selectors.obligation_state import (
    calculate_obligation_state_as_of,
    get_active_repayment_schedule_as_of,
)


class PawnLoanDelinquencyError(ValueError):
    pass


@dataclass(frozen=True)
class PawnLoanDelinquency:
    loan_id: int
    as_of_date: date
    assessment: DelinquencyResult
    legacy_is_overdue: bool
    overdue_variance: bool


def get_pawn_loan_delinquency(loan_id: int, *, as_of_date: date):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PawnLoanDelinquencyError("Delinquency requires an active tenant schema.")
    try:
        loan = PawnLoan.objects.select_related("product_version").get(
            pk=loan_id, workspace_id=workspace_id
        )
    except PawnLoan.DoesNotExist as exc:
        raise PawnLoanDelinquencyError("PawnLoan was not found in the active workspace.") from exc
    schedule = get_active_repayment_schedule_as_of(loan, as_of_date)
    obligation_state = calculate_obligation_state_as_of(schedule, as_of_date)
    rows = tuple(
        UnpaidObligation(
            due_date=row.due_date,
            principal=row.principal,
            interest=row.interest,
        )
        for row in obligation_state.obligations
    )
    assessment = calculate_delinquency(
        rows,
        as_of_date=as_of_date,
        operational_grace_days=loan.product_version.operational_grace_days,
    )
    legacy = get_pawn_loan_balance(loan, as_of_date=as_of_date).is_overdue
    return PawnLoanDelinquency(
        loan_id=loan.pk,
        as_of_date=as_of_date,
        assessment=assessment,
        legacy_is_overdue=legacy,
        overdue_variance=legacy != bool(assessment.overdue),
    )
