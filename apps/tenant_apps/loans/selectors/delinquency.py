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


def get_pawn_loan_delinquency(loan_id: int, *, as_of_date: date, _inputs=None):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PawnLoanDelinquencyError("Delinquency requires an active tenant schema.")
    if _inputs is None:
        try:
            loan = PawnLoan.objects.select_related("product_version").get(
                pk=loan_id, workspace_id=workspace_id
            )
        except PawnLoan.DoesNotExist as exc:
            raise PawnLoanDelinquencyError("PawnLoan was not found in the active workspace.") from exc
        schedule = get_active_repayment_schedule_as_of(loan, as_of_date)
        balance = get_pawn_loan_balance(loan, as_of_date=as_of_date)
    else:
        _inputs.require(loan_id, as_of_date)
        loan, schedule, balance = _inputs.loan, _inputs.schedule, _inputs.position.recorded_balance
    grace_days = loan.product_version.operational_grace_days
    if balance.financial_history_from is not None:
        from apps.tenant_apps.loans.services.opening_evidence import read_opening_evidence
        origin = loan.loan_events.get(event_kind="MIGRATION_OPENING")
        from apps.tenant_apps.loans.services.opening_corrections import opening_schedule_source
        if not balance.financially_settled and (schedule is None or schedule.source_event_id != opening_schedule_source(loan, origin)):
            raise PawnLoanDelinquencyError("Opening delinquency requires its reviewed remaining obligations.")
        grace_days = read_opening_evidence(loan, origin)["review"]["terms"]["grace_days"]
    obligation_state = (_inputs.obligation_state if _inputs is not None
                        else calculate_obligation_state_as_of(schedule, as_of_date))
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
