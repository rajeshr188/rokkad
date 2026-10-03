from dataclasses import dataclass
from decimal import Decimal

from django.core.paginator import Paginator
from django.db.models import Count
from django.urls import reverse
from django.utils import timezone

from apps.tenant_apps.loans.domain import PawnLoanState
from apps.tenant_apps.loans.models import PawnLoan

from .balances import PawnLoanBalanceSelectorError, get_pawn_loan_balance


@dataclass(frozen=True)
class PartyPawnLoanRow:
    pk: int
    loan_id: str
    loan_type: str
    loan_date: object
    status: str
    total_outstanding: Decimal | None
    principal_due: Decimal | None
    interest_due: Decimal | None
    payment_count: int
    total_payment_amount: Decimal
    unposted_payment_count: int
    notice_count: int
    collateral_items_count: int
    collateral_loan_amount: None
    detail_url: str
    repayment_url: str
    document_links: tuple
    account_state: str = ""


def _loan_row(loan: PawnLoan, *, as_of_date) -> PartyPawnLoanRow:
    balance = None
    if loan.state == PawnLoanState.ACTIVE.value:
        try:
            balance = get_pawn_loan_balance(loan.pk, as_of_date=as_of_date)
        except (PawnLoanBalanceSelectorError, ValueError):
            balance = None

    return PartyPawnLoanRow(
        pk=loan.pk,
        loan_id=loan.loan_number,
        loan_type="PawnLoan",
        loan_date=loan.loan_date,
        status=loan.get_state_display(),
        total_outstanding=getattr(balance, "total_due", None),
        principal_due=getattr(balance, "principal_outstanding", None),
        interest_due=getattr(balance, "interest_outstanding", None),
        payment_count=0,
        total_payment_amount=Decimal("0"),
        unposted_payment_count=0,
        notice_count=0,
        collateral_items_count=loan.collateral_items_count,
        collateral_loan_amount=None,
        detail_url=reverse("workspace_loans:pawn_loan_detail", kwargs={"workspace_slug": loan.workspace.slug, "pk": loan.pk}),
        repayment_url=reverse("workspace_loans:pawn_loan_repay", kwargs={"workspace_slug": loan.workspace.slug, "pk": loan.pk}),
        document_links=(),
        account_state=loan.state,
    )


def get_party_pawn_loan_history_summary(
    party, *, limit=20, page_size=None, active_page=1, closed_page=1, sort="newest",
):
    """Return Party-owned Loans history without consulting retired Girvi."""
    as_of_date = timezone.localdate()
    sort = sort if sort in {"oldest", "newest"} else "newest"
    ordering = ("loan_date", "pk") if sort == "oldest" else ("-loan_date", "-pk")
    loans = list(
        PawnLoan.objects.filter(borrower=party).select_related("workspace")
        .annotate(collateral_items_count=Count("collateral_items", distinct=True))
        .order_by(*ordering)
    )
    active_states = {
        PawnLoanState.DRAFT.value,
        PawnLoanState.APPROVED.value,
        PawnLoanState.ACTIVE.value,
    }
    active = [loan for loan in loans if loan.state in active_states]
    closed = [loan for loan in loans if loan.state not in active_states]
    # The display limit must never truncate the borrower's outstanding balance.
    active_rows = tuple(_loan_row(loan, as_of_date=as_of_date) for loan in active)
    outstanding = sum(
        (row.total_outstanding for row in active_rows if row.total_outstanding is not None),
        Decimal("0"),
    )
    pages = {}
    if page_size is not None:
        active_page = Paginator(active_rows, page_size).get_page(active_page)
        closed_page = Paginator(closed, page_size).get_page(closed_page)
        closed_page.object_list = tuple(
            _loan_row(loan, as_of_date=as_of_date) for loan in closed_page.object_list
        )
        displayed_active = active_page.object_list
        displayed_closed = closed_page.object_list
        pages = {"active_page": active_page, "closed_page": closed_page}
    else:
        displayed_active = active_rows[:limit]
        displayed_closed = tuple(_loan_row(loan, as_of_date=as_of_date) for loan in closed[:limit])
    return {
        **pages,
        "sort": sort,
        "active_loans": displayed_active,
        "closed_loans": displayed_closed,
        "counts": {
            "active_loans": len(active),
            "closed_loans": len(closed),
            "active_outstanding": outstanding,
            "collateral_items": sum(loan.collateral_items_count for loan in loans),
            "collateral_loan_amount": None,
        },
    }
