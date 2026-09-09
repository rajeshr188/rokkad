"""Read selectors for workspace dashboard composition."""

from apps.onboarding.services import build_workspace_setup_checklist
from apps.orgs.models import CompanyInvitation


def get_workspace_dashboard_context(*, workspace, access):
    """Compose authorized Workspace administration and setup information."""
    context = {}
    if access.can("team.view"):
        context["team_count"] = workspace.memberships.count()
        context["pending_invitations"] = workspace.invitations.filter(
            status=CompanyInvitation.Status.PENDING, accepted=False,
        ).count()
    if access.can("workspace.settings.manage"):
        context["setup_checklist"] = build_workspace_setup_checklist(workspace=workspace)

    return context
