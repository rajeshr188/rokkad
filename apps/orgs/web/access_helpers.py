"""Access helpers; existing control-plane policy remains authoritative."""

from django.core.exceptions import PermissionDenied

from apps.orgs.permissions import (
    get_effective_permissions,
    is_platform_admin,
)
from apps.orgs.access import resolve_workspace_access


def _assert_workspace_access(
    request,
    workspace,
    required_permissions=None,
    allow_platform_admin=True,
):
    """Validate workspace access and return normalized access context."""
    required_permissions = set(required_permissions or [])

    access = resolve_workspace_access(actor=request.user, workspace=workspace)
    if access.platform_override and not allow_platform_admin:
        raise PermissionDenied("Platform override is not allowed here")
    if access.membership is None and not access.platform_override:
        raise PermissionDenied("You are not a member of this workspace")
    for permission in required_permissions:
        access.require(permission)
    effective_perms = get_effective_permissions(request.user, workspace)
    role_name = "Superuser" if access.platform_override else access.membership.role.name
    return {
        "membership": access.membership,
        "role_name": role_name,
        "effective_permissions": effective_perms,
        "access": access,
    }


def _assert_owner_access(request, workspace, allow_platform_admin=True):
    """Allow only workspace owner (or platform admin when enabled)."""
    access = _assert_workspace_access(
        request,
        workspace,
        required_permissions=set(),
        allow_platform_admin=allow_platform_admin,
    )
    if allow_platform_admin and is_platform_admin(request.user):
        return access
    if access["role_name"].lower() != "owner":
        raise PermissionDenied("Only workspace owners can access this page")
    return access
