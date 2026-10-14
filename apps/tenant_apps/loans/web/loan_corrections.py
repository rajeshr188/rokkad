"""Common correction preparation; existing commands own the reviewed changes."""
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from apps.tenant_apps.loans.access import loans_action_required, LOANS_ADMIN_ACTION
from apps.tenant_apps.loans.models import PawnLoan
from apps.tenant_apps.loans.services.borrower_corrections import borrower_correction_blockers
from apps.tenant_apps.loans.services.recorded_collections import recording_for


@loans_action_required(LOANS_ADMIN_ACTION)
@never_cache
def correction_review(request, pk):
    loan = get_object_or_404(PawnLoan, pk=pk, workspace=request.loans_workspace)
    if loan.state == "DRAFT":
        return redirect("workspace_loans:pawn_loan_update", workspace_slug=request.workspace.slug, pk=loan.pk)
    return render(request, "loans/pawn/loan_corrections.html", dict(loan=loan,
        borrower_blockers=borrower_correction_blockers(loan), recorded=recording_for(loan)))
