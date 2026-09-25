"""Photo gallery/default mutations under the customer lock and Party permissions."""
from django.db import transaction
from apps.orgs.audit import AuditLog
from apps.tenant_apps.party.models import Party, PartyPhoto
from apps.tenant_apps.party.access import PARTY_ACTION_PERMISSIONS
from .action_access import require_party_service_permission


def remember_profile_photo(party, *, previous_name="", actor=None):
    """Internal helper after an authorized create/update under the Party lock.

    Reuse existing private files; selecting a default does not copy image bytes.
    """
    current = party.profile_photo.name or ""
    for name in dict.fromkeys((previous_name, current)):
        if name:
            photo, created = PartyPhoto.objects.get_or_create(workspace_id=party.workspace_id, party=party,
                file=name, defaults={"created_by": actor})
            if created and actor is not None:
                AuditLog.log("UPDATE", user=actor, company=party.workspace,
                    description="Added customer photo to gallery.",
                    data={"party_id": party.pk, "photo_id": photo.pk})
    if not current and previous_name:
        # The existing clear control removes the selected photo from the gallery.
        PartyPhoto.objects.filter(party=party, workspace_id=party.workspace_id, file=previous_name).delete()
        remaining = party.photos.order_by("pk").first()
        if remaining:
            party.profile_photo = remaining.file.name
            party.save(update_fields=["profile_photo", "updated_at"])


@transaction.atomic
def choose_photo(*, party, photo_id, actor):
    require_party_service_permission(party.workspace_id, actor, *PARTY_ACTION_PERMISSIONS["edit"])
    party = Party.objects.select_for_update().get(pk=party.pk, workspace_id=party.workspace_id)
    photo = PartyPhoto.objects.get(pk=photo_id, party=party, workspace_id=party.workspace_id)
    remember_profile_photo(party, actor=actor)
    party.profile_photo = photo.file.name
    party.updated_by = actor
    party.save(update_fields=["profile_photo", "updated_at", "updated_by"])
    AuditLog.log("UPDATE", user=actor, company=party.workspace,
        description="Changed customer default photo.", data={"party_id":party.pk,"photo_id":photo.pk})
    return party


@transaction.atomic
def remove_photo(*, party, photo_id=None, actor):
    require_party_service_permission(party.workspace_id, actor, *PARTY_ACTION_PERMISSIONS["edit"])
    party = Party.objects.select_for_update().get(pk=party.pk, workspace_id=party.workspace_id)
    remember_profile_photo(party, actor=actor)
    photo = (party.photos.get(pk=photo_id) if photo_id is not None else
             party.photos.filter(file=party.profile_photo.name).first())
    if photo is None:
        return party
    selected = photo.file.name == party.profile_photo.name
    removed_id = photo.pk
    photo.delete()
    if selected:
        remaining = party.photos.order_by("pk").first()
        party.profile_photo = remaining.file.name if remaining else ""
        party.updated_by = actor
        party.save(update_fields=["profile_photo", "updated_at", "updated_by"])
    # Retain private bytes: old snapshots/merged records may still reference them.
    AuditLog.log("UPDATE", user=actor, company=party.workspace,
        description="Removed customer photo from gallery.", data={"party_id":party.pk,"photo_id":removed_id})
    return party
