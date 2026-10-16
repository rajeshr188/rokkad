from dataclasses import dataclass
from datetime import date
from apps.tenant_apps.loans.domain.delinquency import (
    DelinquencyResult,
    UnpaidObligation,
    calculate_delinquency,
)
from .financial_inputs import (
    PawnLoanObligationInputs, PawnLoanFinancialReadError, get_pawn_loan_obligation_inputs,
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


def get_pawn_loan_delinquency(
    loan_id: int, *, as_of_date: date, financial_inputs: PawnLoanObligationInputs | None = None,
):
    try:
        inputs = financial_inputs if financial_inputs is not None else get_pawn_loan_obligation_inputs(loan_id, as_of_date=as_of_date)
        inputs.require(loan_id, as_of_date)
    except PawnLoanFinancialReadError as exc:
        raise PawnLoanDelinquencyError(str(exc)) from exc
    loan, schedule, balance = inputs.loan, inputs.schedule, inputs.balance
    grace_days = inputs.operational_grace_days
    obligation_state = inputs.obligation_state
    if schedule is None and (
        balance.total_due != 0 or loan.state == "ACTIVE" and not balance.financially_settled
    ):
        raise PawnLoanDelinquencyError("An unsettled loan has no active repayment schedule.")
    if obligation_state.integrity_findings:
        raise PawnLoanDelinquencyError(
            "Delinquency evidence is inconsistent: " + " ".join(obligation_state.integrity_findings)
        )
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
        operational_grace_days=grace_days,
    )
    legacy = balance.is_overdue
    return PawnLoanDelinquency(
        loan_id=loan.pk,
        as_of_date=as_of_date,
        assessment=assessment,
        legacy_is_overdue=legacy,
        overdue_variance=legacy != bool(assessment.overdue),
    )
