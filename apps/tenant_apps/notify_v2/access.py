import functools

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from apps.orgs.permissions import (
    get_effective_permissions,
    get_workspace_role_name,
    is_platform_admin,
)
from apps.orgs.tenant_context import resolve_request_workspace


NOTIFY_V2_ACTION_PERMISSIONS = {
    "view": ("data_view",),
    "create": ("data_create",),
    "edit": ("data_edit",),
    "delete": ("data_delete",),
    "send": ("data_edit",),
    "print": ("data_view",),
}


def assert_notify_v2_workspace_access(request):
    try:
        workspace = resolve_request_workspace(request)
    except AttributeError as exc:
        raise PermissionDenied("Invalid tenant workspace context") from exc
    if workspace is None:
        raise PermissionDenied("No tenant workspace selected")

    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        raise PermissionDenied("Authentication required")

    if is_platform_admin(user) or getattr(workspace, "owner", None) == user:
        return workspace

    if get_workspace_role_name(user, workspace) is None:
        raise PermissionDenied("Not a workspace member")

    return workspace


def assert_notify_v2_permission(request, *permissions, require_all=False):
    workspace = assert_notify_v2_workspace_access(request)
    user = request.user

    if is_platform_admin(user) or getattr(workspace, "owner", None) == user:
        return workspace
    if not permissions:
        return workspace

    effective_permissions = get_effective_permissions(user, workspace)
    has_required = (
        all(permission in effective_permissions for permission in permissions)
        if require_all
        else any(permission in effective_permissions for permission in permissions)
    )
    if not has_required:
        required = ", ".join(permissions)
        raise PermissionDenied(f"Missing workspace permission(s): {required}")
    return workspace


def assert_notify_v2_action_permission(request, action):
    permissions = NOTIFY_V2_ACTION_PERMISSIONS.get(action)
    if permissions is None:
        raise ValueError(f"Unknown Notify v2 action '{action}'")
    return assert_notify_v2_permission(request, *permissions, require_all=False)


def notify_v2_action_required(action):
    def _decorator(view_func):
        @functools.wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            assert_notify_v2_action_permission(request, action)
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return _decorator


def notify_v2_admin_required(view_func):
    @functools.wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        workspace = assert_notify_v2_workspace_access(request)
        user = request.user
        if not (
            is_platform_admin(user)
            or getattr(workspace, "owner_id", None) == user.pk
            or get_workspace_role_name(user, workspace) in {"Owner", "Admin"}
        ):
            raise PermissionDenied(
                "Notify v2 provider setup requires workspace administration access."
            )
        request.notify_v2_workspace = workspace
        return view_func(request, *args, **kwargs)

    return _wrapped_view


class NotifyV2ActionRequiredMixin(LoginRequiredMixin):
    required_action = None

    def dispatch(self, request, *args, **kwargs):
        if self.required_action is None:
            raise ValueError("NotifyV2ActionRequiredMixin requires required_action")
        assert_notify_v2_action_permission(request, self.required_action)
        return super().dispatch(request, *args, **kwargs)
