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
            workspace = (
                getattr(user.profile, "workspace", None)
                if hasattr(user, "profile")
                else None
            )

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

            # Get user's membership
            try:
                membership = Membership.objects.select_related("role").get(
                    user=user, company=workspace
                )
            except Membership.DoesNotExist:
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

            # Check if role has permission
            has_perm = membership.role.permissions.filter(codename=perm).exists()

            if not has_perm:
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
                            "role": membership.role.name,
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
            workspace = (
                getattr(user.profile, "workspace", None)
                if hasattr(user, "profile")
                else None
            )

            if not workspace:
                if raise_exception:
                    raise PermissionDenied("No workspace selected")
                return HttpResponseForbidden("No workspace selected")

            try:
                membership = Membership.objects.select_related("role").get(
                    user=user, company=workspace
                )
            except Membership.DoesNotExist:
                if raise_exception:
                    raise PermissionDenied("Not a workspace member")
                return HttpResponseForbidden("Not a workspace member")

            # Check if role has ANY of the permissions
            has_any_perm = membership.role.permissions.filter(
                codename__in=perms
            ).exists()

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
                    workspace = (
                        getattr(request.user.profile, "workspace", None)
                        if hasattr(request.user, "profile")
                        else None
                    )
                    if workspace:
                        try:
                            membership = Membership.objects.select_related("role").get(
                                user=request.user, company=workspace
                            )
                            has_global = membership.role.permissions.filter(
                                codename=perm
                            ).exists()
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
