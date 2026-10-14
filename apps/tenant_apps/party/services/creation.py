"""Shared create boundary for the existing Party form and staged imports."""
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.tenant_apps.party.access import PARTY_ACTION_PERMISSIONS
from .action_access import require_party_service_permission


@transaction.atomic
def create_party_from_form(*, form, workspace_id, actor, _business_code=None):
    require_party_service_permission(workspace_id, actor, *PARTY_ACTION_PERMISSIONS["create"])
    if form.instance.pk or not form.is_valid():
        raise ValidationError("A valid new Party form is required.")
    party = form.save(commit=False)
    party.workspace_id = workspace_id
    if _business_code is not None:
        if type(_business_code) is not str or not _business_code.strip() or len(_business_code) > 32:
            raise ValidationError("A preserved source customer code must be nonempty text of at most 32 characters.")
        party.party_code = _business_code
        party.full_clean()
    party.created_by = actor
    party.updated_by = actor
    party.save()
    from .photos import remember_profile_photo
    remember_profile_photo(party, actor=actor)
    return party
