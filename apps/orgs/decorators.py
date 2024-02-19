from django.http import HttpResponseForbidden
from apps.orgs.models import Membership,Company
from django.contrib.auth.decorators import login_required

def role_required(role_name):
    def decorator(view_func):
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            user = request.user
            company_id = kwargs.get('company_id')  # Assuming tenant is passed as a keyword argument to the view
            company = Company.objects.get(id=company_id)
            try:
                membership = Membership.objects.get(user=user, company=company)
                if membership.role.name != role_name:
                    return HttpResponseForbidden()
            except Membership.DoesNotExist:
                return HttpResponseForbidden()
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def company_member_required(view_func):
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        company_id = kwargs.get('company_id')  # Assuming company_id is passed as a keyword argument to the view
        try:
            membership = Membership.objects.get(user=request.user, company_id=company_id)
        except Membership.DoesNotExist:
            return HttpResponseForbidden()
        return view_func(request, *args, **kwargs)
    return _wrapped_view