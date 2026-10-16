"""Workspace navigation views; existing policy and services remain authoritative."""

from types import SimpleNamespace
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe
from django.urls import reverse
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
        "has_workspace_history": user.memberships.exists(),
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
@never_cache
@require_safe
def workspace_dashboard(request, workspace_id):
    """Render navigation first; load authorized financial sections independently."""
    section = request.GET.get("section", "")
    if section not in ("", "queues", "overview", "full"):
        return HttpResponseBadRequest("Unknown dashboard section.")
    fragment = section in ("queues", "overview")
    workspace = get_object_or_404(Company, id=workspace_id)
    try:
        access_context = _assert_workspace_access(request, workspace, allow_platform_admin=True)
        if fragment:
            from apps.tenancy.context import current_workspace_id
            if (getattr(request, "workspace", None) is None
                    or request.workspace.pk != workspace.pk
                    or current_workspace_id() != workspace.pk):
                raise PermissionDenied("Dashboard requires its matching Workspace context.")
            access_context["access"].require("data.view")
    except PermissionDenied:
        if fragment:
            return HttpResponseForbidden("Access denied to this dashboard section.")
        messages.error(request, "Access denied to this workspace")
        return redirect("workspace_list")

    # Only ordinary navigation changes the user's saved Workspace preference.
    if not fragment and request.user.profile.workspace != workspace:
        request.user.profile.workspace = workspace
        request.user.profile.save()
    if workspace.slug == "public":
        return redirect("dashboard")

    from urllib.parse import urlencode
    access = access_context["access"]
    if not fragment and access.can("data.view") and request.GET.get("queue") == "overdue":
        query = urlencode({key: request.GET[key]
            for key in ("period", "start", "end", "page") if key in request.GET})
        destination = reverse("workspace_loans:overdue_payments", args=[workspace.slug])
        return redirect(destination + ("?" + query if query else ""))
    role_name = access_context["role_name"]
    activity_data = request.GET.copy()
    if "period" not in activity_data:
        activity_data["period"] = "month"
    dashboard_query = urlencode({key: activity_data[key]
        for key in ("period", "start", "end") if key in activity_data})
    if section == "full":
        dashboard_query = "section=full&" + dashboard_query
    context = {
        "request": request,
        "workspace": workspace,
        "membership": access_context["membership"] or SimpleNamespace(role=SimpleNamespace(name=role_name)),
        "role": role_name,
        "can_view": role_name in ("Owner", "Admin", "Superuser"),
        "can_use_counter": access.can("data.view"),
        "can_create_loan": access.can("data.view") and access.can("data.create"),
        "can_manage_health": access.can("workspace.settings.manage"),
        "user_permissions": access_context["effective_permissions"],
        "dashboard_url": reverse("workspace_slug_dashboard", args=[workspace.slug]),
        "dashboard_query": dashboard_query,
        "dashboard_full": section == "full",
    }
    if context["can_use_counter"] and section in ("overview", "full"):
        from apps.tenant_apps.loans.selectors.business_overview import get_business_overview
        from apps.tenant_apps.loans.web.dashboard_forms import DashboardActivityForm
        activity_form = DashboardActivityForm(activity_data)
        activity_dates = {}
        if activity_form.is_valid():
            activity_dates = {"activity_start": activity_form.cleaned_data["start"],
                              "activity_end": activity_form.cleaned_data["end"]}
        context["activity_form"] = activity_form
        context["business_overview"] = get_business_overview(workspace=workspace, **activity_dates)
    if context["can_use_counter"] and section in ("queues", "full"):
        from django.core.paginator import Paginator
        from apps.tenant_apps.loans.selectors.counter_work import get_workspace_counter_work
        work = get_workspace_counter_work(workspace=workspace)
        default_queue = next((key for key in ("overdue", "due", "approved", "draft", "review")
                              if work["queues"][key]["count"]), "draft")
        selected = work["queues"].get(request.GET.get("queue"), work["queues"][default_queue])
        context.update(counter_work=work, work_queues=work["queues"].values(),
                       selected_queue=selected,
                       work_page=Paginator(selected["rows"], 20).get_page(request.GET.get("page")))
        from apps.tenant_apps.loans.selectors.business_overview import get_daily_counter_activity
        context['daily_activity'] = get_daily_counter_activity(workspace=workspace)
        context['overdue_preview'] = selected['key'] == 'overdue'
        if context['overdue_preview']:
            context['work_page'] = Paginator(selected['rows'][:5], 5).get_page(1)
    if fragment:
        # Partials need the checked request/permissions, not global shell processors.
        template = "company/_dashboard_queues.html" if section == "queues" else "company/_business_overview.html"
        response = HttpResponse(render_to_string(template, context))
        response["X-Rokkad-Fragment"] = "dashboard-" + section
        return response

    context.update(get_workspace_dashboard_context(workspace=workspace, access=access))
    if context.get("setup_checklist") is not None:
        context["setup_state"] = build_workspace_setup_display_state(
            user=request.user, workspace=workspace, checklist=context["setup_checklist"])
    return render(request, "company/workspace_dashboard.html", context)
