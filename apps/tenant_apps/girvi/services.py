import re
from collections import Counter
from datetime import datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import (Avg, Case, Count, F, IntegerField, Max, OuterRef,
                              Q, Subquery, Sum, Value, When, Window)
from django.db.models.functions import Coalesce, ExtractYear, TruncDate

from .models import (Customer, License, Loan, LoanItem, LoanPayment, Release,
                     Series)


def generate_loan_id(series_id: int = None) -> str:
    # TODO: handle concurrency issues
    try:
        series = get_or_create_series(series_id)
        series_title = series.name

        with transaction.atomic():
            last_loan = Loan.objects.filter(series=series).order_by("-loan_id").first()
            sequence_number = get_next_sequence_number(last_loan, series_title)

            num_length = series.max_limit  # Adjust the padding length as needed
            new_loan_id = f"{series_title}{sequence_number:0{num_length}d}"
            return new_loan_id

    except (Series.DoesNotExist, License.DoesNotExist) as e:
        raise
    except Exception as e:
        raise


def get_or_create_series(series_id: int = None) -> Series:
    if series_id:
        return Series.objects.get(id=series_id)
    try:
        return Series.objects.latest("id")
    except Series.DoesNotExist:
        license = License.objects.first()
        if not license:
            raise License.DoesNotExist("No license found.")
        series = Series.objects.create(name="A", license=license, is_active=True)
        print(f"Series 'A' created with license '{license}'.")
        return series


def get_next_sequence_number(last_loan: Loan, series_title: str) -> int:
    if last_loan:
        last_id = last_loan.loan_id
        print(f"Last loan ID: {last_id}")
        match = re.match(rf"^{re.escape(series_title)}(\d+)$", last_id)
        if match:
            return int(match.group(1)) + 1
    return 1  # Start with 1 if no previous loan exists or no match found


def get_loan_cumulative_amount():
    loans = (
        Loan.unreleased.annotate(
            cumsum=Window(Sum("loan_amount"), order_by=F("loan_date").asc())
        )
        .values("loan_date__date", "cumsum")
        .order_by("loan_date")
    )
    return loans


def get_average_loan_instance_per_day():
    # Get the total number of distinct Loan instances
    total_loans = Loan.objects.filter(series__is_active=True).count()

    # Get the earliest and latest Loan instance
    earliest_loan = (
        Loan.objects.filter(series__is_active=True).order_by("loan_date").first()
    )
    latest_loan = (
        Loan.objects.filter(series__is_active=True).order_by("-loan_date").first()
    )

    # If there are no Loan instances, return 0
    if earliest_loan is None or latest_loan is None:
        return 0

    # Calculate the number of days between the earliest and latest Loan instance
    num_days = (latest_loan.loan_date - earliest_loan.loan_date).days + 1

    # Calculate the average number of Loan instances per day
    average_loan_instance_per_day = total_loans / num_days

    return round(average_loan_instance_per_day, 0)


def get_loan_counts_grouped():
    # Query to get the loan counts for each customer
    loan_counts = (
        Loan.objects.unreleased()
        .values("customer__id", "customer__name")  # Group by customer
        .annotate(loan_count=Count("id"))
        .order_by("loan_count")  # Count the number of loans
    )

    # Use Counter to group customers by loan count
    grouped_loan_counts = Counter(
        loan_count for loan_count in loan_counts.values_list("loan_count", flat=True)
    )
    # Convert the Counter to a list of tuples for easier iteration in the template
    grouped_loan_counts_list = list(grouped_loan_counts.items())

    return grouped_loan_counts_list


def get_loans_by_year():
    loans_by_year = (
        Loan.objects.annotate(
            year=ExtractYear("loan_date"),
            has_release=Case(
                When(release__isnull=False, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ),
        )  # Extract year from loan start_date and check if there is a release
        .values("year")
        .annotate(
            loans_count=Count("id"),  # Count all loans
            unreleased_count=Count(
                "id", filter=Q(has_release=0)
            ),  # Count loans without a release
        )
        .order_by("year")
    )
    return loans_by_year


def get_unreleased_loans_by_year():
    data = (
        Loan.objects.unreleased()
        .annotate(year=ExtractYear("loan_date"))  # Extract year from start_date
        .values("year")  # Group by year
        .annotate(release_count=Count("id"))  # Count the number of loans
        .order_by("year")
    )
    return data


def get_loanamount_by_itemtype():
    query = (
        LoanItem.objects.filter(loan__release__isnull=True, loan__loan_type="Given")
        .values("itemtype")
        .annotate(total_loan_amount=Sum("loanamount"))  # Group by loan type
    )
    return query


from decimal import Decimal

from django.db.models import (Case, Count, DecimalField, ExpressionWrapper, F,
                              Sum, Value, When)
from django.db.models.functions import Coalesce


def get_itemtype_averages():
    """Calculate average loan amount per gram for each item type."""
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
                        Q(total_weight__gt=0),  # Compare annotated field instead of Sum
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


def get_interest_paid():
    data = (
        LoanPayment.objects.annotate(year=ExtractYear("payment_date"))
        .values("year")
        .annotate(total_interest=Sum("interest_payment"))
        .order_by("year")
    )

    labels = [entry["year"] for entry in data]
    interest_paid = [float(entry["total_interest"]) for entry in data]

    return data


def notify_customer(customer: Customer):
    pass


def notify_all_customers(customer: list[Customer]):
    pass
