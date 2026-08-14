from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Avg, Count, DecimalField, DurationField, ExpressionWrapper, F, Sum
from django.db.models.functions import ExtractYear
from django.db.models.functions import Coalesce

from .models import Customer


@dataclass(frozen=True)
class CustomerLoanSummary:
    """Read-side loan metrics for a contact backed by refactored Girvi loans."""

    customer: Customer

    @property
    def loans(self):
        return self.customer.loans_received.all().unreleased()

    @property
    def total_loan_amount(self):
        return (
            self.customer.loans_received.all()
            .unreleased()
            .aggregate(
                total=Coalesce(
                    Sum("loanitems__loanamount"),
                    Decimal("0"),
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                )
            )["total"]
            or Decimal("0")
        )

    @property
    def total_interest_due(self):
        total_int = Decimal("0")
        for loan in self.loans:
            total_int += loan.interest_due()
        return total_int

    @property
    def loans_count(self):
        return self.customer.loans_received.all().unreleased().count()

    @property
    def base_interest_due(self):
        return (
            self.customer.loans_received.all()
            .unreleased()
            .aggregate(
                total=Coalesce(
                    Sum("loanitems__interest"),
                    Decimal("0"),
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                )
            )["total"]
            or Decimal("0")
        )

    @property
    def release_average_months(self):
        average_release_time = (
            self.customer.loans_received.all()
            .released()
            .annotate(
                duration=ExpressionWrapper(
                    F("release__release_date") - F("loan_date"),
                    output_field=DurationField(),
                )
            )
            .aggregate(average=Avg("duration"))["average"]
        )

        if average_release_time is None:
            return 0

        return round(average_release_time.days / 30.44)


def get_customer_loan_summary(customer):
    return CustomerLoanSummary(customer)


def get_customers_by_year():
    # Query to get the count of customers created by year
    customer_data_by_year = (
        Customer.objects.annotate(
            year=ExtractYear("created")
        )  # Extract year from customer created_at
        .values("year")
        .annotate(total_customers=Count("id"))
        .order_by("year")
    )

    return customer_data_by_year


def get_customers_by_type():
    customer_data_by_type = Customer.objects.values(
        "customer_type"
    ).annotate(  # Group by customer type
        total_customers=Count("id")
    )
    return customer_data_by_type


def active_customers():
    # Query to get the count of customers with at least one unreleased GivenLoan.
    from apps.tenant_apps.girvi.facade import count_customers_with_active_given_loans

    return count_customers_with_active_given_loans(Customer.objects.all())
