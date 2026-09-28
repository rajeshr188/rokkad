import json
from django.core.exceptions import PermissionDenied
from django.db import transaction
from apps.configuration.models import PreferenceAuditLog
from apps.orgs.models import Company
from apps.tenant_apps.loans.models import LoanOriginationSettings, current_tenant_workspace_id
from .action_access import require_setup_administration


def collateral_photos_required(workspace_id):
    if current_tenant_workspace_id() != workspace_id:
        raise PermissionDenied("Select the matching workspace.")
    return bool(LoanOriginationSettings.objects.filter(workspace_id=workspace_id)
                .values_list("require_collateral_photos", flat=True).first())


@transaction.atomic
def set_collateral_photo_requirement(*, workspace, required, actor):
    require_setup_administration(workspace.pk, actor)
    if type(required) is not bool:
        raise ValueError("Choose whether collateral photographs are required.")
    Company.objects.select_for_update().get(pk=workspace.pk)
    row, _ = LoanOriginationSettings.objects.get_or_create(workspace=workspace)
    before = row.require_collateral_photos
    row.require_collateral_photos, row.updated_by = required, actor
    row.save()
    PreferenceAuditLog.objects.create(scope="workspace", key="loans.require_collateral_photos",
        workspace=workspace, changed_by=actor, old_value=json.dumps(before), new_value=json.dumps(required))
    return row
