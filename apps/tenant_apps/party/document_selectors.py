"""Authorized Party-owned display facts for first-issue documents."""

from dataclasses import dataclass

from django.core.exceptions import PermissionDenied

from apps.orgs.access import resolve_workspace_access
from apps.tenancy.context import current_workspace_id
from .models import Party


class DocumentAddressSelectionRequired(ValueError):
    def __init__(self, addresses):
        self.choices = tuple((str(address.pk), str(address)) for address in addresses)
        super().__init__("Choose the customer's address for this document. Party defaults will not change.")


@dataclass(frozen=True)
class PartyDocumentIdentity:
    party_id: int
    name: str
    code: str
    relationship: str
    address: str
    address_id: int | None
    phone: str
    photo: object


def document_identity(*, workspace, party_id, actor, address_id=None, include_address=True):
    if current_workspace_id() != workspace.pk:
        raise PermissionDenied("Party document facts require the matching Workspace.")
    access = resolve_workspace_access(actor=actor, workspace=workspace)
    if not (access.can("data.view") or access.can("contact.view")):
        raise PermissionDenied("Customer document access denied.")
    party = Party.objects.get(pk=party_id, workspace=workspace)
    address = None
    if include_address:
        addresses = list(party.addresses.filter(workspace=workspace).order_by("pk"))
        if address_id:
            address = next((value for value in addresses if str(value.pk) == str(address_id)), None)
            if address is None:
                raise ValueError("Selected address does not belong to this customer and Workspace.")
        else:
            defaults = [value for value in addresses if value.is_default and value.address_type == "HOME"]
            if len(defaults) == 1:
                address = defaults[0]
            elif len(addresses) == 1:
                address = addresses[0]
            elif addresses:
                raise DocumentAddressSelectionRequired(addresses)
    return PartyDocumentIdentity(
        party.pk, party.display_name or "", party.party_code or "", party.relation_display or "",
        ", ".join(value for value in (address.line1, address.line2, address.area, address.city, address.state, address.postal_code, address.country) if value) if address else "",
        address.pk if address else None, party.primary_phone or "", party.profile_photo,
    )
