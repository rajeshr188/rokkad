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


def party_identification(party):
    """Display defaults for an already authorized, workspace-scoped Party.

    Match borrower search: primary phone, then a primary telephone contact;
    default HOME address, then the first other default. Never invent a default.
    At most two bounded queries, independent of the number of loans or photos.
    """
    from django.core.exceptions import PermissionDenied
    from apps.tenancy.context import current_workspace_id

    if current_workspace_id() != party.workspace_id:
        raise PermissionDenied("Party identification requires its Workspace.")
    addresses = list(party.addresses.filter(workspace_id=party.workspace_id, is_default=True).order_by("pk"))
    address = next((item for item in addresses if item.address_type == "HOME"), addresses[0] if addresses else None)
    phone = party.primary_phone
    if not phone:
        phone = party.contact_methods.filter(
            workspace_id=party.workspace_id, is_primary=True,
            contact_type__in=["PHONE", "MOBILE", "WHATSAPP"],
        ).order_by("pk").values_list("value", flat=True).first() or ""
    words = party.display_name.split()
    initials = (words[0][0] + (words[-1][0] if len(words) > 1 else "")).upper() if words else "?"
    return {"phone": phone, "address": str(address) if address else "", "initials": initials}


def get_workspace_customer_party_dashboard_summary():
    """Return the legacy dashboard context shape from canonical Party rows."""
    from apps.tenant_apps.loans.domain import PawnLoanState

    customers = parties_with_role("CUSTOMER").distinct()
    active_loan_states = {
        PawnLoanState.APPROVED.value,
        PawnLoanState.ACTIVE.value,
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
