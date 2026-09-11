"""Explicit Workspace boundary for trusted Loans operator commands."""
from contextlib import contextmanager

from django.core.management.base import CommandError

from apps.orgs.models import Company
from apps.tenancy.context import current_workspace_id, workspace_context


@contextmanager
def command_workspace(workspace_id, *, read_only=False):
    if not isinstance(workspace_id, int) or isinstance(workspace_id, bool) or workspace_id <= 0:
        raise CommandError("--workspace-id must be a positive integer.")
    if current_workspace_id() not in (None, workspace_id):
        raise CommandError("The requested Workspace conflicts with the active context.")
    try:
        workspace = Company.all_objects.exclude(schema_name="public").get(pk=workspace_id)
    except Company.DoesNotExist as exc:
        raise CommandError("Workspace not found.") from exc
    if not read_only and workspace.lifecycle_state != Company.LifecycleState.ACTIVE:
        raise CommandError("This operation requires an ACTIVE Workspace.")
    with workspace_context(workspace.pk):
        yield workspace
