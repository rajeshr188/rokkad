import logging
from types import SimpleNamespace

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django_tenants.utils import get_public_schema_name
from dynamic_preferences.views import PreferenceFormView
from invitations.views import AcceptInvite
from render_block import render_block_to_string

from .audit import AuditLog, audit_log
from .decorators_v2 import permission_required
from .forms import (
    CompanyForm,
    CompanyInvitationForm,
    MembershipForm,
    company_preference_form_builder,
)
from .models import Company, CompanyInvitation, Membership, Role
from .permissions import get_effective_permissions, is_platform_admin
from .registries import company_preference_registry
from .services import control_plane
from .tenant_context import resolve_request_workspace

# Create your views here.
logger = logging.getLogger(__name__)
User = get_user_model()


def has_permission(user, tenant, permission_codename):
    try:
        # Get the user's role in the tenant
        membership = Membership.objects.get(user=user, tenant=tenant)
        role = membership.role
    except Membership.DoesNotExist:
        # The user does not have a role in the tenant
        return False

    # Check if the role has the permission
    return role.permissions.filter(codename=permission_codename).exists()


def has_role(user, tenant, role_name):
    try:
        # Get the user's role in the tenant
        membership = Membership.objects.get(user=user, tenant=tenant)
        role = membership.role
    except Membership.DoesNotExist:
        # The user does not have a role in the tenant
        return False

    # Check if the role has the permission
    return role.name == role_name


def _assert_workspace_access(
    request,
    workspace,
    required_permissions=None,
    allow_platform_admin=True,
):
    """Validate workspace access and return normalized access context."""
    required_permissions = set(required_permissions or [])

    if allow_platform_admin and is_platform_admin(request.user):
        effective_perms = get_effective_permissions(request.user, workspace)
        return {
            "membership": None,
            "role_name": "Superuser",
            "effective_permissions": effective_perms,
        }

    membership = (
        Membership.objects.select_related("role")
        .filter(user=request.user, company=workspace)
        .first()
    )
    if membership is None:
        raise PermissionDenied("You are not a member of this workspace")

    effective_perms = get_effective_permissions(request.user, workspace)
    missing_permissions = required_permissions - effective_perms
    if missing_permissions:
        raise PermissionDenied(
            f"Missing required workspace permissions: {', '.join(sorted(missing_permissions))}"
        )

    role_name = membership.role.name if membership.role else "Member"
    return {
        "membership": membership,
        "role_name": role_name,
        "effective_permissions": effective_perms,
    }


def _is_owner_membership(membership):
    return bool(
        membership
        and getattr(membership, "role", None)
        and getattr(membership.role, "name", "").lower() == "owner"
    )


def _owner_membership_count(workspace):
    return Membership.objects.filter(company=workspace, role__name__iexact="owner").count()


def _assert_owner_access(request, workspace, allow_platform_admin=True):
    """Allow only workspace owner (or platform admin when enabled)."""
    access = _assert_workspace_access(
        request,
        workspace,
        required_permissions=set(),
        allow_platform_admin=allow_platform_admin,
    )
    if access["role_name"].lower() != "owner":
        raise PermissionDenied("Only workspace owners can access this page")
    return access


@login_required
@audit_log("COMPANY_CREATE", description="Create new company")
def workspace_create(request):
    """
    Create a new workspace.
    User becomes Owner with full permissions.
    """
    if request.method == "POST":
        form = CompanyForm(request.POST, request.FILES)
        if form.is_valid():
            company = control_plane.create_workspace_from_form(
                form=form,
                user=request.user,
                request=request,
            )
            request.user.profile.set_workspace(company)
            return redirect("workspace_list")
        else:
            # Handle form errors
            return render(request, "company/company_form.html", {"form": form})
    else:
        form = CompanyForm()
    return render(request, "company/company_form.html", {"form": form})


@login_required
def workspace_list(request):
    """
    Legacy workspace listing endpoint.

    Canonical entrypoint is workspace_selector. Keep this route as a
    compatibility alias to avoid breaking old links.
    """
    return redirect("workspace_selector")


