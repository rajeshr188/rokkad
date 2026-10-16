from .counter_navigation import preserve_counter_return
from django import forms
from decimal import Decimal
from apps.onboarding.navigation import setup_saved_redirect

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
from apps.tenant_apps.loans.services.origination_summary import native_origination_summary


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
        return setup_saved_redirect(request, step="lending") or redirect('workspace_loans:loan_workflow_settings', workspace_slug=request.workspace.slug)
    return render(request, "loans/setup/workflow.html", {"form": form})


@loans_owner_required
@never_cache
@preserve_counter_return
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
            economics, token = make_review(loan, actor=request.user, effective_date=form.initial["effective_date"])
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
        "agreement": native_origination_summary(loan, economics),
    })


class EarlierPayoutForm(forms.Form):
    review_token = forms.CharField(widget=forms.HiddenInput)
    reason = forms.CharField(label="Why is this payout being recorded or corrected now?", max_length=500,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        help_text="Include a paper ticket or other reference where available.")
    confirmed = forms.BooleanField(label="I confirm the money was already paid on the actual payout date shown, and these are the correct terms.",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))


class CompletedPayoutForm(forms.Form):
    source_reference = forms.CharField(max_length=160, label="Original ticket or payout reference")
    reason = forms.CharField(max_length=235, label="Why is this completed payout being recorded now?",
        widget=forms.Textarea(attrs={"rows": 2}))
    advance_months = forms.TypedChoiceField(coerce=int, label="Advance interest deducted",
        choices=((0, "None"), (1, "One month")))
    document_charge = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0, label="Document charge deducted")
    cash_paid = forms.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"), required=False,
        label="Net amount already paid", help_text="Leave blank to calculate from the agreed deductions; confirm the actual amount in the review.")
    currency_quantum = forms.ChoiceField(label="Agreed interest rounding", choices=(("0.01", "Paise"), ("1", "Whole rupees")))
    monitoring_method = forms.ChoiceField(label="Saved valuation fallback", choices=(
        ("CALCULATED_METAL_VALUE", "Current metal price"), ("LATEST_APPRAISAL", "Approved appraisal"),
        ("LOWER_OF_CALCULATED_AND_APPRAISAL", "Lower of price and appraisal")))
    monitoring_ltv = forms.DecimalField(max_digits=7, decimal_places=6, min_value=Decimal("0.000001"), max_value=1,
        label="Saved reference LTV ratio")
    monitoring_reason = forms.CharField(max_length=255, label="Source of saved valuation/reference")
    reviewed_evidence = forms.BooleanField(required=False,
        label="I reviewed the retained approval and the evidence status shown, including any corrections or withdrawals.")
    confirmed_rule = forms.BooleanField(initial=True, widget=forms.HiddenInput)

    def __init__(self, *args, approval_evidence=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reviewed_evidence"].required = bool(approval_evidence)
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "form-check-input" if isinstance(field, forms.BooleanField) else "form-select" if isinstance(field, forms.ChoiceField) else "form-control"
            if name in ("currency_quantum", "monitoring_method", "monitoring_ltv", "monitoring_reason") and self.initial.get(name) is not None:
                field.widget = forms.HiddenInput()


@loans_action_required("data.edit")
@loans_action_required("loan.disburse")
@never_cache
@preserve_counter_return
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
    # Keep issued paper-history submissions on their original signed command.
    if request.method == "POST" and "intent_token" in request.POST and not request.POST.get("completed_payout_form"):
        return paper_history_entry(request, draft=loan)
    return _completed_payout_review(request, loan)


def _completed_payout_review(request, loan):
    from apps.tenant_apps.loans.selectors.monitoring_policy import current_monitoring_context
    from apps.tenant_apps.loans.services.completed_payouts import (
        completed_payout_defaults, retained_approval_evidence, preview_completed_payout, record_completed_payout,
    )
    from apps.tenant_apps.loans.services.recorded_history import new_recording_intent
    post = request.POST if request.method == "POST" else None
    evidence = retained_approval_evidence(loan)
    defaults, error = {}, None
    try:
        defaults = completed_payout_defaults(loan)
    except (ValueError, ValidationError) as exc:
        error = str(exc)
    form = CompletedPayoutForm(post, initial=defaults, approval_evidence=evidence)
    intent = (post.get("intent_token", "") if post is not None else "") or new_recording_intent(
        workspace=request.loans_workspace, actor=request.user, draft_id=loan.pk)
    review, token = None, ""
    agreement = native_origination_summary(loan, None)
    if post is not None and post.get("action") != "edit" and form.is_valid():
        arguments = dict(workspace=request.loans_workspace, actor=request.user, loan_id=loan.pk,
            values=form.cleaned_data, intent_token=intent)
        try:
            if post.get("action") == "confirm":
                result, created = record_completed_payout(**arguments, review_token=post.get("review_token"),
                    confirmed=post.get("confirm_review") == "on")
                messages.success(request, "Completed payout recorded with its actual date." if created else
                    "This payout was already recorded; no duplicate was created.")
                return redirect("workspace_loans:pawn_loan_detail", workspace_slug=request.workspace.slug, pk=result.pk)
            review, token, agreement = preview_completed_payout(**arguments)
        except (ValueError, ValidationError) as exc:
            form.add_error(None, str(exc))
    return render(request, "loans/pawn/completed_payout.html", dict(loan=loan, form=form,
        agreement=agreement, approval_evidence=evidence, review=review, review_token=token,
        intent_token=intent, review_error=error, completed_draft=loan, agreement_pending_payout=review is None,
        current_monitoring=current_monitoring_context(loan.series)))


@loans_action_required("workspace.settings.manage")
@loans_action_required("data.create")
@loans_action_required("data.edit")
@loans_action_required("loan.disburse")
@never_cache
@preserve_counter_return
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
@preserve_counter_return
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
        "agreement": native_origination_summary(loan, economics),
        "can_edit_loan": request.loans_workspace_access.can("data.edit")})
