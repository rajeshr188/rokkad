"""Girvi public facade for other tenant apps."""

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import Exists, OuterRef


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GirviLoanCoexistenceRow:
    """Stable legacy-loan read contract for side-by-side portfolio consumers."""

    source_id: int
    source_key: str
    loan_kind: str
    loan_number: str
    loan_date: date
    party_id: int | None
    party_name: str
    stored_status: str
    lifecycle_status: str
    lifecycle_bucket: str
    original_principal: Decimal
    principal_outstanding: Decimal
    interest_outstanding: Decimal
    total_due: Decimal
    collateral_count: int
    custody_summary: str
    owner_action_name: str
    owner_action_url: str
    financial_data_available: bool
    release_status: str = "NONE"
    dea_visibility: str = "NOT_VISIBLE"
    read_error: str = ""
    source_system: str = "GIRVI"
    source_label: str = "Girvi"
    owner_app: str = "girvi"


def get_loan_coexistence_rows(*, as_of_date: date) -> tuple[GirviLoanCoexistenceRow, ...]:
    """Return source-owned Given/Taken loan rows without exposing Girvi models."""
    from apps.tenant_apps.girvi import lifecycle
    from apps.tenant_apps.girvi.models import GivenLoan, TakenLoan
    from apps.tenant_apps.girvi.selectors import build_loan_settlement_balance

    given_loans = (
        GivenLoan.objects.select_related(
            "borrower", "borrower_party", "series", "release"
        )
        .prefetch_related("loanitems", "payments")
        .order_by("loan_date", "pk")
    )
    taken_loans = (
        TakenLoan.objects.select_related("lender", "lender_party", "series")
        .prefetch_related("repledge_history_items", "payments")
        .order_by("loan_date", "pk")
    )
    rows = [
        _build_coexistence_row(
            loan,
            loan_kind="PAWN",
            party=getattr(loan, "borrower_party", None),
            legacy_party=getattr(loan, "borrower", None),
            normalized_status=lifecycle.canonical_status(loan.status),
            lifecycle_bucket=_given_lifecycle_bucket(loan.status, lifecycle),
            collateral=tuple(loan.loanitems.all()),
            owner_action_name="girvi:girvi_loan_detail",
            as_of_date=as_of_date,
            settlement_builder=build_loan_settlement_balance,
        )
        for loan in given_loans
    ]
    rows.extend(
        _build_coexistence_row(
            loan,
            loan_kind="FUNDING",
            party=getattr(loan, "lender_party", None),
            legacy_party=getattr(loan, "lender", None),
            normalized_status=lifecycle.taken_canonical_status(loan.status),
            lifecycle_bucket=_taken_lifecycle_bucket(loan.status, lifecycle),
            collateral=tuple(loan.repledge_history_items.all()),
            owner_action_name="girvi:taken_loan_collateral_detail",
            as_of_date=as_of_date,
            settlement_builder=build_loan_settlement_balance,
        )
        for loan in taken_loans
    )
    return tuple(rows)


