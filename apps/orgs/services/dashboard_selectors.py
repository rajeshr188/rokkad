"""Read selectors for workspace dashboard composition."""

from apps.orgs.models import CompanyInvitation


def get_workspace_dashboard_context(*, workspace):
    """Compose orgs-owned metrics with tenant-app summaries via public facades."""
    context = {
        "team_count": workspace.memberships.count(),
        "pending_invitations": workspace.invitations.filter(
            status=CompanyInvitation.Status.PENDING,
            accepted=False,
        ).count(),
    }

    from apps.tenant_apps.contact.facade import (
        get_workspace_customer_dashboard_summary,
    )
    from apps.tenant_apps.girvi.facade import get_workspace_loan_dashboard_summary
    from apps.tenant_apps.rates.facade import get_workspace_rate_dashboard_summary

    context.update(get_workspace_customer_dashboard_summary())
    context.update(get_workspace_loan_dashboard_summary())
    context.update(get_workspace_rate_dashboard_summary())
    return context
