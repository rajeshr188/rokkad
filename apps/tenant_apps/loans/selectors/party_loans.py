"""Compose distinct loan kinds without changing pawn-only selector contracts."""
from decimal import Decimal

from django.core.paginator import Paginator
from django.urls import reverse
from django.utils import timezone

from .party_history import PartyPawnLoanRow, get_party_pawn_loan_history_summary
from .khata_summary import portfolio_summary, LIVE_STATES


def get_party_loan_history_summary(party, *, limit=20, page_size=None,
                                   active_page=1, closed_page=1, sort="newest"):
    pawn = get_party_pawn_loan_history_summary(party, limit=None, sort=sort)
    khata = portfolio_summary(workspace=party.workspace, borrower=party)
    active, closed = list(pawn["active_loans"]), list(pawn["closed_loans"])
    unavailable = sum(r.account_state == "ACTIVE" and r.total_outstanding is None for r in active)
    for summary in khata["rows"]:
        account = summary["account"]
        opened = account.opened_on is not None
        known = not summary.get("unavailable")
        row = PartyPawnLoanRow(pk=account.pk, loan_id=account.account_number, loan_type="Khata",
            loan_date=account.opened_on or timezone.localdate(account.created_at), status=account.get_state_display(),
            total_outstanding=summary["outstanding"] if known and opened else None,
            principal_due=summary["principal"] if known and opened else None,
            interest_due=summary["interest"] if known and opened else None,
            payment_count=0, total_payment_amount=Decimal(0), unposted_payment_count=0, notice_count=0,
            collateral_items_count=summary.get("held_count", 0), collateral_loan_amount=None,
            detail_url=reverse("workspace_loans:khata_detail", kwargs={"workspace_slug": party.workspace.slug, "pk": account.pk}),
            repayment_url="", document_links=(), account_state=account.state)
        (active if account.state in LIVE_STATES else closed).append(row)
    unavailable += khata["unavailable"]
    sort = pawn["sort"]
    ordering = lambda r: (r.loan_date, r.loan_type, r.pk)
    active.sort(key=ordering, reverse=sort == "newest")
    closed.sort(key=ordering, reverse=sort == "newest")
    pages = {}
    counts = dict(active_loans=len(active), closed_loans=len(closed),
        active_outstanding=None if unavailable else sum((r.total_outstanding for r in active if r.total_outstanding is not None), Decimal(0)),
        collateral_items=pawn["counts"]["collateral_items"] + sum(s.get("held_count", 0) for s in khata["rows"]),
        collateral_loan_amount=None, unavailable_balances=unavailable,
        khata_active=khata["active_count"], khata_interest=khata["interest"], khata_pending_returns=khata["pending_returns"])
    if page_size is not None:
        a, c = Paginator(active, page_size).get_page(active_page), Paginator(closed, page_size).get_page(closed_page)
        pages = dict(active_page=a, closed_page=c)
        active, closed = a.object_list, c.object_list
    else:
        active, closed = active[:limit], closed[:limit]
    return dict(**pages, sort=sort, active_loans=active, closed_loans=closed, counts=counts)
