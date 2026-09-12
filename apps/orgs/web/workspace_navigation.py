"""Workspace navigation views; existing policy and services remain authoritative."""

from types import SimpleNamespace
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.onboarding.services import build_workspace_setup_display_state
from apps.orgs.audit import AuditLog
from apps.orgs.models import Company, CompanyInvitation
from apps.orgs.services.dashboard_selectors import get_workspace_dashboard_context
from apps.orgs.tenant_context import resolve_preferred_workspace
from apps.orgs.web.access_helpers import _assert_workspace_access


@login_required
def workspace_selector(request):
    """
    Workspace selection page - shows user's available workspaces.

    Displays:
    - User's available workspaces with membership info
    - Pending invitations
    - Quick actions (create workspace)

    Always displays the list, independently of the saved navigation preference.
    """
    user = request.user
    profile = user.profile

    # Get user's workspace memberships
    memberships = (
        user.memberships.select_related("company", "role")
        .filter(company__lifecycle_state=Company.LifecycleState.ACTIVE)
        .order_by("-company__updated_at")
    )

    selected_workspace = resolve_preferred_workspace(user)

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
@require_POST
def workspace_select(request, workspace_id):
    """
    Select a workspace to work in.
    Sets the selected workspace in UserProfile and redirects to company dashboard.
    """
    user = request.user

    workspace = Company.objects.filter(id=workspace_id).first()
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

    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect(
        "workspace_slug_dashboard",
        workspace_slug=workspace.slug,
    )


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
    # Get workspace and validate access policy.
    workspace = get_object_or_404(Company, id=workspace_id)

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
    if workspace.slug == "public":
        return redirect("dashboard")

    context = {}
    context["workspace"] = workspace
    context["membership"] = membership
    context["role"] = role_name

    # Check if user can view detailed metrics (Owner/Admin)
    context["can_view"] = role_name in ["Owner", "Admin", "Superuser"]
    access = access_context["access"]
    context.update(get_workspace_dashboard_context(workspace=workspace, access=access))
    context["can_use_counter"] = access.can("data.view")
    context["can_create_loan"] = access.can("data.view") and access.can("data.create")
    if context["can_use_counter"]:
        from django.core.paginator import Paginator
        from apps.tenant_apps.loans.selectors.counter_work import get_workspace_counter_work
        from apps.tenant_apps.loans.selectors.business_overview import get_business_overview
        from apps.tenant_apps.loans.web.dashboard_forms import DashboardActivityForm

        activity_data = request.GET.copy()
        if "period" not in activity_data:
            activity_data["period"] = "month"
        activity_form = DashboardActivityForm(activity_data)
        activity_dates = {}
        if activity_form.is_valid():
            activity_dates = {"activity_start": activity_form.cleaned_data["start"],
                              "activity_end": activity_form.cleaned_data["end"]}
        context["activity_form"] = activity_form
        context["business_overview"] = get_business_overview(workspace=workspace, **activity_dates)
        from urllib.parse import urlencode
        context["dashboard_query"] = urlencode({key: activity_data[key]
            for key in ("period", "start", "end") if key in activity_data})

        work = get_workspace_counter_work(workspace=workspace)
        default_queue = next((key for key in ("overdue", "due", "approved", "draft", "review") if work["queues"][key]["count"]), "draft")
        selected = work["queues"].get(request.GET.get("queue"), work["queues"][default_queue])
        context["counter_work"] = work
        context["work_queues"] = work["queues"].values()
        context["selected_queue"] = selected
        context["work_page"] = Paginator(selected["rows"], 20).get_page(request.GET.get("page"))
    if context.get("setup_checklist") is not None:
        context["setup_state"] = build_workspace_setup_display_state(
            user=request.user,
            workspace=workspace,
            checklist=context["setup_checklist"],
        )

    return render(request, "company/workspace_dashboard.html", context)
