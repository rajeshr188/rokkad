"""Tenant and role boundary for standalone accounting screens."""

import functools

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from apps.orgs.permissions import get_effective_permissions
from apps.orgs.tenant_context import resolve_request_workspace


def accounting_workspace_required(view):
    @functools.wraps(view)
    @login_required
    def wrapped(request, *args, **kwargs):
        workspace = resolve_request_workspace(request)
        if workspace is None:
            raise PermissionDenied("No tenant workspace selected.")
        permissions = get_effective_permissions(request.user, workspace)
        if not permissions.intersection(
            {"accounting_voucher_create", "accounting_period_manage", "dea_report_view"}
        ):
            raise PermissionDenied("Accounting workspace access is required.")
        request.accounting_workspace = workspace
        return view(request, *args, **kwargs)

    return wrapped