def _build_coexistence_row(
    loan,
    *,
    loan_kind,
    party,
    legacy_party,
    normalized_status,
    lifecycle_bucket,
    collateral,
    owner_action_name,
    as_of_date,
    settlement_builder,
):
    read_error = ""
    financial_data_available = True
    try:
        settlement = settlement_builder(
            loan,
            loan_kind="taken" if loan_kind == "FUNDING" else "given",
            as_of_date=as_of_date,
        )
        original_principal = Decimal(str(loan.get_loan_amount))
        principal_outstanding = Decimal(str(settlement.principal_due))
        interest_outstanding = Decimal(str(settlement.interest_due))
        total_due = Decimal(str(settlement.total_outstanding))
    except Exception as exc:
        logger.exception("Unable to build coexistence totals for Girvi loan %s", loan.pk)
        original_principal = Decimal("0")
        principal_outstanding = Decimal("0")
        interest_outstanding = Decimal("0")
        total_due = Decimal("0")
        financial_data_available = False
        read_error = str(exc) or "Girvi financial data is unavailable."

    identity = party or legacy_party
    party_name = getattr(identity, "display_name", None) or getattr(
        identity, "name", ""
    )
    loan_date = loan.loan_date.date() if hasattr(loan.loan_date, "date") else loan.loan_date
    custody_summary = _girvi_custody_summary(collateral, loan_kind=loan_kind)
    release_status = _girvi_release_status(
        loan,
        loan_kind=loan_kind,
        collateral=collateral,
    )
    return GirviLoanCoexistenceRow(
        source_id=loan.pk,
        source_key=f"GIRVI:{loan_kind}:{loan.pk}",
        loan_kind=loan_kind,
        loan_number=loan.loan_id,
        loan_date=loan_date,
        party_id=getattr(party, "pk", None),
        party_name=str(party_name or ""),
        stored_status=str(loan.status),
        lifecycle_status=str(normalized_status or loan.status),
        lifecycle_bucket=lifecycle_bucket,
        original_principal=original_principal,
        principal_outstanding=principal_outstanding,
        interest_outstanding=interest_outstanding,
        total_due=total_due,
        collateral_count=len(collateral),
        custody_summary=custody_summary,
        owner_action_name=owner_action_name,
        owner_action_url=loan.get_absolute_url(),
        financial_data_available=financial_data_available,
        release_status=release_status,
        dea_visibility=_girvi_dea_visibility(loan, loan_kind=loan_kind),
        read_error=read_error,
    )


def _given_lifecycle_bucket(status, lifecycle):
    normalized = lifecycle.canonical_status(status)
    if normalized in {
        lifecycle.CANONICAL_ACTIVE_CURRENT,
        lifecycle.CANONICAL_ACTIVE_OVERDUE,
        lifecycle.CANONICAL_ACTIVE_NPA,
        lifecycle.CANONICAL_CLOSURE_PENDING,
        lifecycle.CANONICAL_RENEWAL_PENDING,
        lifecycle.CANONICAL_AUCTION_INITIATED,
        lifecycle.CANONICAL_AUCTION_IN_PROGRESS,
    }:
        return "ACTIVE"
    if normalized in {
        lifecycle.CANONICAL_CLOSED,
        lifecycle.CANONICAL_RENEWED,
        lifecycle.CANONICAL_WRITTEN_OFF,
        lifecycle.CANONICAL_AUCTION_COMPLETE,
    }:
        return "CLOSED"
    if normalized in {lifecycle.CANONICAL_CANCELLED, lifecycle.CANONICAL_REJECTED}:
        return "CANCELLED"
    return "PENDING"


def _taken_lifecycle_bucket(status, lifecycle):
    normalized = lifecycle.taken_canonical_status(status)
    if normalized in {lifecycle.TAKEN_ACTIVE, lifecycle.TAKEN_SETTLEMENT_PENDING}:
        return "ACTIVE"
    if normalized == lifecycle.TAKEN_CLOSED:
        return "CLOSED"
    if normalized == lifecycle.TAKEN_CANCELLED:
        return "CANCELLED"
    return "PENDING"


def _girvi_custody_summary(collateral, *, loan_kind):
    if not collateral:
        return "No collateral"
    if loan_kind == "FUNDING":
        active = sum(getattr(item, "returned_at", None) is None for item in collateral)
        return f"{active} with lender / {len(collateral) - active} returned"
    counts = {"in_vault": 0, "with_lender": 0, "with_customer": 0}
    for item in collateral:
        state = getattr(item, "custody_status", "")
        if state in counts:
            counts[state] += 1
    return (
        f"{counts['in_vault']} vault / {counts['with_lender']} lender / "
        f"{counts['with_customer']} customer"
    )


def _girvi_release_status(loan, *, loan_kind, collateral):
    if loan_kind == "FUNDING":
        returned = sum(getattr(item, "returned_at", None) is not None for item in collateral)
        if collateral and returned == len(collateral):
            return "FULL"
        if returned:
            return "PARTIAL"
        return "NONE"
    if hasattr(loan, "release"):
        return "FULL"
    returned = sum(
        getattr(item, "custody_status", "") == "with_customer" for item in collateral
    )
    return "PARTIAL" if returned else "NONE"


