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


PRODUCT_ADMIN_ROLES = {"Owner", "Admin", "Administrator"}

# Product-specific codenames do not exist yet. Until the permission catalog is
# extended, Product uses the generic workspace data permissions.
PRODUCT_ACTION_PERMISSIONS = {
    "view": ("data_view",),
    "create": ("data_create",),
    "edit": ("data_edit",),
    "delete": ("data_delete",),
    "import": ("data_import",),
    "export": ("data_export",),
}


def assert_product_workspace_access(request):
    """Fail closed unless the request is bound to a Product-capable workspace."""
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


def assert_product_permission(request, *permissions, require_all=False):
    """Fail closed unless the user has the requested Product permission(s)."""
    workspace = assert_product_workspace_access(request)
    user = getattr(request, "user", None)

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


def assert_product_action_permission(request, action):
    """Apply the canonical Product permission set for a named action."""
    permissions = PRODUCT_ACTION_PERMISSIONS.get(action)
    if permissions is None:
        raise ValueError(f"Unknown Product action '{action}'")
    return assert_product_permission(request, *permissions, require_all=False)


def can_administer_product_data(request):
    """Return True for users allowed to perform Product admin-level operations."""
    try:
        workspace = assert_product_workspace_access(request)
    except PermissionDenied:
        return False

    user = getattr(request, "user", None)
    if is_platform_admin(user) or getattr(workspace, "owner", None) == user:
        return True

    role_name = get_workspace_role_name(user, workspace)
    return role_name in PRODUCT_ADMIN_ROLES


def product_workspace_required(view_func):
    @functools.wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        assert_product_workspace_access(request)
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def product_permission_required(*permissions, require_all=False):
    def _decorator(view_func):
        @functools.wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            assert_product_permission(
                request,
                *permissions,
                require_all=require_all,
            )
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return _decorator


def product_action_required(action):
    def _decorator(view_func):
        @functools.wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            assert_product_action_permission(request, action)
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return _decorator


class ProductWorkspaceRequiredMixin(LoginRequiredMixin):
    """Class-based view mixin equivalent of ``product_workspace_required``."""

    def dispatch(self, request, *args, **kwargs):
        assert_product_workspace_access(request)
        return super().dispatch(request, *args, **kwargs)


class ProductPermissionRequiredMixin(ProductWorkspaceRequiredMixin):
    """Class-based view mixin for Product permission-gated endpoints."""

    required_permissions = ()
    permission_require_all = False

    def dispatch(self, request, *args, **kwargs):
        assert_product_permission(
            request,
            *self.required_permissions,
            require_all=self.permission_require_all,
        )
        return super().dispatch(request, *args, **kwargs)


class ProductActionRequiredMixin(ProductWorkspaceRequiredMixin):
    """Class-based view mixin for Product action-gated endpoints."""

    required_action = None

    def dispatch(self, request, *args, **kwargs):
        if self.required_action is None:
            raise ValueError("ProductActionRequiredMixin requires required_action")
        assert_product_action_permission(request, self.required_action)
        return super().dispatch(request, *args, **kwargs)
