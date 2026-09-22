"""Domain write for an already resolved legacy Party; never overwrite local choices."""
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.tenant_apps.party.models import Party, PartyDocument
from .action_access import require_party_service_permission


@transaction.atomic
def attach_legacy_photo(*, workspace_id, actor, party_id, document_name, profile_name, evidence):
    require_party_service_permission(workspace_id, actor, "data.import")
    party = Party.objects.select_for_update().get(pk=party_id, workspace_id=workspace_id)
    if profile_name and party.profile_photo:
        raise ValidationError("The Party already has a profile photo; review the local change before importing.")
    document = PartyDocument.objects.create(
        workspace_id=workspace_id, party=party, document_type="OTHER",
        title="Legacy customer photograph", file=document_name,
        metadata={"legacy_media": evidence, "capture_date": None},
    )
    if profile_name:
        party.profile_photo = profile_name
        party.save(update_fields=["profile_photo"])
    return {"kind": "party", "party_id": party.pk, "document_id": document.pk,
            "document_name": document_name, "profile_name": profile_name}
