"""
Girvi loan list selectors — application-level read layer.

These functions compose queries *across* GivenLoan and TakenLoan models,
handle unified filtering, row-shaping for the combined table, and aggregate
totals for the loan list views and the HTMX table partial.

Design contract:
  - No HttpRequest or view-layer objects enter here.
  - No state mutation (no save/delete/transition).
  - Querysets are returned unevaluated where possible so the caller can
    further chain or pass to django-filter.
  - Row-shaping (build_unified_loan_rows) evaluates the querysets.

Layer boundary:
  View  → calls selectors for querysets/totals/rows
        → applies django-filter / django-tables2 / RequestConfig
        → renders template

  Selector → calls QuerySet/Manager methods from managers_refactored
           → applies cross-model filters and aggregations
"""

from collections import Counter
from decimal import Decimal, InvalidOperation
import logging

from django.db.models import (
    Case,
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
    Window,
)
from django.db.models.functions import Coalesce, ExtractYear, TruncDate
from django.urls import reverse

from .lifecycle import RELEASED_COMPAT_STATUSES, UNRELEASED_EXCLUDED_STATUSES
from .lifecycle import lifecycle_status_badge_class, lifecycle_status_label
from .models import GivenLoan, TakenLoan


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base querysets
# ---------------------------------------------------------------------------


def given_loan_base_qs():
    """
    Annotated GivenLoan queryset ready for table display.

    Includes: metal weights, itemwise loanamounts, current collateral
    value, and payment metrics (via for_table_display).
    """
    return (
        GivenLoan.objects.get_queryset()
        .for_table_display()
        .order_by("-id")
        .select_related("borrower", "series", "created_by")
        .prefetch_related("notifications", "loanitems")
    )


def taken_loan_base_qs():
    """
    Annotated TakenLoan queryset ready for table display.

    Intentionally skips for_table_display() because the shared duration
    annotations reference release__release_date, a relation TakenLoan
    does not have.
    """
    return (
        TakenLoan.objects.get_queryset()
        .with_metal_weights()
        .with_itemwise_amounts()
        .with_current_value()
        .order_by("-id")
        .select_related("lender", "series", "created_by")
        .prefetch_related("repledge_history_items")
    )


# ---------------------------------------------------------------------------
# Cross-model filtering (unified "all" view)
# ---------------------------------------------------------------------------


def filter_unified_loans(given_qs, taken_qs, *, query="", status="All"):
    """
    Apply free-text search and lifecycle status filter to both querysets.

    Args:
        given_qs:  GivenLoan queryset (from given_loan_base_qs or filtered).
        taken_qs:  TakenLoan queryset (from taken_loan_base_qs or filtered).
        query:     Free-text string matched against id, loan_id, and party name.
        status:    One of "All", "Released", "UnReleased".

    Returns:
        (filtered_given_qs, filtered_taken_qs)
    """
    if query:
        given_qs = given_qs.filter(
            Q(id__icontains=query)
            | Q(loan_id__icontains=query)
            | Q(borrower__firstname__icontains=query)
            | Q(borrower__lastname__icontains=query)
        )
        taken_qs = taken_qs.filter(
            Q(id__icontains=query)
            | Q(loan_id__icontains=query)
            | Q(lender__firstname__icontains=query)
            | Q(lender__lastname__icontains=query)
        )

    if status == "Released":
        given_qs = given_qs.filter(release__isnull=False)
        taken_qs = taken_qs.filter(status__in=RELEASED_COMPAT_STATUSES)
    elif status == "UnReleased":
        given_qs = given_qs.filter(release__isnull=True)
        taken_qs = taken_qs.exclude(status__in=UNRELEASED_EXCLUDED_STATUSES)

    return given_qs, taken_qs


# ---------------------------------------------------------------------------
# Row shaping (unified table)
# ---------------------------------------------------------------------------


def build_unified_loan_rows(given_qs, taken_qs):
    """
    Evaluate both querysets and merge into a single list of row dicts
    sorted by loan_date descending, suitable for UnifiedLoanTable.

    Note: this evaluates the querysets — call after all filtering is done.
    """
    rows = [
        {
            "id": loan.id,
            "loan_type": "Given",
            "loan_id": loan.loan_id,
            "loan_date": loan.loan_date,
            "party": loan.borrower.name,
            "status": loan.status,
            "status_label": lifecycle_status_label(loan.status),
            "loan_amount": loan.get_loan_amount,
        }
        for loan in given_qs
    ] + [
        {
            "id": loan.id,
            "loan_type": "Taken",
            "loan_id": loan.loan_id,
            "loan_date": loan.loan_date,
            "party": loan.lender.name,
            "status": loan.status,
            "status_label": lifecycle_status_label(loan.status, loan_kind="taken"),
            "loan_amount": loan.get_loan_amount,
        }
        for loan in taken_qs
    ]
    rows.sort(key=lambda r: r["loan_date"], reverse=True)
    return rows


