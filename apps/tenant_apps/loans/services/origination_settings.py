import json
from django.core.exceptions import PermissionDenied
from django.db import transaction
from apps.configuration.models import PreferenceAuditLog
from apps.orgs.models import Company
from apps.orgs.access import resolve_workspace_access
from apps.tenant_apps.loans.models import LoanOriginationSettings, current_tenant_workspace_id
from .action_access import require_setup_administration


def maximum_quote_age_days(workspace_id):
    """Prospective lending only; monitoring has its own freshness policy."""
    if current_tenant_workspace_id() != workspace_id:
        raise PermissionDenied("Select the matching workspace.")
    value = (LoanOriginationSettings.objects.filter(workspace_id=workspace_id)
        .values_list("maximum_quote_age_days", flat=True).first())
    return 7 if value is None else value


@transaction.atomic
def set_maximum_quote_age(*, workspace, days, actor):
    require_setup_administration(workspace.pk, actor)
    workspace = Company.objects.select_for_update().get(pk=workspace.pk)
    resolve_workspace_access(actor=actor, workspace=workspace).require("workspace.transfer")
    if type(days) is not int or not 0 <= days <= 32767:
        raise ValueError("Choose a whole number of days from 0 to 32767.")
    row, _ = LoanOriginationSettings.objects.get_or_create(workspace=workspace)
    before = row.maximum_quote_age_days
    if before != days:
        row.maximum_quote_age_days, row.updated_by = days, actor
        row.save(update_fields=["maximum_quote_age_days", "updated_by", "updated_at"])
        PreferenceAuditLog.objects.create(scope="workspace", key="loans.maximum_quote_age_days",
            workspace=workspace, changed_by=actor, old_value=json.dumps(before), new_value=json.dumps(days))
    return row


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
