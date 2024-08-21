from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django_tenants.utils import get_public_schema_name

from apps.orgs.decorators import company_member_required
from apps.orgs.models import Company

from .forms import ProfilePictureForm


@login_required
def upload_profile_picture(request):
    if request.method == "POST":
        form = ProfilePictureForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect("home")  # Redirect to a profile page or any other page
    else:
        form = ProfilePictureForm(instance=request.user)
    return render(request, "upload_profile_picture.html", {"form": form})


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
