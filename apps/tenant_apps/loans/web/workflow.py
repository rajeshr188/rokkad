from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache

from apps.tenant_apps.loans.access import loans_owner_required, loans_setup_required, loans_action_required, loans_workspace_required
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
    confirmed = forms.BooleanField(label=_("I have reviewed the terms and paid the borrower the amount shown."), widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))


@loans_owner_required
def loan_workflow_settings(request):
    form = WorkflowForm(request.POST or None, initial={"mode": request.loans_workspace.loan_workflow})
    if request.method == "POST" and form.is_valid():
        set_loan_workflow(actor=request.user, mode=form.cleaned_data["mode"])
        messages.success(request, "Loan workflow updated. Existing loans and their history are unchanged.")
        return redirect('workspace_loans:loan_workflow_settings', workspace_slug=request.workspace.slug)
    return render(request, "loans/setup/workflow.html", {"form": form})


@loans_owner_required
@never_cache
def pawn_loan_review_disburse(request, pk):
    loan = get_object_or_404(PawnLoan.objects.select_related("borrower", "license", "series"), pk=pk, workspace=request.loans_workspace)
    form = ReviewForm(request.POST if request.method == "POST" else None, initial={"effective_date": timezone.localdate()})
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
    return render(request, "loans/pawn/review_disburse.html", {
        "loan": loan, "form": form, "economics": economics,
        "available": available, "review_error": review_error,
        "can_edit_loan": request.loans_workspace_access.can("data.edit"),
    })


class EarlierPayoutForm(forms.Form):
    review_token = forms.CharField(widget=forms.HiddenInput)
    reason = forms.CharField(label="Why is this payout being recorded or corrected now?", max_length=500,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        help_text="Include a paper ticket or other reference where available.")
    confirmed = forms.BooleanField(label="I confirm the money was already paid on the actual payout date shown, and these are the correct terms.",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))


@loans_action_required("data.edit")
@loans_action_required("loan.disburse")
@never_cache
def pawn_loan_record_completed_payout(request, pk):
    from apps.tenant_apps.loans.services.completed_payouts import require_unpaid_draft, completed_payout_adapter
    from .recorded_history import paper_history_entry
    loan = get_object_or_404(PawnLoan.objects.select_related("borrower", "license", "series"),
        pk=pk, workspace=request.loans_workspace)
    adapter = completed_payout_adapter(loan)
    # Native POST retries/stale reviews must reach the native command, including
    # after it has activated the loan. A recorded intent always keeps its adapter.
    native_post = (request.method == "POST" and "intent_token" not in request.POST
        and "review_token" in request.POST)
    if native_post or (adapter == "RETAINED_NATIVE" and "intent_token" not in request.POST):
        return _retained_payout_review(request, pk)
    request.loans_workspace_access.require("data.create")
    # A same-form POST retry must reach the command's existing-result check.
    if request.method != "POST" or loan.state in ("DRAFT", "APPROVED"):
        try:
            require_unpaid_draft(loan)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("workspace_loans:pawn_loan_detail", workspace_slug=request.workspace.slug, pk=pk)
    return paper_history_entry(request, draft=loan)


@loans_action_required("workspace.settings.manage")
@loans_action_required("data.create")
@loans_action_required("data.edit")
@loans_action_required("loan.disburse")
@never_cache
def pawn_loan_correct_origination(request, pk):
    from apps.tenant_apps.loans.services.origination_corrections import correction_source
    from .recorded_history import paper_history_entry
    loan = get_object_or_404(PawnLoan.objects.select_related("borrower", "license", "series"),
        pk=pk, workspace=request.loans_workspace)
    if request.method != "POST" or loan.state == "DRAFT":
        try:
            correction_source(loan, actor=request.user)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("workspace_loans:pawn_loan_detail", workspace_slug=request.workspace.slug, pk=pk)
    return paper_history_entry(request, draft=loan, origination_correction=True)


@loans_workspace_required
@never_cache
def pawn_loan_record_earlier_payout(request, pk):
    get_object_or_404(PawnLoan, pk=pk, workspace=request.loans_workspace)
    if request.method != "POST":
        return redirect("workspace_loans:pawn_loan_record_completed_payout",
            workspace_slug=request.workspace.slug, pk=pk)
    # An already issued v1 review remains valid at its original POST endpoint.
    return _retained_payout_review(request, pk)


@loans_setup_required
def _retained_payout_review(request, pk):
    from apps.tenant_apps.loans.services.loan_workflow import make_earlier_payout_review, record_earlier_payout
    loan = get_object_or_404(PawnLoan.objects.select_related("borrower", "license", "series"),
        pk=pk, workspace=request.loans_workspace)
    form = EarlierPayoutForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            record_earlier_payout(loan.pk, actor=request.user, token=form.cleaned_data["review_token"],
                reason=form.cleaned_data["reason"], confirmed=form.cleaned_data["confirmed"])
        except (ValueError, ValidationError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Completed payout recorded with its actual date. Your signed-in identity and today's recording time are in the loan history.")
            return redirect("workspace_loans:pawn_loan_detail", workspace_slug=request.workspace.slug, pk=loan.pk)
    economics, quotes, basis, error = None, {}, None, None
    try:
        economics, token, quotes, basis = make_earlier_payout_review(loan, actor=request.user)
        if request.method != "POST":
            form.initial["review_token"] = token
    except (ValueError, ValidationError) as exc:
        error = str(exc)
    return render(request, "loans/pawn/earlier_payout.html", {"loan": loan, "form": form,
        "economics": economics, "quotes": quotes, "basis_approval": basis,
        "review_error": error, "available": error is None,
        "is_earlier_payout_review": True,
        "can_edit_loan": request.loans_workspace_access.can("data.edit")})
