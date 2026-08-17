"""
Enhanced permission decorators using django-guardian.
Provides object-level and feature-level permission checking.
"""

import functools
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from guardian.shortcuts import get_perms

from apps.orgs.audit import AuditLog
from apps.orgs.models import Membership
from apps.orgs.access import resolve_workspace_access
from apps.orgs.tenant_context import resolve_request_workspace


def _resolve_workspace(request):
    return resolve_request_workspace(request)


def permission_required(perm, raise_exception=True, log_denial=True):
    """
    Check if user has specific permission in their current workspace.

    Usage:
        @permission_required('data_export')
        def export_data(request):
            ...

    Args:
        perm: Permission codename (e.g., 'data_export')
        raise_exception: If True, raises PermissionDenied; if False, returns 403
        log_denial: If True, logs permission denial to audit log
    """

    def decorator(view_func):
        @functools.wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            user = request.user
            workspace = _resolve_workspace(request)

            if not workspace:
                if log_denial:
                    AuditLog.log(
                        "PERMISSION_DENIED",
                        user=user,
                        description=f"No workspace set for permission '{perm}'",
                        request=request,
                        success=False,
                    )
                if raise_exception:
                    raise PermissionDenied("No workspace selected")
                return HttpResponseForbidden("No workspace selected")

            access = resolve_workspace_access(actor=user, workspace=workspace)

            if access.membership is None and not access.platform_override:
                if log_denial:
                    AuditLog.log(
                        "PERMISSION_DENIED",
                        user=user,
                        company=workspace,
                        description=f"No membership for permission '{perm}'",
                        request=request,
                        success=False,
                    )
                if raise_exception:
                    raise PermissionDenied("Not a workspace member")
                return HttpResponseForbidden("Not a workspace member")

            has_perm = access.can(perm)

            if not has_perm:
                role_name = "Unknown"
                if user.is_superuser:
                    role_name = "Superuser"
                else:
                    try:
                        membership = Membership.objects.select_related("role").get(
                            user=user, company=workspace
                        )
                        role_name = membership.role.name
                    except Membership.DoesNotExist:
                        pass
                if log_denial:
                    AuditLog.log(
                        "PERMISSION_DENIED",
                        user=user,
                        company=workspace,
                        description=f"Permission denied: '{perm}'",
                        request=request,
                        success=False,
                        data={
                            "required_permission": perm,
                            "role": role_name,
                        },
                    )
                if raise_exception:
                    raise PermissionDenied(f"Permission '{perm}' required")
                return HttpResponseForbidden(f"Permission '{perm}' required")

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


def any_permission_required(perms, raise_exception=True):
    """
    Check if user has ANY of the specified permissions.

    Usage:
        @any_permission_required(['data_edit', 'data_create'])
        def create_or_edit_data(request):
            ...
    """

    def decorator(view_func):
        @functools.wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            user = request.user
            workspace = _resolve_workspace(request)

            if not workspace:
                if raise_exception:
                    raise PermissionDenied("No workspace selected")
                return HttpResponseForbidden("No workspace selected")

            access = resolve_workspace_access(actor=user, workspace=workspace)

            if access.membership is None and not access.platform_override:
                if raise_exception:
                    raise PermissionDenied("Not a workspace member")
                return HttpResponseForbidden("Not a workspace member")

            has_any_perm = any(access.can(perm) for perm in perms)

            if not has_any_perm:
                AuditLog.log(
                    "PERMISSION_DENIED",
                    user=user,
                    company=workspace,
                    description=f"None of required permissions: {perms}",
                    request=request,
                    success=False,
                )
                if raise_exception:
                    raise PermissionDenied(f"One of permissions {perms} required")
                return HttpResponseForbidden()

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


def object_permission_required(
    perm, model, pk_url_kwarg="pk", accept_global_perms=True
):
    """
    Check object-level permissions using Guardian.

    Usage:
        @object_permission_required('change_company', Company, pk_url_kwarg='company_id')
        def update_company(request, company_id):
            ...
    """

    def decorator(view_func):
        @functools.wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            # Get object_id from URL kwargs
            object_id = kwargs.get(pk_url_kwarg)
            if not object_id:
                raise Http404(f"Missing {pk_url_kwarg} in URL")

            # Get the object
            obj = get_object_or_404(model, pk=object_id)

            # Check permission using Guardian
            user_perms = get_perms(request.user, obj)

            if perm not in user_perms:
                # Also check global permission from role if accept_global_perms
                if accept_global_perms:
                    workspace = _resolve_workspace(request)
                    if workspace:
                        try:
                            has_global = resolve_workspace_access(
                                actor=request.user, workspace=workspace
                            ).can(perm)
                            if has_global:
                                return view_func(request, *args, **kwargs)
                        except Membership.DoesNotExist:
                            pass

                # Log denial
                AuditLog.log(
                    "PERMISSION_DENIED",
                    user=request.user,
                    description=f"Object permission denied: '{perm}' on {model.__name__} {object_id}",
                    request=request,
                    success=False,
                    content_object=obj,
                )

                raise PermissionDenied(
                    f"You don't have permission to {perm} this {model.__name__}"
                )

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


# Backward compatible aliases
@functools.wraps(permission_required)
def role_based_permission(perm):
    """Alias for permission_required for clarity"""
    return permission_required(perm)


def roles_required(allowed_roles):
    """
    Coarse role-name gate.  Checks that the authenticated user has a
    Membership whose role.name is in `allowed_roles`.

    Use permission_required for fine-grained per-permission checks.
    Use this only where you need a simple role-name guard (e.g. "Owner only").
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            from apps.orgs.tenant_context import is_public_workspace

            user = request.user
            workspace = _resolve_workspace(request)

            if not workspace:
                raise PermissionDenied("No workspace selected")

            if is_public_workspace(workspace):
                # Public-schema context: company must be supplied via URL kwarg
                company_id = kwargs.get("company_id")
                if not company_id:
                    raise PermissionDenied("Company ID required")
                from apps.orgs.models import Company
                try:
                    workspace = Company.objects.get(id=company_id)
                except Company.DoesNotExist:
                    raise Http404("Company not found")

            try:
                membership = Membership.objects.select_related("role").get(
                    user=user, company=workspace
                )
            except Membership.DoesNotExist:
                raise PermissionDenied("Not a workspace member")

            if membership.role.name not in allowed_roles:
                raise PermissionDenied(
                    f"Role '{membership.role.name}' is not in {allowed_roles}"
                )

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


def workspace_required(view_func):
    """
    Ensures an authenticated user has a resolved (non-None) workspace.
    Raises PermissionDenied if not.  Use as the lightest membership gate.
    """
    @functools.wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        workspace = _resolve_workspace(request)
        if request.user.is_authenticated and workspace:
            return view_func(request, *args, **kwargs)
        raise PermissionDenied("Workspace required")

    return _wrapped_view
