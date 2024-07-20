from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden
from django_tenants.utils import get_public_schema_name

from apps.orgs.models import Company, Membership


def role_required(role_name):
    def decorator(view_func):
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            user = request.user
            # company = request.user.workspace

            # print(f"User: {user} Company:{company} role_required: {role_name}")
            company_id = kwargs.get(
                "company_id"
            )  # Assuming tenant is passed as a keyword argument to the view
            company = Company.objects.get(id=company_id)
            try:
                membership = Membership.objects.get(user=user, company=company)
                print(
                    f"Membership {membership} Role: {membership.role.name} {membership.role.name == role_name}"
                )
                if membership.role.name != role_name:
                    raise Http404(
                        "Need to be A Company Owner to proceed with this action."
                    )
                    # return HttpResponseForbidden()
            except Membership.DoesNotExist:
                # return HttpResponseForbidden()
                raise Http404(
                    "Need to be A member or Company Owner to proceed with this action."
                )
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


def roles_required(allowed_roles):
    def decorator(view_func):
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            user = request.user
            company = request.user.workspace

            print(f"User: {user} Company:{company} roles_required: {allowed_roles}")
            try:
                membership = Membership.objects.get(user=user, company=company)
                print(
                    f"Membership {membership} Role: {membership.role.name} {membership.role.name in allowed_roles}"
                )
                if membership.role.name not in allowed_roles:
                    raise Http404(
                        "You do not have the required role to proceed with this action."
                    )
            except Membership.DoesNotExist:
                raise Http404(
                    "You do not have the required role to proceed with this action."
                )
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


def company_member_required(view_func):
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        company = request.user.workspace
        # company_id = kwargs.get('company_id')  # Assuming company_id is passed as a keyword argument to the view
        if company and company.schema_name != get_public_schema_name():
            try:
                membership = Membership.objects.get(
                    user=request.user, company_id=company.id
                )
            except Membership.DoesNotExist:
                return HttpResponseForbidden()
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def membership_required(role_name):
    def decorator(view_func):
        @functools.wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            company = request.user.workspace
            if company and company.schema_name != get_public_schema_name():
                try:
                    membership = Membership.objects.get(
                        user=request.user, company_id=company.id
                    )
                    if membership.role != role_name:
                        return HttpResponseForbidden()
                except Membership.DoesNotExist:
                    return HttpResponseForbidden()
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


from functools import wraps

from django.core.exceptions import PermissionDenied


def workspace_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.workspace.name != "Public":
            return view_func(request, *args, **kwargs)
        else:
            raise PermissionDenied

    return _wrapped_view