# ---------------------------------------------------------------------------
# Totals
# ---------------------------------------------------------------------------


def get_loan_totals(*, given_qs=None, taken_qs=None):
    """
    Aggregate principal and interest totals across given and/or taken loans.

    Accepts keyword-only querysets so callers are explicit:
      get_loan_totals(given_qs=filter.qs)
      get_loan_totals(taken_qs=filter.qs)
      get_loan_totals(given_qs=given_qs, taken_qs=taken_qs)

    Returns a dict that can be unpacked directly into template context:
      {"total_loan_amount": {"total": <Decimal>}, "total_interest": {"total": <Decimal>}}

    Values are normalised to 0 when the queryset is empty or contains no items.
    """
    given_amount = 0
    given_interest = 0
    taken_amount = 0
    taken_interest = 0

    if given_qs is not None:
        given_amount = (
            given_qs.aggregate(total=Sum("loanitems__loanamount"))["total"] or 0
        )
        given_interest = (
            given_qs.aggregate(total=Sum("loanitems__interest"))["total"] or 0
        )

    if taken_qs is not None:
        taken_interest_expression = ExpressionWrapper(
            F("repledge_history_items__repledged_amount")
            * F("repledge_history_items__loan_item__interestrate")
            / Value(100),
            output_field=DecimalField(max_digits=15, decimal_places=2),
        )
        taken_amount = (
            taken_qs.aggregate(
                total=Sum("repledge_history_items__repledged_amount")
            )["total"]
            or 0
        )
        taken_interest = (
            taken_qs.aggregate(total=Sum(taken_interest_expression))["total"] or 0
        )

    return {
        "total_loan_amount": {"total": given_amount + taken_amount},
        "total_interest": {"total": given_interest + taken_interest},
    }


# ---------------------------------------------------------------------------
# Analytics / dashboard selectors
# ---------------------------------------------------------------------------


def get_loan_cumulative_amount():
    """Return unreleased GivenLoan principal totals as a cumulative time series."""
    from .models import LoanItem

    loan_amount_subquery = (
        LoanItem.objects.filter(loan=OuterRef("pk"))
        .values("loan")
        .annotate(total=Sum("loanamount"))
        .values("total")
    )

    return (
        GivenLoan.objects.unreleased()
        .annotate(loan_amount=Subquery(loan_amount_subquery))
        .annotate(cumsum=Window(Sum("loan_amount"), order_by=F("loan_date").asc()))
        .values("loan_date__date", "cumsum")
        .order_by("loan_date")
    )


def get_average_loan_instance_per_day():
    """Average number of GivenLoan records created on days that had loan activity."""
    loans_per_day = (
        GivenLoan.objects.annotate(day=TruncDate("loan_date"))
        .values("day")
        .annotate(count=Count("id"))
        .aggregate(total_loans=Sum("count"), total_days=Count("day", distinct=True))
    )

    if not loans_per_day["total_loans"]:
        return 0

    average = loans_per_day["total_loans"] / loans_per_day["total_days"]
    return round(average, 0)


def get_loan_counts_grouped():
    """Group unreleased GivenLoan counts by customer frequency bucket."""
    loan_counts = (
        GivenLoan.objects.unreleased()
        .values("customer__id", "customer__firstname", "customer__lastname")
        .annotate(loan_count=Count("id"))
        .order_by("loan_count")
    )

    grouped_loan_counts = Counter(
        loan_count for loan_count in loan_counts.values_list("loan_count", flat=True)
    )
    return list(grouped_loan_counts.items())


