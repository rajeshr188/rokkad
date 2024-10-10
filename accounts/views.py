from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django_tenants.utils import get_public_schema_name

from apps.orgs.decorators import company_member_required
from apps.orgs.models import Company

from .forms import ProfilePictureForm, SwitchWorkspaceForm, UserProfileForm
from .models import UserProfile

# views.py


def userprofile_detail(request, pk):
    userprofile = get_object_or_404(UserProfile, pk=pk)
    return render(
        request, "account/userprofile_detail.html", {"userprofile": userprofile}
    )


def userprofile_update(request, pk):
    userprofile = get_object_or_404(UserProfile, pk=pk)
    if request.method == "POST":
        form = UserProfileForm(request.POST, request.FILES, instance=userprofile)
        if form.is_valid():
            form.save()
            return redirect("userprofile_detail", pk=userprofile.pk)
    else:
        form = UserProfileForm(instance=userprofile)
    return render(request, "account/userprofile_form.html", {"form": form})


# not relevant since userprofile
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


@login_required
def switch_workspace(request, workspace_id):
    tenant = get_object_or_404(Company, id=workspace_id)

    # Check if the user is a member of the company
    if tenant.members.filter(id=request.user.id).exists():
        request.user.profile.workspace = tenant
        request.user.profile.save()
        return redirect("/")
    else:
        raise PermissionDenied


# @login_required
# def switch_workspace(request):
#     if request.method == "POST":
#         form = SwitchWorkspaceForm(request.POST)
#         if form.is_valid():
#             workspace_id = form.cleaned_data['workspace_id']
#             tenant = get_object_or_404(Company, id=workspace_id)

#             # Check if the user is a member of the company
#             if tenant.members.filter(id=request.user.id).exists():
#                 request.user.workspace = tenant
#                 request.user.save()
#                 return redirect("/")
#             else:
#                 raise PermissionDenied


@login_required
def clear_workspace(request):
    public = Company.objects.get(schema_name=get_public_schema_name())
    request.user.profile.workspace = public
    request.user.profile.save()
    return redirect("/")
