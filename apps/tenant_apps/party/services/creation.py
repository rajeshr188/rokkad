"""Shared create boundary for the existing Party form and staged imports."""
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.tenant_apps.party.access import PARTY_ACTION_PERMISSIONS
from .action_access import require_party_service_permission


@transaction.atomic
def create_party_from_form(*, form, workspace_id, actor):
    require_party_service_permission(workspace_id, actor, *PARTY_ACTION_PERMISSIONS["create"])
    if form.instance.pk or not form.is_valid():
        raise ValidationError("A valid new Party form is required.")
    party = form.save(commit=False)
    party.workspace_id = workspace_id
    party.created_by = actor
    party.updated_by = actor
    party.save()
    return party
