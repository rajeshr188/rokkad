"""Girvi public facade for other tenant apps."""

import logging

from django.db.models import Exists, OuterRef


logger = logging.getLogger(__name__)


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


__all__ = [
    "count_customers_with_active_given_loans",
    "count_unreleased_given_loans",
    "get_workspace_loan_dashboard_summary",
    "run_period_close_interest_accrual",
]
