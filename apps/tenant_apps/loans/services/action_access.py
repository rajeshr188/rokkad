"""Actor authorization for loan commands, independent of HTTP requests."""

from django.core.exceptions import PermissionDenied

from apps.orgs.access import resolve_workspace_access
from apps.orgs.models import Company
from apps.tenant_apps.loans.models import current_tenant_workspace_id


def require_loan_action(loan, actor, *actions):
    require_workspace_action(loan.workspace, actor, *actions)


def require_workspace_action(workspace, actor, *actions):
    access = resolve_workspace_access(actor=actor, workspace=workspace)
    access.require("data.view")
    for action in actions:
        access.require(action)


def require_setup_administration(workspace_id, actor):
    """Authorize configuration writes in the active Workspace."""
    if workspace_id is None or current_tenant_workspace_id() != workspace_id:
        raise PermissionDenied("Setup requires the matching active workspace.")
    workspace = Company.objects.get(pk=workspace_id)
    resolve_workspace_access(actor=actor, workspace=workspace).require(
        "workspace.settings.manage"
    )
