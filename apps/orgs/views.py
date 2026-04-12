import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django_tenants.utils import get_public_schema_name, remove_www,schema_context
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
from .models import Company, CompanyInvitation, Domain, Membership, Role
from .registries import company_preference_registry
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


@login_required
@audit_log("COMPANY_CREATE", description="Create new company")
def workspace_create(request):
    """
    Create a new workspace.
    User becomes Owner with full permissions.
    """
    if request.method == "POST":
        form = CompanyForm(request.POST, request.FILES)
        print(f"form: {form.is_valid()}")
        if form.is_valid():
            with schema_context(get_public_schema_name()):
                company = form.save(commit=False)
                company.schema_name = company.name.lower().replace(" ", "_")
                company.creator = request.user
                company.owner = request.user
                company.save()
                domain = remove_www(request.get_host().split(":")[0]).lower()
                company_domain = f"{company.schema_name}.{domain}"
                Domain.objects.create(
                    tenant=company, domain=company_domain, is_primary=True
                )
                Membership.objects.create(
                    user=request.user,
                    company=company,
                    role=Role.objects.get(name="Owner"),
                )
                request.user.profile.set_workspace(company)

                # Log successful company creation
                AuditLog.log(
                    "COMPANY_CREATE",
                    user=request.user,
                    company=company,
                    description=f"Created company: {company.name}",
                    request=request,
                    success=True,
                )
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
    List all workspaces user has access to.
    Shows workspace cards with membership info.
    """
    companies = request.user.owned_companies.exclude(name="public").annotate(
        num_members=Count("memberships")
    )
    form = CompanyForm()
    return render(
        request, "company/company_list.html", {"companies": companies, "form": form}
    )


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

    try:
        membership = Membership.objects.select_related("role").get(
            user=request.user,
            company=company,
        )
    except Membership.DoesNotExist:
        raise PermissionDenied("Not a workspace member")

    has_view_permission = membership.role.permissions.filter(
        codename="workspace_view"
    ).exists()
    if not has_view_permission:
        raise PermissionDenied("Permission 'workspace_view' required")

    roles = Role.objects.all()
    return render(
        request, "company/company_detail.html", {"company": company, "roles": roles}
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

    company = Company.objects.get(id=workspace_id)
    if request.method == "POST":
        form = CompanyForm(request.POST, instance=company)
        if form.is_valid():
            form.save()
            AuditLog.log(
                "COMPANY_UPDATE",
                user=request.user,
                company=company,
                description=f"Updated company: {company.name}",
                request=request,
                success=True,
            )
            return redirect("workspace_list")
    else:
        form = CompanyForm(instance=company)
    return render(
        request, "company/company_form.html", {"form": form, "company": company}
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

    company = get_object_or_404(Company, id=workspace_id)

    if request.method == "GET":
        return render(
            request, "company/company_delete_confirm.html", {"company": company}
        )

    elif request.method == "POST":
        if request.user != company.owner:
            AuditLog.log(
                "COMPANY_DELETE",
                user=request.user,
                company=company,
                description=f"Unauthorized delete attempt: {company.name}",
                request=request,
                success=False,
            )
            return redirect("error_page")  # Redirect to an error page

        # Log before deletion
        AuditLog.log(
            "COMPANY_DELETE",
            user=request.user,
            company=company,
            description=f"Archived workspace: {company.name}",
            request=request,
            success=True,
        )

        company.archive()

        # Reset the user's workspace to the public schema if needed
        if getattr(request.user.profile, "workspace", None) == company:
            request.user.profile.workspace = Company.objects.get(
                schema_name=get_public_schema_name()
            )
            request.user.profile.save(update_fields=["workspace"])

        return redirect("workspace_list")


@login_required
def companyinvitations_list(request):
    invitations = CompanyInvitation.objects.filter(email=request.user.email)
    return render(
        request, "company/company_invitations_list.html", {"invitations": invitations}
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

    company = Company.objects.get(id=workspace_id)
    if request.method == "POST":
        form = CompanyInvitationForm(
            request.POST, inviter=request.user, request=request, company=company
        )
        if form.is_valid():
            invitation = form.save()
            AuditLog.log(
                "TEAM_INVITE",
                user=request.user,
                company=company,
                description=f"Invited {invitation.email} to company",
                request=request,
                success=True,
                content_object=invitation,
            )
            messages.success(request, "Invitation sent successfully")
            return redirect("invite-success-url")
        else:
            messages.error(request, "correct the errors")
    else:
        form = CompanyInvitationForm(inviter=request.user, company=company)
    return render(
        request,
        "company/invitation_form.html",
        {
            "form": form,
            "company": company,
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

    company = get_object_or_404(Company, id=workspace_id)
    membership = get_object_or_404(Membership, id=membership_id, company=company)

    # Log before deletion
    AuditLog.log(
        "TEAM_MEMBER_REMOVE",
        user=request.user,
        company=company,
        description=f"Removed member: {membership.user.email}",
        request=request,
        success=True,
        content_object=membership.user,
    )

    membership.delete()
    return redirect("workspace_list")  # Redirect to the list of workspaces


@login_required
@permission_required("team_change_role")
def team_change_role(request, workspace_id=None, membership_id=None, company_id=None):
    """
    Change team member's role.
    Requires team_change_role permission (Owner only).
    """
    print("team_change_role")
    workspace_id = workspace_id or company_id
    if workspace_id is None:
        raise Http404("Workspace ID is required")

    company = get_object_or_404(Company, id=workspace_id)
    membership = get_object_or_404(Membership, id=membership_id, company=company)
    roles = Role.objects.all()

    if request.method in ["POST", "PATCH"]:
        old_role = membership.role.name
        role_id = request.POST.get("role")
        role = get_object_or_404(Role, id=role_id)
        membership.role = role
        membership.save()

        # Log role change
        AuditLog.log(
            "TEAM_ROLE_CHANGE",
            user=request.user,
            company=company,
            description=f"Changed {membership.user.email} role from {old_role} to {role.name}",
            request=request,
            success=True,
            content_object=membership.user,
            data={"old_role": old_role, "new_role": role.name},
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
    memberships = request.user.memberships.all()
    return render(request, "company/membership_list.html", {"memberships": memberships})


@login_required
def profile(request):
    return render(request, "company/profile.html")


@login_required
def invitation_delete(request, invitation_id):
    invitation = get_object_or_404(CompanyInvitation, id=invitation_id)

    # Check if the user has the permission to delete the invitation
    if request.user != invitation.inviter:
        return redirect("error_page")  # Redirect to an error page

    invitation.delete()

    # return redirect(
    #     "orgs_companyinvitations_list"
    # )  # Redirect to the list of invitations
    return HttpResponse("Invitation deleted successfully")


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
    selected_workspace = resolve_request_workspace(
        request,
        include_public=True,
        allow_profile_fallback=True,
    )
    if selected_workspace and selected_workspace.schema_name != "public":
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
        CompanyInvitation.objects.filter(
            email=user.email,
            accepted=False,
        )
        .select_related("company", "role")
        .order_by("-created")
    )

    # Filter out expired invitations
    valid_invitations = [inv for inv in pending_invitations if not inv.key_expired()]

    context = {
        "workspaces": memberships,
        "pending_invitations": valid_invitations,
        "current_workspace": selected_workspace,
        "workspace_count": memberships.count(),
        "invitation_count": len(valid_invitations),
        "has_workspaces": memberships.exists(),
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

            if action == "accept":
                # Check if user already a member
                existing = Membership.objects.filter(
                    user=user, company=invitation.company
                ).exists()

                if not existing:
                    # Create membership
                    Membership.objects.create(
                        user=user,
                        company=invitation.company,
                        role=invitation.role,
                    )

                # Mark invitation as accepted
                invitation.accept(request)

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
                # Simply leave invitation unaccepted (no rejection mechanism in model)
                # Invitation will expire after 7 days

                messages.info(
                    request, f"Declined invitation from {invitation.company.name}"
                )

                return redirect("workspace_list")

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

    try:
        workspace = Company.objects.get(id=workspace_id, is_deleted=False)

        # Verify user is member
        user.memberships.get(company=workspace)

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

        return redirect("workspace_dashboard", workspace_id=workspace.id)

    except (Company.DoesNotExist, Membership.DoesNotExist):
        messages.error(request, "Workspace not found or access denied")
        return redirect("workspace_selector")


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

    # Get workspace and verify membership
    workspace = get_object_or_404(Company, id=workspace_id, is_deleted=False)

    try:
        membership = request.user.memberships.get(company=workspace)
    except Membership.DoesNotExist:
        messages.error(request, "Access denied to this workspace")
        return redirect("workspace_list")

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
    context["role"] = membership.role

    # Check if user can view detailed metrics (Owner/Admin)
    context["can_view"] = membership.role.name in ["Owner", "Admin"]

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
        accepted=False
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
