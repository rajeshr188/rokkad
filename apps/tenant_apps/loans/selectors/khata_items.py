"""Account-scoped collateral browsing without loading a whole holding into a widget."""
from decimal import Decimal, ROUND_DOWN

from django.db.models import Case, CharField, Exists, OuterRef, Q, Subquery, Value, When
from django.utils import timezone

from apps.tenant_apps.loans.models import KhataCollateralItem, KhataCollateralPhoto, KhataCollateralSelection, KhataOperation
from .origination_rates import get_origination_quote_rows


def collateral_items(account, *, mode="browse"):
    selections = KhataCollateralSelection.objects.filter(item_id=OuterRef("pk"), operation__corrected_by__isnull=True)
    items = KhataCollateralItem.objects.filter(workspace_id=account.workspace_id, account=account).select_related("received_operation").annotate(
        returned=Exists(KhataOperation.objects.filter(item_id=OuterRef("pk"), kind__in=("RETURN", "HANDOVER"))),
        reserved=Exists(selections.filter(role="OUT")), used_in=Exists(selections.filter(role="IN")),
        reservation_id=Subquery(selections.filter(role="OUT").order_by("-pk").values("operation_id")[:1]),
        photo_pk=Subquery(KhataCollateralPhoto.objects.filter(item_id=OuterRef("pk")).order_by("-pk").values("pk")[:1]),
    ).annotate(custody=Case(When(returned=True, then=Value("returned")),
        When(reserved=True, then=Value("pending")), default=Value("held"), output_field=CharField()))
    if mode in ("outgoing", "incoming"):
        items = items.filter(returned=False, reserved=False)
    if mode == "incoming":
        items = items.filter(used_in=False)
    if mode == "held":
        items = items.filter(returned=False)
    if mode == "pending":
        items = items.filter(returned=False, reserved=True)
    return items


def filter_items(items, data):
    q = data.get("q", "").strip()
    if q:
        # A bare item number must find that identity, not incidental digits in other UUIDs.
        match = Q(pk=int(q)) if q.isdecimal() and len(q) <= 18 else (
            Q(description__icontains=q) | Q(storage_reference__icontains=q) | Q(public_id__icontains=q))
        items = items.filter(match)
    if data.get("metal"):
        items = items.filter(metal=data["metal"])
    if data.get("custody"):
        items = items.filter(custody=data["custody"])
    if data.get("from_date"):
        items = items.filter(received_operation__business_date__gte=data["from_date"])
    if data.get("to_date"):
        items = items.filter(received_operation__business_date__lte=data["to_date"])
    prefix = "" if data.get("sort") == "oldest" else "-"
    return items.order_by(prefix + "received_operation__business_date", prefix + "pk")


def suggested_values(account, items):
    """Suggestions only; the reviewed command remains authoritative."""
    quotes = get_origination_quote_rows(workspace_id=account.workspace_id,
        loan_date=timezone.localdate(), metals=[i.metal for i in items])
    prices = {r["metal"]: r["rate"].buying_rate for r in quotes if r["fresh"]}
    return {i.pk: (prices[i.metal] * i.net_weight * i.purity / 100).quantize(
        Decimal("0.01"), rounding=ROUND_DOWN) if i.metal in prices else None for i in items}
