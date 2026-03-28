from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django_tenants.utils import get_public_schema_name

from apps.orgs.models import Company
from apps.orgs.tenant_context import resolve_request_workspace

from .forms import UserProfileForm
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
# @login_required
# def upload_profile_picture(request):
#     if request.method == "POST":
#         form = ProfilePictureForm(request.POST, request.FILES, instance=request.user)
#         if form.is_valid():
#             form.save()
#             return redirect("home")  # Redirect to a profile page or any other page
#     else:
#         form = ProfilePictureForm(instance=request.user)
#     return render(request, "upload_profile_picture.html", {"form": form})


@login_required
def switch_workspace(request, workspace_id):
    """
    Backward-compatible alias for canonical workspace switch view.
    """
    return redirect("workspace_select", workspace_id=workspace_id)


@login_required
def clear_workspace(request):
    """
    Clear/reset workspace to public schema.

    Allows user to:
    - Return to public (root) workspace
    - Reset workspace selection
    - Access workspace selector again
    """
    try:
        # Get public schema
        public = Company.objects.get(schema_name=get_public_schema_name())

        # Store current workspace for logging
        current_workspace = resolve_request_workspace(
            request,
            include_public=True,
            allow_profile_fallback=True,
        )

        # Reset to public workspace
        request.user.profile.set_workspace(public)

        # Log the action
        from apps.orgs.models import AuditLog

        AuditLog.log(
            "WORKSPACE_CLEAR",
            user=request.user,
            company=current_workspace,
            description=f'Cleared workspace (was: {current_workspace.name if current_workspace else "None"})',
            request=request,
            success=True,
        )

        messages.success(
            request, "Workspace cleared. You can now select a different one."
        )
        return redirect("workspace_selector")

    except Company.DoesNotExist:
        messages.error(request, "Unable to clear workspace. Please try again.")
        return redirect("dashboard")


@login_required
def workspace_management(request):
    """
    User workspace management dashboard.

    Allows user to:
    - View current active workspace
    - See all available workspaces
    - Switch between workspaces
    - Clear/reset workspace selection
    - View workspace roles/permissions
    """
    user = request.user
    profile = user.profile

    # Get active workspace
    current_workspace = resolve_request_workspace(
        request,
        include_public=True,
        allow_profile_fallback=True,
    )

    # Get all user's workspaces (memberships)
    memberships = (
        user.memberships.select_related("company", "role")
        .filter(company__is_deleted=False)
        .order_by("-company__updated_at")
    )

    context = {
        "current_workspace": current_workspace,
        "memberships": memberships,
        "total_workspaces": memberships.count(),
        "is_public": current_workspace and current_workspace.schema_name == "public",
    }

    return render(request, "account/workspace_management.html", context)


@login_required
def reset_workspace(request):
    """
    Backward-compatible alias for clear workspace.
    """
    return clear_workspace(request)
