import functools

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from apps.orgs.permissions import (
    get_effective_permissions,
    get_workspace_role_name,
    is_platform_admin,
)
from apps.orgs.tenant_context import resolve_request_workspace


def assert_girvi_workspace_access(request):
    """Fail closed when a Girvi request is not bound to an accessible workspace."""
    try:
        workspace = resolve_request_workspace(request)
    except AttributeError as exc:
        raise PermissionDenied("Invalid tenant workspace context") from exc
    if workspace is None:
        raise PermissionDenied("No tenant workspace selected")

    user = getattr(request, "user", None)
    if is_platform_admin(user):
        return workspace

    if getattr(workspace, "owner", None) == user:
        return workspace

    if get_workspace_role_name(user, workspace) is None:
        raise PermissionDenied("Not a workspace member")

    return workspace


def girvi_workspace_required(view_func):
    @functools.wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        assert_girvi_workspace_access(request)
        return view_func(request, *args, **kwargs)

    return _wrapped_view


class GirviWorkspaceRequiredMixin:
    """Class-based view mixin equivalent of ``girvi_workspace_required``."""

    def dispatch(self, request, *args, **kwargs):
        assert_girvi_workspace_access(request)
        return super().dispatch(request, *args, **kwargs)


def assert_girvi_workspace_permission(request, *permissions, require_all=True):
    """Fail closed when a Girvi request lacks required workspace permissions."""
    workspace = assert_girvi_workspace_access(request)
    user = getattr(request, "user", None)

    if is_platform_admin(user) or getattr(workspace, "owner", None) == user:
        return workspace

    effective_permissions = get_effective_permissions(user, workspace)
    if not permissions:
        return workspace

    has_required = (
        all(permission in effective_permissions for permission in permissions)
        if require_all
        else any(permission in effective_permissions for permission in permissions)
    )
    if not has_required:
        required = ", ".join(permissions)
        raise PermissionDenied(f"Missing workspace permission(s): {required}")

    return workspace


def girvi_permission_required(*permissions, require_all=True):
    """Decorator that applies workspace access and permission checks to Girvi views."""

    def _decorator(view_func):
        @functools.wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            assert_girvi_workspace_permission(
                request,
                *permissions,
                require_all=require_all,
            )
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return _decorator


class GirviPermissionRequiredMixin(GirviWorkspaceRequiredMixin):
    """Class-based view mixin for permission-gated Girvi endpoints."""

    required_permissions = ()
    permission_require_all = True

    def dispatch(self, request, *args, **kwargs):
        assert_girvi_workspace_permission(
            request,
            *self.required_permissions,
            require_all=self.permission_require_all,
        )
        return super().dispatch(request, *args, **kwargs)
