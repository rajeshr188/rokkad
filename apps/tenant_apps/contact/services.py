from django.db.models import Count, Exists, OuterRef
from django.db.models.functions import ExtractYear

from .models import Customer


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
    # Query to get the count of customers with at least one unreleased GivenLoan
    from apps.tenant_apps.girvi.models import Release

    customers_count = (
        Customer.objects.filter(
            ~Exists(
                Release.objects.filter(loan__borrower=OuterRef("pk"))
            ),  # Without a corresponding Release
            loans_received__isnull=False,  # Customers with at least one GivenLoan (reverse relation)
        )
        .distinct()
        .count()
    )
    return customers_count