@login_required
def workspace_detail(request, workspace_id=None, company_id=None):
    """
    Display workspace details including team members and invitations.
    Requires workspace_view permission.
    """
    workspace_id = workspace_id or company_id
    if workspace_id is None:
        raise Http404("Workspace ID is required")

    company = get_object_or_404(Company, id=workspace_id)
    if company.is_deleted:
        raise Http404("Company not found")

    _assert_workspace_access(
        request,
        company,
        required_permissions={"workspace_view"},
        allow_platform_admin=True,
    )

    roles = Role.objects.all()
    return render(
        request, "company/company_detail.html", {"company": company, "roles": roles, "workspace": company}
    )


@login_required
@permission_required("workspace_edit")
@audit_log("COMPANY_UPDATE", description="Update company settings")
def workspace_update(request, workspace_id=None, company_id=None):
    """
    Update workspace settings.
    Requires workspace_edit permission (Owner/Admin).
    """
    workspace_id = workspace_id or company_id
    if workspace_id is None:
        raise Http404("Workspace ID is required")

    company = get_object_or_404(Company, id=workspace_id, is_deleted=False)
    _assert_workspace_access(
        request,
        company,
        required_permissions={"workspace_edit"},
        allow_platform_admin=True,
    )
    _assert_owner_access(request, company, allow_platform_admin=True)

    if request.method == "POST":
        form = CompanyForm(request.POST, instance=company)
        if form.is_valid():
            control_plane.save_workspace_update_form(
                form=form,
                actor=request.user,
                request=request,
            )
            return redirect("workspace_list")
    else:
        form = CompanyForm(instance=company)
    return render(
        request, "company/company_form.html", {"form": form, "company": company, "workspace": company}
    )


@login_required
@permission_required("workspace_delete")
def workspace_delete(request, workspace_id=None, company_id=None):
    """
    Delete workspace (Owner only).
    Requires workspace_delete permission.
    """
    workspace_id = workspace_id or company_id
    if workspace_id is None:
        raise Http404("Workspace ID is required")

    company = get_object_or_404(Company, id=workspace_id, is_deleted=False)
    _assert_workspace_access(
        request,
        company,
        required_permissions={"workspace_delete"},
        allow_platform_admin=True,
    )

    if request.method == "GET":
        return render(
            request, "company/company_delete_confirm.html", {"company": company, "workspace": company}
        )

    elif request.method == "POST":
        if request.user != company.owner and not is_platform_admin(request.user):
            AuditLog.log(
                "COMPANY_DELETE",
                user=request.user,
                company=company,
                description=f"Unauthorized delete attempt: {company.name}",
                request=request,
                success=False,
            )
            return redirect("error_page")  # Redirect to an error page

        control_plane.archive_workspace(
            company=company,
            actor=request.user,
            request=request,
        )

        # Reset the user's workspace to the public schema if needed
        if getattr(request.user.profile, "workspace", None) == company:
            request.user.profile.workspace = Company.objects.get(
                schema_name=get_public_schema_name()
            )
            request.user.profile.save(update_fields=["workspace"])

        return redirect("workspace_list")


@login_required
def companyinvitations_list(request):
    workspace = resolve_request_workspace(
        request,
        include_public=False,
        allow_profile_fallback=True,
    )

    if workspace is not None:
        _assert_workspace_access(
            request,
            workspace,
            required_permissions={"team_invite"},
            allow_platform_admin=True,
        )

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

    company = get_object_or_404(Company, id=workspace_id, is_deleted=False)
    _assert_workspace_access(
        request,
        company,
        required_permissions={"team_invite"},
        allow_platform_admin=True,
    )

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
                return redirect("team_invite_success")
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
            "url": reverse("team_invite", kwargs={"workspace_id": workspace_id}),
        },
    )


@login_required
def invite_success(request):
    return render(request, "company/invite_success.html")