def get_loans_by_year():
    """Return yearly GivenLoan counts with unreleased totals."""
    return (
        GivenLoan.objects.annotate(
            year=ExtractYear("loan_date"),
            has_release=Case(
                When(release__isnull=False, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ),
        )
        .values("year")
        .annotate(
            loans_count=Count("id"),
            unreleased_count=Count("id", filter=Q(has_release=0)),
        )
        .order_by("year")
    )


def get_unreleased_loans_by_year():
    """Return yearly counts for unreleased GivenLoan records."""
    return (
        GivenLoan.objects.unreleased()
        .annotate(year=ExtractYear("loan_date"))
        .values("year")
        .annotate(release_count=Count("id"))
        .order_by("year")
    )


def get_loanamount_by_itemtype():
    """Aggregate unreleased loan amounts by `LoanItem.itemtype`."""
    from .models import LoanItem

    return (
        LoanItem.objects.filter(loan__release__isnull=True)
        .values("itemtype")
        .annotate(total_loan_amount=Sum("loanamount"))
    )


def get_itemtype_averages():
    """Calculate average loan amount per gram for each item type."""
    from .models import LoanItem

    try:
        stats = (
            LoanItem.objects.filter(loan__release__isnull=True)
            .values("itemtype")
            .annotate(
                total_weight=Coalesce(Sum("weight"), Decimal("0.00")),
                total_amount=Coalesce(Sum("loanamount"), Decimal("0.00")),
            )
            .annotate(
                avg_per_gram=Case(
                    When(
                        Q(total_weight__gt=0),
                        then=ExpressionWrapper(
                            F("total_amount") / F("total_weight"),
                            output_field=DecimalField(max_digits=10, decimal_places=2),
                        ),
                    ),
                    default=Value(Decimal("0.00")),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                ),
                count=Count("id"),
            )
            .order_by("itemtype")
        )

        return {
            item["itemtype"]: {
                "avg_per_gram": item["avg_per_gram"],
                "total_weight": item["total_weight"],
                "total_amount": item["total_amount"],
                "count": item["count"],
            }
            for item in stats
        }
    except Exception:
        logger.exception("Error calculating item type averages.")
        return {}


def get_dashboard_payment_counts():
    """Return dashboard payment counts through the Girvi DEA adapter boundary."""
    from apps.tenant_apps.girvi.integrations.dea_adapter import (
        get_payment_voucher_counts,
    )

    return get_payment_voucher_counts()


# ---------------------------------------------------------------------------
# Loan detail (cross-domain read model)
# ---------------------------------------------------------------------------


def given_loan_detail_qs():
    """
    Base queryset for loan detail screens.

    Prefetches all relations required by detail tabs so view handlers stay thin.
    """
    return (
        GivenLoan.objects.select_related("borrower", "created_by", "series")
        .prefetch_related(
            "loanitems",
            "notifications",
            "payments",
            "renewals_as_source__renewed_loan",
            "renewal_record__source_loan",
        )
    )


def get_given_loan_detail(loan_id):
    """Fetch a single GivenLoan with detail relations loaded."""
    return given_loan_detail_qs().get(pk=loan_id)


def get_given_loan_journal_entries(loan):
    """
    Resolve loan-linked JournalEntry records through payment and voucher links:
      GivenLoan -> PaymentVoucher -> Voucher -> JournalEntry
    """
    from apps.tenant_apps.girvi.integrations.dea_adapter import get_loan_journal_entries

    return get_loan_journal_entries(loan)


def _as_decimal(value, default=Decimal("0.00")):
    amount = getattr(value, "amount", value)
    if amount is None:
        return default
    try:
        return Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError):
        return default


def _is_positive(value):
    return _as_decimal(value) > 0


def _non_negative_amount(value):
    if value is None:
        return None
    try:
        return max(value, 0)
    except TypeError:
        amount_value = getattr(value, "amount", None)
        if amount_value is not None:
            return max(amount_value, 0)
    return value


def _metal_weight_part(weight_summary, item_type, label, field_name, *, places=None):
    value = weight_summary.get(item_type, {}).get(field_name, 0)
    if not _is_positive(value):
        return ""
    if places is not None:
        value = round(value, places)
    return f"{label}:{value} gms"


def build_given_loan_release_action(loan):
    """Build release CTA metadata for loan detail surfaces."""
    if getattr(loan, "release", None):
        return None

    status = str(getattr(loan, "status", "") or "")
    allowed_statuses = {
        "Disbursed",
        "ActiveCurrent",
        "ActiveOverdue",
        "ActiveNPA",
        "ClosurePending",
    }
    if status not in allowed_statuses:
        return None

    outstanding_amount = getattr(loan, "outstanding_amount", None)
    if outstanding_amount is None:
        total_due = getattr(loan, "total_due", None)
        total_payments_getter = getattr(loan, "get_total_payments", None)
        if total_due is not None and callable(total_payments_getter):
            try:
                outstanding_amount = total_due - total_payments_getter()
            except Exception:
                outstanding_amount = total_due

    outstanding_amount = _non_negative_amount(outstanding_amount)
    closure_exception = bool(getattr(loan, "closure_exception_approved", False))
    needs_settlement = (
        outstanding_amount is not None
        and _is_positive(outstanding_amount)
        and not closure_exception
    )

    return {
        "title": "Start Release Workflow",
        "icon": ">",
        "button_class": "btn-success" if not needs_settlement else "btn-outline-secondary",
        "href": reverse("girvi:release_loan_check_custody", args=[loan.id]),
        "disabled": needs_settlement,
        "outstanding_amount": outstanding_amount,
        "closure_exception_approved": closure_exception,
    }


