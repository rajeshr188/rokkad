import functools

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from apps.orgs.access import resolve_workspace_access
from apps.orgs.tenant_context import resolve_request_workspace


PARTY_ADMIN_ACTION = "workspace.settings.manage"

PARTY_ACTION_PERMISSIONS = {
    "view": ("contact.view", "data.view"),
    "create": ("contact.create", "data.create"),
    "edit": ("contact.edit", "data.edit"),
    "delete": ("contact.delete", "data.delete"),
    "export": ("contact.export", "data.export"),
}


def assert_party_workspace_access(request):
    """Fail closed unless the request is bound to a Party-capable workspace."""
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

    request.party_workspace_access = access
    return workspace


def assert_party_permission(request, *permissions, require_all=False):
    """Fail closed unless the user has the requested Party permission(s)."""
    workspace = assert_party_workspace_access(request)
    if not permissions:
        return workspace

    access = request.party_workspace_access
    has_required = (
        all(access.can(permission) for permission in permissions)
        if require_all
        else any(access.can(permission) for permission in permissions)
    )
    if not has_required:
        required = ", ".join(permissions)
        raise PermissionDenied(f"Missing workspace permission(s): {required}")

    return workspace


def assert_party_action_permission(request, action):
    """Apply the canonical Party permission set for a named action."""
    permissions = PARTY_ACTION_PERMISSIONS.get(action)
    if permissions is None:
        raise ValueError(f"Unknown Party action '{action}'")
    return assert_party_permission(request, *permissions, require_all=False)


def can_administer_party_data(request):
    """Return True for users allowed to perform Party admin-level operations."""
    try:
        workspace = assert_party_workspace_access(request)
    except PermissionDenied:
        return False

    return request.party_workspace_access.can(PARTY_ADMIN_ACTION)


def party_workspace_required(view_func):
    @functools.wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        assert_party_workspace_access(request)
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def party_permission_required(*permissions, require_all=False):
    def _decorator(view_func):
        @functools.wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            assert_party_permission(
                request,
                *permissions,
                require_all=require_all,
            )
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return _decorator


def party_action_required(action):
    def _decorator(view_func):
        @functools.wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            assert_party_action_permission(request, action)
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return _decorator


class PartyWorkspaceRequiredMixin(LoginRequiredMixin):
    """Class-based view mixin equivalent of ``party_workspace_required``."""

    def dispatch(self, request, *args, **kwargs):
        assert_party_workspace_access(request)
        return super().dispatch(request, *args, **kwargs)


class PartyPermissionRequiredMixin(PartyWorkspaceRequiredMixin):
    """Class-based view mixin for Party permission-gated endpoints."""

    required_permissions = ()
    permission_require_all = False

    def dispatch(self, request, *args, **kwargs):
        assert_party_permission(
            request,
            *self.required_permissions,
            require_all=self.permission_require_all,
        )
        return super().dispatch(request, *args, **kwargs)
