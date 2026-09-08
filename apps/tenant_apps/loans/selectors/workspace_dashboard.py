from decimal import Decimal

from django.utils import timezone

from apps.tenant_apps.loans.domain import PawnLoanState
from apps.tenant_apps.loans.models import PawnLoan

from .balances import PawnLoanBalanceSelectorError, get_pawn_loan_balance


def get_workspace_pawn_loan_dashboard_summary(*, workspace):
    """Return conservative PawnLoan metrics for the workspace dashboard."""
    as_of_date = timezone.localdate()
    loans = list(PawnLoan.objects.filter(workspace=workspace).order_by("pk"))
    active = [loan for loan in loans if loan.state == PawnLoanState.ACTIVE.value]
    closed_count = sum(loan.state == PawnLoanState.CLOSED.value for loan in loans)
    cancelled_count = sum(loan.state == PawnLoanState.CANCELLED.value for loan in loans)
    balances = []
    for loan in active:
        try:
            balances.append(get_pawn_loan_balance(loan.pk, as_of_date=as_of_date))
        except (PawnLoanBalanceSelectorError, ValueError):
            continue

    total_due = sum((balance.total_due for balance in balances), Decimal("0"))
    total_interest = sum(
        (balance.interest_outstanding for balance in balances), Decimal("0")
    )
    lifecycle_count = len(active) + closed_count
    loan_progress = (
        round(closed_count / lifecycle_count * 100, 2) if lifecycle_count else 0.0
    )
    return {
        "loan_count": len(active),
        "total_loan_amount": total_due,
        "total_interest": total_interest,
        "loan_progress": loan_progress,
        "pawn_loan_counts": {
            "draft": sum(loan.state == PawnLoanState.DRAFT.value for loan in loans),
            "approved": sum(loan.state == PawnLoanState.APPROVED.value for loan in loans),
            "active": len(active),
            "closed": closed_count,
            "cancelled": cancelled_count,
        },
        # Girvi's "sunken" valuation concept has no canonical Loans equivalent.
        "sunken": {"loan_count": 0},
    }
