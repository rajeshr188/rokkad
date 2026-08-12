from dataclasses import dataclass
from datetime import date

from apps.tenant_apps.dea.facade import get_pawn_loan_receivable_balance
from apps.tenant_apps.loans.models import PawnLoan, current_tenant_workspace_id
from .exposure import get_pawn_loan_exposure


@dataclass(frozen=True)
class PawnLoanReceivableReconciliation:
    loan_id: int
    as_of_date: date
    loans_receivable: object
    dea_receivable: object
    variance: object
    status: str


def reconcile_pawn_loan_receivable(loan_id: int, *, as_of_date: date):
    loan = PawnLoan.objects.get(pk=loan_id, workspace_id=current_tenant_workspace_id())
    exposure = get_pawn_loan_exposure(loan.pk, as_of_date=as_of_date)
    event_ids = loan.accounting_events.filter(effective_date__lte=as_of_date).values_list("pk", flat=True)
    dea = get_pawn_loan_receivable_balance(source_event_ids=event_ids, as_of_date=as_of_date)
    variance = exposure.accounting_receivable - dea.total
    status = "MATCH" if variance == 0 else "VARIANCE"
    if dea.status != "OK": status = "ERROR"
    return PawnLoanReceivableReconciliation(loan.pk, as_of_date, exposure.accounting_receivable, dea, variance, status)
