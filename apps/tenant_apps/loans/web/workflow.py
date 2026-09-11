from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.tenant_apps.loans.access import loans_owner_required
from apps.tenant_apps.loans.forms import PawnDisbursalForm
from apps.tenant_apps.loans.models import PawnLoan
from apps.tenant_apps.loans.services.loan_workflow import make_review, review_and_disburse, set_loan_workflow


class WorkflowForm(forms.Form):
    mode = forms.ChoiceField(label="Loan workflow", choices=[
        ("EXTENDED", "Separate approval and disbursal"),
        ("SIMPLE", "Owner review and disburse"),
    ], widget=forms.RadioSelect)


class ReviewForm(PawnDisbursalForm):
    review_token = forms.CharField(widget=forms.HiddenInput)
    confirmed = forms.BooleanField(label="I have reviewed the terms and paid the borrower the amount shown.")


@loans_owner_required
def loan_workflow_settings(request):
    form = WorkflowForm(request.POST or None, initial={"mode": request.loans_workspace.loan_workflow})
    if request.method == "POST" and form.is_valid():
        set_loan_workflow(actor=request.user, mode=form.cleaned_data["mode"])
        messages.success(request, "Loan workflow updated. Existing loans and their history are unchanged.")
        return redirect('workspace_loans:loan_workflow_settings', workspace_slug=request.workspace.slug)
    return render(request, "loans/setup/workflow.html", {"form": form})


@loans_owner_required
def pawn_loan_review_disburse(request, pk):
    loan = get_object_or_404(PawnLoan.objects.select_related("borrower", "license", "series"), pk=pk, workspace=request.loans_workspace)
    form = ReviewForm(request.POST or None, initial={"effective_date": timezone.localdate()})
    if request.method == "POST" and form.is_valid():
        try:
            review_and_disburse(loan.pk, actor=request.user, effective_date=form.cleaned_data["effective_date"], token=form.cleaned_data["review_token"])
        except (ValueError, ValidationError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Loan approved and disbursed. You can now print its documents.")
            return redirect('workspace_loans:pawn_loan_detail', pk=loan.pk, workspace_slug=request.workspace.slug)
    economics = None
    review_error = None
    available = loan.state == "DRAFT" and request.loans_workspace.loan_workflow == "SIMPLE"
    try:
        if available:
            economics, token = make_review(loan)
            if request.method != "POST":
                form.initial["review_token"] = token
        else:
            raise ValueError("Use this action for a draft in the owner review-and-disburse workflow.")
    except (ValueError, ValidationError) as exc:
        available = False
        review_error = str(exc)
    return render(request, "loans/pawn/review_disburse.html", {"loan": loan, "form": form, "economics": economics, "available": available, "review_error": review_error})
