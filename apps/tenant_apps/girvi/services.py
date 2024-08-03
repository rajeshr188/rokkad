from collections import Counter
from datetime import datetime

from django.db.models import (Avg, Case, Count, IntegerField, Q, Sum, Value,Window,F,
                              When, Subquery, OuterRef)
from django.db.models.functions import ExtractYear, TruncDate

from .models import Customer, Loan, LoanItem, LoanPayment, Release

def get_loan_cumulative_amount():
    loans = Loan.unreleased.annotate(
            cumsum = Window(Sum('loan_amount'), order_by=F('loan_date').asc())
        ).values('loan_date__date', 'cumsum').order_by('loan_date')
    return loans


def get_average_loan_instance_per_day():
    # Get the total number of distinct Loan instances
    total_loans = Loan.objects.count()

    # Get the earliest and latest Loan instance
    earliest_loan = Loan.objects.order_by("loan_date").first()
    latest_loan = Loan.objects.order_by("-loan_date").first()

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
    query = LoanItem.objects.values("itemtype").annotate(  # Group by loan type
        total_loan_amount=Sum("loanamount")
    )
    return query


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
