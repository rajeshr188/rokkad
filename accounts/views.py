from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django_tenants.utils import get_public_schema_name

from apps.orgs.decorators import company_member_required
from apps.orgs.models import Company


@login_required
def profile(request):
    return render(request, "account/profile.html")


@login_required
def membership_list(request):
    memberships = request.user.memberships.all()
    return render(request, "account/membership_list.html", {"memberships": memberships})


@company_member_required
def switch_workspace(request, workspace_id):
    tenant = Company.objects.get(pk=workspace_id)
    # Check if the user is a member of the company
    if tenant.members.filter(id=request.user.id).exists():
        request.user.workspace = tenant
        request.user.save()
        return redirect("/")
    else:
        raise PermissionDenied


@company_member_required
def clear_workspace(request):
    public = Company.objects.get(schema_name=get_public_schema_name())
    request.user.workspace = public
    request.user.save()
    return redirect("/")
