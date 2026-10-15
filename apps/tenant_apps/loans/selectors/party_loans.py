"""Compose distinct loan kinds without changing pawn-only selector contracts."""
from decimal import Decimal
from collections import defaultdict
from dataclasses import replace

from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef
from django.urls import reverse
from django.utils import timezone

from .party_history import PartyPawnLoanRow, get_party_pawn_loan_history_summary
from .khata_summary import portfolio_summary, LIVE_STATES
from .loan_summary import collateral_preview
from apps.tenant_apps.loans.models import KhataCollateralItem, KhataOperation, PawnCollateralItem


def _with_collateral_previews(rows, *, workspace_id):
    """Fetch item details for displayed rows only, independently of full totals."""
    items = defaultdict(list)
    for kind, model, field in (("PawnLoan", PawnCollateralItem, "loan_id"),
                               ("Khata", KhataCollateralItem, "account_id")):
        ids = [row.pk for row in rows if row.loan_type == kind]
        if ids:
            records = model.objects.filter(workspace_id=workspace_id, **{field + "__in": ids}).order_by("pk")
            if kind == "Khata":
                records = records.annotate(preview_returned=Exists(KhataOperation.objects.filter(
                    workspace_id=workspace_id, item_id=OuterRef("pk"), kind__in=("RETURN", "HANDOVER"))))
            for item in records:
                items[(kind, getattr(item, field))].append(item)
    return [replace(row, collateral_preview=collateral_preview(items[(row.loan_type, row.pk)],
        provisional=row.account_state in {"DRAFT", "APPROVED", "CANCELLED"})) for row in rows]


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
            repayment_url="", document_links=(), account_state=account.state,
            fees_due=Decimal(0) if known and opened else None)
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
    for key, field in (("active_principal", "principal_due"), ("active_interest", "interest_due"), ("active_fees", "fees_due")):
        counts[key] = None if unavailable else sum((getattr(row, field) for row in active if getattr(row, field) is not None), Decimal(0))
    if page_size is not None:
        a, c = Paginator(active, page_size).get_page(active_page), Paginator(closed, page_size).get_page(closed_page)
        pages = dict(active_page=a, closed_page=c)
        active, closed = a.object_list, c.object_list
    else:
        active, closed = active[:limit], closed[:limit]
    visible = _with_collateral_previews([*active, *closed], workspace_id=party.workspace_id)
    active, closed = visible[:len(active)], visible[len(active):]
    if pages:
        pages["active_page"].object_list = active
        pages["closed_page"].object_list = closed
    return dict(**pages, sort=sort, active_loans=active, closed_loans=closed, counts=counts)
