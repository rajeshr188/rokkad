"""Account pages and retired preferences compatibility route."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from apps.configuration.views import WorkspacePreferenceBuilder
from apps.orgs.models import Company, CompanyInvitation
from apps.orgs.tenant_context import resolve_preferred_workspace

class CompanyPreferenceBuilder(WorkspacePreferenceBuilder):
    """Legacy URL uses the same authorized settings guidance."""


@login_required
def profile(request):
    user = request.user
    workspace = resolve_preferred_workspace(request.user)

    memberships = (
        user.memberships.select_related("company", "role")
        .filter(company__lifecycle_state=Company.LifecycleState.ACTIVE)
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
