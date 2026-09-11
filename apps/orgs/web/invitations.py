"""Invitations views; existing services enforce membership policy."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.orgs.audit import audit_log
from apps.orgs.decorators_v2 import permission_required
from apps.orgs.forms import CompanyInvitationForm
from apps.orgs.models import Company, CompanyInvitation
from apps.orgs.services import control_plane
from apps.orgs.services.membership_capacity import get_workspace_seat_capacity_snapshot
from apps.orgs.tenant_context import resolve_request_workspace
from apps.orgs.web.access_helpers import _assert_workspace_access


@login_required
def companyinvitations_list(request, workspace_id=None):
    workspace = None
    if workspace_id is not None:
        workspace = get_object_or_404(Company, id=workspace_id)
    if workspace is None:
        workspace = _get_workspace_from_query(request)
    if workspace is None:
        workspace = resolve_request_workspace(request, include_public=False)

    if workspace is not None:
        _assert_workspace_access(
            request,
            workspace,
            required_permissions={"team_invite"},
            allow_platform_admin=True,
        )

    seat_capacity = None
    if isinstance(workspace, Company):
        seat_capacity = get_workspace_seat_capacity_snapshot(workspace=workspace)

    invitations = CompanyInvitation.objects.select_related(
        "company", "role", "inviter"
    ).order_by("-created")

    if workspace is not None:
        invitations = invitations.filter(company=workspace)
    else:
        invitations = invitations.filter(inviter=request.user)

    invitations_with_state = []
    for invitation in invitations:
        invitations_with_state.append(
            {
                "invitation": invitation,
                "state": invitation.lifecycle_state(),
            }
        )

    return render(
        request,
        "company/company_invitations_list.html",
        {
            "invitations": invitations_with_state,
            "current_workspace": workspace,
            "workspace": workspace,
            "seat_capacity": seat_capacity,
        },
    )


@login_required
@permission_required("team_invite")
@audit_log("TEAM_INVITE", description="Send team invitation")
def team_invite(request, workspace_id=None, company_id=None):
    """
    Send team invitation to new member.
    Requires team_invite permission (Owner/Admin).
    """
    workspace_id = workspace_id or company_id
    if workspace_id is None:
        raise Http404("Workspace ID is required")

    company = get_object_or_404(Company, id=workspace_id)
    _assert_workspace_access(
        request,
        company,
        required_permissions={"team_invite"},
        allow_platform_admin=True,
    )
    seat_capacity = get_workspace_seat_capacity_snapshot(workspace=company)

    if request.method == "POST":
        form = CompanyInvitationForm(
            request.POST, inviter=request.user, request=request, company=company
        )
        if form.is_valid():
            try:
                control_plane.send_team_invitation(
                    form=form,
                    actor=request.user,
                    company=company,
                    request=request,
                )
                messages.success(request, "Invitation sent successfully")
                return redirect(
                    "workspace_slug_settings_invitations",
                    workspace_slug=company.slug,
                )
            except (ValidationError, ValueError) as exc:
                form.add_error(None, str(exc))
                messages.error(request, "Unable to send invitation. Please review errors.")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = CompanyInvitationForm(inviter=request.user, company=company)
    return render(
        request,
        "company/invitation_form.html",
        {
            "form": form,
            "company": company,
            "workspace": company,
            "seat_capacity": seat_capacity,
            "url": reverse("team_invite", kwargs={"workspace_id": workspace_id}),
        },
    )


@login_required
def invite_success(request):
    workspace = None
    sent_invitations_url = reverse("team_invitations_list")
    workspace = _get_workspace_from_query(request)
    if workspace is not None:
        _assert_workspace_access(
            request,
            workspace,
            required_permissions={"team_invite"},
            allow_platform_admin=True,
        )
        sent_invitations_url = reverse(
            "workspace_slug_settings_invitations",
            kwargs={"workspace_slug": workspace.slug},
        )

    return render(
        request,
        "company/invite_success.html",
        {
            "workspace": workspace,
            "current_workspace": workspace,
            "sent_invitations_url": sent_invitations_url,
        },
    )


def team_accept_invitation(request, key):
    if not request.user.is_authenticated:
        accept_url = reverse("team_accept_invitation", kwargs={"key": key})
        return redirect(f"{reverse('account_login')}?next={accept_url}")

    invitation = (
        CompanyInvitation.objects.select_related("company", "role")
        .filter(key=key.lower())
        .first()
    )
    if invitation is None:
        messages.error(request, "Invitation not found.")
        return redirect("team_invitations")

    if invitation.email.casefold() != request.user.email.casefold():
        messages.error(request, "This invitation was sent to a different email address.")
        return redirect("team_invitations")

    current_state = invitation.lifecycle_state()
    if current_state == "expired":
        messages.error(request, f"Invitation from {invitation.company.name} has expired.")
        return redirect("team_invitations")

    if current_state != CompanyInvitation.Status.PENDING:
        messages.info(request, f"Invitation is already {current_state}.")
        return redirect("team_invitations")

    if request.method != "POST":
        return render(
            request,
            "company/invitation_accept_confirm.html",
            {"invitation": invitation},
        )

    try:
        control_plane.accept_invitation(
            invitation=invitation,
            user=request.user,
            request=request,
        )
    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect("team_invitations")

    if hasattr(request.user, "profile"):
        request.user.profile.workspace = invitation.company
        request.user.profile.save()

    messages.success(
        request,
        f"Added to {invitation.company.name} as {invitation.role.name}",
    )
    return redirect(
        "workspace_slug_dashboard",
        workspace_slug=invitation.company.slug,
    )


@login_required
@require_POST
def invitation_delete(request, invitation_id):
    invitation = get_object_or_404(CompanyInvitation, id=invitation_id)

    # Inviter can always revoke. Workspace admins/owners can also revoke.
    can_revoke = request.user == invitation.inviter
    if not can_revoke:
        try:
            _assert_workspace_access(
                request,
                invitation.company,
                required_permissions={"team_invite"},
                allow_platform_admin=True,
            )
            can_revoke = True
        except PermissionDenied:
            can_revoke = False

    if not can_revoke:
        messages.error(request, "You do not have permission to revoke this invitation.")
        return redirect("workspace_selector")

    control_plane.revoke_invitation(
        invitation=invitation,
        actor=request.user,
        request=request,
    )

    messages.success(request, "Invitation revoked successfully")

    if request.headers.get("HX-Request"):
        return HttpResponse("Invitation revoked successfully")

    return redirect(
        reverse(
            "workspace_slug_settings_invitations",
            kwargs={"workspace_slug": invitation.company.slug},
        )
    )


@login_required
def team_invitations(request):
    """
    Manage pending invitations to workspaces.
    Allow user to accept or decline invitations.
    """
    user = request.user

    # Get pending invitations
    pending_invitations = CompanyInvitation.objects.filter(
        email=user.email,
        status=CompanyInvitation.Status.PENDING,
        accepted=False,
    ).select_related("company", "role")

    # Filter valid (not expired)
    invitations_data = []
    for inv in pending_invitations:
        if not inv.key_expired():
            invitations_data.append(
                {
                    "invitation": inv,
                    "is_expired": False,
                }
            )

    if request.method == "POST":
        action = request.POST.get("action")
        invitation_id = request.POST.get("invitation_id")

        try:
            invitation = CompanyInvitation.objects.get(
                id=invitation_id, email__iexact=user.email
            )

            current_state = invitation.lifecycle_state()
            if current_state == "expired":
                messages.error(
                    request,
                    f"Invitation from {invitation.company.name} has expired.",
                )
                return redirect("team_invitations")

            if current_state != CompanyInvitation.Status.PENDING:
                messages.info(
                    request,
                    f"Invitation is already {current_state}.",
                )
                return redirect("team_invitations")

            if action == "accept":
                try:
                    control_plane.accept_invitation(
                        invitation=invitation,
                        user=user,
                        request=request,
                    )
                except ValidationError as exc:
                    messages.error(request, str(exc))
                    return redirect("team_invitations")

                # Set as active workspace
                user.profile.workspace = invitation.company
                user.profile.save()

                messages.success(
                    request,
                    f"✅ Added to {invitation.company.name} as {invitation.role.name}",
                )

                return redirect(
                    "workspace_slug_dashboard",
                    workspace_slug=invitation.company.slug,
                )

            elif action == "decline":
                control_plane.decline_invitation(
                    invitation=invitation,
                    actor=user,
                    request=request,
                )

                messages.info(
                    request, f"Declined invitation from {invitation.company.name}"
                )

                return redirect("team_invitations")

        except CompanyInvitation.DoesNotExist:
            messages.error(request, "Invitation not found")
            return redirect("workspace_list")

    context = {
        "invitations": invitations_data,
        "invitation_count": len(invitations_data),
    }

    return render(request, "company/workspace_invitations.html", context)


def _get_workspace_from_query(request):
    workspace_id = request.GET.get("workspace_id")
    if not workspace_id:
        return None
    if not workspace_id.isdigit():
        raise Http404("Invalid workspace ID")
    return get_object_or_404(Company, id=workspace_id)
