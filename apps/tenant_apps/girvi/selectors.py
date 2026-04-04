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
from decimal import Decimal

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

from .models import GivenLoan, LoanStatus, TakenLoan


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
        .prefetch_related("repledgedloanitems")
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
        taken_qs = taken_qs.filter(status=LoanStatus.RELEASED)
    elif status == "UnReleased":
        given_qs = given_qs.filter(release__isnull=True)
        taken_qs = taken_qs.exclude(status=LoanStatus.RELEASED)

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
        taken_amount = (
            taken_qs.aggregate(
                total=Sum("repledgedloanitems__repledged_loanamount")
            )["total"]
            or 0
        )
        taken_interest = (
            taken_qs.aggregate(total=Sum("repledgedloanitems__interest"))["total"] or 0
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
            LoanItem.objects.filter(loan__release__isnull=True, loan__loan_type="Given")
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
    except Exception as e:
        print(f"Error calculating averages: {e}")
        return {}


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
            "statementitem_set__statement",
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
    from django.contrib.contenttypes.models import ContentType

    from apps.tenant_apps.dea.models import PaymentVoucher, Voucher

    from .models import JournalEntry

    payment_ids = list(loan.payments.values_list("id", flat=True))
    if not payment_ids:
        return JournalEntry.objects.none()

    payment_ct = ContentType.objects.get_for_model(PaymentVoucher)
    vouchers = Voucher.objects.filter(
        doc_content_type=payment_ct,
        doc_object_id__in=payment_ids,
    )
    if not vouchers.exists():
        return JournalEntry.objects.none()

    return (
        JournalEntry.objects.filter(voucher__in=vouchers)
        .select_related("voucher", "posted_by")
        .order_by("-posted_at")
    )


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

    return {
        "loan": loan,
        "items": loan.loanitems.all(),
        "payments": payments,
        "journal_entries": journal_entries,
        "statement_items": statement_items,
        "notifications": notifications,
            "renewals_as_source": loan.renewals_as_source.all(),
            "origin_renewal": loan.renewal_record.first(),
        "summary": {
            "status": loan.status,
            "is_released": loan.is_released,
            "is_overdue": loan.is_overdue,
            "payment_count": payments.count(),
            "journal_entry_count": journal_entries.count(),
            "interest_due": loan.interest_due(),
            "total_due": loan.total_due,
            "outstanding_principal": getattr(loan, "outstanding_principal", None),
        },
    }


def get_given_loan_detail_read_model(loan_id):
    """Fetch and assemble a full cross-domain read model for loan detail tabs."""
    return build_given_loan_detail_read_model(get_given_loan_detail(loan_id))
