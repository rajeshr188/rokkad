"""Pawn setup actions; existing services own business rules."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import (
    redirect,
    render,
)

from apps.tenant_apps.loans.access import loans_action_required
from apps.tenant_apps.loans.forms import PawnSetupTransferForm
from apps.tenant_apps.loans.services import (
    PawnLifecycleError,
    transfer_expired_draft_setup,
)
from apps.tenant_apps.loans.web.pawn_read_helpers import (
    _pawn_loan_for_workspace,
)


@loans_action_required("data.edit")
def pawn_loan_transfer_setup(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    form = PawnSetupTransferForm(request.POST or None, workspace=request.loans_workspace)
    if request.method == "POST" and form.is_valid():
        try:
            transfer_expired_draft_setup(
                loan.pk,
                license_id=form.cleaned_data["license"].pk,
                series_id=form.cleaned_data["series"].pk,
                reason=form.cleaned_data["reason"],
                actor=request.user,
            )
        except (PawnLifecycleError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Draft moved to active license setup and requires approval again.")
            return redirect('workspace_loans:pawn_loan_detail', pk=loan.pk, workspace_slug=request.workspace.slug)
    return render(request, "loans/pawn/transition_form.html", {"loan": loan, "form": form, "action_label": "Transfer setup"})