@method_decorator(login_required, name="dispatch")
@method_decorator(permission_required("workspace_settings"), name="dispatch")
class CompanyPreferenceBuilder(PreferenceFormView):
    template_name = "company/company_preferences.html"
    title = "Company Preferences"

    def dispatch(self, request, *args, **kwargs):
        workspace_id = kwargs.get("workspace_id")
        if workspace_id is None:
            raise Http404("Workspace ID is required")

        workspace = get_object_or_404(Company, id=workspace_id, is_deleted=False)
        _assert_workspace_access(
            request,
            workspace,
            required_permissions={"workspace_settings"},
            allow_platform_admin=True,
        )
        _assert_owner_access(request, workspace, allow_platform_admin=True)

        return super().dispatch(request, *args, **kwargs)

    def get_section(self):
        """Get section from URL parameter, default to showing all"""
        return self.request.GET.get("section", None)

    def get_success_url(self):
        section = self.get_section()
        workspace_id = self.kwargs.get("workspace_id")

        if workspace_id:
            base_url = reverse_lazy(
                "workspace_preferences", kwargs={"workspace_id": workspace_id}
            )
        else:
            base_url = reverse_lazy("company-preferences")

        if section:
            return f"{base_url}?section={section}"
        return base_url

    def get_form_class(self):
        section = self.get_section()
        preferences = []

        if section:
            # Filter preferences by section
            registry = company_preference_registry
            if section in registry:
                preferences = list(registry[section].values())

        return company_preference_form_builder(
            instance=resolve_request_workspace(self.request), Preferences=preferences
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get all available sections
        registry = company_preference_registry
        context["sections"] = [
            {"name": section, "obj": registry.section_objects.get(section)}
            for section in registry.sections()
        ]
        context["current_section"] = self.get_section()
        context["workspace_id"] = self.kwargs.get("workspace_id")
        return context

    def render_to_response(self, context, **response_kwargs):
        # Check if the request is made via HTMX
        if self.request.headers.get("HX-Request", False):
            # Render only the specific block content for HTMX requests
            content = render_block_to_string(
                "company/company_preferences.html", "content", context, self.request
            )
            return HttpResponse(content)
        else:
            # Proceed with the normal flow for non-HTMX requests
            return super().render_to_response(context, **response_kwargs)


@login_required
@permission_required("team_remove")
def team_remove_member(request, workspace_id=None, membership_id=None, company_id=None):
    """
    Remove team member from workspace.
    Requires team_remove permission (Owner only).
    """
    workspace_id = workspace_id or company_id
    if workspace_id is None:
        raise Http404("Workspace ID is required")

    company = get_object_or_404(Company, id=workspace_id, is_deleted=False)
    _assert_workspace_access(
        request,
        company,
        required_permissions={"team_remove"},
        allow_platform_admin=True,
    )

    membership = get_object_or_404(Membership, id=membership_id, company=company)

    is_self_leave = membership.user == request.user
    if _is_owner_membership(membership):
        owner_count = _owner_membership_count(company)
        if owner_count <= 1:
            messages.error(
                request,
                "Cannot remove the last owner. Transfer ownership first.",
            )
            return redirect("workspace_detail", workspace_id=workspace_id)

        if is_self_leave:
            messages.error(
                request,
                "Owner must transfer ownership before leaving the workspace.",
            )
            return redirect("workspace_detail", workspace_id=workspace_id)

    control_plane.remove_membership(
        membership=membership,
        actor=request.user,
        request=request,
    )

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

    company = get_object_or_404(Company, id=workspace_id, is_deleted=False)
    _assert_workspace_access(
        request,
        company,
        required_permissions={"team_change_role"},
        allow_platform_admin=True,
    )

    membership = get_object_or_404(Membership, id=membership_id, company=company)
    roles = Role.objects.all()

    if request.method in ["POST", "PATCH"]:
        role_id = request.POST.get("role")
        role = get_object_or_404(Role, id=role_id)

        demoting_owner = (
            _is_owner_membership(membership)
            and role.name.lower() != "owner"
        )
        if demoting_owner and _owner_membership_count(company) <= 1:
            messages.error(
                request,
                "Cannot demote the last owner. Transfer ownership first.",
            )
            if request.htmx:
                return JsonResponse(
                    {"success": False, "error": "last_owner_cannot_be_demoted"},
                    status=400,
                )
            return redirect("workspace_detail", workspace_id=workspace_id)

        control_plane.change_membership_role(
            membership=membership,
            new_role=role,
            actor=request.user,
            request=request,
        )

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
def membership_list(request):
    workspace = resolve_request_workspace(
        request,
        include_public=False,
        allow_profile_fallback=True,
    )

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
        "can_change_role": "team_change_role" in access["effective_permissions"],
        "can_remove_member": "team_remove" in access["effective_permissions"],
    }
    return render(request, "company/membership_list.html", context)


