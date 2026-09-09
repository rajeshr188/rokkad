"""Actor checks for Party commands outside HTTP adapters."""

from django.core.exceptions import PermissionDenied

from apps.orgs.access import resolve_workspace_access
from apps.orgs.models import Company
from apps.tenancy.context import current_workspace_id


def require_party_service_permission(workspace_id, actor, *permissions):
    if workspace_id is None or current_workspace_id() != workspace_id:
        raise PermissionDenied("Party commands require the matching active workspace.")
    workspace = Company.objects.get(pk=workspace_id)
    access = resolve_workspace_access(actor=actor, workspace=workspace)
    if not any(access.can(permission) for permission in permissions):
        raise PermissionDenied("Missing Party command permission.")
    return workspace