def _girvi_dea_visibility(loan, *, loan_kind):
    if loan_kind != "PAWN":
        return "NOT_SUPPORTED"
    try:
        from apps.tenant_apps.girvi.selectors import get_given_loan_journal_entries

        return "VISIBLE" if get_given_loan_journal_entries(loan).exists() else "NOT_VISIBLE"
    except Exception:
        logger.exception("Unable to inspect Girvi DEA visibility for loan %s", loan.pk)
        return "UNAVAILABLE"


def count_customers_with_active_given_loans(customer_queryset) -> int:
    """
    Return how many customers in customer_queryset have active GivenLoan records.

    Other apps should use this instead of importing Girvi loan models directly.
    """
    from apps.tenant_apps.girvi.models import GivenLoan

    return (
        customer_queryset.annotate(
            has_active_loan=Exists(
                GivenLoan.objects.unreleased().filter(borrower=OuterRef("pk"))
            )
        )
        .filter(has_active_loan=True)
        .distinct()
        .count()
    )


def count_unreleased_given_loans() -> int:
    """Return the number of GivenLoan records that are not released."""
    from apps.tenant_apps.girvi.models import GivenLoan

    return GivenLoan.objects.unreleased().count()


def get_workspace_loan_dashboard_summary():
    """Return Girvi dashboard metrics needed by the workspace dashboard."""
    from datetime import date

    from django.db.models import Count, Exists, OuterRef, Sum

    from apps.tenant_apps.contact.models import Customer
    from apps.tenant_apps.girvi.models import GivenLoan, License, LoanItem, Release
    from apps.tenant_apps.girvi.services import (
        get_average_loan_instance_per_day,
        get_itemtype_averages,
        get_loan_cumulative_amount,
        get_loanamount_by_itemtype,
        get_loans_by_year,
    )

    loan = GivenLoan.objects.for_table_display()
    released = loan.released()
    unreleased = loan.unreleased()
    sunken = unreleased
    today = date.today()

    due_amount_calc = LoanItem.objects.filter(loan__in=unreleased).aggregate(
        loan_amount__sum=Sum("loanamount"),
        total_interest__sum=Sum("interest"),
    )
    weight_stats = unreleased.with_metal_weights().aggregate(
        gold=Sum("gold_weight"),
        silver=Sum("silver_weight"),
        bronze=Sum("bronze_weight"),
        pure_gold=Sum("pure_gold_weight"),
        pure_silver=Sum("pure_silver_weight"),
        pure_bronze=Sum("pure_bronze_weight"),
    )
    value_stats = (
        unreleased.with_metal_weights()
        .with_current_value()
        .aggregate(total_current=Sum("total_current_value"))
    )
    itemwise_stats = (
        unreleased.with_itemwise_amounts()
        .with_current_value()
        .aggregate(
            gold=Sum("gold_value"),
            silver=Sum("silver_value"),
            bronze=Sum("bronze_value"),
        )
    )

    sunken_weight_stats = sunken.with_metal_weights().aggregate(
        gold=Sum("gold_weight"),
        silver=Sum("silver_weight"),
        bronze=Sum("bronze_weight"),
        pure_gold=Sum("pure_gold_weight"),
        pure_silver=Sum("pure_silver_weight"),
        pure_bronze=Sum("pure_bronze_weight"),
    )
    sunken_amount_calc = LoanItem.objects.filter(loan__in=sunken).aggregate(
        loan_amount__sum=Sum("loanamount"),
        total_interest__sum=Sum("interest"),
    )
    sunken_value_stats = (
        sunken.with_metal_weights()
        .with_current_value()
        .aggregate(total_current=Sum("total_current_value"))
    )
    sunken_itemwise_stats = (
        sunken.with_itemwise_amounts()
        .with_current_value()
        .aggregate(
            gold=Sum("gold_value"),
            silver=Sum("silver_value"),
            bronze=Sum("bronze_value"),
        )
    )

    try:
        loan_progress = round(released.count() / loan.count() * 100, 2)
    except ZeroDivisionError:
        loan_progress = 0.0

    today_loan = LoanItem.objects.filter(loan__loan_date__gte=today).aggregate(
        amount=Sum("loanamount"),
        interest=Sum("interest"),
    )
    today_release_loans = Release.objects.filter(
        release_date__gte=today
    ).values_list("loan_id", flat=True)
    today_release = LoanItem.objects.filter(
        loan_id__in=today_release_loans
    ).aggregate(amount=Sum("loanamount"), interest=Sum("interest"))

    return {
        "item_loanamount_avg": get_itemtype_averages(),
        "today_loan": today_loan,
        "today_release": today_release,
        "loan_count": unreleased.count(),
        "due_amount": due_amount_calc,
        "total_loan_amount": due_amount_calc.get("loan_amount__sum") or 0,
        "total_interest": due_amount_calc.get("total_interest__sum") or 0,
        "assets": unreleased.with_itemwise_amounts().total_itemwise_loanamount(),
        "loanbyitemtype": get_loanamount_by_itemtype(),
        "weight": _sum_stats(weight_stats, "gold", "silver", "bronze"),
        "pure_weight": _sum_stats(
            weight_stats,
            "pure_gold",
            "pure_silver",
            "pure_bronze",
        ),
        "current_value": value_stats.get("total_current") or 0,
        "itemwise_value": itemwise_stats,
        "total_current_value": value_stats.get("total_current") or 0,
        "sunken": {
            "loan_count": sunken.count(),
            "total_loan_amount": sunken.total_loanamount(),
            "assets": sunken.with_itemwise_amounts().total_itemwise_loanamount(),
            "weight": _sum_stats(sunken_weight_stats, "gold", "silver", "bronze"),
            "due_amount": sunken_amount_calc,
            "current_value": sunken_value_stats.get("total_current") or 0,
            "itemwise_value": sunken_itemwise_stats,
            "total_current_value": sunken_value_stats.get("total_current") or 0,
            "total_interest": sunken_amount_calc.get("total_interest__sum") or 0,
            "pure_weight": _sum_stats(
                sunken_weight_stats,
                "pure_gold",
                "pure_silver",
                "pure_bronze",
            ),
        },
        "loan_progress": loan_progress,
        "loan_data_by_year": get_loans_by_year(),
        "avg_loan_per_day": get_average_loan_instance_per_day(),
        "maxloans": (
            Customer.objects.filter(
                ~Exists(Release.objects.filter(loan__borrower=OuterRef("pk")))
            )
            .annotate(
                num_loans=Count("loans_received", distinct=True),
                sum_loans=Sum("loans_received__loanitems__loanamount"),
                tint=Sum("loans_received__loanitems__interest"),
            )
            .values("firstname", "num_loans", "sum_loans", "tint")
            .order_by("-num_loans", "sum_loans", "tint")
        ),
        "loan_cumsum": list(get_loan_cumulative_amount()),
        "license_data": [
            license.get_unreleased_loan_data() for license in License.objects.all()
        ],
    }


