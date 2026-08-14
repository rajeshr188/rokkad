import functools

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from apps.orgs.permissions import get_workspace_role_name, is_platform_admin
from apps.orgs.tenant_context import resolve_request_workspace


ACCOUNTANT_ROLES = {"Owner", "Admin", "Accountant"}


def can_view_dea_accountant_tools(request):
    """Return True when the request user may view accountant-only DEA navigation."""
    try:
        workspace = resolve_request_workspace(request)
    except AttributeError:
        return False
    if workspace is None:
        return False

    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return False

    if is_platform_admin(user) or getattr(user, "is_staff", False):
        return True

    if getattr(workspace, "owner", None) == user:
        return True

    role_name = get_workspace_role_name(user, workspace)
    return role_name in ACCOUNTANT_ROLES


def assert_dea_accountant_access(request):
    """Fail closed unless the request user may use accountant-only DEA surfaces."""
    try:
        workspace = resolve_request_workspace(request)
    except AttributeError as exc:
        raise PermissionDenied("Invalid tenant workspace context") from exc
    if workspace is None:
        raise PermissionDenied("No tenant workspace selected")

    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        raise PermissionDenied("Authentication required")

    if is_platform_admin(user) or getattr(user, "is_staff", False):
        return workspace

    if getattr(workspace, "owner", None) == user:
        return workspace

    role_name = get_workspace_role_name(user, workspace)
    if role_name not in ACCOUNTANT_ROLES:
        raise PermissionDenied("Accounting access requires owner, admin, or accountant role")

    return workspace


def dea_accountant_required(view_func):
    @functools.wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        assert_dea_accountant_access(request)
        return view_func(request, *args, **kwargs)

    return _wrapped_view


class DeaAccountantRequiredMixin(LoginRequiredMixin):
    """Class-based view mixin for accountant-only DEA surfaces."""

    def dispatch(self, request, *args, **kwargs):
        assert_dea_accountant_access(request)
        return super().dispatch(request, *args, **kwargs)
