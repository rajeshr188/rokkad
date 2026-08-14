from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.template.response import TemplateResponse

from ..models import Voucher, VoucherStatus, VoucherType


def _safe_decimal(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _voucher_amount(voucher):
    """Use ledger transaction totals as voucher amount (single-side total)."""
    total = Decimal("0")
    for je in voucher.journal_entries.all():
        for ltxn in je.ltxns.all():
            total += ltxn.amount.amount
    return total


def _party_label(voucher):
    """Best-effort extraction of party/contact label from business_doc."""
    doc = voucher.business_doc
    if not doc:
        return "-"

    attr_paths = [
        ("contact", "name"),
        ("customer", "name"),
        ("vendor", "name"),
        ("party", "name"),
    ]
    for obj_attr, name_attr in attr_paths:
        obj = getattr(doc, obj_attr, None)
        if obj is not None:
            label = getattr(obj, name_attr, None)
            if label:
                return str(label)
            return str(obj)

    for raw_attr in ("contact_name", "customer_name", "vendor_name", "party_name"):
        label = getattr(doc, raw_attr, None)
        if label:
            return str(label)

    return str(doc)


@login_required
def transaction_list(request):
    """Unified transaction list over all vouchers with advanced filtering."""
    queryset = Voucher.objects.select_related(
        "voucher_type", "created_by", "doc_content_type"
    ).prefetch_related("journal_entries__ltxns").order_by("-voucher_date", "-created_at")

    search = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    voucher_type_id = request.GET.get("voucher_type", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    amount_min = _safe_decimal(request.GET.get("amount_min"))
    amount_max = _safe_decimal(request.GET.get("amount_max"))
    party = request.GET.get("party", "").strip().lower()

    if search:
        queryset = queryset.filter(
            Q(voucher_no__icontains=search)
            | Q(narration__icontains=search)
            | Q(voucher_type__name__icontains=search)
        )

    if status:
        queryset = queryset.filter(status=status)

    if voucher_type_id:
        queryset = queryset.filter(voucher_type_id=voucher_type_id)

    if date_from:
        queryset = queryset.filter(voucher_date__gte=date_from)

    if date_to:
        queryset = queryset.filter(voucher_date__lte=date_to)

    rows = []
    for voucher in queryset:
        row_amount = _voucher_amount(voucher)
        row_party = _party_label(voucher)

        if amount_min is not None and row_amount < amount_min:
            continue
        if amount_max is not None and row_amount > amount_max:
            continue
        if party and party not in row_party.lower():
            continue

        rows.append(
            {
                "id": voucher.pk,
                "voucher_no": voucher.voucher_no,
                "type": voucher.voucher_type.name,
                "status": voucher.status,
                "status_label": voucher.get_status_display(),
                "voucher_date": voucher.voucher_date,
                "created_at": voucher.created_at,
                "party": row_party,
                "amount": row_amount,
                "detail_url": voucher.get_absolute_url(),
                "source": voucher.doc_content_type.model,
                "narration": voucher.narration or "",
            }
        )

    # Secondary sorting options
    sort = request.GET.get("sort", "date_desc")
    if sort == "date_asc":
        rows.sort(key=lambda r: (r["voucher_date"], r["created_at"]))
    elif sort == "amount_desc":
        rows.sort(key=lambda r: r["amount"], reverse=True)
    elif sort == "amount_asc":
        rows.sort(key=lambda r: r["amount"])
    else:
        rows.sort(key=lambda r: (r["voucher_date"], r["created_at"]), reverse=True)

    paginator = Paginator(rows, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "title": "Unified Transactions",
        "rows": page_obj,
        "page_obj": page_obj,
        "statuses": VoucherStatus.choices,
        "voucher_types": VoucherType.objects.all().order_by("name"),
        "filters": {
            "q": search,
            "status": status,
            "voucher_type": voucher_type_id,
            "date_from": date_from,
            "date_to": date_to,
            "amount_min": request.GET.get("amount_min", ""),
            "amount_max": request.GET.get("amount_max", ""),
            "party": request.GET.get("party", ""),
            "sort": sort,
        },
    }
    return TemplateResponse(request, "dea/transaction_list.html", context)
