"""Read-only navigation between PawnLoans in the same numbered series."""

from dataclasses import dataclass

from django.db.models import Q

from apps.tenant_apps.loans.models import PawnLoan


@dataclass(frozen=True)
class PawnLoanSeriesNavigation:
    previous: PawnLoan | None
    next: PawnLoan | None


def get_pawn_loan_series_navigation(loan: PawnLoan) -> PawnLoanSeriesNavigation:
    """Return adjacent loans in canonical model order, scoped to one series."""
    series_loans = PawnLoan.objects.filter(
        workspace_id=loan.workspace_id,
        series_id=loan.series_id,
    )
    earlier = Q(loan_date__lt=loan.loan_date) | Q(
        loan_date=loan.loan_date,
        loan_number__lt=loan.loan_number,
    ) | Q(
        loan_date=loan.loan_date,
        loan_number=loan.loan_number,
        pk__lt=loan.pk,
    )
    later = Q(loan_date__gt=loan.loan_date) | Q(
        loan_date=loan.loan_date,
        loan_number__gt=loan.loan_number,
    ) | Q(
        loan_date=loan.loan_date,
        loan_number=loan.loan_number,
        pk__gt=loan.pk,
    )
    return PawnLoanSeriesNavigation(
        previous=series_loans.filter(earlier).order_by(
            "-loan_date", "-loan_number", "-pk"
        ).first(),
        next=series_loans.filter(later).order_by(
            "loan_date", "loan_number", "pk"
        ).first(),
    )
