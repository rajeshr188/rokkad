from django.db.models import Count
from django.db.models.functions import ExtractYear

from .models import Party, PartyRole


def active_parties():
    return Party.objects.filter(status=Party.PartyStatus.ACTIVE)


def parties_with_role(role_key):
    return active_parties().filter(
        roles__role_type__key=role_key,
        roles__status=PartyRole.RoleStatus.ACTIVE,
    )


def party_detail_queryset():
    return Party.objects.prefetch_related(
        "roles__role_type",
        "addresses",
        "contact_methods",
        "identifiers",
        "documents",
        "relationships_from__to_party",
        "relationships_to__from_party",
    )


def get_workspace_customer_party_dashboard_summary():
    """Return the legacy dashboard context shape from canonical Party rows."""
    from apps.tenant_apps.loans.models import PawnLoanState

    customers = parties_with_role("CUSTOMER").distinct()
    active_loan_states = {
        PawnLoanState.APPROVED.value,
        PawnLoanState.ACTIVE.value,
        PawnLoanState.DEFAULTED.value,
    }
    return {
        "total_customers": customers.count(),
        "new_customers": customers.order_by("-created_at")[:5],
        "customer_count": customers.values("party_type").annotate(count=Count("id")),
        "customer_data_by_year": (
            customers.annotate(year=ExtractYear("created_at"))
            .values("year")
            .annotate(total_customers=Count("id"))
            .order_by("year")
        ),
        "customer_data_by_type": customers.values("party_type").annotate(
            total_customers=Count("id")
        ),
        "active_customers": customers.filter(
            pawn_loans__state__in=active_loan_states
        ).distinct().count(),
    }
