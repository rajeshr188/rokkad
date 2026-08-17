from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.orgs.tenant_context import resolve_preferred_workspace

from .forms import UserProfileForm
from .models import UserProfile

# views.py


@login_required
def userprofile_detail(request, pk):
    userprofile = get_object_or_404(UserProfile, pk=pk, user=request.user)
    return render(
        request, "account/userprofile_detail.html", {"userprofile": userprofile}
    )


@login_required
def userprofile_update(request, pk):
    userprofile = get_object_or_404(UserProfile, pk=pk, user=request.user)
    if request.method == "POST":
        form = UserProfileForm(
            request.POST,
            request.FILES,
            instance=userprofile,
            user=request.user,
        )
        if form.is_valid():
            form.save()
            return redirect("userprofile_detail", pk=userprofile.pk)
    else:
        form = UserProfileForm(instance=userprofile, user=request.user)
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
@require_POST
def switch_workspace(request, workspace_id):
    """
    Backward-compatible alias for canonical workspace switch view.
    """
    from apps.orgs.views import workspace_select

    return workspace_select(request, workspace_id=workspace_id)


@login_required
@require_POST
def clear_workspace(request):
    """Clear the user's selected Workspace navigation preference."""

    preferred_workspace = resolve_preferred_workspace(request.user)
    request.user.profile.set_workspace(None)

    from apps.orgs.models import AuditLog

    AuditLog.log(
        "WORKSPACE_CLEAR",
        user=request.user,
        company=preferred_workspace,
        description=f'Cleared workspace preference (was: {preferred_workspace.name if preferred_workspace else "None"})',
        request=request,
        success=True,
    )
    messages.success(request, "Workspace cleared. You can now select a different one.")
    return redirect("workspace_selector")


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

    preferred_workspace = resolve_preferred_workspace(user)

    # Get all user's workspaces (memberships)
    memberships = (
        user.memberships.select_related("company", "role")
        .filter(company__lifecycle_state=Company.LifecycleState.ACTIVE)
        .order_by("-company__updated_at")
    )

    context = {
        "preferred_workspace": preferred_workspace,
        "memberships": memberships,
        "total_workspaces": memberships.count(),
    }

    return render(request, "account/workspace_management.html", context)


@login_required
@require_POST
def reset_workspace(request):
    """
    Backward-compatible alias for clear workspace.
    """
    return clear_workspace(request)
