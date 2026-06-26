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
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import logging

from django.db.models import (
    Case,
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    Func,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Q,
    Value,
    When,
    Window,
)
from django.db.models.functions import Coalesce, ExtractYear, TruncDate
from django.urls import reverse
from django.utils import timezone

from .lifecycle import RELEASED_COMPAT_STATUSES, UNRELEASED_EXCLUDED_STATUSES
from .lifecycle import lifecycle_status_badge_class, lifecycle_status_label
from .lifecycle import (
    CANONICAL_ACTIVE_CURRENT,
    CANONICAL_ACTIVE_NPA,
    CANONICAL_ACTIVE_OVERDUE,
    CANONICAL_CLOSURE_PENDING,
    CANONICAL_DRAFT,
    CANONICAL_PENDING_APPROVAL,
    CANONICAL_APPROVED,
    CANONICAL_REJECTED,
    CANONICAL_CANCELLED,
    canonical_status,
)
from .models import GivenLoan, TakenLoan
from .integrations.notification_adapter import (
    get_draft_notice_status_value,
    get_pending_notifications_count,
    get_total_notifications_count,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoanSettlementBalance:
    principal_due: Decimal
    interest_due: Decimal
    principal_paid: Decimal
    interest_paid: Decimal
    total_paid: Decimal
    total_due: Decimal
    total_outstanding: Decimal
    overpayment: Decimal


@dataclass(frozen=True)
class RepaymentPreview:
    settlement: LoanSettlementBalance
    suggested_total_amount: Decimal
    suggested_interest_amount: Decimal
    suggested_principal_amount: Decimal
    is_settled: bool


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


def build_girvi_dashboard_read_model(*, user=None, workspace=None, recent_release_limit=5):
    """Return consolidated dashboard context so views stay as thin render adapters."""
    from apps.tenant_apps.girvi.models import (
        License,
        LoanItemStorageBox,
        Release,
        Series,
        StatementItem,
    )

    given_loans = GivenLoan.objects
    payment_counts = get_dashboard_payment_counts()
    operational_queue = build_dashboard_operational_queue(
        user=user,
        workspace=workspace,
    )

    return {
        "total_loans": given_loans.count(),
        "unreleased_loans": given_loans.unreleased().count(),
        "released_loans": given_loans.released().count(),
        "overdue_loans": given_loans.non_performing_loans_stats().count(),
        "total_loan_amount": given_loans.get_queryset().total_loan_amount() or 0,
        "total_releases": Release.objects.count(),
        "recent_releases": Release.objects.order_by("-release_date")[:recent_release_limit],
        "total_licenses": License.objects.count(),
        "active_licenses": License.objects.filter(is_active=True).count(),
        "total_series": Series.objects.count(),
        "active_series": Series.objects.filter(is_active=True).count(),
        "total_boxes": LoanItemStorageBox.objects.count(),
        "total_payments": payment_counts["total_payments"],
        "pending_payments": payment_counts["pending_payments"],
        "total_statements": StatementItem.objects.count(),
        "total_notifications": get_total_notifications_count(),
        "pending_notifications": get_pending_notifications_count(),
        "operational_queue": operational_queue,
        "queue_counts": operational_queue["counts"],
    }


def _queue_transition_url(loan, transition_name):
    return f"{reverse('girvi:girvi_loan_transition', args=[loan.pk])}?transition={transition_name}"


def _build_operational_queue_entry(loan, *, settlement, policy, draft_notice_exists):
    return {
        "loan": loan,
        "loan_id": getattr(loan, "loan_id", ""),
        "borrower_name": getattr(getattr(loan, "borrower", None), "name", ""),
        "status": getattr(loan, "status", ""),
        "status_label": lifecycle_status_label(getattr(loan, "status", "")),
        "status_badge_class": lifecycle_status_badge_class(getattr(loan, "status", "")),
        "maturity_date": policy.maturity_date,
        "total_outstanding": settlement.total_outstanding,
        "settlement_amount": policy.settlement_amount,
        "current_value": policy.current_value,
        "undersecured": policy.undersecured,
        "has_draft_notice": draft_notice_exists,
        "detail_url": reverse("girvi:girvi_loan_detail", args=[loan.pk]),
    }


def build_dashboard_operational_queue(
    *,
    user=None,
    workspace=None,
    as_of_date=None,
    limit=10,
    loans=None,
):
    """Build the dashboard queue for due/overdue/NPA/cure/notice workflows."""
    from apps.tenant_apps.girvi.flows import build_runtime_loan_flow
    from apps.tenant_apps.girvi.service_modules.overdue_policy import evaluate_overdue_policy

    if loans is None:
        loans = (
            GivenLoan.objects.filter(
                status__in=(
                    CANONICAL_ACTIVE_CURRENT,
                    CANONICAL_ACTIVE_OVERDUE,
                    CANONICAL_ACTIVE_NPA,
                    CANONICAL_CLOSURE_PENDING,
                )
            )
            .select_related("borrower")
            .order_by("loan_date")[: max(limit * 8, 40)]
        )

    today = as_of_date or timezone.localdate()
    due_today = []
    overdue_candidates = []
    npa_candidates = []
    cure_candidates = []
    notice_candidates = []

    for loan in loans:
        try:
            settlement = build_loan_settlement_balance(loan)
            policy = evaluate_overdue_policy(loan, as_of_date=today)
            flow = build_runtime_loan_flow(loan, user, workspace)
        except Exception:
            continue

        notifications = getattr(loan, "notifications", None)
        draft_notice_exists = False
        if notifications is not None:
            try:
                draft_notice_exists = notifications.filter(
                    status=get_draft_notice_status_value()
                ).exists()
            except Exception:
                draft_notice_exists = False

        entry = _build_operational_queue_entry(
            loan,
            settlement=settlement,
            policy=policy,
            draft_notice_exists=draft_notice_exists,
        )

        mark_overdue = getattr(flow, "mark_overdue", None)
        mark_npa = getattr(flow, "mark_npa", None)
        cure_to_current = getattr(flow, "cure_to_current", None)

        if (
            getattr(loan, "status", None) == CANONICAL_ACTIVE_CURRENT
            and policy.maturity_date == today
            and settlement.total_outstanding > Decimal("0.00")
        ):
            due_today.append(entry)

        if mark_overdue and mark_overdue.can_proceed() and policy.is_overdue:
            overdue_entry = dict(entry)
            overdue_entry["action_url"] = _queue_transition_url(loan, "mark_overdue")
            overdue_entry["action_label"] = "Mark Overdue"
            overdue_candidates.append(overdue_entry)

        if mark_npa and mark_npa.can_proceed() and policy.is_npa:
            npa_entry = dict(entry)
            npa_entry["action_url"] = _queue_transition_url(loan, "mark_npa")
            npa_entry["action_label"] = "Mark NPA"
            npa_candidates.append(npa_entry)

        if cure_to_current and cure_to_current.can_proceed():
            cure_entry = dict(entry)
            cure_entry["action_url"] = _queue_transition_url(loan, "cure_to_current")
            cure_entry["action_label"] = "Cure to Current"
            cure_candidates.append(cure_entry)

        if (
            getattr(loan, "status", None)
            in (CANONICAL_ACTIVE_OVERDUE, CANONICAL_ACTIVE_NPA)
            and not draft_notice_exists
        ):
            notice_entry = dict(entry)
            notice_entry["action_url"] = reverse("girvi:girvi_loan_notice", args=[loan.pk])
            notice_entry["action_label"] = "Create Notice"
            notice_candidates.append(notice_entry)

    return {
        "due_today": due_today[:limit],
        "overdue_candidates": overdue_candidates[:limit],
        "npa_candidates": npa_candidates[:limit],
        "cure_candidates": cure_candidates[:limit],
        "notice_candidates": notice_candidates[:limit],
        "counts": {
            "due_today": len(due_today),
            "overdue_candidates": len(overdue_candidates),
            "npa_candidates": len(npa_candidates),
            "cure_candidates": len(cure_candidates),
            "notice_candidates": len(notice_candidates),
        },
    }


def _should_have_disbursal_voucher(loan):
    status = canonical_status(getattr(loan, "status", ""))
    return status not in {
        CANONICAL_DRAFT,
        CANONICAL_PENDING_APPROVAL,
        CANONICAL_APPROVED,
        CANONICAL_REJECTED,
        CANONICAL_CANCELLED,
    }


def _is_release_payment(payment):
    if getattr(payment, "create_release", False):
        return True
    marker = str(getattr(payment, "reference_number", "") or "")
    return marker.startswith("RELEASE-")


def build_loan_accounting_reconciliation_report(*, limit=200, loans=None):
    """Return loans with accounting mismatches for operational reconciliation."""
    if loans is None:
        loans = (
            GivenLoan.objects.select_related("borrower")
            .prefetch_related("payments")
            .order_by("-loan_date")[: max(limit * 4, 200)]
        )

    issue_rows = []
    issue_counts = Counter()

    for loan in loans:
        payments = list(getattr(loan, "payments", []).all()) if hasattr(getattr(loan, "payments", None), "all") else list(getattr(loan, "payments", []) or [])

        posted_disbursal = any(
            getattr(payment, "posted", False)
            and getattr(payment, "payment_type", "") == "DISBURSAL"
            and getattr(payment, "direction", "") == "PAYMENT"
            and getattr(payment, "reversal_of_id", None) is None
            for payment in payments
        )
        unposted_payments = [payment for payment in payments if not getattr(payment, "posted", False)]
        posted_release_receipt = any(
            getattr(payment, "posted", False)
            and getattr(payment, "direction", "") == "RECEIPT"
            and _is_release_payment(payment)
            and getattr(payment, "reversal_of_id", None) is None
            for payment in payments
        )

        has_release = False
        try:
            has_release = bool(getattr(loan, "release", None))
        except Exception:
            has_release = False

        base_payload = {
            "loan": loan,
            "loan_id": getattr(loan, "loan_id", ""),
            "borrower_name": getattr(getattr(loan, "borrower", None), "name", ""),
            "status": getattr(loan, "status", ""),
            "status_label": lifecycle_status_label(getattr(loan, "status", "")),
            "status_badge_class": lifecycle_status_badge_class(getattr(loan, "status", "")),
            "loan_detail_url": reverse("girvi:girvi_loan_detail", args=[loan.pk]),
        }

        if _should_have_disbursal_voucher(loan) and not posted_disbursal:
            issue_counts["missing_disbursal_voucher"] += 1
            issue_rows.append(
                {
                    **base_payload,
                    "issue_code": "missing_disbursal_voucher",
                    "issue_label": "Missing disbursal voucher",
                    "severity": "high",
                    "details": "Loan moved beyond approval but no posted disbursal voucher exists.",
                }
            )

        for payment in unposted_payments:
            issue_counts["failed_payment_posting"] += 1
            issue_rows.append(
                {
                    **base_payload,
                    "issue_code": "failed_payment_posting",
                    "issue_label": "Failed payment posting",
                    "severity": "high",
                    "details": f"Unposted payment voucher {getattr(payment, 'payment_id', payment.pk)}.",
                }
            )

        if has_release and not posted_release_receipt:
            issue_counts["release_without_voucher"] += 1
            issue_rows.append(
                {
                    **base_payload,
                    "issue_code": "release_without_voucher",
                    "issue_label": "Release without voucher",
                    "severity": "high",
                    "details": "Release document exists but posted release receipt voucher is missing.",
                }
            )

        if posted_disbursal and not _should_have_disbursal_voucher(loan):
            issue_counts["posted_voucher_state_mismatch"] += 1
            issue_rows.append(
                {
                    **base_payload,
                    "issue_code": "posted_voucher_state_mismatch",
                    "issue_label": "Posted voucher state mismatch",
                    "severity": "medium",
                    "details": "Posted disbursal voucher exists while loan is in a pre-disbursal status.",
                }
            )

        if posted_release_receipt and not has_release:
            issue_counts["posted_voucher_state_mismatch"] += 1
            issue_rows.append(
                {
                    **base_payload,
                    "issue_code": "posted_voucher_state_mismatch",
                    "issue_label": "Posted voucher state mismatch",
                    "severity": "medium",
                    "details": "Posted release receipt exists but no release document is linked to this loan.",
                }
            )

    return {
        "rows": issue_rows[:limit],
        "counts": {
            "missing_disbursal_voucher": issue_counts["missing_disbursal_voucher"],
            "failed_payment_posting": issue_counts["failed_payment_posting"],
            "release_without_voucher": issue_counts["release_without_voucher"],
            "posted_voucher_state_mismatch": issue_counts["posted_voucher_state_mismatch"],
        },
        "total_issues": sum(issue_counts.values()),
        "generated_at": timezone.now(),
        "scanned_loans": len(loans),
    }


def build_loan_accounting_reconciliation_report_context(*, report=None):
    """Return template-ready context for the reconciliation report view."""
    report = report or build_loan_accounting_reconciliation_report()
    return {
        "report": report,
        "report_rows": report["rows"],
        "report_counts": report["counts"],
    }


def _aging_bucket_label(days_overdue):
    if days_overdue <= 0:
        return "current"
    if days_overdue <= 30:
        return "1-30"
    if days_overdue <= 60:
        return "31-60"
    if days_overdue <= 90:
        return "61-90"
    return "90+"


def build_operational_controls_report(*, limit=200, loans=None, as_of_date=None):
    """Return essential operational control reports for MVP monitoring."""
    from apps.tenant_apps.girvi.models.custody_tracking import ItemCustodyStatus
    from apps.tenant_apps.girvi.service_modules.overdue_policy import evaluate_overdue_policy
    from apps.tenant_apps.girvi.services import RateCacheService

    if loans is None:
        loans = (
            GivenLoan.objects.select_related("borrower")
            .prefetch_related("loanitems")
            .order_by("-loan_date")[: max(limit * 3, 300)]
        )

    aging_rows = []
    custody_rows = []
    release_ready_rows = []
    rate_exception_rows = []
    aging_buckets = Counter()
    today = as_of_date or timezone.localdate()

    for loan in loans:
        try:
            settlement = build_loan_settlement_balance(loan)
        except Exception:
            continue

        try:
            policy = evaluate_overdue_policy(loan, as_of_date=today)
            maturity_date = policy.maturity_date
        except Exception:
            maturity_date = None

        days_overdue = 0
        if maturity_date and settlement.total_outstanding > Decimal("0.00"):
            days_overdue = max((today - maturity_date).days, 0)
        aging_bucket = _aging_bucket_label(days_overdue)
        aging_buckets[aging_bucket] += 1
        aging_rows.append(
            {
                "loan": loan,
                "loan_id": getattr(loan, "loan_id", ""),
                "borrower_name": getattr(getattr(loan, "borrower", None), "name", ""),
                "maturity_date": maturity_date,
                "days_overdue": days_overdue,
                "bucket": aging_bucket,
                "outstanding": settlement.total_outstanding,
                "detail_url": reverse("girvi:girvi_loan_detail", args=[loan.pk]),
            }
        )

        items_relation = getattr(loan, "loanitems", None)
        if items_relation is not None:
            in_vault = items_relation.filter(custody_status=ItemCustodyStatus.IN_VAULT).count()
            with_lender = items_relation.filter(custody_status=ItemCustodyStatus.WITH_LENDER).count()
            with_customer = items_relation.filter(custody_status=ItemCustodyStatus.WITH_CUSTOMER).count()
            total_items = in_vault + with_lender + with_customer
            custody_rows.append(
                {
                    "loan": loan,
                    "loan_id": getattr(loan, "loan_id", ""),
                    "borrower_name": getattr(getattr(loan, "borrower", None), "name", ""),
                    "in_vault": in_vault,
                    "with_lender": with_lender,
                    "with_customer": with_customer,
                    "total_items": total_items,
                    "detail_url": reverse("girvi:girvi_loan_detail", args=[loan.pk]),
                }
            )

            can_release = (
                settlement.total_outstanding <= Decimal("0.00")
                and with_lender == 0
                and not getattr(loan, "is_released", False)
            )
            release_ready_rows.append(
                {
                    "loan": loan,
                    "loan_id": getattr(loan, "loan_id", ""),
                    "borrower_name": getattr(getattr(loan, "borrower", None), "name", ""),
                    "outstanding": settlement.total_outstanding,
                    "with_lender": with_lender,
                    "can_release": can_release,
                    "detail_url": reverse("girvi:girvi_loan_detail", args=[loan.pk]),
                }
            )

            for item in items_relation.all():
                market_rate = RateCacheService.get_rate_or_none(getattr(item, "itemtype", ""))
                interest_rate = _as_decimal(getattr(item, "interestrate", Decimal("0.00")))
                if market_rate is None or interest_rate <= Decimal("0.00"):
                    rate_exception_rows.append(
                        {
                            "loan": loan,
                            "loan_id": getattr(loan, "loan_id", ""),
                            "item_id": getattr(item, "pk", None),
                            "item_type": getattr(item, "itemtype", ""),
                            "item_desc": getattr(item, "itemdesc", ""),
                            "configured_interest_rate": interest_rate,
                            "market_rate": market_rate,
                            "issue": "missing_market_rate" if market_rate is None else "invalid_interest_rate",
                            "detail_url": reverse("girvi:girvi_loan_detail", args=[loan.pk]),
                        }
                    )

    aging_rows.sort(key=lambda row: row["days_overdue"], reverse=True)
    custody_rows.sort(key=lambda row: row["with_lender"], reverse=True)
    release_ready_rows.sort(
        key=lambda row: (row["can_release"], -_as_decimal(row["outstanding"])),
        reverse=True,
    )

    return {
        "aging": {
            "rows": aging_rows[:limit],
            "bucket_counts": {
                "current": aging_buckets["current"],
                "b1_30": aging_buckets["1-30"],
                "b31_60": aging_buckets["31-60"],
                "b61_90": aging_buckets["61-90"],
                "b90_plus": aging_buckets["90+"],
            },
        },
        "custody": {
            "rows": custody_rows[:limit],
        },
        "release_ready": {
            "rows": release_ready_rows[:limit],
            "ready_count": sum(1 for row in release_ready_rows if row["can_release"]),
        },
        "rate_exceptions": {
            "rows": rate_exception_rows[:limit],
            "total": len(rate_exception_rows),
        },
        "generated_at": timezone.now(),
        "scanned_loans": len(loans),
    }


def build_operational_controls_report_context(*, report=None):
    """Return template-ready context for operational controls report views."""
    report = report or build_operational_controls_report()
    return {
        "report": report,
        "aging_rows": report["aging"]["rows"],
        "aging_bucket_counts": report["aging"]["bucket_counts"],
        "custody_rows": report["custody"]["rows"],
        "release_ready_rows": report["release_ready"]["rows"],
        "release_ready_count": report["release_ready"]["ready_count"],
        "rate_exception_rows": report["rate_exceptions"]["rows"],
        "rate_exception_total": report["rate_exceptions"]["total"],
    }


def build_operations_console_read_model(*, failed_event_limit=25, audit_event_limit=20):
    """Return one consolidated read model for operations-console summary widgets."""
    from apps.tenant_apps.girvi.integrations.dea_adapter import (
        get_payment_voucher_posting_counts,
    )
    from apps.tenant_apps.girvi.services import get_rate_setup_counts
    from apps.tenant_apps.girvi.models import (
        GirviPostingOutboxEvent,
        GirviPostingOutboxStatus,
        LoanChangeLog,
        Series,
    )

    payment_counts = get_payment_voucher_posting_counts()
    outbox_counts = {
        status: GirviPostingOutboxEvent.objects.filter(status=status).count()
        for status, _label in GirviPostingOutboxStatus.choices
    }

    series_summary = {
        "total": Series.objects.count(),
        "active": Series.objects.filter(is_active=True).count(),
        "loans_locked": Series.objects.filter(deactivated_for_loans=True).count(),
        "releases_locked": Series.objects.filter(deactivated_for_releases=True).count(),
    }
    rate_summary = get_rate_setup_counts()

    failed_events = GirviPostingOutboxEvent.objects.filter(
        status__in=[
            GirviPostingOutboxStatus.FAILED,
            GirviPostingOutboxStatus.DEAD_LETTER,
        ]
    ).order_by("-updated_at")[:failed_event_limit]
    recent_audit_events = LoanChangeLog.objects.select_related("author").order_by(
        "-changed"
    )[:audit_event_limit]

    return {
        "payment_counts": payment_counts,
        "outbox_counts": outbox_counts,
        "series_summary": series_summary,
        "rate_summary": rate_summary,
        "failed_events": failed_events,
        "recent_audit_events": recent_audit_events,
    }


def build_repledge_history_read_model(
    *,
    status=None,
    customer_id=None,
    lender_id=None,
    limit=100,
):
    """Build selector payload for repledge history report with optional filters."""
    from apps.tenant_apps.girvi.models.custody_tracking import RepledgeHistory

    history = RepledgeHistory.objects.select_related(
        "loan_item",
        "loan_item__loan",
        "loan_item__loan__borrower",
        "taken_loan",
        "taken_loan__lender",
        "repledged_by",
        "returned_by",
    )

    if status == "active":
        history = history.filter(returned_at__isnull=True)
    elif status == "returned":
        history = history.filter(returned_at__isnull=False)

    if customer_id:
        history = history.filter(loan_item__loan__borrower_id=customer_id)

    if lender_id:
        history = history.filter(taken_loan__lender_id=lender_id)

    return {
        "history": history[:limit],
        "total_active": RepledgeHistory.objects.filter(returned_at__isnull=True).count(),
        "total_returned": RepledgeHistory.objects.filter(returned_at__isnull=False).count(),
    }


def build_item_custody_status_payload(item):
    """Build JSON-safe item custody payload for API endpoints."""
    return {
        "item_id": item.id,
        "custody_status": item.custody_status,
        "custody_display": item.get_custody_status_display(),
        "is_repledged": item.is_repledged,
        "repledged_to": {
            "id": item.repledged_to.id,
            "loan_id": item.repledged_to.loan_id,
            "lender": item.repledged_to.lender.name,
        }
        if item.repledged_to
        else None,
        "can_release": item.is_available_for_release,
        "can_repledge": item.is_available_for_repledge,
        "can_return": item.can_be_returned_from_lender,
    }


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


def _decimal_round(value):
    return _as_decimal(value).quantize(Decimal("0.01"))


def _sum_payment_component(loan, *, direction, field_name):
    payments_relation = getattr(loan, "payments", None)
    if payments_relation is None or not getattr(loan, "pk", None):
        return Decimal("0.00")

    try:
        queryset = payments_relation.filter(direction=direction)
        total = queryset.aggregate(total=Sum(field_name))["total"]
        return _decimal_round(total)
    except Exception:
        return Decimal("0.00")


def build_loan_settlement_balance(loan, *, loan_kind="given", as_of_date=None):
    """
    Return one canonical money split for repayment, release, closure, and UI reads.

    The calculation prefers voucher component fields because total receipts can
    include both principal and interest. Legacy helper methods remain as a
    fallback for old rows and lightweight tests.
    """
    loan_amount_attr = getattr(loan, "get_loan_amount", None)
    has_loan_amount = loan_amount_attr is not None
    explicit_attrs = vars(loan) if hasattr(loan, "__dict__") else {}
    outstanding_interest = explicit_attrs.get("outstanding_interest")
    if outstanding_interest is not None:
        interest_due = _decimal_round(outstanding_interest)
    else:
        interest_due_getter = getattr(loan, "interest_outstanding", None)
        if callable(interest_due_getter):
            interest_due = _decimal_round(interest_due_getter(as_of_date))
        else:
            outstanding_interest = getattr(loan, "outstanding_interest", None)
            if outstanding_interest is not None:
                interest_due = _decimal_round(outstanding_interest)
            else:
                interest_due_attr = getattr(loan, "interest_due", None)
                if callable(interest_due_attr):
                    interest_due = _decimal_round(interest_due_attr(as_of_date))
                else:
                    interest_due = _decimal_round(interest_due_attr)

    payment_direction = "PAYMENT" if loan_kind == "taken" else "RECEIPT"
    principal_paid = _sum_payment_component(
        loan, direction=payment_direction, field_name="principal_amount"
    )
    interest_paid = _sum_payment_component(
        loan, direction=payment_direction, field_name="interest_amount"
    )
    total_paid = _sum_payment_component(
        loan, direction=payment_direction, field_name="amount_in_base_currency"
    )

    if principal_paid == Decimal("0.00"):
        principal_getter = getattr(loan, "get_total_principal_payments", None)
        if callable(principal_getter):
            principal_paid = _decimal_round(principal_getter())
    if interest_paid == Decimal("0.00"):
        interest_getter = getattr(loan, "get_total_interest_payments", None)
        if callable(interest_getter):
            interest_paid = _decimal_round(interest_getter())
    if total_paid == Decimal("0.00"):
        total_getter = getattr(loan, "get_total_payments", None)
        if callable(total_getter):
            total_paid = _decimal_round(total_getter())
        else:
            total_attr = getattr(loan, "total_paid", None)
            total_paid = _decimal_round(total_attr)

    total_due_attr = getattr(loan, "total_due", None)
    if callable(total_due_attr):
        total_due_attr = total_due_attr()
    legacy_total_due = _decimal_round(total_due_attr)

    principal_base = _decimal_round(loan_amount_attr) if has_loan_amount else Decimal("0.00")
    if not has_loan_amount and legacy_total_due > 0:
        principal_base = max(legacy_total_due - interest_due, Decimal("0.00"))

    principal_outstanding = max(principal_base - principal_paid, Decimal("0.00"))
    total_due = principal_base + interest_due
    if not has_loan_amount and legacy_total_due > 0:
        total_due = legacy_total_due
    component_outstanding = principal_outstanding + interest_due
    total_outstanding = max(total_due - total_paid, Decimal("0.00"))
    if principal_paid or interest_paid:
        total_outstanding = max(component_outstanding, Decimal("0.00"))
    overpayment = max(total_paid - total_due, Decimal("0.00"))

    return LoanSettlementBalance(
        principal_due=principal_outstanding,
        interest_due=interest_due,
        principal_paid=principal_paid,
        interest_paid=interest_paid,
        total_paid=total_paid,
        total_due=total_due,
        total_outstanding=total_outstanding,
        overpayment=overpayment,
    )


def build_repayment_preview(loan, *, loan_kind="given", as_of_date=None):
    settlement = build_loan_settlement_balance(
        loan,
        loan_kind=loan_kind,
        as_of_date=as_of_date,
    )
    suggested_interest = min(settlement.interest_due, settlement.total_outstanding)
    suggested_principal = max(
        settlement.total_outstanding - suggested_interest,
        Decimal("0.00"),
    )
    return RepaymentPreview(
        settlement=settlement,
        suggested_total_amount=settlement.total_outstanding,
        suggested_interest_amount=suggested_interest,
        suggested_principal_amount=suggested_principal,
        is_settled=settlement.total_outstanding <= Decimal("0.00"),
    )


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

    settlement = build_loan_settlement_balance(loan)
    outstanding_amount = _non_negative_amount(settlement.total_outstanding)
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


def _first_enabled_action(actions):
    for action in actions or []:
        if not action.get("disabled"):
            return action
    return None


def build_given_loan_action_readiness(
    loan,
    *,
    transition_actions=None,
    release_action=None,
    changelog=None,
):
    """Build the loan-detail next-action summary without owning transition rules."""
    settlement = build_loan_settlement_balance(loan)
    current_value = _as_decimal(getattr(loan, "current_value", Decimal("0.00")))
    total_due = _as_decimal(settlement.total_due)
    collateral_margin = current_value - total_due
    accounting_status = None
    journal_count = 0
    try:
        from apps.tenant_apps.girvi.integrations.dea_adapter import get_source_posting_status

        accounting_status = get_source_posting_status(loan)
    except Exception:
        try:
            journal_count = get_given_loan_journal_entries(loan).count()
        except Exception:
            journal_count = 0
        accounting_status = {
            "label": "Posted" if journal_count > 0 else "No posted journal",
            "badge_class": "bg-success" if journal_count > 0 else "bg-secondary",
            "posted_payment_count": journal_count,
            "pending_payment_count": 0,
            "failed_outbox_count": 0,
            "pending_outbox_count": 0,
        }

    enabled_release = release_action if release_action and not release_action.get("disabled") else None
    enabled_transition = _first_enabled_action(transition_actions)
    blocked_release = release_action if release_action and release_action.get("disabled") else None

    if enabled_release:
        primary_action = enabled_release
        primary_reason = "Settlement is clear enough to start collateral release."
    elif enabled_transition:
        primary_action = enabled_transition
        primary_reason = "This is the next valid lifecycle action for the current state."
    elif blocked_release:
        primary_action = blocked_release
        primary_reason = "Release is blocked until outstanding dues are settled."
    else:
        primary_action = None
        primary_reason = "No staff action is currently available from this state."

    return {
        "primary_action": primary_action,
        "primary_reason": primary_reason,
        "settlement": {
            "label": "Clear" if settlement.total_outstanding <= Decimal("0.00") else "Outstanding",
            "badge_class": "bg-success" if settlement.total_outstanding <= Decimal("0.00") else "bg-warning text-dark",
            "amount": settlement.total_outstanding,
        },
        "collateral": {
            "label": "Adequate" if collateral_margin >= Decimal("0.00") else "Undersecured",
            "badge_class": "bg-success" if collateral_margin >= Decimal("0.00") else "bg-danger",
            "current_value": current_value,
            "margin": collateral_margin,
        },
        "accounting": accounting_status,
        "timeline": {
            "event_count": len(changelog) if isinstance(changelog, list) else getattr(changelog, "count", lambda: 0)(),
        },
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

    settlement = build_loan_settlement_balance(loan)
    due = settlement.total_due
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
    settlement = build_loan_settlement_balance(loan)

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
            "interest_due": settlement.interest_due,
            "total_due": settlement.total_due,
            "outstanding_principal": settlement.principal_due,
            "total_outstanding": settlement.total_outstanding,
            "overpayment": settlement.overpayment,
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


def loan_interest_due(loan, as_of_date=None):
    """Compute interest due using the shared interest policy service."""
    from apps.tenant_apps.girvi.services import InterestCalculationService

    return InterestCalculationService.interest_due(
        loan.get_interest_amount,
        loan.loan_date,
        as_of_date,
    )


def loan_total_receipt_payments(loan):
    """Sum all receipt-side loan payments across voucher and legacy relations."""
    if getattr(loan, "pk", None):
        payments_relation = getattr(loan, "payments", None)
        if payments_relation is not None:
            try:
                total = payments_relation.filter(direction="RECEIPT").aggregate(
                    total=Sum("amount_in_base_currency")
                )["total"]
                if hasattr(total, "amount"):
                    return Decimal(str(total.amount))
                if total not in (None, ""):
                    return Decimal(str(total))
            except Exception:
                pass

    loan_payments = getattr(loan, "loan_payments", None)
    if loan_payments is None:
        return Decimal(0)
    return loan_payments.aggregate(Sum("payment_amount"))["payment_amount__sum"] or Decimal(0)


def loan_total_principal_payments(loan):
    """Sum principal receipts across voucher and legacy loan payment relations."""
    if getattr(loan, "pk", None):
        payments_relation = getattr(loan, "payments", None)
        if payments_relation is not None:
            try:
                total = payments_relation.filter(direction="RECEIPT").aggregate(
                    total_principal=Sum("principal_amount")
                )["total_principal"]
                if hasattr(total, "amount"):
                    return Decimal(str(total.amount))
                if total not in (None, ""):
                    return Decimal(str(total))
            except Exception:
                pass

    loan_payments = getattr(loan, "loan_payments", None)
    if loan_payments is None:
        return Decimal(0)
    return loan_payments.aggregate(Sum("principal_payment"))["principal_payment__sum"] or Decimal(0)


def loan_total_interest_payments(loan):
    """Sum interest receipts across voucher and legacy loan payment relations."""
    if getattr(loan, "pk", None):
        payments_relation = getattr(loan, "payments", None)
        if payments_relation is not None:
            try:
                total = payments_relation.filter(direction="RECEIPT").aggregate(
                    total_interest=Sum("interest_amount")
                )["total_interest"]
                if hasattr(total, "amount"):
                    return Decimal(str(total.amount))
                if total not in (None, ""):
                    return Decimal(str(total))
            except Exception:
                pass

    loan_payments = getattr(loan, "loan_payments", None)
    if loan_payments is None:
        return Decimal(0)
    return loan_payments.aggregate(Sum("interest_payment"))["interest_payment__sum"] or Decimal(0)


def loan_interest_accrued_gross(loan, as_of_date=None):
    """Compute gross accrued interest, preferring posted accrual rows when available."""
    if not getattr(loan, "pk", None):
        return round(loan_interest_due(loan, as_of_date), 2)

    accruals = getattr(loan, "interest_accruals", None)
    if accruals is None:
        return round(loan_interest_due(loan, as_of_date), 2)

    try:
        queryset = accruals.all()
        if as_of_date is not None:
            cutoff = as_of_date.date() if hasattr(as_of_date, "date") else as_of_date
            queryset = queryset.filter(period_end__lte=cutoff)
        total = queryset.aggregate(total=Sum("accrued_amount"))["total"] or Decimal(0)
    except Exception:
        total = Decimal(0)

    if total == 0:
        return round(loan_interest_due(loan, as_of_date), 2)
    return round(Decimal(str(total)), 2)


def loan_interest_receivable_balance(loan):
    """Compute booked interest receivable that remains unpaid."""
    if not getattr(loan, "pk", None):
        return Decimal("0.00")

    accruals = getattr(loan, "interest_accruals", None)
    if accruals is None:
        return Decimal("0.00")

    try:
        posted_total = (
            accruals.filter(status="POSTED").aggregate(total=Sum("accrued_amount"))["total"]
            or Decimal(0)
        )
    except Exception:
        posted_total = Decimal(0)

    outstanding = Decimal(str(posted_total)) - round(loan_total_interest_payments(loan), 2)
    return round(max(outstanding, Decimal("0")), 2)


def loan_last_accrual_date(loan):
    """Return last accrued period end date if accrual rows exist."""
    if not getattr(loan, "pk", None):
        return None

    accruals = getattr(loan, "interest_accruals", None)
    if accruals is None:
        return None

    try:
        return accruals.order_by("-period_end").values_list("period_end", flat=True).first()
    except Exception:
        return None


def given_loan_amount(loan):
    """Return principal amount from pledged given-loan items."""
    return loan.loanitems.aggregate(Sum("loanamount"))["loanamount__sum"] or Decimal(0)


def given_loan_interest_amount(loan):
    """Return base monthly interest amount from given-loan items."""
    return loan.loanitems.aggregate(Sum("interest"))["interest__sum"] or Decimal(0)


def given_loan_weight_summary(loan):
    """Return weight summary grouped by item metal type for given loans."""
    return loan.loanitems.values("itemtype").annotate(
        total_weight=Sum("weight"),
        pure_weight=Sum(
            Func(
                ExpressionWrapper(
                    F("weight") * F("purity") / 100,
                    output_field=DecimalField(max_digits=10, decimal_places=3),
                ),
                function="ROUND",
                template="%(function)s(%(expressions)s, 3)",
            )
        ),
    )


def given_loan_item_description(loan):
    """Return comma-separated pledged item descriptions for a given loan."""
    return ", ".join(loan.loanitems.values_list("itemdesc", flat=True))


def given_loan_current_value(loan):
    """Return current collateral market value for all given-loan items."""
    return sum(item.current_value() for item in loan.loanitems.all())


def taken_loan_amount(loan):
    """Return principal from taken-loan repledge history rows."""
    return loan.repledge_history_items.aggregate(Sum("repledged_amount"))["repledged_amount__sum"] or Decimal(0)


def taken_loan_interest_amount(loan):
    """Return base monthly interest amount from taken-loan repledged rows."""
    interest_expression = ExpressionWrapper(
        F("repledged_amount") * F("loan_item__interestrate") / Value(100),
        output_field=DecimalField(max_digits=15, decimal_places=2),
    )
    return (
        loan.repledge_history_items.aggregate(
            interest=Coalesce(
                Sum(interest_expression),
                Value(0),
                output_field=DecimalField(max_digits=15, decimal_places=2),
            )
        )["interest"]
        or Decimal(0)
    )


def taken_loan_weight_summary(loan):
    """Return weight summary grouped by item metal type for taken loans."""
    return loan.repledge_history_items.values(itemtype=F("loan_item__itemtype")).annotate(
        total_weight=Sum("loan_item__weight"),
        pure_weight=Sum(
            Func(
                ExpressionWrapper(
                    F("loan_item__weight") * F("loan_item__purity") / 100,
                    output_field=DecimalField(max_digits=10, decimal_places=3),
                ),
                function="ROUND",
                template="%(function)s(%(expressions)s, 3)",
            )
        ),
    )


def taken_loan_item_description(loan):
    """Return comma-separated repledged item descriptions for a taken loan."""
    return ", ".join(
        loan.repledge_history_items.select_related("loan_item").values_list(
            "loan_item__itemdesc", flat=True
        )
    )


def taken_loan_current_value(loan):
    """Return current collateral market value for taken-loan history rows."""
    return sum(
        history.loan_item.current_value()
        for history in loan.repledge_history_items.select_related("loan_item__item").all()
    )


def get_statement_missing_loans(statement):
    """Return the missing-loan queryset for a verification statement."""
    verified_loans = statement.statementitem_set.values_list("loan_id", flat=True)
    if statement.is_complete:
        return GivenLoan.objects.unreleased().exclude(id__in=verified_loans)
    return GivenLoan.objects.filter(
        statementitem__statement=statement,
        statementitem__descrepancy_type="MISSING",
    )


def get_statement_released_items_present(statement):
    """Return statement items where collateral is present for already-released loans."""
    return statement.statementitem_set.filter(
        loan__release__isnull=False,
        descrepancy_found=True,
        descrepancy_note="Loan already released",
    )


def build_statement_verification_summary(statement):
    """Return verification summary payload for statement completion/reporting surfaces."""
    missing_loans = get_statement_missing_loans(statement)
    released_present = get_statement_released_items_present(statement)
    return {
        "total_verified": statement.statementitem_set.count(),
        "missing_loans": list(missing_loans),
        "released_present": list(released_present),
        "missing_count": missing_loans.count(),
        "released_present_count": released_present.count(),
    }


def build_statement_detail_read_model(statement):
    """Build detail-page read model for statement verification screens."""
    statement_items = statement.statementitem_set.select_related("loan").all()
    summary = {}
    if statement.completed:
        summary = {
            "dc": statement_items.filter(descrepancy_found=True),
            "descrepancy_loans": statement.statementitem_set.aggregate(
                total=Count("pk"),
                discrepancy=Count("pk", filter=Q(descrepancy_found=True)),
            ),
            "missing_loans": GivenLoan.objects.filter(release__isnull=True).exclude(
                loan_id__in=statement_items.values_list("loan__loan_id", flat=True)
            ),
            "unreleased": GivenLoan.objects.filter(release__isnull=True),
        }

    return {
        "statement": statement,
        "items": statement_items,
        "summary": summary,
    }
