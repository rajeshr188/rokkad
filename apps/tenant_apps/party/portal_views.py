from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.tenant_apps.party.portal_access import resolve_portal_identity
from apps.tenant_apps.party.portal_selectors import (
    get_portal_dashboard_summary,
    get_portal_documents_summary,
    get_portal_invoices_summary,
    get_portal_loans_summary,
    get_portal_payments_summary,
    get_portal_statements_summary,
)


def _portal_context(request, *, section, summary):
    identity = resolve_portal_identity(request)
    return {
        "portal_identity": identity,
        "portal_party_name": identity.party.display_name,
        "portal_workspace_name": getattr(identity.workspace, "name", ""),
        "portal_active_section": section,
        "summary": summary(identity),
    }


@login_required
def portal_dashboard(request):
    return render(
        request,
        "party/portal/dashboard.html",
        _portal_context(
            request,
            section="dashboard",
            summary=get_portal_dashboard_summary,
        ),
    )


@login_required
def portal_loans(request):
    return render(
        request,
        "party/portal/loans.html",
        _portal_context(request, section="loans", summary=get_portal_loans_summary),
    )


@login_required
def portal_invoices(request):
    return render(
        request,
        "party/portal/invoices.html",
        _portal_context(request, section="invoices", summary=get_portal_invoices_summary),
    )


@login_required
def portal_payments(request):
    return render(
        request,
        "party/portal/payments.html",
        _portal_context(request, section="payments", summary=get_portal_payments_summary),
    )


@login_required
def portal_documents(request):
    return render(
        request,
        "party/portal/documents.html",
        _portal_context(request, section="documents", summary=get_portal_documents_summary),
    )


@login_required
def portal_statements(request):
    return render(
        request,
        "party/portal/statements.html",
        _portal_context(request, section="statements", summary=get_portal_statements_summary),
    )
