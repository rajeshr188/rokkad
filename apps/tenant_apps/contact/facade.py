"""Contact public facade for cross-app read access."""


def customer_queryset():
    from apps.tenant_apps.contact.models import Customer

    return Customer.objects.select_related("party").with_contacts().active()


def get_workspace_customer_dashboard_summary():
    from django.db.models import Count

    from apps.tenant_apps.contact.models import Customer
    from apps.tenant_apps.contact.services import (
        active_customers,
        get_customers_by_type,
        get_customers_by_year,
    )

    customers = Customer.objects.all()
    return {
        "total_customers": customers.filter(active=True).count(),
        "new_customers": customers.only(
            "id",
            "firstname",
            "customer_type",
        ).prefetch_related("address")[:5],
        "customer_count": customers.values("customer_type").annotate(
            count=Count("id")
        ),
        "customer_data_by_year": get_customers_by_year(),
        "customer_data_by_type": get_customers_by_type(),
        "active_customers": active_customers(),
    }


__all__ = [
    "customer_queryset",
    "get_workspace_customer_dashboard_summary",
]
