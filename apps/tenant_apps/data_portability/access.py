from django.core.exceptions import PermissionDenied

from apps.orgs.access import resolve_workspace_access
from apps.orgs.lifecycle import lifecycle_access
from apps.orgs.models import Company
from apps.tenancy.context import current_workspace_id
from apps.tenant_apps.party.access import PARTY_ACTION_PERMISSIONS


def require_access(workspace_id, actor, operation):
    if not workspace_id or current_workspace_id() != workspace_id:
        raise PermissionDenied("Portability requires a matching explicit Workspace context.")
    workspace = Company.all_objects.get(pk=workspace_id)
    access = resolve_workspace_access(actor=actor, workspace=workspace)
    if not access.platform_override and access.membership is None:
        raise PermissionDenied("Workspace access is required.")
    if not any(access.can(code) for code in PARTY_ACTION_PERMISSIONS["view"]):
        raise PermissionDenied("Party read permission is required.")
    if operation == "export":
        if not any(access.can(code) for code in PARTY_ACTION_PERMISSIONS["export"]):
            raise PermissionDenied("Party export permission is required.")
        policy = lifecycle_access(workspace=workspace, access=access)
        if not (policy.may_enter_business or policy.may_use_recovery):
            raise PermissionDenied("Workspace export is unavailable.")
    else:
        access.require("data.import")
        if workspace.lifecycle_state != Company.LifecycleState.ACTIVE:
            raise PermissionDenied("Import requires an active Workspace.")
        if operation == "commit" and not any(access.can(code) for code in PARTY_ACTION_PERMISSIONS["create"]):
            raise PermissionDenied("Party creation permission is required.")
        if operation == "child_commit" and not any(access.can(code) for code in PARTY_ACTION_PERMISSIONS["edit"]):
            raise PermissionDenied("Party edit permission is required for child imports.")
    return workspace