def build_given_loan_detail_display(loan):
    """Build display-only loan detail metrics used by the full detail view."""
    raw_weight_summary = getattr(loan, "get_weight_summary", []) or []
    weight_summary = {item["itemtype"]: item for item in raw_weight_summary}

    weight = " ".join(
        filter(
            None,
            [
                _metal_weight_part(weight_summary, "Gold", "G", "total_weight"),
                _metal_weight_part(weight_summary, "Silver", "S", "total_weight"),
                _metal_weight_part(weight_summary, "Bronze", "B", "total_weight"),
            ],
        )
    )
    pure = " ".join(
        filter(
            None,
            [
                _metal_weight_part(weight_summary, "Gold", "G", "pure_weight", places=3),
                _metal_weight_part(weight_summary, "Silver", "S", "pure_weight", places=3),
                _metal_weight_part(weight_summary, "Bronze", "B", "pure_weight", places=3),
            ],
        )
    )

    value = getattr(loan, "current_value", Decimal("0.00"))
    value_decimal = _as_decimal(value)
    loan_amount_decimal = _as_decimal(getattr(loan, "get_loan_amount", None), default=None)
    lvratio = 0
    if value_decimal > 0 and loan_amount_decimal is not None:
        lvratio = round(float(loan_amount_decimal) / float(value_decimal) * 100, 2)

    due = getattr(loan, "total_due", Decimal("0.00"))
    due_decimal = _as_decimal(due)
    dvratio = 0
    if due_decimal > 0 and value_decimal > 0:
        dvratio = round(float(due_decimal) / float(value_decimal), 2) * 100

    get_storage_box = getattr(loan, "get_storage_box", None)
    location = get_storage_box() if callable(get_storage_box) else None
    position = location.position_for_item(loan.id) if location else None

    interest_reporting = {
        "gross_accrued": getattr(loan, "gross_accrued_interest", Decimal("0.00")),
        "paid": loan.interest_paid_total()
        if hasattr(loan, "interest_paid_total")
        else Decimal("0.00"),
        "outstanding": getattr(loan, "outstanding_interest", Decimal("0.00")),
        "receivable_balance": loan.interest_receivable_balance()
        if hasattr(loan, "interest_receivable_balance")
        else Decimal("0.00"),
        "last_accrual_date": getattr(loan, "last_accrual_date", None),
    }

    return {
        "weight_summary": weight_summary,
        "weight": weight,
        "pure": pure,
        "value": value,
        "due": due,
        "worth": value - due,
        "lvratio": lvratio,
        "dvratio": dvratio,
        "location": location,
        "position": position,
        "interest_reporting": interest_reporting,
    }


def build_given_loan_detail_read_model(loan):
    """
    Build a cross-domain read model for loan detail tabs.

    Includes loan core entity, payments, voucher/journal trail, notifications,
    statement entries, and status-derived summary fields.
    """
    payments = loan.payments.order_by("-payment_date")
    journal_entries = get_given_loan_journal_entries(loan)
    statement_items = loan.statementitem_set.select_related("statement").all()
    notifications = loan.notifications.all()
    display = build_given_loan_detail_display(loan)

    return {
        "loan": loan,
        "items": loan.loanitems.all(),
        "payments": payments,
        "journal_entries": journal_entries,
        "statement_items": statement_items,
        "notifications": notifications,
        "renewals_as_source": loan.renewals_as_source.all(),
        "origin_renewal": loan.renewal_record.first(),
        "display": display,
        "release_action": build_given_loan_release_action(loan),
        "summary": {
            "status": loan.status,
            "status_label": lifecycle_status_label(loan.status),
            "status_badge_class": lifecycle_status_badge_class(loan.status),
            "is_released": loan.is_released,
            "is_overdue": loan.is_overdue,
            "payment_count": payments.count(),
            "journal_entry_count": journal_entries.count(),
            "interest_due": loan.interest_due(),
            "total_due": loan.total_due,
            "outstanding_principal": getattr(loan, "outstanding_principal", None),
            "gross_accrued_interest": getattr(loan, "gross_accrued_interest", Decimal("0.00")),
            "interest_paid_total": loan.interest_paid_total()
            if hasattr(loan, "interest_paid_total")
            else Decimal("0.00"),
            "interest_outstanding": getattr(loan, "outstanding_interest", Decimal("0.00")),
            "interest_receivable_balance": loan.interest_receivable_balance()
            if hasattr(loan, "interest_receivable_balance")
            else Decimal("0.00"),
            "last_accrual_date": getattr(loan, "last_accrual_date", None),
        },
    }


def get_given_loan_detail_read_model(loan_id):
    """Fetch and assemble a full cross-domain read model for loan detail tabs."""
    return build_given_loan_detail_read_model(get_given_loan_detail(loan_id))
