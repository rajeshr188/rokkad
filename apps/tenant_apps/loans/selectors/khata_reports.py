"""Source-linked cash and current custody, never historical outstanding balances."""
from decimal import Decimal

from django.db.models import Case, CharField, Count, DecimalField, Exists, F, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce

from apps.tenancy.context import current_workspace_id
from apps.tenant_apps.loans.models import KhataOperation, KhataCollateralItem, KhataCollateralSelection

ZERO = Decimal("0.00")


def _scope(qs, workspace, data, *, account_prefix):
    if current_workspace_id() != workspace.pk:
        raise ValueError("Khata reports require the matching Workspace context.")
    qs = qs.filter(workspace=workspace)
    for key in ("series", "borrower", "account"):
        if data.get(key):
            name = account_prefix + key if key != "account" else "account_id"
            qs = qs.filter(**{name: data[key]})
    if data.get("association"):
        qs = qs.filter(**{account_prefix + "series__license__isnull": data["association"] == "independent"})
    return qs


def cash_operations(*, workspace, data):
    qs = _scope(KhataOperation.objects.all(), workspace, data, account_prefix="account__").filter(
        Q(kind__in=("WITHDRAW", "INTEREST", "SETTLE", "CORRECT")) | Q(kind="REVISE", amount__gt=0))
    for key, lookup in (("from_date", "gte"), ("to_date", "lte")):
        if data.get(key):
            qs = qs.filter(**{"business_date__" + lookup: data[key]})
    if data.get("kind"):
        qs = qs.filter(kind=data["kind"])
    if data.get("q"):
        term = data["q"]
        qs = qs.filter(Q(account__account_number__icontains=term) | Q(account__borrower__display_name__icontains=term)
            | Q(account__borrower__party_code__icontains=term) | Q(evidence__payment_reference__icontains=term)
            | Q(evidence__resolution_reference__icontains=term))
    money = DecimalField(max_digits=20, decimal_places=2)
    qs = qs.annotate(
        principal_in=Case(When(kind__in=("REVISE", "SETTLE"), then=F("amount")), default=Value(ZERO), output_field=money),
        interest_in=Case(When(kind="INTEREST", corrected_by__evidence__cash_resolution="NOT_RECEIVED", then=Value(ZERO)),
            When(kind="INTEREST", then=F("amount")), When(kind="SETTLE", then=F("interest_amount")), default=Value(ZERO), output_field=money),
        cash_out=Case(When(kind="WITHDRAW", then=F("amount")),
            When(kind="CORRECT", correction_of__kind="INTEREST", evidence__cash_resolution="REFUNDED", then=F("amount")),
            default=Value(ZERO), output_field=money),
    ).annotate(cash_in=F("principal_in") + F("interest_in"))
    prefix = "-" if data.get("sort") == "newest" else ""
    return qs.select_related("account__borrower", "account__series__license", "created_by", "corrected_by", "correction_of").order_by(
        prefix + "business_date", prefix + "account_id", prefix + "sequence", prefix + "pk")


def cash_totals(operations):
    keys = ("principal_in", "interest_in", "cash_in", "cash_out")
    # Separate aggregate aliases from the row annotations they sum.
    summed = operations.aggregate(**{key + "_total": Coalesce(Sum(key), Value(ZERO)) for key in keys})
    totals = {key: summed[key + "_total"] for key in keys}
    totals["net_cash"] = totals["cash_in"] - totals["cash_out"]
    return totals


def cash_row(op):
    note = ""
    if op.kind == "INTEREST" and getattr(op, "corrected_by", None):
        note = ("Receipt not received; zero actual cash" if op.corrected_by.evidence["cash_resolution"] == "NOT_RECEIVED"
            else "Original receipt retained; actual refund is a separate dated outflow")
    elif op.kind == "CORRECT":
        note = {"NOT_RECEIVED": "No cash movement; corrects a receipt not received",
            "REFUNDED": "Full amount actually refunded"}.get(op.evidence.get("cash_resolution"), "Exchange correction; no cash movement")
    return dict(operation=op, note=note, reference=op.evidence.get("payment_reference") or op.evidence.get("resolution_reference", ""))


def custody_items(*, workspace, data):
    returns = KhataOperation.objects.filter(workspace=workspace, item_id=OuterRef("pk"), kind__in=("RETURN", "HANDOVER"))
    reservations = KhataCollateralSelection.objects.filter(workspace=workspace, item_id=OuterRef("pk"), role="OUT",
        operation__corrected_by__isnull=True).order_by("-pk")
    qs = _scope(KhataCollateralItem.objects.all(), workspace, data, account_prefix="account__").annotate(
        returned=Exists(returns), reserved=Exists(reservations),
        return_id=Subquery(returns.values("pk")[:1]), return_on=Subquery(returns.values("business_date")[:1]),
        return_recipient=Subquery(returns.values("evidence__recipient")[:1]),
        return_reference=Coalesce(Subquery(returns.values("evidence__reference")[:1]), Subquery(returns.values("evidence__reason")[:1])),
        reservation_id=Subquery(reservations.values("operation_id")[:1]),
        reserved_on=Subquery(reservations.values("operation__business_date")[:1]),
    ).annotate(custody=Case(When(returned=True, then=Value("returned")), When(reserved=True, then=Value("pending")),
        default=Value("held"), output_field=CharField()))
    mode = data.get("custody") or "physical"
    if mode == "physical":
        qs = qs.filter(returned=False)
    elif mode in ("held", "pending", "returned"):
        qs = qs.filter(custody=mode)
    if data.get("metal"):
        qs = qs.filter(metal=data["metal"])
    for key, lookup in (("from_date", "gte"), ("to_date", "lte")):
        if data.get(key):
            qs = qs.filter(**{"received_operation__business_date__" + lookup: data[key]})
    if data.get("q"):
        term = data["q"]
        qs = qs.filter(Q(account__account_number__icontains=term) | Q(account__borrower__display_name__icontains=term)
            | Q(account__borrower__party_code__icontains=term) | Q(description__icontains=term)
            | Q(storage_reference__icontains=term) | Q(public_id__icontains=term)
            | (Q(pk=int(term)) if term.isdecimal() and len(term) <= 18 else Q(pk__isnull=True)))
    prefix = "" if data.get("sort") == "oldest" else "-"
    return qs.select_related("account__borrower", "account__series__license", "received_operation").order_by(
        prefix + "received_operation__business_date", prefix + "pk")


def custody_totals(items):
    return list(items.order_by().values("metal", "custody").annotate(
        records=Count("pk"), pieces=Sum("quantity"), net=Sum("net_weight")).order_by("metal", "custody"))
