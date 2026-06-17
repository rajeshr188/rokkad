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
    "run_period_close_interest_accrual",
]
