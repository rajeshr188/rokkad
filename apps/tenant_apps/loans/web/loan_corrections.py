"""Compatibility route to the contextual correction actions on loan detail."""
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.cache import never_cache
from apps.tenant_apps.loans.access import loans_action_required, LOANS_ADMIN_ACTION
from apps.tenant_apps.loans.models import PawnLoan


@loans_action_required(LOANS_ADMIN_ACTION)
@never_cache
def correction_review(request, pk):
    loan = get_object_or_404(PawnLoan, pk=pk, workspace=request.loans_workspace)
    if loan.state == "DRAFT":
        return redirect("workspace_loans:pawn_loan_update", workspace_slug=request.workspace.slug, pk=loan.pk)
    return redirect(reverse("workspace_loans:pawn_loan_detail", args=[request.workspace.slug, loan.pk]) + "#loan-corrections")
