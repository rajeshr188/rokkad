import functools

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from apps.orgs.access import resolve_workspace_access
from apps.orgs.tenant_context import resolve_request_workspace


NOTIFY_V2_ADMIN_ACTION = "workspace.settings.manage"

NOTIFY_V2_ACTION_PERMISSIONS = {
    "view": ("data.view",),
    "create": ("data.create",),
    "edit": ("data.edit",),
    "delete": ("data.delete",),
    "send": ("data.edit",),
    "print": ("data.view",),
    "export": ("data.export",),
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

    access = resolve_workspace_access(actor=user, workspace=workspace)
    if access.membership is None and not access.platform_override:
        raise PermissionDenied("Not a workspace member")

    request.notify_v2_workspace_access = access
    return workspace


def assert_notify_v2_permission(request, *permissions, require_all=False):
    workspace = assert_notify_v2_workspace_access(request)
    if not permissions:
        return workspace

    access = request.notify_v2_workspace_access
    has_required = (
        all(access.can(permission) for permission in permissions)
        if require_all
        else any(access.can(permission) for permission in permissions)
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
        if not request.notify_v2_workspace_access.can(NOTIFY_V2_ADMIN_ACTION):
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
