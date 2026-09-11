"""Team members views; existing services enforce membership policy."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.orgs.decorators_v2 import permission_required
from apps.orgs.forms import MembershipForm
from apps.orgs.models import Company, Membership, Role
from apps.orgs.services import control_plane
from apps.orgs.services.membership_capacity import get_workspace_seat_capacity_snapshot
from apps.orgs.services import role_policy
from apps.orgs.tenant_context import resolve_request_workspace
from apps.orgs.web.access_helpers import _assert_workspace_access


@login_required
@permission_required("team_remove")
@require_POST
def team_remove_member(request, workspace_id=None, membership_id=None, company_id=None):
    """
    Remove team member from workspace.
    Requires team_remove permission (Owner only).
    """
    workspace_id = workspace_id or company_id
    if workspace_id is None:
        raise Http404("Workspace ID is required")

    company = get_object_or_404(Company, id=workspace_id)
    _assert_workspace_access(
        request,
        company,
        required_permissions={"team_remove"},
        allow_platform_admin=True,
    )

    membership = get_object_or_404(Membership, id=membership_id, company=company)

    is_self_leave = membership.user == request.user
    try:
        control_plane.remove_membership(
            membership=membership,
            actor=request.user,
            request=request,
        )
    except PermissionDenied as exc:
        messages.error(request, str(exc))
        return redirect("workspace_detail", workspace_id=workspace_id)

    # If removed member had this workspace selected, clear stale selection.
    if hasattr(membership.user, "profile") and membership.user.profile.workspace == company:
        membership.user.profile.workspace = None
        membership.user.profile.save(update_fields=["workspace"])

    if is_self_leave:
        messages.success(request, "You have left the workspace.")
        return redirect("workspace_selector")

    return redirect("workspace_list")  # Redirect to the list of workspaces


@login_required
@permission_required("team_change_role")
def team_change_role(request, workspace_id=None, membership_id=None, company_id=None):
    """
    Change team member's role.
    Requires team_change_role permission (Owner only).
    """
    workspace_id = workspace_id or company_id
    if workspace_id is None:
        raise Http404("Workspace ID is required")

    company = get_object_or_404(Company, id=workspace_id)
    _assert_workspace_access(
        request,
        company,
        required_permissions={"team_change_role"},
        allow_platform_admin=True,
    )

    membership = get_object_or_404(Membership, id=membership_id, company=company)
    roles = role_policy.allowed_invitation_roles(actor=request.user, workspace=company)

    if request.method in ["POST", "PATCH"]:
        role_id = request.POST.get("role")
        role = get_object_or_404(Role, id=role_id)

        try:
            control_plane.change_membership_role(
                membership=membership,
                new_role=role,
                actor=request.user,
                request=request,
            )
        except ValidationError as exc:
            messages.error(request, str(exc))
            if request.htmx:
                return JsonResponse(
                    {"success": False, "error": str(exc)},
                    status=400,
                )
            return redirect("workspace_detail", workspace_id=workspace_id)
        except PermissionDenied as exc:
            messages.error(request, str(exc))
            if request.htmx:
                return JsonResponse(
                    {"success": False, "error": str(exc)},
                    status=400,
                )
            return redirect("workspace_detail", workspace_id=workspace_id)

        if request.htmx:
            return JsonResponse({"success": True, "role": role.name})
        return redirect("workspace_detail", workspace_id=workspace_id)
    else:
        form = MembershipForm(instance=membership)
    return render(
        request,
        "company/partials/role_form.html",
        {"form": form, "membership": membership, "company": company, "roles": roles},
    )


@login_required
def membership_list(request, workspace_id=None):
    if workspace_id is not None:
        workspace = get_object_or_404(Company, id=workspace_id)
    else:
        workspace = resolve_request_workspace(request, include_public=False)

    if not workspace:
        messages.info(request, "Select a workspace to view team members.")
        return redirect("workspace_selector")

    try:
        access = _assert_workspace_access(
            request,
            workspace,
            required_permissions={"team_list"},
            allow_platform_admin=True,
        )
    except PermissionDenied:
        messages.error(request, "You do not have permission to view team members.")
        return redirect("workspace_selector")

    memberships = (
        Membership.objects.select_related("user", "role", "company")
        .filter(company=workspace)
        .order_by("role__name", "user__username")
    )

    context = {
        "workspace": workspace,
        "memberships": memberships,
        "workspace_count": memberships.count(),
        "seat_capacity": get_workspace_seat_capacity_snapshot(workspace=workspace),
        "can_change_role": (workspace.owner_id == request.user.pk or access["access"].platform_override),
        "can_remove_member": (workspace.owner_id == request.user.pk or access["access"].platform_override),
    }
    return render(request, "company/membership_list.html", context)


@login_required
def my_memberships(request):
    return redirect("workspace_selector")


@login_required
def workspace_leave(request, workspace_id):
    """
    Allow any workspace member to leave a workspace themselves.
    Owners must transfer ownership before leaving.
    """
    company = get_object_or_404(Company, id=workspace_id)
    membership = get_object_or_404(Membership, user=request.user, company=company)

    if request.method == "GET":
        return render(request, "company/workspace_leave_confirm.html", {
            "company": company,
            "workspace": company,
            "membership": membership,
        })

    if request.method == "POST":
        if _is_owner_membership(membership):
            if _owner_membership_count(company) <= 1:
                messages.error(
                    request,
                    "You are the only owner. Transfer ownership to another member before leaving.",
                )
                return redirect("workspace_detail", workspace_id=workspace_id)
            messages.error(
                request,
                "Owner must transfer ownership before leaving the workspace.",
            )
            return redirect("workspace_detail", workspace_id=workspace_id)

        try:
            control_plane.remove_membership(
                membership=membership,
                actor=request.user,
                request=request,
            )
        except PermissionDenied as exc:
            messages.error(request, str(exc))
            return redirect("workspace_detail", workspace_id=workspace_id)

        if request.user.profile.workspace == company:
            request.user.profile.workspace = None
            request.user.profile.save(update_fields=["workspace"])

        messages.success(request, f"You have left {company.name}.")
        return redirect("workspace_selector")


def _is_owner_membership(membership):
    return role_policy.is_owner_membership(membership)


def _owner_membership_count(workspace):
    return role_policy.owner_membership_count(workspace)
