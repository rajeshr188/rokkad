from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache

from apps.subscriptions.access_policy import workspace_activity
from apps.tenant_apps.loans.access import loans_workspace_required
from apps.tenant_apps.loans.models import PawnLoan
from apps.tenant_apps.loans.services.valuation_review import preview_updated_valuation, confirm_updated_valuation


class ValuationReviewForm(forms.Form):
    review_token = forms.CharField(widget=forms.HiddenInput)
    unpaid = forms.BooleanField(label="No cash has been paid for this loan. I accept today's date and the updated terms shown.",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))


@loans_workspace_required
@never_cache
def review_updated_valuation(request, pk):
    loan = get_object_or_404(PawnLoan.objects.select_related("workspace", "borrower", "license", "series"),
        workspace=request.loans_workspace, pk=pk)
    form = ValuationReviewForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            loan, changed = confirm_updated_valuation(loan.pk, actor=request.user,
                token=form.cleaned_data["review_token"], unpaid=form.cleaned_data["unpaid"])
        except (ValueError, ValidationError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Updated valuation approved. The loan number and previous approval are preserved. Review and print the updated ticket before payment; disbursal is still a separate confirmation."
                if changed else "This valuation review was already saved. No additional approval or payment was recorded.")
            destination = "pawn_loan_disburse" if loan.state == "APPROVED" and request.loans_workspace_access.can("loan.disburse") else "pawn_loan_detail"
            return redirect("workspace_loans:" + destination, workspace_slug=request.workspace.slug, pk=loan.pk)
    preview, error = None, None
    try:
        preview = preview_updated_valuation(loan, actor=request.user)
        if request.method != "POST":
            form.initial["review_token"] = preview["token"]
    except (ValueError, ValidationError) as exc:
        error = str(exc)
    return render(request, "loans/pawn/valuation_review.html", {
        "loan": loan, "form": form, "preview": preview, "review_error": error,
        "can_reapprove": workspace_activity(request.loans_workspace).can_write and all(
            request.loans_workspace_access.can(action) for action in ("data.edit", "loan.approve")),
        "can_edit_loan": request.loans_workspace_access.can("data.edit"),
    })
