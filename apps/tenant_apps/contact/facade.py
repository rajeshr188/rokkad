"""Contact public facade for other tenant apps."""

from apps.tenant_apps.contact.models import Customer


def customer_queryset():
    """Return the canonical Customer queryset for forms, filters, and selectors."""
    return Customer.objects.all()


__all__ = [
    "customer_queryset",
]