def _sum_stats(stats, *keys):
    return sum((stats.get(key) or 0) for key in keys)


def run_period_close_interest_accrual(*, period, user) -> list[str]:
    """
    Run Girvi interest accrual catch-up before closing an accounting period.

    Returns warning messages for any loan that could not be accrued. The caller
    decides whether those warnings should block its workflow.
    """
    from apps.tenant_apps.girvi.models import GivenLoan
    from apps.tenant_apps.girvi.service_modules.accrual import (
        InterestAccrualCommand,
        InterestAccrualService,
    )

    accrual_failures = []
    active_loans = GivenLoan.objects.unreleased()
    for loan in active_loans:
        try:
            result = InterestAccrualService.execute(
                InterestAccrualCommand(
                    loan=loan,
                    as_of_date=period.end_date,
                    trigger_source="PERIOD_CLOSE",
                    created_by=user,
                    notes=f"Period close catch-up for {period.name}",
                    post_to_accounting=True,
                )
            )
            if not result.success:
                accrual_failures.append(f"Loan {loan.loan_id}: {result.message}")
        except Exception:
            logger.exception(
                "Accrual catch-up failed for loan %s during period close %s",
                loan.pk,
                period.pk,
            )
            accrual_failures.append(
                f"Loan {getattr(loan, 'loan_id', loan.pk)}: accrual catch-up error"
            )
    return accrual_failures