@login_required
def my_memberships(request):
    memberships = (
        request.user.memberships.select_related("company", "role")
        .filter(company__is_deleted=False)
        .order_by("company__name")
    )

    context = {
        "memberships": memberships,
        "membership_count": memberships.count(),
        "active_workspace": resolve_request_workspace(
            request,
            include_public=False,
            allow_profile_fallback=True,
        ),
    }
    return render(request, "company/my_memberships.html", context)


@login_required
def workspace_leave(request, workspace_id):
    """
    Allow any workspace member to leave a workspace themselves.
    Owners must transfer ownership before leaving.
    """
    company = get_object_or_404(Company, id=workspace_id, is_deleted=False)
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

        control_plane.remove_membership(
            membership=membership,
            actor=request.user,
            request=request,
        )

        if request.user.profile.workspace == company:
            request.user.profile.workspace = None
            request.user.profile.save(update_fields=["workspace"])

        messages.success(request, f"You have left {company.name}.")
        return redirect("workspace_selector")


@login_required
def profile(request):
    user = request.user
    workspace = resolve_request_workspace(
        request,
        include_public=False,
        allow_profile_fallback=True,
    )

    memberships = (
        user.memberships.select_related("company", "role")
        .filter(company__is_deleted=False)
        .order_by("company__name")
    )
    pending_invitations = CompanyInvitation.pending_queryset().filter(
        email=user.email
    ).count()

    context = {
        "workspace": workspace,
        "memberships": memberships,
        "workspace_count": memberships.count(),
        "pending_invitation_count": pending_invitations,
    }
    return render(request, "company/profile.html", context)


@login_required
def account_settings(request):
    return render(request, "company/account_settings.html")


@login_required
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

    return redirect("team_invitations_list")


from io import StringIO

from django.core.management import call_command
from django.views import View


class BackupSchemaView(View):
    def get(self, request, *args, **kwargs):
        schema_name = request.GET.get("schema_name")
        if not schema_name:
            return JsonResponse(
                {"status": "error", "message": "schema_name parameter is required"},
                status=400,
            )

        out = StringIO()
        try:
            call_command("backup", schema_name, stdout=out)
            response = {"status": "success", "message": out.getvalue()}
        except Exception as e:
            response = {"status": "error", "message": str(e)}
        return JsonResponse(response)


class BackupDatabaseView(View):
    def get(self, request, *args, **kwargs):
        out = StringIO()
        try:
            call_command("backup", stdout=out)
            response = {"status": "success", "message": out.getvalue()}
        except Exception as e:
            response = {"status": "error", "message": str(e)}
        return JsonResponse(response)


# ============================================================================
# WORKSPACE SELECTION & MANAGEMENT VIEWS
# ============================================================================


