from dataclasses import dataclass
from typing import Any, Callable

from django.core.exceptions import PermissionDenied


class PortalIdentityNotConfigured(PermissionDenied):
    """Raised when portal identity binding is not available yet."""


class PortalIdentityDenied(PermissionDenied):
    """Raised when the current user has no verified portal identity."""


@dataclass(frozen=True)
class PortalIdentity:
    user: Any
    workspace: Any
    party: Any
    access_grant: Any


PortalBindingLookup = Callable[[Any, Any], PortalIdentity | None]


def lookup_active_portal_access(user, request):
    from apps.tenant_apps.party.models import PartyPortalAccess

    grant = (
        PartyPortalAccess.objects.select_related("party", "user")
        .filter(user=user, status=PartyPortalAccess.Status.ACTIVE)
        .order_by("id")
        .first()
    )
    if grant is None:
        return None
    return PortalIdentity(
        user=user,
        workspace=getattr(request, "workspace", None),
        party=grant.party,
        access_grant=grant,
    )


def resolve_portal_identity(request, *, binding_lookup: PortalBindingLookup | None = None):
    """Resolve the authenticated user's Workspace Party portal identity.

    The first live portal routes must call this helper, or a stricter successor,
    before reading loans, invoices, payments, documents, or statements.
    """
    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        raise PortalIdentityDenied("Authentication is required for portal access.")

    if binding_lookup is None:
        binding_lookup = lookup_active_portal_access

    identity = binding_lookup(user, request)
    return validate_portal_identity(identity)


def validate_portal_identity(identity):
    if identity is None:
        raise PortalIdentityDenied("No verified portal identity is available.")

    missing = [
        field_name
        for field_name in ("user", "workspace", "party", "access_grant")
        if getattr(identity, field_name, None) is None
    ]
    if missing:
        raise PortalIdentityDenied(
            f"Portal identity is incomplete: {', '.join(missing)}."
        )

    party = identity.party
    if getattr(party, "status", "ACTIVE") != "ACTIVE":
        raise PortalIdentityDenied("Portal party is not active.")

    access_grant = identity.access_grant
    if getattr(access_grant, "status", "ACTIVE") != "ACTIVE":
        raise PortalIdentityDenied("Portal access grant is not active.")

    return identity
