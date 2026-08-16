"""Read selectors for workspace dashboard composition."""

from apps.onboarding.services import build_workspace_setup_checklist
from apps.orgs.models import CompanyInvitation


def get_workspace_dashboard_context(*, workspace):
    """Compose orgs-owned metrics with tenant-app summaries via public facades."""
    context = {
        "team_count": workspace.memberships.count(),
        "pending_invitations": workspace.invitations.filter(
            status=CompanyInvitation.Status.PENDING,
            accepted=False,
        ).count(),
        "setup_checklist": build_workspace_setup_checklist(workspace=workspace),
    }

    from apps.tenant_apps.party.facade import (
        get_workspace_customer_party_dashboard_summary,
    )
    from apps.tenant_apps.loans.selectors import get_workspace_pawn_loan_dashboard_summary
    from apps.tenant_apps.rates.facade import get_workspace_rate_dashboard_summary

    context.update(get_workspace_customer_party_dashboard_summary())
    context.update(get_workspace_pawn_loan_dashboard_summary(workspace=workspace))
    context.update(get_workspace_rate_dashboard_summary())
    return context