@login_required
def workspace_selector(request):
    """
    Workspace selection page - shows user's available workspaces.

    Displays:
    - User's available workspaces with membership info
    - Pending invitations
    - Quick actions (create workspace)

    Redirects to workspace_dashboard if user already has valid selected workspace.
    """
    user = request.user
    profile = user.profile

    # Get user's workspace memberships
    memberships = (
        user.memberships.select_related("company", "role")
        .filter(company__is_deleted=False)
        .order_by("-company__updated_at")
    )

    # If user has a valid selected workspace, take them directly to workspace dashboard
    # unless ?show_all=1 is passed (e.g. from "Back to Workspaces" link)
    selected_workspace = resolve_request_workspace(
        request,
        include_public=True,
        allow_profile_fallback=True,
    )
    if selected_workspace and selected_workspace.schema_name != "public" and not request.GET.get("show_all"):
        try:
            # Verify membership still active
            memberships.get(company=selected_workspace)
            return redirect("workspace_dashboard", workspace_id=selected_workspace.id)
        except Membership.DoesNotExist:
            # Workspace is no longer valid, clear it
            profile.workspace = None
            profile.save()

    # Get pending invitations
    pending_invitations = (
        CompanyInvitation.pending_queryset().filter(
            email=user.email,
        )
        .select_related("company", "role")
        .order_by("-created")
    )

    # Filter out expired invitations
    valid_invitations = [inv for inv in pending_invitations if not inv.key_expired()]

    # Count outgoing pending invitations sent by this user
    sent_invitations_count = CompanyInvitation.objects.filter(
        inviter=user,
        status=CompanyInvitation.Status.PENDING,
    ).count()

    context = {
        "workspaces": memberships,
        "pending_invitations": valid_invitations,
        "current_workspace": selected_workspace,
        "workspace_count": memberships.count(),
        "invitation_count": len(valid_invitations),
        "has_workspaces": memberships.exists(),
        "sent_invitations_count": sent_invitations_count,
    }

    return render(request, "company/workspace_home.html", context)


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
                id=invitation_id, email=user.email
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
                control_plane.accept_invitation(
                    invitation=invitation,
                    user=user,
                    request=request,
                )

                # Set as active workspace
                user.profile.workspace = invitation.company
                user.profile.save()

                messages.success(
                    request,
                    f"✅ Added to {invitation.company.name} as {invitation.role.name}",
                )

                return redirect(
                    "workspace_dashboard", workspace_id=invitation.company.id
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


@login_required
def workspace_select(request, workspace_id):
    """
    Select a workspace to work in.
    Sets the selected workspace in UserProfile and redirects to company dashboard.
    """
    user = request.user

    workspace = Company.objects.filter(id=workspace_id, is_deleted=False).first()
    if workspace is None:
        messages.error(request, "Workspace not found")
        return redirect("workspace_selector")

    try:
        _assert_workspace_access(request, workspace, allow_platform_admin=True)
    except PermissionDenied:
        messages.error(request, "Workspace not found or access denied")
        return redirect("workspace_selector")

    # Set as active workspace
    user.profile.set_workspace(workspace)

    AuditLog.log(
        "WORKSPACE_SWITCH",
        user=user,
        company=workspace,
        description=f"Switched to workspace: {workspace.name}",
        request=request,
        success=True,
    )

    messages.success(request, f"Switched to {workspace.name}")

    next_url = request.GET.get("next")
    if next_url and next_url.startswith("/"):
        return redirect(next_url)
    return redirect("workspace_dashboard", workspace_id=workspace.id)


def subscription_required(view_func):
    """
    Decorator to ensure workspace has active subscription.
    Redirects to subscription dashboard if subscription missing or expired.
    """

    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("account_login")

        workspace = resolve_request_workspace(request)
        if not workspace:
            return redirect("workspace_list")

        # Check subscription
        try:
            subscription = workspace.subscription

            if not subscription.is_active:
                messages.warning(
                    request, "Subscription expired. Please renew to continue."
                )
                return redirect("subscriptions:dashboard")

            # Warn if due soon (7 days or less)
            if (
                subscription.end_date
                and (subscription.end_date - timezone.now()).days <= 7
            ):
                messages.warning(
                    request,
                    f"Subscription renews in {(subscription.end_date - timezone.now()).days} days",
                )

        except AttributeError:
            # No subscription attached
            messages.warning(
                request, "No active subscription found. Please set up billing."
            )
            return redirect("subscriptions:dashboard")

        return view_func(request, *args, **kwargs)

    return wrapper


# ============================================================================
# WORKSPACE DASHBOARD
# ============================================================================


@login_required
def workspace_dashboard(request, workspace_id):
    """
    Main workspace dashboard - shows key metrics and activity.

    Displays:
    - Loan statistics (unreleased, sunken, today's activity)
    - Customer statistics
    - Financial metrics
    - Team information

    Requires: User must be a member of the workspace (Owner/Admin/Member)

    """
    from apps.tenant_apps.contact.models import Customer
    from apps.tenant_apps.contact.services import (
        active_customers,
        get_customers_by_type,
        get_customers_by_year,
    )
    from apps.tenant_apps.girvi.models import License, GivenLoan, LoanItem, Release
    from apps.tenant_apps.girvi.services import (
        get_itemtype_averages,
        get_loans_by_year,
        get_loanamount_by_itemtype,
        get_average_loan_instance_per_day,
        get_loan_cumulative_amount,
    )
    from apps.tenant_apps.rates.models import Rate
    from django.db.models import Sum, Count, Exists, OuterRef
    from datetime import date

    # Get workspace and validate access policy.
    workspace = get_object_or_404(Company, id=workspace_id, is_deleted=False)

    try:
        access_context = _assert_workspace_access(
            request,
            workspace,
            allow_platform_admin=True,
        )
    except PermissionDenied:
        messages.error(request, "Access denied to this workspace")
        return redirect("workspace_list")

    membership = access_context["membership"]
    role_name = access_context["role_name"]
    if membership is None:
        membership = SimpleNamespace(role=SimpleNamespace(name=role_name))

    # Set as active workspace if not already
    if request.user.profile.workspace != workspace:
        request.user.profile.workspace = workspace
        request.user.profile.save()

    # Redirect to public if somehow in public schema
    if workspace.schema_name == "public":
        return redirect("dashboard")

    context = {}
    context["workspace"] = workspace
    context["membership"] = membership
    context["role"] = role_name

    # Check if user can view detailed metrics (Owner/Admin)
    context["can_view"] = role_name in ["Owner", "Admin", "Superuser"]

    # Customer statistics
    customers = Customer.objects.all()
    context["total_customers"] = customers.filter(active=True).count()
    context["item_loanamount_avg"] = get_itemtype_averages()
    context["new_customers"] = customers.only(
        "id", "firstname", "customer_type"
    ).prefetch_related("address")[:5]
    context["customer_count"] = customers.values("customer_type").annotate(
        count=Count("id")
    )

    # Loan statistics
    loan = GivenLoan.objects.for_table_display()
    released = loan.released()
    unreleased = loan.unreleased()
    sunken = unreleased
    today = date.today()

    # Today's activity
    today_loan = LoanItem.objects.filter(loan__loan_date__gte=today).aggregate(
        amount=Sum("loanamount"), interest=Sum("interest")
    )
    today_release_loans = Release.objects.filter(release_date__gte=today).values_list(
        "loan_id", flat=True
    )
    today_release = LoanItem.objects.filter(loan_id__in=today_release_loans).aggregate(
        amount=Sum("loanamount"), interest=Sum("interest")
    )
    context["today_loan"] = today_loan
    context["loan_count"] = unreleased.count()

    # Unreleased loan amounts
    due_amount_calc = LoanItem.objects.filter(loan__in=unreleased).aggregate(
        loan_amount__sum=Sum("loanamount"), total_interest__sum=Sum("interest")
    )
    context["due_amount"] = due_amount_calc
    context["total_loan_amount"] = due_amount_calc.get("loan_amount__sum") or 0
    context["total_interest"] = due_amount_calc.get("total_interest__sum") or 0

    context["assets"] = unreleased.with_itemwise_amounts().total_itemwise_loanamount()
    context["loanbyitemtype"] = get_loanamount_by_itemtype()

    # Weight statistics
    weight_stats = unreleased.with_metal_weights().aggregate(
        gold=Sum("gold_weight"),
        silver=Sum("silver_weight"),
        bronze=Sum("bronze_weight"),
        pure_gold=Sum("pure_gold_weight"),
        pure_silver=Sum("pure_silver_weight"),
        pure_bronze=Sum("pure_bronze_weight"),
    )
    context["weight"] = (
        (weight_stats.get("gold") or 0)
        + (weight_stats.get("silver") or 0)
        + (weight_stats.get("bronze") or 0)
    )
    context["pure_weight"] = (
        (weight_stats.get("pure_gold") or 0)
        + (weight_stats.get("pure_silver") or 0)
        + (weight_stats.get("pure_bronze") or 0)
    )

    # Current value statistics
    value_stats = (
        unreleased.with_metal_weights()
        .with_current_value()
        .aggregate(total_current=Sum("total_current_value"))
    )
    context["current_value"] = value_stats.get("total_current") or 0

    # Itemwise value statistics
    itemwise_stats = (
        unreleased.with_itemwise_amounts()
        .with_current_value()
        .aggregate(
            gold=Sum("gold_value"),
            silver=Sum("silver_value"),
            bronze=Sum("bronze_value"),
        )
    )
    context["itemwise_value"] = itemwise_stats
    context["total_current_value"] = value_stats.get("total_current") or 0

    # Sunken loan statistics
    context["sunken"] = {}
    context["sunken"]["loan_count"] = sunken.count()
    context["sunken"]["total_loan_amount"] = sunken.total_loanamount()
    context["sunken"][
        "assets"
    ] = sunken.with_itemwise_amounts().total_itemwise_loanamount()

    # Sunken weight statistics
    sunken_weight_stats = sunken.with_metal_weights().aggregate(
        gold=Sum("gold_weight"),
        silver=Sum("silver_weight"),
        bronze=Sum("bronze_weight"),
        pure_gold=Sum("pure_gold_weight"),
        pure_silver=Sum("pure_silver_weight"),
        pure_bronze=Sum("pure_bronze_weight"),
    )
    context["sunken"]["weight"] = (
        (sunken_weight_stats.get("gold") or 0)
        + (sunken_weight_stats.get("silver") or 0)
        + (sunken_weight_stats.get("bronze") or 0)
    )

    # Sunken loan amounts
    sunken_amount_calc = LoanItem.objects.filter(loan__in=sunken).aggregate(
        loan_amount__sum=Sum("loanamount"), total_interest__sum=Sum("interest")
    )
    context["sunken"]["due_amount"] = sunken_amount_calc

    # Sunken value statistics
    sunken_value_stats = (
        sunken.with_metal_weights()
        .with_current_value()
        .aggregate(total_current=Sum("total_current_value"))
    )
    context["sunken"]["current_value"] = sunken_value_stats.get("total_current") or 0

    # Sunken itemwise values
    sunken_itemwise_stats = (
        sunken.with_itemwise_amounts()
        .with_current_value()
        .aggregate(
            gold=Sum("gold_value"),
            silver=Sum("silver_value"),
            bronze=Sum("bronze_value"),
        )
    )
    context["sunken"]["itemwise_value"] = sunken_itemwise_stats
    context["sunken"]["total_current_value"] = (
        sunken_value_stats.get("total_current") or 0
    )
    context["sunken"]["total_interest"] = (
        sunken_amount_calc.get("total_interest__sum") or 0
    )
    context["sunken"]["pure_weight"] = (
        (sunken_weight_stats.get("pure_gold") or 0)
        + (sunken_weight_stats.get("pure_silver") or 0)
        + (sunken_weight_stats.get("pure_bronze") or 0)
    )

    # Loan progress
    try:
        context["loan_progress"] = round(released.count() / loan.count() * 100, 2)
    except ZeroDivisionError:
        context["loan_progress"] = 0.0

    # Additional analytics
    context["loan_data_by_year"] = get_loans_by_year()
    context["customer_data_by_year"] = get_customers_by_year()
    context["customer_data_by_type"] = get_customers_by_type()
    context["active_customers"] = active_customers()
    context["avg_loan_per_day"] = get_average_loan_instance_per_day()

    # Max loans by customer
    context["maxloans"] = (
        Customer.objects.filter(
            ~Exists(Release.objects.filter(loan__borrower=OuterRef("pk")))
        )
        .annotate(
            num_loans=Count("loans_received", distinct=True),
            sum_loans=Sum("loans_received__loanitems__loanamount"),
            tint=Sum("loans_received__loanitems__interest"),
        )
        .values("firstname", "num_loans", "sum_loans", "tint")
        .order_by("-num_loans", "sum_loans", "tint")
    )
    context["loan_cumsum"] = list(get_loan_cumulative_amount())

    # License data
    licenses = License.objects.all()
    license_data = [license.get_unreleased_loan_data() for license in licenses]
    context["license_data"] = license_data

    # Team information
    context["team_count"] = workspace.memberships.count()
    context["pending_invitations"] = workspace.invitations.filter(
        status=CompanyInvitation.Status.PENDING,
        accepted=False,
    ).count()

    # Current metal rates
    context["gold_rate"] = (
        Rate.objects.filter(metal=Rate.Metal.GOLD, purity=Rate.Purity.K24)
        .order_by("-timestamp")
        .first()
    )
    context["silver_rate"] = (
        Rate.objects.filter(metal=Rate.Metal.SILVER)
        .order_by("-timestamp")
        .first()
    )

    # Breadcrumb context
    context["breadcrumb_items"] = [
        {"name": "Dashboard", "url": "dashboard"},
        {"name": workspace.name, "url": None},
    ]

    return render(request, "company/workspace_dashboard.html", context)
