import functools

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from apps.orgs.access import resolve_workspace_access
from apps.orgs.tenant_context import resolve_request_workspace


LOANS_ADMIN_ACTION = "workspace.settings.manage"
LOANS_SETUP_ACTION = LOANS_ADMIN_ACTION
LOANS_OWNER_ACTION = "workspace.transfer"
LOANS_WORKSPACE_ACTION = "data.view"


def loans_action_required(action):
    def decorate(view_func):
        @functools.wraps(view_func)
        @loans_workspace_required
        def wrapped(request, *args, **kwargs):
            request.loans_workspace_access.require(action)
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorate


def _resolve_loans_access(request):
    workspace = resolve_request_workspace(request)
    if workspace is None:
        raise PermissionDenied("No tenant workspace selected.")

    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        raise PermissionDenied("Authentication required.")

    access = resolve_workspace_access(actor=user, workspace=workspace)
    if access.membership is None and not access.platform_override:
        raise PermissionDenied("Pawn loans require workspace membership.")

    request.loans_workspace_access = access
    return workspace, access


def assert_loans_setup_access(request):
    workspace, access = _resolve_loans_access(request)
    if not access.can(LOANS_SETUP_ACTION):
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
    workspace, access = _resolve_loans_access(request)
    if not access.can(LOANS_OWNER_ACTION):
        raise PermissionDenied("This Loans operation requires the workspace Owner.")
    return workspace


def loans_owner_required(view_func):
    @functools.wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        request.loans_workspace = assert_loans_owner_access(request)
        return view_func(request, *args, **kwargs)

    return _wrapped


def assert_loans_workspace_access(request):
    workspace, access = _resolve_loans_access(request)
    if not access.can(LOANS_WORKSPACE_ACTION):
        raise PermissionDenied("Pawn loan access requires data view permission.")
    return workspace


def loans_workspace_required(view_func):
    @functools.wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        request.loans_workspace = assert_loans_workspace_access(request)
        return view_func(request, *args, **kwargs)

    return _wrapped