def get_party_loan_history_summary(party, *, limit=20):
    """Return party-centric loan history for Party detail pages."""
    from django.db.models import Count, Q, Sum
    from django.urls import reverse

    from apps.tenant_apps.girvi.lifecycle import (
        CANONICAL_ACTIVE_CURRENT,
        CANONICAL_ACTIVE_NPA,
        CANONICAL_ACTIVE_OVERDUE,
        CANONICAL_AUCTION_COMPLETE,
        CANONICAL_CLOSED,
        CANONICAL_CLOSURE_PENDING,
        CANONICAL_RENEWAL_PENDING,
        CANONICAL_RENEWED,
        CANONICAL_WRITTEN_OFF,
        TAKEN_ACTIVE,
        TAKEN_CLOSED,
        TAKEN_SETTLEMENT_PENDING,
        canonical_status,
        taken_canonical_status,
    )
    from apps.tenant_apps.girvi.models import GivenLoan, TakenLoan
    from apps.tenant_apps.girvi.selectors import build_loan_settlement_balance

    customer = getattr(party, "legacy_customer", None)
    given_filter = Q(borrower_party=party)
    taken_filter = Q(lender_party=party)
    if customer is not None:
        given_filter = given_filter | Q(borrower=customer)
        taken_filter = taken_filter | Q(lender=customer)

    given_qs = (
        GivenLoan.objects.filter(given_filter)
        .select_related("borrower")
        .annotate(
            payment_count=Count("payments", distinct=True),
            unposted_payment_count=Count(
                "payments",
                filter=Q(payments__posted=False),
                distinct=True,
            ),
            total_payment_amount=Sum("payments__amount_in_base_currency"),
            notice_count=Count("notifications", distinct=True),
            collateral_items_count=Count("loanitems", distinct=True),
            collateral_loan_amount=Sum("loanitems__loanamount"),
        )
        .order_by("-loan_date")
    )

    taken_qs = (
        TakenLoan.objects.filter(taken_filter)
        .select_related("lender")
        .annotate(
            payment_count=Count("payments", distinct=True),
            unposted_payment_count=Count(
                "payments",
                filter=Q(payments__posted=False),
                distinct=True,
            ),
            total_payment_amount=Sum("payments__amount_in_base_currency"),
            collateral_items_count=Count("repledge_history_items", distinct=True),
            collateral_loan_amount=Sum("repledge_history_items__repledged_amount"),
        )
        .order_by("-loan_date")
    )

    def _settlement_for_given_loan(loan):
        try:
            return build_loan_settlement_balance(loan)
        except Exception:
            logger.exception(
                "Unable to build Party loan-history settlement for GivenLoan %s",
                getattr(loan, "pk", None),
            )
            return None

    def _release_document_links(loan):
        release = getattr(loan, "release", None)
        if not release:
            return []

        return [
            {
                "label": "Release",
                "url": reverse("girvi:girvi_release_detail", args=[release.pk]),
            },
            {
                "label": "Form H",
                "url": reverse("girvi:release_form_h", args=[release.pk]),
            },
        ]

    def _given_row(loan):
        settlement = _settlement_for_given_loan(loan)
        return {
            "loan": loan,
            "loan_id": loan.loan_id,
            "loan_type": "Given",
            "status": loan.status,
            "loan_date": loan.loan_date,
            "detail_url": loan.get_absolute_url(),
            "repayment_url": reverse("girvi:girvi_loanpayment_create", args=[loan.pk]),
            "payment_count": getattr(loan, "payment_count", 0) or 0,
            "unposted_payment_count": getattr(loan, "unposted_payment_count", 0) or 0,
            "total_payment_amount": getattr(loan, "total_payment_amount", 0) or 0,
            "notice_count": getattr(loan, "notice_count", 0) or 0,
            "collateral_items_count": getattr(loan, "collateral_items_count", 0) or 0,
            "collateral_loan_amount": getattr(loan, "collateral_loan_amount", 0) or 0,
            "principal_due": getattr(settlement, "principal_due", None),
            "interest_due": getattr(settlement, "interest_due", None),
            "total_outstanding": getattr(settlement, "total_outstanding", None),
            "document_links": _release_document_links(loan),
        }

    def _taken_row(loan):
        return {
            "loan": loan,
            "loan_id": loan.loan_id,
            "loan_type": "Taken",
            "status": loan.status,
            "loan_date": loan.loan_date,
            "detail_url": loan.get_absolute_url(),
            "repayment_url": reverse("girvi:takenloan_payment_create", args=[loan.pk]),
            "payment_count": getattr(loan, "payment_count", 0) or 0,
            "unposted_payment_count": getattr(loan, "unposted_payment_count", 0) or 0,
            "total_payment_amount": getattr(loan, "total_payment_amount", 0) or 0,
            "notice_count": 0,
            "collateral_items_count": getattr(loan, "collateral_items_count", 0) or 0,
            "collateral_loan_amount": getattr(loan, "collateral_loan_amount", 0) or 0,
            "principal_due": None,
            "interest_due": None,
            "total_outstanding": None,
            "document_links": [],
        }

    active_given_states = {
        CANONICAL_ACTIVE_CURRENT,
        CANONICAL_ACTIVE_OVERDUE,
        CANONICAL_ACTIVE_NPA,
        CANONICAL_CLOSURE_PENDING,
        CANONICAL_RENEWAL_PENDING,
    }
    closed_given_states = {
        CANONICAL_CLOSED,
        CANONICAL_RENEWED,
        CANONICAL_WRITTEN_OFF,
        CANONICAL_AUCTION_COMPLETE,
    }
    active_taken_states = {TAKEN_ACTIVE, TAKEN_SETTLEMENT_PENDING}
    closed_taken_states = {TAKEN_CLOSED}

    active_rows = []
    closed_rows = []

    for loan in given_qs:
        row = _given_row(loan)
        state = canonical_status(loan.status)
        if state in active_given_states:
            active_rows.append(row)
        elif state in closed_given_states:
            closed_rows.append(row)

    for loan in taken_qs:
        row = _taken_row(loan)
        state = taken_canonical_status(loan.status)
        if state in active_taken_states:
            active_rows.append(row)
        elif state in closed_taken_states:
            closed_rows.append(row)

    active_rows.sort(key=lambda item: item["loan_date"], reverse=True)
    closed_rows.sort(key=lambda item: item["loan_date"], reverse=True)

    limited_active = active_rows[:limit]
    limited_closed = closed_rows[:limit]
    all_rows = active_rows + closed_rows
    active_outstanding = sum(
        (row["total_outstanding"] or 0) for row in active_rows
    )
    total_collateral_amount = sum(
        (row["collateral_loan_amount"] or 0) for row in all_rows
    )
    return {
        "active_loans": limited_active,
        "closed_loans": limited_closed,
        "counts": {
            "active_loans": len(active_rows),
            "closed_loans": len(closed_rows),
            "payments": sum(row["payment_count"] for row in all_rows),
            "notices": sum(row["notice_count"] for row in all_rows),
            "collateral_items": sum(
                row["collateral_items_count"] for row in all_rows
            ),
            "active_outstanding": active_outstanding,
            "collateral_loan_amount": total_collateral_amount,
        },
    }


__all__ = [
    "GirviLoanCoexistenceRow",
    "count_customers_with_active_given_loans",
    "count_unreleased_given_loans",
    "get_loan_coexistence_rows",
    "get_party_loan_history_summary",
    "get_workspace_loan_dashboard_summary",
    "run_period_close_interest_accrual",
]
