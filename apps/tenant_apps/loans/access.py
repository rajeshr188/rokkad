import functools

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from apps.orgs.permissions import get_workspace_role_name, is_platform_admin
from apps.orgs.tenant_context import resolve_request_workspace


def assert_loans_setup_access(request):
    workspace = resolve_request_workspace(request)
    if workspace is None:
        raise PermissionDenied("No tenant workspace selected.")

    user = getattr(request, "user", None)
    if is_platform_admin(user) or workspace.owner_id == getattr(user, "pk", None):
        return workspace

    if get_workspace_role_name(user, workspace) not in {"Owner", "Admin"}:
        raise PermissionDenied("Loan setup requires workspace administration access.")
    return workspace


def loans_setup_required(view_func):
    @functools.wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        request.loans_workspace = assert_loans_setup_access(request)
        return view_func(request, *args, **kwargs)

    return _wrapped


def assert_loans_owner_access(request):
    workspace = resolve_request_workspace(request)
    if workspace is None:
        raise PermissionDenied("No tenant workspace selected.")

    user = getattr(request, "user", None)
    if is_platform_admin(user) or workspace.owner_id == getattr(user, "pk", None):
        return workspace
    raise PermissionDenied("This Loans operation requires the workspace Owner.")


def loans_owner_required(view_func):
    @functools.wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        request.loans_workspace = assert_loans_owner_access(request)
        return view_func(request, *args, **kwargs)

    return _wrapped


def assert_loans_workspace_access(request):
    workspace = resolve_request_workspace(request)
    if workspace is None:
        raise PermissionDenied("No tenant workspace selected.")

    user = getattr(request, "user", None)
    if is_platform_admin(user) or workspace.owner_id == getattr(user, "pk", None):
        return workspace
    if get_workspace_role_name(user, workspace) is None:
        raise PermissionDenied("Pawn loans require workspace membership.")
    return workspace


def loans_workspace_required(view_func):
    @functools.wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        request.loans_workspace = assert_loans_workspace_access(request)
        return view_func(request, *args, **kwargs)

    return _wrapped
